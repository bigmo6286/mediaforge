"""Wan video-generation provider (text-to-video, image-to-video motion).

Wan (Wan2.1 / Wan2.2, by Alibaba's Wan-AI team) is an open-source video model.
It needs a GPU, so generation runs on a hosted GPU (fal / replicate) or locally
on a CUDA box. This module covers *motion* generation; talking-avatar (audio
driven) generation lives in ``avatar.py``.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from .. import config
from ..jobs import JobProgress
from . import _hosted
from ._hosted import ProviderError  # re-export for callers


def _to_data_uri(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/{mime};base64,{b64}"


def _finish_video(data: dict, provider: str, model: str,
                  progress: JobProgress) -> dict:
    url = _hosted.extract_url(data, ("video", "videos"))
    if not url:
        raise ProviderError(f"{provider} returned no video: {data}")
    dest = _hosted.out_path(".mp4", prefix="wan")
    _hosted.download(url, dest, progress)
    return {"output": _hosted.rel(dest), "provider": provider, "model": model}


# --- local diffusers (GPU only) -------------------------------------------
def _local_run(prompt: str, image_path: Optional[Path], params: dict,
               progress: JobProgress) -> dict:
    try:
        import torch
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(
            "Local Wan needs PyTorch. Install torch (CUDA build) + diffusers."
        ) from exc
    if not torch.cuda.is_available():
        raise ProviderError(
            "WAN_PROVIDER=local requires a CUDA GPU, none detected. "
            "Use WAN_PROVIDER=fal or =replicate on this machine."
        )
    from diffusers import WanPipeline
    from diffusers.utils import export_to_video

    progress.update(0.1, "loading Wan pipeline (first run downloads weights)")
    pipe = WanPipeline.from_pretrained(config.WAN_LOCAL_MODEL,
                                       torch_dtype=torch.bfloat16).to("cuda")
    progress.update(0.4, "generating frames")
    frames = pipe(
        prompt=prompt,
        num_frames=int(params.get("num_frames", 81)),
        height=int(params.get("height", 480)),
        width=int(params.get("width", 832)),
        guidance_scale=float(params.get("guidance_scale", 5.0)),
    ).frames[0]
    dest = _hosted.out_path(".mp4", prefix="wan")
    export_to_video(frames, str(dest), fps=int(params.get("fps", 16)))
    return {"output": _hosted.rel(dest), "provider": "local",
            "model": config.WAN_LOCAL_MODEL}


# --- public API ------------------------------------------------------------
def text_to_video(prompt: str, params: dict, progress: JobProgress) -> dict:
    provider = config.WAN_PROVIDER
    negative = params.get("negative_prompt", "")
    if provider == "fal":
        payload = {"prompt": prompt, "negative_prompt": negative,
                   "resolution": params.get("resolution", "480p"),
                   "num_frames": int(params.get("num_frames", 81))}
        return _finish_video(_hosted.fal_call(config.FAL_T2V_MODEL, payload, progress),
                             "fal", config.FAL_T2V_MODEL, progress)
    if provider == "replicate":
        inp = {"prompt": prompt, "num_frames": int(params.get("num_frames", 81))}
        if negative:
            inp["negative_prompt"] = negative
        return _finish_video(
            _hosted.replicate_call(config.REPLICATE_T2V_MODEL, inp, progress),
            "replicate", config.REPLICATE_T2V_MODEL, progress)
    if provider == "local":
        return _local_run(prompt, None, params, progress)
    raise ProviderError(f"Unknown WAN_PROVIDER: {provider}")


def image_to_video(prompt: str, image_path: Path, params: dict,
                   progress: JobProgress) -> dict:
    provider = config.WAN_PROVIDER
    if provider == "fal":
        payload = {"prompt": prompt, "image_url": _to_data_uri(image_path),
                   "resolution": params.get("resolution", "480p"),
                   "num_frames": int(params.get("num_frames", 81))}
        return _finish_video(_hosted.fal_call(config.FAL_I2V_MODEL, payload, progress),
                             "fal", config.FAL_I2V_MODEL, progress)
    if provider == "replicate":
        inp = {"prompt": prompt, "image": _to_data_uri(image_path),
               "num_frames": int(params.get("num_frames", 81))}
        return _finish_video(
            _hosted.replicate_call(config.REPLICATE_I2V_MODEL, inp, progress),
            "replicate", config.REPLICATE_I2V_MODEL, progress)
    if provider == "local":
        return _local_run(prompt, image_path, params, progress)
    raise ProviderError(f"Unknown WAN_PROVIDER: {provider}")
