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


def _load_local():
    """Load the InsightFace detector + inswapper once; returns (cv2, app, swapper)."""
    if not config.INSWAPPER_MODEL or not Path(config.INSWAPPER_MODEL).exists():
        raise ProviderError(
            "Local face swap needs the InsightFace inswapper model.\n"
            "  pip install insightface onnxruntime opencv-python\n"
            "  then set INSWAPPER_MODEL=/path/to/inswapper_128.onnx")
    try:
        import cv2
        import insightface
        from insightface.app import FaceAnalysis
    except Exception as exc:  # noqa: BLE001
        raise ProviderError("pip install insightface onnxruntime opencv-python") from exc
    app = FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0 if config.HAS_GPU else -1, det_size=(640, 640))
    swapper = insightface.model_zoo.get_model(config.INSWAPPER_MODEL)
    return cv2, app, swapper


def _local(source_face: Path, target: Path, progress: JobProgress) -> dict:
    """InsightFace inswapper: detect faces in target, paste the source identity."""
    cv2, app, swapper = _load_local()
    progress.update(0.3, "detecting faces")
    src_faces = app.get(cv2.imread(str(source_face)))
    if not src_faces:
        raise ProviderError("No face found in the source image.")
    tgt_img = cv2.imread(str(target))
    tgt_faces = app.get(tgt_img)
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


def _local_video(source_face: Path, target_video: Path, progress: JobProgress) -> dict:
    """Swap the source face into every frame of the video, then re-encode."""
    import shutil

    from .. import ffmpeg_tools

    cv2, app, swapper = _load_local()
    src_faces = app.get(cv2.imread(str(source_face)))
    if not src_faces:
        raise ProviderError("No face found in the source image.")
    src_face = src_faces[0]

    frames_dir, fps = ffmpeg_tools.explode_frames(target_video, progress)
    frames = sorted(frames_dir.glob("*.png"))
    if not frames:
        raise ProviderError("Could not extract frames from the video.")

    total = len(frames)
    for i, fp in enumerate(frames):
        img = cv2.imread(str(fp))
        for face in app.get(img):  # swap any faces present in this frame
            img = swapper.get(img, face, src_face, paste_back=True)
        cv2.imwrite(str(fp), img)
        if i % 5 == 0:
            progress.update(0.1 + 0.8 * (i / total), f"swapping frame {i+1}/{total}")

    out = ffmpeg_tools.assemble_video(frames_dir, fps, target_video, progress)
    shutil.rmtree(frames_dir, ignore_errors=True)
    return {"output": _hosted.rel(out), "provider": "local", "model": "inswapper",
            "frames": total}


def swap_video(source_face: Path, target_video: Path, progress: JobProgress) -> dict:
    """Swap `source_face` into every frame of `target_video`."""
    provider = config.FACESWAP_PROVIDER
    if provider == "fal":
        payload = {"video_url": _img_uri(target_video),  # data-uri also works for video
                   "swap_image_url": _img_uri(source_face)}
        data = _hosted.fal_call(config.FAL_FACESWAP_VIDEO_MODEL, payload, progress)
        url = _hosted.extract_url(data, ("video", "videos", "output"))
        if not url:
            raise ProviderError(f"fal (video face-swap) returned no video: {data}")
        dest = _hosted.out_path(".mp4", prefix="faceswap")
        _hosted.download(url, dest, progress)
        return {"output": _hosted.rel(dest), "provider": "fal",
                "model": config.FAL_FACESWAP_VIDEO_MODEL}
    if provider == "replicate":
        inp = {"target_video": _img_uri(target_video), "swap_image": _img_uri(source_face)}
        pred = _hosted.replicate_call(config.REPLICATE_FACESWAP_VIDEO_MODEL, inp, progress)
        url = _hosted.extract_url(pred, ("video", "output"))
        if not url:
            raise ProviderError(f"replicate (video face-swap) returned no video: {pred}")
        dest = _hosted.out_path(".mp4", prefix="faceswap")
        _hosted.download(url, dest, progress)
        return {"output": _hosted.rel(dest), "provider": "replicate",
                "model": config.REPLICATE_FACESWAP_VIDEO_MODEL}
    if provider == "local":
        return _local_video(source_face, target_video, progress)
    raise ProviderError(f"Unknown FACESWAP_PROVIDER: {provider}")


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
