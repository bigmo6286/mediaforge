"""Face restoration — sharpen/enhance faces (great after a face swap).

Uses GFPGAN (open-source, Apache-2.0). Runs locally on CPU/GPU, or on a hosted
GPU. Exposes helpers so the face-swap video loop can restore frames in-place
without a second decode pass.
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..jobs import JobProgress
from . import _hosted
from ._hosted import ProviderError

_RESTORER = None  # lazily-loaded GFPGANer, cached across calls


def _load_gfpgan():
    """Load and cache a GFPGANer restorer (heavy import, done on first use)."""
    global _RESTORER
    if _RESTORER is not None:
        return _RESTORER
    try:
        from gfpgan import GFPGANer
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(
            "Local face restore needs GFPGAN:\n"
            "  pip install gfpgan basicsr facexlib realesrgan\n"
            "(or set RESTORE_PROVIDER=fal/replicate with an API key)") from exc
    _RESTORER = GFPGANer(
        model_path=config.GFPGAN_MODEL,   # a URL auto-downloads on first run
        upscale=1, arch="clean", channel_multiplier=2,
        device="cuda" if config.HAS_GPU else "cpu",
    )
    return _RESTORER


def restore_array(img_bgr):
    """Restore faces in a single BGR image array; returns the enhanced array."""
    restorer = _load_gfpgan()
    _, _, restored = restorer.enhance(
        img_bgr, has_aligned=False, only_center_face=False, paste_back=True)
    return restored


def _img_uri(path: Path) -> str:
    import base64
    ext = path.suffix.lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
    return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode()


# --- public: image ---------------------------------------------------------
def restore_image(path: Path, progress: JobProgress) -> dict:
    provider = config.RESTORE_PROVIDER
    if provider == "local":
        import cv2
        progress.update(0.3, "restoring faces (GFPGAN)")
        out = _hosted.out_path(".png", prefix="restore")
        cv2.imwrite(str(out), restore_array(cv2.imread(str(path))))
        return {"output": _hosted.rel(out), "provider": "local", "model": "GFPGAN"}
    if provider == "fal":
        data = _hosted.fal_call(config.FAL_RESTORE_MODEL, {"image_url": _img_uri(path)}, progress)
        url = _hosted.extract_url(data, ("image", "images", "output"))
        if not url:
            raise ProviderError(f"fal (restore) returned no image: {data}")
        out = _hosted.out_path(".png", prefix="restore")
        _hosted.download(url, out, progress)
        return {"output": _hosted.rel(out), "provider": "fal", "model": config.FAL_RESTORE_MODEL}
    if provider == "replicate":
        pred = _hosted.replicate_call(config.REPLICATE_RESTORE_MODEL, {"img": _img_uri(path)}, progress)
        url = _hosted.extract_url(pred, ("image", "output"))
        if not url:
            raise ProviderError(f"replicate (restore) returned no image: {pred}")
        out = _hosted.out_path(".png", prefix="restore")
        _hosted.download(url, out, progress)
        return {"output": _hosted.rel(out), "provider": "replicate", "model": config.REPLICATE_RESTORE_MODEL}
    raise ProviderError(f"Unknown RESTORE_PROVIDER: {provider}")


# --- public: video ---------------------------------------------------------
def restore_video(path: Path, progress: JobProgress) -> dict:
    """Restore faces across every frame (local only; hosted rarely does video)."""
    if config.RESTORE_PROVIDER != "local":
        raise ProviderError(
            "Video face restore runs locally (RESTORE_PROVIDER=local, needs GFPGAN). "
            "For hosted, restore key frames as images instead.")
    import shutil

    import cv2

    from .. import ffmpeg_tools

    _load_gfpgan()  # fail fast if GFPGAN missing
    frames_dir, fps = ffmpeg_tools.explode_frames(path, progress)
    frames = sorted(frames_dir.glob("*.png"))
    total = len(frames)
    for i, fp in enumerate(frames):
        cv2.imwrite(str(fp), restore_array(cv2.imread(str(fp))))
        if i % 5 == 0:
            progress.update(0.1 + 0.8 * (i / max(1, total)), f"restoring frame {i+1}/{total}")
    out = ffmpeg_tools.assemble_video(frames_dir, fps, path, progress)
    shutil.rmtree(frames_dir, ignore_errors=True)
    return {"output": _hosted.rel(out), "provider": "local", "model": "GFPGAN", "frames": total}
