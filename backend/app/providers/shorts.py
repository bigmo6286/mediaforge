"""Shorts maker: an uploaded video -> vertical short clips with burned-in
captions.

Pipeline:

    video ─► extract audio ─► Whisper transcription (word timestamps, auto
    language detection) ─► split the transcript into ~N-second windows at
    sentence boundaries ─► for each window: cut, reframe to 9:16, burn styled
    captions ─► one short mp4 per window.

Transcription uses faster-whisper (CTranslate2) with large-v3 by default. That
model covers many African languages — Yoruba, Hausa, Swahili, Amharic, Shona,
Somali, Afrikaans — though accuracy varies and Igbo / Nigerian Pidgin are weak
(little training data). The model and forced language are configurable
(WHISPER_MODEL / SHORTS_LANGUAGE, or the per-request `language` param) so a
fine-tuned model, Meta MMS, or a hosted API can be swapped in without touching
the rest of the pipeline.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .. import config, ffmpeg_tools
from ..jobs import JobProgress
from ._hosted import ProviderError, out_path, rel


def _ffmpeg() -> str:
    return ffmpeg_tools._resolve_ffmpeg()


# --- Whisper model (loaded once, cached across jobs) ------------------------
_MODEL = None
_MODEL_KEY: tuple | None = None


def _get_model():
    """Load (and cache) the faster-whisper model for the configured name."""
    global _MODEL, _MODEL_KEY
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise ProviderError(
            "Shorts needs faster-whisper. Install it:\n"
            "  pip install faster-whisper") from exc
    device = "cuda" if config.HAS_GPU else "cpu"
    compute = "float16" if config.HAS_GPU else "int8"
    key = (config.WHISPER_MODEL, device, compute)
    if _MODEL is None or _MODEL_KEY != key:
        _MODEL = WhisperModel(config.WHISPER_MODEL, device=device, compute_type=compute)
        _MODEL_KEY = key
    return _MODEL


def _extract_audio(video: Path, progress: JobProgress) -> Path:
    out = out_path(".wav", prefix="shorts_audio")
    cmd = [_ffmpeg(), "-y", "-i", str(video), "-vn",
           "-ac", "1", "-ar", "16000", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise ProviderError(f"Could not extract audio:\n{(proc.stderr or '')[-300:]}")
    return out


def _transcribe(audio: Path, language: str, progress: JobProgress):
    """Return (segments, detected_language). Each segment: {start,end,text,words}."""
    model = _get_model()
    segments, info = model.transcribe(
        str(audio),
        language=language or None,     # None = auto-detect
        word_timestamps=True,
        vad_filter=True,               # skip silence -> fewer hallucinations
    )
    segs = []
    for s in segments:
        words = [{"start": w.start, "end": w.end, "word": w.word}
                 for w in (s.words or []) if w.start is not None]
        text = (s.text or "").strip()
        if text:
            segs.append({"start": s.start, "end": s.end, "text": text, "words": words})
    return segs, info.language


# --- MMS (Meta Massively Multilingual Speech) -------------------------------
# Covers 1000+ languages incl. Igbo (ibo), Nigerian Pidgin (pcm), Yoruba (yor),
# Hausa (hau) — the ones vanilla Whisper handles poorly. MMS is a CTC model, so
# it needs an explicit language and gives word timestamps from frame offsets.
_MMS = None            # (model, processor)
_MMS_LANG: str | None = None


def _get_mms(lang: str):
    global _MMS, _MMS_LANG
    try:
        import torch  # noqa: F401
        from transformers import AutoProcessor, Wav2Vec2ForCTC
    except ImportError as exc:  # pragma: no cover
        raise ProviderError(
            "MMS needs transformers + torch. Install:\n"
            "  pip install transformers torch") from exc
    if _MMS is None:
        processor = AutoProcessor.from_pretrained(config.MMS_MODEL)
        model = Wav2Vec2ForCTC.from_pretrained(config.MMS_MODEL)
        if config.HAS_GPU:
            model.to("cuda")
        _MMS = (model, processor)
    model, processor = _MMS
    if _MMS_LANG != lang:
        # Swap in the per-language adapter (downloads a few MB on first use).
        processor.tokenizer.set_target_lang(lang)
        model.load_adapter(lang)
        _MMS_LANG = lang
    return model, processor


def _read_wav16k(path: Path):
    import wave

    import numpy as np
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    if sr != 16000:
        raise ProviderError(f"Expected 16 kHz audio for MMS, got {sr} Hz.")
    data = np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0
    return data, sr


def _words_to_segments(words: list[dict], max_gap: float = 0.6,
                       max_dur: float = 8.0) -> list[dict]:
    """Group a flat word stream (from CTC) into segments at speech pauses."""
    def mk(ws):
        return {"start": ws[0]["start"], "end": ws[-1]["end"],
                "text": "".join(w["word"] for w in ws).strip(), "words": ws}
    segs, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > max_gap
                    or w["end"] - cur[0]["start"] > max_dur):
            segs.append(mk(cur))
            cur = []
        cur.append(w)
    if cur:
        segs.append(mk(cur))
    return [s for s in segs if s["text"]]


def _transcribe_mms(audio: Path, language: str, progress: JobProgress):
    """Transcribe with MMS. `language` is an ISO-639-3 code (e.g. 'ibo', 'pcm')."""
    import torch
    lang = language or "eng"
    model, processor = _get_mms(lang)
    device = "cuda" if config.HAS_GPU else "cpu"
    data, sr = _read_wav16k(audio)
    tpf = model.config.inputs_to_logits_ratio / sr   # seconds per output frame
    chunk = 20 * sr                                   # 20s windows (CTC memory)
    words: list[dict] = []
    total = max(1, len(data))
    for off in range(0, len(data), chunk):
        seg = data[off:off + chunk]
        if len(seg) < int(0.2 * sr):
            continue
        input_values = processor(seg, sampling_rate=sr,
                                 return_tensors="pt").input_values.to(device)
        with torch.no_grad():
            logits = model(input_values).logits
        ids = torch.argmax(logits, dim=-1)
        decoded = processor.batch_decode(ids, output_word_offsets=True)
        base = off / sr
        for wo in decoded["word_offsets"][0]:
            words.append({
                "start": base + wo["start_offset"] * tpf,
                "end": base + wo["end_offset"] * tpf,
                "word": " " + wo["word"],
            })
        progress.update(0.12 + 0.08 * (off / total), "transcribing (MMS)")
    return _words_to_segments(words), lang


# --- Segment the transcript into shorts -------------------------------------
def _segment(segs: list[dict], target: float, max_len: float) -> list[tuple]:
    """Group consecutive transcript segments into ~target-second windows,
    breaking only at segment (sentence) boundaries, never exceeding max_len."""
    windows, cur, start = [], [], None
    for s in segs:
        if start is None:
            start = s["start"]
        cur.append(s)
        dur = s["end"] - start
        if dur >= target or dur >= max_len:
            windows.append((start, s["end"], cur))
            cur, start = [], None
    if cur:
        windows.append((start, cur[-1]["end"], cur))
    return windows


# --- Styled ASS captions ----------------------------------------------------
def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "").replace("}", "").replace("\n", " ").strip()


def _chunk_words(words: list[dict], max_words: int = 5, max_gap: float = 0.8) -> list[list[dict]]:
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["start"] - cur[-1]["end"] > max_gap):
            chunks.append(cur)
            cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    return chunks


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,80,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,5,2,2,80,80,320,1

[Events]
Format: Layer, Start, End, Style, Text
"""


