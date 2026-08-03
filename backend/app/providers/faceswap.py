"""Face swap — replace the face in a target photo with a source face.

A standard creative tool (same class as the open-source FaceFusion / Roop).
Use it only on faces you have permission to edit.

Backends:
  * hosted (fal / replicate) — default off-GPU
  * local  — InsightFace `inswapper` (CPU-capable) when INSWAPPER_MODEL is set
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
        raise ProviderError(f"{provider} (face-swap) returned no image: {data}")
    dest = _hosted.out_path(".png", prefix="faceswap")
    _hosted.download(url, dest, progress)
    return {"output": _hosted.rel(dest), "provider": provider, "model": model}


def _local(source_face: Path, target: Path, progress: JobProgress) -> dict:
    """InsightFace inswapper: detect faces in target, paste the source identity."""
    if not config.INSWAPPER_MODEL or not Path(config.INSWAPPER_MODEL).exists():
        raise ProviderError(
            "Local face swap needs the InsightFace inswapper model.\n"
            "  pip install insightface onnxruntime\n"
            "  then set INSWAPPER_MODEL=/path/to/inswapper_128.onnx")
    try:
        import cv2
        import insightface
        from insightface.app import FaceAnalysis
    except Exception as exc:  # noqa: BLE001
        raise ProviderError("pip install insightface onnxruntime opencv-python") from exc

    progress.update(0.2, "detecting faces")
    app = FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0 if config.HAS_GPU else -1, det_size=(640, 640))
    swapper = insightface.model_zoo.get_model(config.INSWAPPER_MODEL)

    src_img = cv2.imread(str(source_face))
    tgt_img = cv2.imread(str(target))
    src_faces = app.get(src_img)
    tgt_faces = app.get(tgt_img)
    if not src_faces:
        raise ProviderError("No face found in the source image.")
    if not tgt_faces:
        raise ProviderError("No face found in the target image.")

    progress.update(0.6, "swapping")
    src_face = src_faces[0]
    result = tgt_img.copy()
    for face in tgt_faces:  # swap every face in the target
        result = swapper.get(result, face, src_face, paste_back=True)
    dest = _hosted.out_path(".png", prefix="faceswap")
    cv2.imwrite(str(dest), result)
    return {"output": _hosted.rel(dest), "provider": "local", "model": "inswapper"}


def swap(source_face: Path, target: Path, progress: JobProgress) -> dict:
    """Put the face from `source_face` onto the person in `target`."""
    provider = config.FACESWAP_PROVIDER
    if provider == "fal":
        payload = {"base_image_url": _img_uri(target),
                   "swap_image_url": _img_uri(source_face)}
        return _finish_image(_hosted.fal_call(config.FAL_FACESWAP_MODEL, payload, progress),
                             "fal", config.FAL_FACESWAP_MODEL, progress)
    if provider == "replicate":
        inp = {"input_image": _img_uri(target), "swap_image": _img_uri(source_face)}
        return _finish_image(
            _hosted.replicate_call(config.REPLICATE_FACESWAP_MODEL, inp, progress),
            "replicate", config.REPLICATE_FACESWAP_MODEL, progress)
    if provider == "local":
        return _local(source_face, target, progress)
    raise ProviderError(f"Unknown FACESWAP_PROVIDER: {provider}")
