"""Local, deterministic video/image editing via ffmpeg.

ffmpeg is located in this order:
  1. $FFMPEG_BIN if set
  2. a system ``ffmpeg`` on PATH
  3. the binary bundled with the ``imageio-ffmpeg`` pip package (no sudo needed)

All ops run on CPU and are fine on modest hardware.
"""
from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

from . import config
from .jobs import JobProgress

_FFMPEG: Optional[str] = None
_FFPROBE: Optional[str] = None


def _resolve_ffmpeg() -> str:
    global _FFMPEG
    if _FFMPEG:
        return _FFMPEG
    import os

    cand = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg")
    if not cand:
        try:  # bundled binary — installed via `pip install imageio-ffmpeg`
            import imageio_ffmpeg

            cand = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "ffmpeg not found. Install it, or `pip install imageio-ffmpeg`."
            ) from exc
    _FFMPEG = cand
    return cand


def _resolve_ffprobe() -> Optional[str]:
    global _FFPROBE
    if _FFPROBE:
        return _FFPROBE
    _FFPROBE = shutil.which("ffprobe")
    return _FFPROBE


def _out_path(suffix: str) -> Path:
    name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    return config.OUTPUT_DIR / name


def _rel(path: Path) -> str:
    """Path relative to the data dir, used in URLs the frontend can fetch."""
    return str(path.relative_to(config.DATA_DIR)).replace("\\", "/")


def _run(cmd: list[str], progress: JobProgress) -> None:
    progress.update(message="running ffmpeg")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-6:]
        raise RuntimeError("ffmpeg failed:\n" + "\n".join(tail))


def probe(input_path: Path) -> dict:
    """Return basic media info (duration, size, streams) if ffprobe exists."""
    fp = _resolve_ffprobe()
    if not fp:
        return {"note": "ffprobe not available"}
    import json

    cmd = [fp, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", str(input_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"note": "probe failed"}
    return json.loads(proc.stdout or "{}")


# --- Operations ------------------------------------------------------------
# Each takes an input file path + params and returns a result dict.

def trim(input_path: Path, start: float, end: float, progress: JobProgress) -> dict:
    out = _out_path(input_path.suffix or ".mp4")
    dur = max(0.0, float(end) - float(start))
    cmd = [_resolve_ffmpeg(), "-y", "-ss", str(start), "-i", str(input_path),
           "-t", str(dur), "-c:v", "libx264", "-c:a", "aac", "-preset",
           "veryfast", str(out)]
    _run(cmd, progress)
    return {"output": _rel(out)}


def crop(input_path: Path, w: int, h: int, x: int, y: int, progress: JobProgress) -> dict:
    out = _out_path(input_path.suffix or ".mp4")
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
           "-vf", f"crop={w}:{h}:{x}:{y}", "-c:a", "copy",
           "-preset", "veryfast", str(out)]
    _run(cmd, progress)
    return {"output": _rel(out)}


def resize(input_path: Path, width: int, progress: JobProgress) -> dict:
    """Scale to a target width, keeping aspect ratio (height auto, even)."""
    out = _out_path(input_path.suffix or ".mp4")
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
           "-vf", f"scale={int(width)}:-2", "-c:a", "copy",
           "-preset", "veryfast", str(out)]
    _run(cmd, progress)
    return {"output": _rel(out)}


def speed(input_path: Path, factor: float, progress: JobProgress) -> dict:
    """Change playback speed. factor>1 = faster, <1 = slower."""
    out = _out_path(input_path.suffix or ".mp4")
    f = float(factor)
    v_pts = 1.0 / f
    # audio atempo only supports 0.5..2.0 per filter; chain for extremes
    atempo, remaining = [], f
    while remaining > 2.0:
        atempo.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        atempo.append("atempo=0.5")
        remaining *= 2.0
    atempo.append(f"atempo={remaining:.4f}")
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
           "-filter_complex",
           f"[0:v]setpts={v_pts:.4f}*PTS[v];[0:a]{','.join(atempo)}[a]",
           "-map", "[v]", "-map", "[a]", "-preset", "veryfast", str(out)]
    # Fall back to video-only if the source has no audio.
    try:
        _run(cmd, progress)
    except RuntimeError:
        cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
               "-vf", f"setpts={v_pts:.4f}*PTS", "-an",
               "-preset", "veryfast", str(out)]
        _run(cmd, progress)
    return {"output": _rel(out)}


def to_gif(input_path: Path, fps: int, width: int, progress: JobProgress) -> dict:
    out = _out_path(".gif")
    vf = (f"fps={int(fps)},scale={int(width)}:-1:flags=lanczos,"
          "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse")
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path), "-vf", vf, str(out)]
    _run(cmd, progress)
    return {"output": _rel(out)}


def convert(input_path: Path, fmt: str, progress: JobProgress) -> dict:
    out = _out_path("." + fmt.lstrip("."))
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
           "-preset", "veryfast", str(out)]
    _run(cmd, progress)
    return {"output": _rel(out)}


def extract_frames(input_path: Path, fps: float, progress: JobProgress) -> dict:
    stamp = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    folder = config.OUTPUT_DIR / f"frames_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
           "-vf", f"fps={fps}", str(folder / "frame_%04d.png")]
    _run(cmd, progress)
    frames = sorted(p.name for p in folder.glob("*.png"))
    return {"output_dir": _rel(folder), "count": len(frames),
            "frames": [_rel(folder / f) for f in frames[:200]]}