def _write_ass(wsegs: list[dict], offset: float) -> Path:
    """Build a styled ASS caption file for one short (times relative to its start)."""
    lines = [_ASS_HEADER]
    for seg in wsegs:
        if seg["words"]:
            for chunk in _chunk_words(seg["words"]):
                start = _ass_time(chunk[0]["start"] - offset)
                end = _ass_time(chunk[-1]["end"] - offset)
                text = _ass_escape("".join(w["word"] for w in chunk))
                if text:
                    lines.append(f"Dialogue: 0,{start},{end},Cap,,0,0,0,,{text}")
        else:  # no word timestamps -> one caption per segment
            start = _ass_time(seg["start"] - offset)
            end = _ass_time(seg["end"] - offset)
            text = _ass_escape(seg["text"])
            if text:
                lines.append(f"Dialogue: 0,{start},{end},Cap,,0,0,0,,{text}")
    out = out_path(".ass", prefix="shorts_cap")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def _filter_path(p: Path) -> str:
    # Escape the path for use inside an ffmpeg filtergraph value.
    return str(p).replace("\\", "/").replace(":", r"\:")


def _render_short(video: Path, start: float, end: float, ass_path: Path | None,
                  vertical: bool) -> Path:
    out = out_path(".mp4", prefix="short")
    vf = []
    if vertical:
        # Fill a 1080x1920 canvas and centre-crop -> 9:16 vertical.
        vf.append("scale=1080:1920:force_original_aspect_ratio=increase")
        vf.append("crop=1080:1920")
    if ass_path is not None:
        vf.append(f"ass={_filter_path(ass_path)}")
    cmd = [_ffmpeg(), "-y", "-ss", f"{start:.3f}", "-i", str(video),
           "-t", f"{max(0.1, end - start):.3f}"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise ProviderError(f"ffmpeg failed rendering short:\n{(proc.stderr or '')[-400:]}")
    return out


# --- Entry point ------------------------------------------------------------
def make_shorts(video_path: Path, params: dict, progress: JobProgress) -> dict:
    target = float(params.get("clip_seconds", 45) or 45)
    max_len = max(target + 15, float(params.get("max_seconds", 90) or 90))
    vertical = bool(params.get("vertical", True))
    captions = bool(params.get("captions", True))
    language = str(params.get("language", "") or config.SHORTS_LANGUAGE)
    engine = str(params.get("engine", "") or config.SHORTS_ENGINE).lower()
    max_shorts = int(params.get("max_shorts", 0) or 0)

    progress.update(0.05, "extracting audio")
    audio = _extract_audio(video_path, progress)

    if engine == "mms":
        progress.update(0.12, f"transcribing with MMS ({language or 'eng'})")
        segs, detected = _transcribe_mms(audio, language, progress)
    else:
        progress.update(0.12, f"transcribing with Whisper ({config.WHISPER_MODEL})")
        segs, detected = _transcribe(audio, language, progress)
    if not segs:
        raise ProviderError(
            "No speech was detected in the video (or the language wasn't "
            "recognised). Try setting the language explicitly.")

    windows = _segment(segs, target, max_len)
    if max_shorts:
        windows = windows[:max_shorts]

    results = []
    n = len(windows) or 1
    for i, (s, e, wsegs) in enumerate(windows):
        progress.update(0.2 + 0.75 * (i / n), f"rendering short {i + 1}/{len(windows)}")
        ass = _write_ass(wsegs, s) if captions else None
        out = _render_short(video_path, s, e, ass, vertical)
        results.append({
            "output": rel(out),
            "start": round(s, 2),
            "end": round(e, 2),
            "duration": round(e - s, 2),
            "language": detected,
            "text": " ".join(x["text"] for x in wsegs),
        })

    progress.update(1.0, f"done — {len(results)} shorts ({detected})")
    return {"shorts": results, "language": detected, "count": len(results)}
