"""Central configuration for MediaForge.

Reads settings from environment variables (and an optional .env file in the
backend directory). Nothing secret is hard-coded; provider API keys are only
ever read from the environment.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Load .env if present (tiny parser, no extra dependency) ---------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = BACKEND_DIR / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


# --- Paths -----------------------------------------------------------------
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = Path(os.environ.get("MEDIAFORGE_DATA", ROOT_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
for _d in (UPLOAD_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --- GPU detection ---------------------------------------------------------
def detect_device() -> str:
    """Return 'cuda' if a usable GPU + torch are present, else 'cpu'.

    Safe on machines without torch installed (this CPU box) — import failure
    just means 'cpu'. Result is cached on the function.
    """
    cached = getattr(detect_device, "_cached", None)
    if cached is not None:
        return cached
    device = "cpu"
    try:
        import torch  # noqa: PLC0415

        if torch.cuda.is_available():
            device = "cuda"
    except Exception:  # noqa: BLE001 - no torch / driver issues -> cpu
        pass
    detect_device._cached = device  # type: ignore[attr-defined]
    return device


DEVICE = detect_device()
HAS_GPU = DEVICE == "cuda"


def _default_provider() -> str:
    """When a GPU is present, run models locally by default; else use a host.

    Overridable per-feature via the WAN_/MOTION_/AVATAR_PROVIDER env vars.
    """
    return "local" if HAS_GPU else "fal"


# --- Provider selection ----------------------------------------------------
# Which backend runs Wan: "fal", "replicate", or "local" (needs a CUDA GPU).
# Defaults to "local" automatically on a GPU box, "fal" otherwise.
WAN_PROVIDER = os.environ.get("WAN_PROVIDER", _default_provider()).lower()

# API keys (only read from env — never committed).
FAL_KEY = os.environ.get("FAL_KEY", "")
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN", "")

# Default hosted model IDs (override via env to switch Wan versions/sizes).
FAL_T2V_MODEL = os.environ.get("FAL_T2V_MODEL", "fal-ai/wan-t2v")
FAL_I2V_MODEL = os.environ.get("FAL_I2V_MODEL", "fal-ai/wan-i2v")
REPLICATE_T2V_MODEL = os.environ.get(
    "REPLICATE_T2V_MODEL", "wan-video/wan-2.2-t2v-fast"
)
REPLICATE_I2V_MODEL = os.environ.get(
    "REPLICATE_I2V_MODEL", "wan-video/wan-2.2-i2v-fast"
)

# Local diffusers model (only used when WAN_PROVIDER=local on a GPU box).
WAN_LOCAL_MODEL = os.environ.get("WAN_LOCAL_MODEL", "Wan-AI/Wan2.1-T2V-1.3B-Diffusers")

# --- Motion generation (base model for text/image -> video) ----------------
# Which base model the Motion tab uses by default: "ltx" (best for long clips
# on free GPUs) or "wan". MOTION_PROVIDER mirrors WAN_PROVIDER unless overridden.
MOTION_MODEL = os.environ.get("MOTION_MODEL", "ltx").lower()
MOTION_PROVIDER = os.environ.get("MOTION_PROVIDER", WAN_PROVIDER).lower()

# LTX-Video (Lightricks, open-source, Apache-2.0) — efficient, T4-friendly.
FAL_LTX_T2V_MODEL = os.environ.get("FAL_LTX_T2V_MODEL", "fal-ai/ltx-video")
FAL_LTX_I2V_MODEL = os.environ.get("FAL_LTX_I2V_MODEL", "fal-ai/ltx-video/image-to-video")
REPLICATE_LTX_MODEL = os.environ.get("REPLICATE_LTX_MODEL", "lightricks/ltx-video")
LTX_LOCAL_MODEL = os.environ.get("LTX_LOCAL_MODEL", "Lightricks/LTX-Video")

# Long-clip chaining: seconds per generated segment (segments are stitched).
SEGMENT_SECONDS = float(os.environ.get("SEGMENT_SECONDS", "5"))

# --- Talking-avatar (photo + voice -> lip-synced presenter) ----------------
# Open-source options: SadTalker, Hallo, Wan2.2-S2V. Uses the same provider
# (fal/replicate/local) as Wan by default; override with AVATAR_PROVIDER.
AVATAR_PROVIDER = os.environ.get("AVATAR_PROVIDER", WAN_PROVIDER).lower()
FAL_AVATAR_MODEL = os.environ.get("FAL_AVATAR_MODEL", "fal-ai/sadtalker")
REPLICATE_AVATAR_MODEL = os.environ.get(
    "REPLICATE_AVATAR_MODEL", "lucataco/sadtalker")
# Field names differ per avatar model — override without touching code.
FAL_AVATAR_IMAGE_FIELD = os.environ.get("FAL_AVATAR_IMAGE_FIELD", "source_image_url")
FAL_AVATAR_AUDIO_FIELD = os.environ.get("FAL_AVATAR_AUDIO_FIELD", "driven_audio_url")
REPLICATE_AVATAR_IMAGE_FIELD = os.environ.get("REPLICATE_AVATAR_IMAGE_FIELD", "source_image")
REPLICATE_AVATAR_AUDIO_FIELD = os.environ.get("REPLICATE_AVATAR_AUDIO_FIELD", "driven_audio")
# Local avatar (AVATAR_PROVIDER=local): a cloned SadTalker checkout + its python.
# https://github.com/OpenTalker/SadTalker  — set SADTALKER_DIR to the clone.
SADTALKER_DIR = os.environ.get("SADTALKER_DIR", "")
SADTALKER_PYTHON = os.environ.get("SADTALKER_PYTHON", "python")

# --- Face swap (change the face in a photo) --------------------------------
# Local: InsightFace inswapper (CPU-capable). Hosted: fal / replicate.
FACESWAP_PROVIDER = os.environ.get("FACESWAP_PROVIDER", _default_provider()).lower()
FAL_FACESWAP_MODEL = os.environ.get("FAL_FACESWAP_MODEL", "fal-ai/face-swap")
REPLICATE_FACESWAP_MODEL = os.environ.get(
    "REPLICATE_FACESWAP_MODEL", "cdingram/face-swap")
# Video face-swap (hosted): swaps the face across a whole clip.
FAL_FACESWAP_VIDEO_MODEL = os.environ.get(
    "FAL_FACESWAP_VIDEO_MODEL", "fal-ai/face-swap/video")
REPLICATE_FACESWAP_VIDEO_MODEL = os.environ.get(
    "REPLICATE_FACESWAP_VIDEO_MODEL", "arabyai-replicate/roop_face_swap")
# Local inswapper .onnx (set INSWAPPER_MODEL to enable FACESWAP_PROVIDER=local).
INSWAPPER_MODEL = os.environ.get("INSWAPPER_MODEL", "")

# --- Dress / outfit change (virtual try-on) --------------------------------
# Hosted diffusion try-on (IDM-VTON etc.); local needs a big GPU.
TRYON_PROVIDER = os.environ.get("TRYON_PROVIDER", _default_provider()).lower()
FAL_TRYON_MODEL = os.environ.get("FAL_TRYON_MODEL", "fal-ai/idm-vton")
REPLICATE_TRYON_MODEL = os.environ.get("REPLICATE_TRYON_MODEL", "cuuupid/idm-vton")

# --- Text-to-speech (script -> voice) --------------------------------------
# Local: Piper (CPU, free). Voices are .onnx files under PIPER_VOICES_DIR.
# Hosted fallback: Kokoro (open-source) via fal/replicate.
PIPER_VOICES_DIR = Path(os.environ.get("PIPER_VOICES_DIR", BACKEND_DIR / "voices"))
PIPER_MODEL = os.environ.get("PIPER_MODEL", "")  # optional explicit default .onnx


def piper_voices() -> list[str]:
    """Voice ids (file stems) available locally, e.g. 'en_US-amy-medium'."""
    if PIPER_VOICES_DIR.exists():
        return sorted(p.stem for p in PIPER_VOICES_DIR.glob("*.onnx"))
    return []


def piper_voice_path(voice: str = "") -> str:
    """Resolve a voice name (or path) to a .onnx file, with sane fallbacks."""
    if voice:
        cand = PIPER_VOICES_DIR / f"{voice}.onnx"
        if cand.exists():
            return str(cand)
        if Path(voice).exists():
            return voice
    if PIPER_MODEL:
        return PIPER_MODEL
    voices = piper_voices()
    return str(PIPER_VOICES_DIR / f"{voices[0]}.onnx") if voices else ""


# Default to local Piper whenever voices are present; else the hosted provider.
_HAS_PIPER = bool(piper_voices() or PIPER_MODEL)
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "piper" if _HAS_PIPER else WAN_PROVIDER).lower()
FAL_TTS_MODEL = os.environ.get("FAL_TTS_MODEL", "fal-ai/kokoro")
REPLICATE_TTS_MODEL = os.environ.get("REPLICATE_TTS_MODEL", "jaaari/kokoro-82m")

# --- Server ----------------------------------------------------------------
HOST = os.environ.get("MEDIAFORGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("MEDIAFORGE_PORT", "8000"))

# How many blocking jobs (ffmpeg / model calls) may run at once.
MAX_WORKERS = int(os.environ.get("MEDIAFORGE_WORKERS", "2"))


def provider_status() -> dict:
    """Human-readable readiness of each generation provider (for the UI)."""
    return {
        "active": WAN_PROVIDER,
        "device": DEVICE,
        "has_gpu": HAS_GPU,
        "fal": {"configured": bool(FAL_KEY), "t2v": FAL_T2V_MODEL, "i2v": FAL_I2V_MODEL},
        "replicate": {
            "configured": bool(REPLICATE_API_TOKEN),
            "t2v": REPLICATE_T2V_MODEL,
            "i2v": REPLICATE_I2V_MODEL,
        },
        "local": {"model": WAN_LOCAL_MODEL, "note": "requires CUDA GPU"},
        "motion": {
            "model": MOTION_MODEL,
            "provider": MOTION_PROVIDER,
            "segment_seconds": SEGMENT_SECONDS,
            "ltx": {"fal": FAL_LTX_T2V_MODEL, "replicate": REPLICATE_LTX_MODEL,
                    "local": LTX_LOCAL_MODEL},
        },
        "avatar": {
            "provider": AVATAR_PROVIDER,
            "fal": FAL_AVATAR_MODEL,
            "replicate": REPLICATE_AVATAR_MODEL,
        },
        "tts": {
            "provider": TTS_PROVIDER,
            "piper_configured": _HAS_PIPER,
            "voices": piper_voices() if TTS_PROVIDER == "piper" else [],
            "fal": FAL_TTS_MODEL,
            "replicate": REPLICATE_TTS_MODEL,
        },
        "faceswap": {"provider": FACESWAP_PROVIDER,
                     "local_ready": bool(INSWAPPER_MODEL),
                     "fal": FAL_FACESWAP_MODEL, "replicate": REPLICATE_FACESWAP_MODEL},
        "tryon": {"provider": TRYON_PROVIDER,
                  "fal": FAL_TRYON_MODEL, "replicate": REPLICATE_TRYON_MODEL},
    }
