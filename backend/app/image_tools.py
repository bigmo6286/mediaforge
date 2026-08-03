"""Local image editing.

Background removal uses ``rembg`` (U^2-Net, ONNX, CPU-friendly) if installed.
It is a heavy optional dependency, so it is imported lazily and a clear error
is returned when it is missing rather than crashing the whole app at boot.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from . import config
from .jobs import JobProgress


def _out_path(suffix: str) -> Path:
    name = f"img_{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    return config.OUTPUT_DIR / name


def _rel(path: Path) -> str:
    return str(path.relative_to(config.DATA_DIR)).replace("\\", "/")


def remove_background(input_path: Path, progress: JobProgress) -> dict:
    progress.update(0.1, "loading rembg (first run downloads the model)")
    try:
        from rembg import remove  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Background removal needs rembg. Run: pip install rembg onnxruntime"
        ) from exc
    from PIL import Image

    progress.update(0.4, "removing background")
    img = Image.open(input_path).convert("RGBA")
    out_img = remove(img)
    out = _out_path(".png")  # PNG to preserve transparency
    out_img.save(out)
    return {"output": _rel(out)}


def convert_format(input_path: Path, fmt: str, progress: JobProgress) -> dict:
    from PIL import Image

    progress.update(0.3, "converting")
    img = Image.open(input_path)
    fmt = fmt.lower().lstrip(".")
    if fmt in ("jpg", "jpeg") and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    out = _out_path("." + fmt)
    img.save(out)
    return {"output": _rel(out)}


def resize_image(input_path: Path, width: int, progress: JobProgress) -> dict:
    from PIL import Image

    progress.update(0.3, "resizing")
    img = Image.open(input_path)
    w = int(width)
    h = int(img.height * (w / img.width))
    img = img.resize((w, h))
    out = _out_path(input_path.suffix or ".png")
    img.save(out)
    return {"output": _rel(out)}
