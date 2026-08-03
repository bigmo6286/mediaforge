"""Talking-avatar generation: one photo + a voice -> a lip-synced presenter clip.

This is the core UGC / tutorial / virtual-presenter feature. Pipeline:

    portrait photo ─┐
                    ├─►  avatar model (SadTalker / Hallo / Wan2.2-S2V)  ─► mp4
    voice audio ────┘

The voice can be uploaded, or synthesized from a typed script via TTS
(local Piper on CPU, or hosted Kokoro). Avatar generation itself needs a GPU,
so it runs on the configured hosted provider (or locally on a CUDA box).

NOTE: hosted models differ in their exact input field names. Defaults target
SadTalker; override the *_FIELD env vars in config to point at another model
without changing code.
"""
from __future__ import annotations

import base64
import subprocess
from pathlib import Path

from .. import config
from ..jobs import JobProgress
from . import _hosted
from ._hosted import ProviderError


def _piper_bin() -> str:
    """Locate the piper executable cross-platform (Linux/macOS/Windows).

    Prefers the one in the running venv's Scripts/bin dir (next to the Python
    that launched the server), then falls back to PATH.
    """
    import sys

    exe = "piper.exe" if sys.platform == "win32" else "piper"
    cand = Path(sys.executable).parent / exe
    return str(cand) if cand.exists() else "piper"


def _audio_data_uri(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".") or "wav"
    mime = {"mp3": "mpeg", "wav": "wav", "m4a": "mp4", "ogg": "ogg"}.get(ext, "mpeg")
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:audio/{mime};base64,{b64}"


