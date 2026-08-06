"""Wan AI video-generation endpoints (text-to-video, image-to-video)."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException

from .. import config
from ..jobs import manager
from ..providers import avatar, motion
from ..providers import shorts as shorts_maker
from .media import _resolve

router = APIRouter()

# A single diffusion call only yields one short window (~5s). Above this we
# transparently switch to the chaining engine to reach the requested length.
_SINGLE_SHOT_MAX_SECONDS = 6.0


@router.get("/providers")
async def providers() -> dict:
    return config.provider_status()


@router.post("/t2v")
async def text_to_video(
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    model: str = Form(""),                 # "ltx" | "wan" | "" -> default
    target_seconds: float = Form(5),
    num_frames: int = Form(121),
) -> dict:
    if not prompt.strip():
        raise HTTPException(400, "prompt is required")
    params = {"negative_prompt": negative_prompt, "model": model or config.MOTION_MODEL,
              "num_frames": num_frames, "target_seconds": target_seconds,
              "segment_seconds": config.SEGMENT_SECONDS}
    if target_seconds > _SINGLE_SHOT_MAX_SECONDS:
        job = manager.submit("generate.long_t2v",
                             lambda pr: motion.long_video(prompt, params, pr))
    else:
        job = manager.submit("generate.t2v",
                             lambda pr: motion.text_to_video(prompt, params, pr))
    return {"job_id": job.id}


@router.post("/i2v")
async def image_to_video(
    prompt: str = Form(""),
    path: str = Form(...),
    model: str = Form(""),
    target_seconds: float = Form(5),
    num_frames: int = Form(121),
) -> dict:
    src = _resolve(path)
    params = {"model": model or config.MOTION_MODEL, "num_frames": num_frames,
              "target_seconds": target_seconds, "segment_seconds": config.SEGMENT_SECONDS}
    if target_seconds > _SINGLE_SHOT_MAX_SECONDS:
        job = manager.submit(
            "generate.long_i2v",
            lambda pr: motion.long_video(prompt, params, pr, seed_image=src))
    else:
        job = manager.submit(
            "generate.i2v",
            lambda pr: motion.image_to_video(prompt, src, params, pr))
    return {"job_id": job.id}


@router.post("/avatar")
async def talking_avatar(
    image: str = Form(...),          # relative path of uploaded portrait
    audio: str = Form(""),           # relative path of uploaded voice (optional)
    script: str = Form(""),          # OR a script to synthesize via TTS
    voice: str = Form("af_heart"),   # TTS voice id (provider-specific)
) -> dict:
    img = _resolve(image)
    params = {"voice": voice}
    if audio:
        aud = _resolve(audio)
        job = manager.submit(
            "generate.avatar",
            lambda pr: avatar.talking_avatar(img, aud, params, pr),
        )
    elif script.strip():
        job = manager.submit(
            "generate.avatar",
            lambda pr: avatar.avatar_from_script(img, script, params, pr),
        )
    else:
        raise HTTPException(400, "Provide either an audio file or a script.")
    return {"job_id": job.id}


@router.post("/shorts")
async def shorts(
    path: str = Form(...),               # relative path of the uploaded video
    clip_seconds: float = Form(45),      # target length of each short
    max_seconds: float = Form(90),       # hard cap per short
    vertical: bool = Form(True),         # reframe to 9:16
    captions: bool = Form(True),         # burn in captions
    language: str = Form(""),            # ISO code, "" = auto-detect
    engine: str = Form("whisper"),       # "whisper" or "mms"
    max_shorts: int = Form(0),           # 0 = as many as the video yields
    viral: bool = Form(False),           # pick the highest-scoring moments
) -> dict:
    src = _resolve(path)
    params = {"clip_seconds": clip_seconds, "max_seconds": max_seconds,
              "vertical": vertical, "captions": captions,
              "language": language, "engine": engine, "max_shorts": max_shorts,
              "viral": viral}
    job = manager.submit("generate.shorts",
                         lambda pr: shorts_maker.make_shorts(src, params, pr))
    return {"job_id": job.id}


@router.post("/tts")
async def tts(text: str = Form(...), voice: str = Form("af_heart")) -> dict:
    if not text.strip():
        raise HTTPException(400, "text is required")

    def _run(pr):
        path = avatar.synthesize_speech(text, {"voice": voice}, pr)
        from ..providers import _hosted
        return {"output": _hosted.rel(path)}

    job = manager.submit("generate.tts", _run)
    return {"job_id": job.id}
