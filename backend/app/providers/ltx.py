"""LTX-Video provider — the efficient long-clip motion model.

LTX-Video (Lightricks, open-source, Apache-2.0) is fast and memory-light enough
to run on a free T4 GPU, which makes it the best base model for longer clips on
free hardware. Same shape as ``wan.py``: hosted (fal/replicate) or local
diffusers on a CUDA box.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from .. import config
from ..jobs import JobProgress
from . import _hosted
from ._hosted import ProviderError


def _img_data_uri(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
    return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _finish(data: dict, provider: str, model: str, progress: JobProgress) -> dict:
    url = _hosted.extract_url(data, ("video", "videos"))
    if not url:
        raise ProviderError(f"{provider} (LTX) returned no video: {data}")
    dest = _hosted.out_path(".mp4", prefix="ltx")
    _hosted.download(url, dest, progress)
    return {"output": _hosted.rel(dest), "provider": provider, "model": model}


def _local(prompt: str, image_path: Optional[Path], params: dict,
           progress: JobProgress) -> dict:
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        raise ProviderError("Local LTX needs PyTorch (CUDA) + diffusers.") from exc
    if not torch.cuda.is_available():
        raise ProviderError(
            "MOTION_PROVIDER=local requires a CUDA GPU (none here). Use fal/replicate.")
    from diffusers.utils import export_to_video

    progress.update(0.1, "loading LTX-Video (first run downloads weights)")
    num_frames = int(params.get("num_frames", 121))
    if image_path is not None:
        from diffusers import LTXImageToVideoPipeline
        from diffusers.utils import load_image
        pipe = LTXImageToVideoPipeline.from_pretrained(
            config.LTX_LOCAL_MODEL, torch_dtype=torch.bfloat16).to("cuda")
        progress.update(0.4, "generating frames")
        frames = pipe(image=load_image(str(image_path)), prompt=prompt,
                      width=int(params.get("width", 704)),
                      height=int(params.get("height", 480)),
                      num_frames=num_frames).frames[0]
    else:
        from diffusers import LTXPipeline
        pipe = LTXPipeline.from_pretrained(
            config.LTX_LOCAL_MODEL, torch_dtype=torch.bfloat16).to("cuda")
        progress.update(0.4, "generating frames")
        frames = pipe(prompt=prompt, width=int(params.get("width", 704)),
                      height=int(params.get("height", 480)),
                      num_frames=num_frames).frames[0]
    dest = _hosted.out_path(".mp4", prefix="ltx")
    export_to_video(frames, str(dest), fps=int(params.get("fps", 24)))
    return {"output": _hosted.rel(dest), "provider": "local",
            "model": config.LTX_LOCAL_MODEL}


def text_to_video(prompt: str, params: dict, progress: JobProgress) -> dict:
    provider = config.MOTION_PROVIDER
    if provider == "fal":
        payload = {"prompt": prompt, "num_frames": int(params.get("num_frames", 121))}
        return _finish(_hosted.fal_call(config.FAL_LTX_T2V_MODEL, payload, progress),
                       "fal", config.FAL_LTX_T2V_MODEL, progress)
    if provider == "replicate":
        inp = {"prompt": prompt, "num_frames": int(params.get("num_frames", 121))}
        return _finish(_hosted.replicate_call(config.REPLICATE_LTX_MODEL, inp, progress),
                       "replicate", config.REPLICATE_LTX_MODEL, progress)
    if provider == "local":
        return _local(prompt, None, params, progress)
    raise ProviderError(f"Unknown MOTION_PROVIDER: {provider}")


def image_to_video(prompt: str, image_path: Path, params: dict,
                   progress: JobProgress) -> dict:
    provider = config.MOTION_PROVIDER
    if provider == "fal":
        payload = {"prompt": prompt, "image_url": _img_data_uri(image_path),
                   "num_frames": int(params.get("num_frames", 121))}
        return _finish(_hosted.fal_call(config.FAL_LTX_I2V_MODEL, payload, progress),
                       "fal", config.FAL_LTX_I2V_MODEL, progress)
    if provider == "replicate":
        inp = {"prompt": prompt, "image": _img_data_uri(image_path),
               "num_frames": int(params.get("num_frames", 121))}
        return _finish(_hosted.replicate_call(config.REPLICATE_LTX_MODEL, inp, progress),
                       "replicate", config.REPLICATE_LTX_MODEL, progress)
    if provider == "local":
        return _local(prompt, image_path, params, progress)
    raise ProviderError(f"Unknown MOTION_PROVIDER: {provider}")
