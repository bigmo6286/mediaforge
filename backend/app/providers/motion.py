"""Model-agnostic dispatch + the long-video chaining engine.

`text_to_video` / `image_to_video` pick the requested base model (Wan or LTX).

`long_video` guarantees a target duration even though every diffusion model
only emits a short window per call: it generates a base segment, then repeatedly
image-to-video's from the previous segment's LAST FRAME and concatenates, giving
a continuous clip of any length. Works with whichever base model is selected and
on the free-tier 1.3B / LTX models.

    seg0 ──lastframe──► seg1 ──lastframe──► seg2 ──► ... ──► concat ──► trim
"""
from __future__ import annotations

from pathlib import Path

from .. import config, ffmpeg_tools
from ..jobs import JobProgress
from . import ltx, wan
from ._hosted import ProviderError

_MODELS = {"wan": wan, "ltx": ltx}


def _pick(model: str):
    mod = _MODELS.get((model or config.MOTION_MODEL).lower())
    if not mod:
        raise ProviderError(f"Unknown motion model: {model} (use 'wan' or 'ltx')")
    return mod


def text_to_video(prompt: str, params: dict, progress: JobProgress) -> dict:
    return _pick(params.get("model")).text_to_video(prompt, params, progress)


def image_to_video(prompt: str, image_path: Path, params: dict,
                   progress: JobProgress) -> dict:
    return _pick(params.get("model")).image_to_video(prompt, image_path, params, progress)


def long_video(prompt: str, params: dict, progress: JobProgress,
               seed_image: Path | None = None) -> dict:
    """Chain short segments up to `target_seconds`. Returns {output, segments}."""
    mod = _pick(params.get("model"))
    target = float(params.get("target_seconds", 15))
    seg_secs = float(params.get("segment_seconds", config.SEGMENT_SECONDS))
    max_segs = max(1, min(12, int(target / seg_secs + 0.999)))

    segments: list[Path] = []

    # --- first segment: from a seed image (i2v) or from text (t2v) ---
    progress.update(0.05, "generating segment 1")
    if seed_image is not None:
        first = mod.image_to_video(prompt, seed_image, params, progress)
    else:
        first = mod.text_to_video(prompt, params, progress)
    segments.append(config.DATA_DIR / first["output"])

    total = ffmpeg_tools.duration_seconds(segments[0]) or seg_secs
    seg_i = 1
    while total < target and seg_i < max_segs:
        seg_i += 1
        progress.update(min(0.85, 0.05 + 0.8 * (seg_i / max_segs)),
                        f"extending — segment {seg_i}/{max_segs}")
        seed = ffmpeg_tools.last_frame(segments[-1], progress)
        nxt = mod.image_to_video(prompt, seed, params, progress)
        clip = config.DATA_DIR / nxt["output"]
        segments.append(clip)
        total += ffmpeg_tools.duration_seconds(clip) or seg_secs

    # --- stitch + trim to the requested length ---
    if len(segments) == 1:
        final = segments[0]
    else:
        progress.update(0.9, "stitching segments")
        final = ffmpeg_tools.concat_paths(segments, progress)
    if total > target + 0.5:
        final = ffmpeg_tools.trim_to(final, target, progress)

    rel = str(final.relative_to(config.DATA_DIR)).replace("\\", "/")
    return {"output": rel, "segments": len(segments),
            "target_seconds": target, "model": (params.get("model") or config.MOTION_MODEL)}
