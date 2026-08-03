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


def detect_gpu() -> tuple[str, float]:
    """Return (gpu_name, total_vram_gb) for device 0, or ('', 0.0)."""
    if detect_device() != "cuda":
        return "", 0.0
    try:
        import torch  # noqa: PLC0415

        p = torch.cuda.get_device_properties(0)
        return p.name, p.total_memory / (1024 ** 3)
    except Exception:  # noqa: BLE001
        return "", 0.0


DEVICE = detect_device()
HAS_GPU = DEVICE == "cuda"
GPU_NAME, VRAM_GB = detect_gpu()

# Heavy generators (Wan/LTX motion, talking-avatar, try-on) need real VRAM.
# Below this, a local GPU would OOM, so those default to a hosted provider even
# though the GPU is used for light tasks (face swap / restore). Tune via env.
HEAVY_MIN_VRAM_GB = float(os.environ.get("HEAVY_MIN_VRAM_GB", "6"))
GPU_OK_FOR_HEAVY = HAS_GPU and VRAM_GB >= HEAVY_MIN_VRAM_GB


def _default_provider(heavy: bool = True) -> str:
    """Default provider for a feature.

    heavy=True  (motion / avatar / try-on): local only if the GPU has enough
                VRAM; otherwise hosted, so a small GPU doesn't OOM.
    heavy=False (face swap / restore): local whenever any GPU is present.
    Always overridable per-feature via the *_PROVIDER env vars.
    """
    if heavy:
        return "local" if GPU_OK_FOR_HEAVY else "fal"
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
# fal endpoints are versioned; the bare "fal-ai/ltx-video" is a namespace (403).
FAL_LTX_T2V_MODEL = os.environ.get("FAL_LTX_T2V_MODEL", "fal-ai/ltx-video-v095")
FAL_LTX_I2V_MODEL = os.environ.get(
    "FAL_LTX_I2V_MODEL", "fal-ai/ltx-video-v095/image-to-video")
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
# Local: InsightFace inswapper (CPU-capable, light). Hosted: fal / replicate.
FACESWAP_PROVIDER = os.environ.get("FACESWAP_PROVIDER", _default_provider(heavy=False)).lower()
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

# --- Face restoration (sharpen / enhance faces, e.g. after a swap) ----------
# Local: GFPGAN (CPU-capable, light). Hosted: fal / replicate GFPGAN.
RESTORE_PROVIDER = os.environ.get("RESTORE_PROVIDER", _default_provider(heavy=False)).lower()
# Local GFPGAN weights — a URL auto-downloads on first use; override with a path.
GFPGAN_MODEL = os.environ.get(
    "GFPGAN_MODEL",
    "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth")
FAL_RESTORE_MODEL = os.environ.get("FAL_RESTORE_MODEL", "fal-ai/gfpgan")
REPLICATE_RESTORE_MODEL = os.environ.get("REPLICATE_RESTORE_MODEL", "tencentarc/gfpgan")

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
        "gpu_name": GPU_NAME,
        "vram_gb": round(VRAM_GB, 1),
        "gpu_ok_for_heavy": GPU_OK_FOR_HEAVY,
        "heavy_min_vram_gb": HEAVY_MIN_VRAM_GB,
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
        "restore": {"provider": RESTORE_PROVIDER,
                    "fal": FAL_RESTORE_MODEL, "replicate": REPLICATE_RESTORE_MODEL},
    }


# --- Settings page (edit .env from the UI) ---------------------------------
# Secret keys the settings UI can set, with guidance shown to the user.
SECRET_FIELDS = [
    {
        "key": "FAL_KEY",
        "label": "fal.ai API key",
        "hint": ("Runs Wan/LTX, talking-avatar, face-swap and try-on on fal's "
                 "GPUs. Pay-per-render, no subscription; new accounts get some "
                 "free credit. Create a key, then paste it here."),
        "link": "https://fal.ai/dashboard/keys",
    },
    {
        "key": "REPLICATE_API_TOKEN",
        "label": "Replicate API token",
        "hint": ("Alternative hosted-GPU provider for the same models. "
                 "Pay-per-render. Create a token in your account settings."),
        "link": "https://replicate.com/account/api-tokens",
    },
]

# Every env var the settings endpoint is allowed to write.
_EDITABLE = {"FAL_KEY", "REPLICATE_API_TOKEN", "WAN_PROVIDER", "MOTION_PROVIDER",
             "AVATAR_PROVIDER", "FACESWAP_PROVIDER", "TRYON_PROVIDER",
             "RESTORE_PROVIDER", "TTS_PROVIDER", "MOTION_MODEL"}
# Setting any of these to a value cascades to every generation provider.
_PROVIDER_VARS = ("WAN_PROVIDER", "MOTION_PROVIDER", "AVATAR_PROVIDER",
                  "FACESWAP_PROVIDER", "TRYON_PROVIDER", "RESTORE_PROVIDER")


def _mask(v: str) -> str:
    if not v:
        return ""
    return f"{v[:3]}…{v[-3:]}" if len(v) > 8 else "••••"


def current_settings() -> dict:
    """What the settings UI renders: masked key state + current provider."""
    return {
        "device": DEVICE,
        "has_gpu": HAS_GPU,
        "gpu_name": GPU_NAME,
        "vram_gb": round(VRAM_GB, 1),
        "gpu_ok_for_heavy": GPU_OK_FOR_HEAVY,
        "provider": WAN_PROVIDER,
        "output_dir": str(OUTPUT_DIR),
        "fields": SECRET_FIELDS,
        "keys": {
            "FAL_KEY": {"set": bool(FAL_KEY), "masked": _mask(FAL_KEY)},
            "REPLICATE_API_TOKEN": {"set": bool(REPLICATE_API_TOKEN),
                                    "masked": _mask(REPLICATE_API_TOKEN)},
        },
    }


def apply_settings(updates: dict) -> dict:
    """Persist edits to .env and apply them live (no restart needed).

    Only whitelisted keys are written. Values are set on os.environ and on this
    module's globals so running providers pick them up immediately.
    """
    import sys

    mod = sys.modules[__name__]

    # Read the existing .env into a dict (preserving unrelated keys).
    env: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, _, v = s.partition("=")
                env[k.strip()] = v.strip()

    applied = []
    for key, raw in updates.items():
        if key not in _EDITABLE:
            continue
        val = str(raw).strip()
        norm = val.lower() if (key.endswith("_PROVIDER") or key == "MOTION_MODEL") else val
        if val:
            env[key] = val
        else:
            env.pop(key, None)
        os.environ[key] = val
        setattr(mod, key, norm)
        applied.append(key)

    # Write .env back (0600 so the key file isn't world-readable).
    body = "\n".join(f"{k}={v}" for k, v in env.items() if v != "") + "\n"
    _ENV_FILE.write_text(body)
    try:
        _ENV_FILE.chmod(0o600)
    except OSError:
        pass
    return {"applied": applied}
