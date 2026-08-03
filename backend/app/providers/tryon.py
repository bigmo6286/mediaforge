"""Virtual try-on — change the outfit on a person photo (dress changing).

Given a person image + a garment image, a diffusion try-on model (IDM-VTON,
OOTDiffusion, CatVTON) renders the person wearing that garment. These are heavy
diffusion models, so they run on a hosted GPU by default; a local path needs a
strong GPU + the model set up separately.
"""
from __future__ import annotations

import base64
from pathlib import Path

from .. import config
from ..jobs import JobProgress
from . import _hosted
from ._hosted import ProviderError


def _img_uri(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
    return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _finish_image(data: dict, provider: str, model: str, progress: JobProgress) -> dict:
    url = _hosted.extract_url(data, ("image", "images", "output"))
    if not url:
        raise ProviderError(f"{provider} (try-on) returned no image: {data}")
    dest = _hosted.out_path(".png", prefix="tryon")
    _hosted.download(url, dest, progress)
    return {"output": _hosted.rel(dest), "provider": provider, "model": model}


def change_outfit(person: Path, garment: Path, params: dict,
                  progress: JobProgress) -> dict:
    """Render `person` wearing `garment`. `category`: upper_body|lower_body|dresses."""
    provider = config.TRYON_PROVIDER
    category = params.get("category", "upper_body")
    desc = params.get("description", "")

    if provider == "fal":
        payload = {"human_image_url": _img_uri(person),
                   "garment_image_url": _img_uri(garment),
                   "description": desc, "category": category}
        return _finish_image(_hosted.fal_call(config.FAL_TRYON_MODEL, payload, progress),
                             "fal", config.FAL_TRYON_MODEL, progress)
    if provider == "replicate":
        inp = {"human_img": _img_uri(person), "garm_img": _img_uri(garment),
               "garment_des": desc or category}
        return _finish_image(
            _hosted.replicate_call(config.REPLICATE_TRYON_MODEL, inp, progress),
            "replicate", config.REPLICATE_TRYON_MODEL, progress)
    if provider == "local":
        raise ProviderError(
            "Local try-on needs a strong GPU + IDM-VTON set up. On this machine "
            "set TRYON_PROVIDER=fal (or replicate) with an API key instead.")
    raise ProviderError(f"Unknown TRYON_PROVIDER: {provider}")
