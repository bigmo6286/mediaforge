"""Settings endpoints — view masked key status and write API keys to .env."""
from __future__ import annotations

from fastapi import APIRouter, Form

from .. import config

router = APIRouter()


@router.get("/settings")
async def get_settings() -> dict:
    return config.current_settings()


@router.post("/settings")
async def update_settings(
    FAL_KEY: str = Form(None),
    REPLICATE_API_TOKEN: str = Form(None),
    provider: str = Form(None),  # "fal" | "replicate" — cascades to all features
) -> dict:
    updates: dict[str, str] = {}
    # Only touch a key when the user actually typed a new value (non-empty).
    if FAL_KEY:
        updates["FAL_KEY"] = FAL_KEY
    if REPLICATE_API_TOKEN:
        updates["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN
    if provider in ("fal", "replicate", "local"):
        for var in config._PROVIDER_VARS:
            updates[var] = provider

    config.apply_settings(updates)
    return {"ok": True, "settings": config.current_settings(),
            "providers": config.provider_status()}