def _image_data_uri(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"


# --- Text-to-speech --------------------------------------------------------
def synthesize_speech(text: str, params: dict, progress: JobProgress) -> Path:
    """Return a local audio file for `text`, using the configured TTS backend."""
    provider = config.TTS_PROVIDER
    progress.update(0.1, f"synthesizing speech ({provider})")

    if provider == "piper":
        model = config.piper_voice_path(params.get("voice", ""))
        if not model:
            raise ProviderError(
                "No Piper voice found. Download one, e.g.:\n"
                "  python -m piper.download_voices en_US-amy-medium --data-dir backend/voices")
        out = _hosted.out_path(".wav", prefix="tts")
        # piper reads text on stdin and writes a WAV to -f/--output_file.
        try:
            proc = subprocess.run(
                [_piper_bin(), "-m", model, "-f", str(out)],
                input=text, text=True, capture_output=True,
            )
        except FileNotFoundError as exc:
            raise ProviderError(
                "piper binary not found. `pip install piper-tts` or set TTS_PROVIDER=fal."
            ) from exc
        if proc.returncode != 0:
            raise ProviderError(f"piper failed: {(proc.stderr or '')[-300:]}")
        return out

    if provider == "fal":
        data = _hosted.fal_call(config.FAL_TTS_MODEL,
                                {"prompt": text, "text": text,
                                 "voice": params.get("voice", "af_heart")}, progress)
        url = _hosted.extract_url(data, ("audio", "audio_url", "audio_file"))
        if not url:
            raise ProviderError(f"TTS (fal) returned no audio: {data}")
        out = _hosted.out_path(".wav", prefix="tts")
        _hosted.download(url, out, progress)
        return out

    if provider == "replicate":
        pred = _hosted.replicate_call(config.REPLICATE_TTS_MODEL,
                                      {"text": text,
                                       "voice": params.get("voice", "af_bella")},
                                      progress)
        url = _hosted.extract_url(pred, ("audio",))
        if not url:
            raise ProviderError(f"TTS (replicate) returned no audio: {pred}")
        out = _hosted.out_path(".wav", prefix="tts")
        _hosted.download(url, out, progress)
        return out

    raise ProviderError(f"Unknown TTS_PROVIDER: {provider}")


# --- Talking avatar --------------------------------------------------------
def talking_avatar(image_path: Path, audio_path: Path, params: dict,
                   progress: JobProgress) -> dict:
    """Animate `image_path` to speak `audio_path`; returns {output: mp4}."""
    provider = config.AVATAR_PROVIDER
    progress.update(0.15, "animating portrait")

    if provider == "fal":
        payload = {
            config.FAL_AVATAR_IMAGE_FIELD: _image_data_uri(image_path),
            config.FAL_AVATAR_AUDIO_FIELD: _audio_data_uri(audio_path),
        }
        data = _hosted.fal_call(config.FAL_AVATAR_MODEL, payload, progress)
        url = _hosted.extract_url(data, ("video", "videos"))
        if not url:
            raise ProviderError(f"avatar (fal) returned no video: {data}")
        dest = _hosted.out_path(".mp4", prefix="avatar")
        _hosted.download(url, dest, progress)
        return {"output": _hosted.rel(dest), "provider": "fal",
                "model": config.FAL_AVATAR_MODEL}

    if provider == "replicate":
        inp = {
            config.REPLICATE_AVATAR_IMAGE_FIELD: _image_data_uri(image_path),
            config.REPLICATE_AVATAR_AUDIO_FIELD: _audio_data_uri(audio_path),
        }
        pred = _hosted.replicate_call(config.REPLICATE_AVATAR_MODEL, inp, progress)
        url = _hosted.extract_url(pred, ("video",))
        if not url:
            raise ProviderError(f"avatar (replicate) returned no video: {pred}")
        dest = _hosted.out_path(".mp4", prefix="avatar")
        _hosted.download(url, dest, progress)
        return {"output": _hosted.rel(dest), "provider": "replicate",
                "model": config.REPLICATE_AVATAR_MODEL}

    if provider == "local":
        return _local_sadtalker(image_path, audio_path, params, progress)

    raise ProviderError(f"Unknown AVATAR_PROVIDER: {provider}")


def _local_sadtalker(image_path: Path, audio_path: Path, params: dict,
                     progress: JobProgress) -> dict:
    """Run a local SadTalker checkout on the GPU to animate the portrait.

    Requires a cloned https://github.com/OpenTalker/SadTalker with its
    checkpoints, pointed to by SADTALKER_DIR. SadTalker writes an mp4 into a
    results folder; we pick the newest one and move it into our outputs.
    """
    import os
    import shutil
    import subprocess

    if not config.HAS_GPU:
        raise ProviderError(
            "AVATAR_PROVIDER=local needs a CUDA GPU (none detected). "
            "Use AVATAR_PROVIDER=fal/replicate here.")
    st_dir = Path(config.SADTALKER_DIR) if config.SADTALKER_DIR else None
    if not st_dir or not (st_dir / "inference.py").exists():
        raise ProviderError(
            "Local avatar needs SadTalker. Clone it and set SADTALKER_DIR:\n"
            "  git clone https://github.com/OpenTalker/SadTalker\n"
            "  (download its checkpoints per that repo's README)\n"
            "  export SADTALKER_DIR=/path/to/SadTalker")

    results_dir = _hosted.out_path("", prefix="sadtalker_run")
    results_dir.mkdir(parents=True, exist_ok=True)
    progress.update(0.3, "running SadTalker on GPU")
    cmd = [
        config.SADTALKER_PYTHON, "inference.py",
        "--source_image", str(image_path),
        "--driven_audio", str(audio_path),
        "--result_dir", str(results_dir),
        "--still", "--preprocess", "full",
    ]
    proc = subprocess.run(cmd, cwd=str(st_dir), capture_output=True, text=True)
    if proc.returncode != 0:
        raise ProviderError(f"SadTalker failed:\n{(proc.stderr or '')[-400:]}")

    mp4s = sorted(results_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not mp4s:
        raise ProviderError("SadTalker produced no mp4 output.")
    dest = _hosted.out_path(".mp4", prefix="avatar")
    shutil.move(str(mp4s[-1]), str(dest))
    shutil.rmtree(results_dir, ignore_errors=True)
    return {"output": _hosted.rel(dest), "provider": "local", "model": "SadTalker"}


def avatar_from_script(image_path: Path, script: str, params: dict,
                       progress: JobProgress) -> dict:
    """Script -> TTS voice -> talking avatar, in one job."""
    audio = synthesize_speech(script, params, progress)
    result = talking_avatar(image_path, audio, params, progress)
    result["voiceover"] = _hosted.rel(audio)
    return result
