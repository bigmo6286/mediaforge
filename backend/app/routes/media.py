"""Upload + local editing endpoints (video via ffmpeg, images via PIL/rembg)."""
from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import config, ffmpeg_tools, image_tools
from ..jobs import manager

router = APIRouter()

_ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".gif",
            ".png", ".jpg", ".jpeg", ".webp",
            ".mp3", ".wav", ".m4a", ".ogg"}


def _save_upload(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(400, f"Unsupported file type: {suffix or 'unknown'}")
    name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    dest = config.UPLOAD_DIR / name
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


def _resolve(rel_or_name: str) -> Path:
    """Resolve a client-supplied path to a file on this machine.

    Relative paths are taken under DATA_DIR (and may not escape it). Absolute
    paths are allowed as-is so the user can point at a big file they dropped on
    the Colab VM directly — e.g. a multi-GB video on their mounted Google Drive
    that's far too large to push through the browser upload. This is a
    single-user app running on the user's own machine, so reading their own
    files by absolute path is fine.
    """
    raw = Path(rel_or_name)
    if raw.is_absolute():
        p = raw.resolve()
    else:
        p = (config.DATA_DIR / rel_or_name).resolve()
        if config.DATA_DIR.resolve() not in p.parents and p != config.DATA_DIR:
            raise HTTPException(400, "Invalid path")
    if not p.exists():
        raise HTTPException(404, f"File not found: {rel_or_name}")
    return p


def _probe_info(dest: Path) -> dict:
    return ffmpeg_tools.probe(dest) if dest.suffix.lower() not in (
        ".png", ".jpg", ".jpeg", ".webp") else {}


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    dest = _save_upload(file)
    rel = str(dest.relative_to(config.DATA_DIR)).replace("\\", "/")
    return {"path": rel, "name": dest.name, "info": _probe_info(dest)}


# --- chunked upload --------------------------------------------------------
# A long video posted as one big multipart body gets dropped by Colab's kernel
# proxy ("Failed to fetch"). The browser instead slices the file into small
# chunks, uploads them sequentially here, then calls /upload/finish to assemble.
_CHUNK_DIR = config.UPLOAD_DIR / ".chunks"


def _safe_upload_id(upload_id: str) -> str:
    uid = "".join(c for c in upload_id.lower() if c in "0123456789abcdef")
    if not 8 <= len(uid) <= 64:
        raise HTTPException(400, "Bad upload id")
    return uid


@router.post("/upload/chunk")
async def upload_chunk(upload_id: str = Form(...), index: int = Form(...),
                       chunk: UploadFile = File(...)) -> dict:
    uid = _safe_upload_id(upload_id)
    _CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    part = _CHUNK_DIR / f"{uid}.part"
    # Chunks arrive in order (the browser uploads them sequentially); index 0
    # truncates to start fresh, later indices append.
    with part.open("wb" if index == 0 else "ab") as f:
        shutil.copyfileobj(chunk.file, f)
    return {"ok": True, "index": index}


@router.post("/upload/finish")
async def upload_finish(upload_id: str = Form(...),
                        filename: str = Form(...)) -> dict:
    uid = _safe_upload_id(upload_id)
    part = _CHUNK_DIR / f"{uid}.part"
    if not part.exists():
        raise HTTPException(404, "No uploaded chunks found")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in _ALLOWED:
        part.unlink(missing_ok=True)
        raise HTTPException(400, f"Unsupported file type: {suffix or 'unknown'}")
    name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    dest = config.UPLOAD_DIR / name
    part.replace(dest)  # atomic rename within the same filesystem
    rel = str(dest.relative_to(config.DATA_DIR)).replace("\\", "/")
    return {"path": rel, "name": dest.name, "info": _probe_info(dest)}


@router.post("/import")
async def import_file(path: str = Form(...)) -> dict:
    """Use a file that's already on the server instead of uploading it.

    Lets the user point MediaForge at a huge file they placed on the Colab VM
    (e.g. a multi-GB video on their mounted Google Drive) that can't go through
    the browser upload. Returns the same {path,name,info} shape as /upload.
    """
    src = _resolve(path.strip())
    if not src.is_file():
        raise HTTPException(400, "Path is not a file")
    if src.suffix.lower() not in _ALLOWED:
        raise HTTPException(400, f"Unsupported file type: {src.suffix or 'unknown'}")
    # Hand back a path the other routes can resolve: relative if it's under
    # DATA_DIR, otherwise the absolute path (which _resolve also accepts).
    try:
        out = str(src.relative_to(config.DATA_DIR.resolve())).replace("\\", "/")
    except ValueError:
        out = str(src)
    return {"path": out, "name": src.name, "info": _probe_info(src)}


# --- video ops -------------------------------------------------------------
@router.post("/video/{op}")
async def video_op(op: str, path: str = Form(...),
                   a: str = Form("0"), b: str = Form("0"),
                   c: str = Form("0"), d: str = Form("0"),
                   fmt: str = Form("mp4")) -> dict:
    src = _resolve(path)
    ops = {
        "trim": lambda pr: ffmpeg_tools.trim(src, float(a), float(b), pr),
        "crop": lambda pr: ffmpeg_tools.crop(src, int(float(a)), int(float(b)),
                                             int(float(c)), int(float(d)), pr),
        "resize": lambda pr: ffmpeg_tools.resize(src, int(float(a)), pr),
        "speed": lambda pr: ffmpeg_tools.speed(src, float(a), pr),
        "gif": lambda pr: ffmpeg_tools.to_gif(src, int(float(a) or 12),
                                              int(float(b) or 480), pr),
        "convert": lambda pr: ffmpeg_tools.convert(src, fmt, pr),
        "frames": lambda pr: ffmpeg_tools.extract_frames(src, float(a) or 1, pr),
        "audio": lambda pr: ffmpeg_tools.extract_audio(src, pr),
    }
    if op not in ops:
        raise HTTPException(404, f"Unknown video op: {op}")
    job = manager.submit(f"video.{op}", ops[op])
    return {"job_id": job.id}


@router.post("/video/concat")
async def video_concat(paths: str = Form(...)) -> dict:
    """paths = comma-separated relative paths."""
    srcs = [_resolve(p.strip()) for p in paths.split(",") if p.strip()]
    if len(srcs) < 2:
        raise HTTPException(400, "Need at least two clips to concatenate")
    job = manager.submit("video.concat", lambda pr: ffmpeg_tools.concat(srcs, pr))
    return {"job_id": job.id}


# --- image ops -------------------------------------------------------------
@router.post("/image/{op}")
async def image_op(op: str, path: str = Form(...),
                   a: str = Form("0"), fmt: str = Form("png")) -> dict:
    src = _resolve(path)
    ops = {
        "rembg": lambda pr: image_tools.remove_background(src, pr),
        "resize": lambda pr: image_tools.resize_image(src, int(float(a)), pr),
        "convert": lambda pr: image_tools.convert_format(src, fmt, pr),
    }
    if op not in ops:
        raise HTTPException(404, f"Unknown image op: {op}")
    job = manager.submit(f"image.{op}", ops[op])
    return {"job_id": job.id}