def concat(input_paths: list[Path], progress: JobProgress) -> dict:
    """Concatenate clips by re-encoding to a common format (safe for mixed inputs)."""
    out = _out_path(".mp4")
    inputs: list[str] = []
    for p in input_paths:
        inputs += ["-i", str(p)]
    n = len(input_paths)
    streams = "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
    fil = f"{streams}concat=n={n}:v=1:a=1[v][a]"
    cmd = [_resolve_ffmpeg(), "-y", *inputs, "-filter_complex", fil,
           "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset",
           "veryfast", str(out)]
    try:
        _run(cmd, progress)
    except RuntimeError:
        # Some inputs may lack audio — retry video-only.
        streams_v = "".join(f"[{i}:v:0]" for i in range(n))
        cmd = [_resolve_ffmpeg(), "-y", *inputs, "-filter_complex",
               f"{streams_v}concat=n={n}:v=1:a=0[v]", "-map", "[v]",
               "-c:v", "libx264", "-preset", "veryfast", str(out)]
        _run(cmd, progress)
    return {"output": _rel(out)}


def extract_audio(input_path: Path, progress: JobProgress) -> dict:
    out = _out_path(".mp3")
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path), "-vn",
           "-q:a", "2", str(out)]
    _run(cmd, progress)
    return {"output": _rel(out)}


# --- helpers used by the long-video chaining engine ------------------------
def last_frame(input_path: Path, progress: JobProgress) -> Path:
    """Grab the final frame of a clip as a PNG (used to seed the next segment)."""
    out = _out_path(".png")
    # -sseof -0.2 seeks 0.2s before the end, then grab one frame.
    cmd = [_resolve_ffmpeg(), "-y", "-sseof", "-0.2", "-i", str(input_path),
           "-vframes", "1", "-q:v", "2", str(out)]
    try:
        _run(cmd, progress)
    except RuntimeError:  # very short clip — fall back to first frame
        cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
               "-vframes", "1", str(out)]
        _run(cmd, progress)
    return out


def duration_seconds(input_path: Path) -> float:
    """Clip duration in seconds. Uses ffprobe if present, else parses ffmpeg's
    stderr (imageio-ffmpeg ships ffmpeg but not ffprobe). 0.0 if unknown."""
    info = probe(input_path)
    try:
        d = float(info.get("format", {}).get("duration", 0.0))
        if d > 0:
            return d
    except (TypeError, ValueError):
        pass
    # Fallback: `ffmpeg -i file` prints "Duration: HH:MM:SS.ms" to stderr.
    import re
    proc = subprocess.run([_resolve_ffmpeg(), "-i", str(input_path)],
                          capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", proc.stderr or "")
    if m:
        h, mnt, sec = m.groups()
        return int(h) * 3600 + int(mnt) * 60 + float(sec)
    return 0.0


def concat_paths(input_paths: list[Path], progress: JobProgress) -> Path:
    """Concatenate clips and return the output Path (not a rel-dict)."""
    res = concat(input_paths, progress)
    return config.DATA_DIR / res["output"]


def trim_to(input_path: Path, seconds: float, progress: JobProgress) -> Path:
    """Trim a clip to at most `seconds` from the start; return the Path."""
    out = _out_path(input_path.suffix or ".mp4")
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path), "-t", str(seconds),
           "-c", "copy", str(out)]
    try:
        _run(cmd, progress)
    except RuntimeError:  # stream-copy can fail on odd keyframes — re-encode
        cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path), "-t", str(seconds),
               "-c:v", "libx264", "-preset", "veryfast", str(out)]
        _run(cmd, progress)
    return out


def output_path_for(suffix: str) -> Path:
    """Public accessor for a fresh output path (used by other modules)."""
    return _out_path(suffix)


def video_fps(input_path: Path) -> float:
    """Frame rate of a clip, parsed from ffmpeg's stderr. Falls back to 24."""
    import re
    proc = subprocess.run([_resolve_ffmpeg(), "-i", str(input_path)],
                          capture_output=True, text=True)
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", proc.stderr or "")
    return float(m.group(1)) if m else 24.0


def explode_frames(input_path: Path, progress: JobProgress) -> tuple[Path, float]:
    """Extract every frame to PNGs in a fresh dir. Returns (dir, fps)."""
    stamp = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    folder = config.OUTPUT_DIR / f"swap_frames_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    progress.update(message="extracting frames")
    cmd = [_resolve_ffmpeg(), "-y", "-i", str(input_path),
           str(folder / "f_%06d.png")]
    _run(cmd, progress)
    return folder, video_fps(input_path)


def assemble_video(frames_dir: Path, fps: float, audio_from: Path,
                   progress: JobProgress) -> Path:
    """Rebuild a clip from PNG frames, muxing audio from the original if any."""
    out = _out_path(".mp4")
    progress.update(message="encoding video")
    cmd = [_resolve_ffmpeg(), "-y", "-framerate", str(fps),
           "-i", str(frames_dir / "f_%06d.png"),
           "-i", str(audio_from), "-map", "0:v:0", "-map", "1:a:0?",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
           "-shortest", str(out)]
    try:
        _run(cmd, progress)
    except RuntimeError:  # original had no audio track
        cmd = [_resolve_ffmpeg(), "-y", "-framerate", str(fps),
               "-i", str(frames_dir / "f_%06d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               str(out)]
        _run(cmd, progress)
    return out
