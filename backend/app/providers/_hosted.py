"""Low-level helpers for hosted GPU providers (fal.ai, replicate.com).

These return the provider's RAW result payload so callers can pull out whatever
media they expect (video for Wan/avatar, audio for TTS). Keeping this generic
means one polling implementation serves every model.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from .. import config
from ..jobs import JobProgress


class ProviderError(RuntimeError):
    pass


def out_path(suffix: str, prefix: str = "gen") -> Path:
    name = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    return config.OUTPUT_DIR / name


def rel(path: Path) -> str:
    return str(path.relative_to(config.DATA_DIR)).replace("\\", "/")


def download(url: str, dest: Path, progress: JobProgress) -> None:
    import httpx

    progress.update(message="downloading result")
    with httpx.stream("GET", url, timeout=300, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


def fal_call(model: str, payload: dict, progress: JobProgress) -> dict:
    """Submit to fal's queue, poll to completion, return the raw result JSON."""
    import httpx

    if not config.FAL_KEY:
        raise ProviderError("FAL_KEY is not set. Add it to backend/.env.")
    headers = {"Authorization": f"Key {config.FAL_KEY}",
               "Content-Type": "application/json"}
    base = f"https://queue.fal.run/{model}"
    progress.update(0.05, "submitting to fal")
    with httpx.Client(timeout=60) as client:
        resp = client.post(base, headers=headers, json=payload)
        if resp.status_code >= 400:
            # Surface fal's own message (e.g. "Exhausted balance", bad field).
            try:
                detail = resp.json().get("detail")
            except Exception:  # noqa: BLE001
                detail = resp.text[:200]
            raise ProviderError(f"fal {resp.status_code}: {detail}")
        req = resp.json()
        status_url = req.get("status_url") or f"{base}/requests/{req['request_id']}/status"
        result_url = req.get("response_url") or f"{base}/requests/{req['request_id']}"
        for i in range(900):  # up to ~15 min
            time.sleep(1)
            st = client.get(status_url, headers=headers)
            st.raise_for_status()
            state = st.json().get("status")
            if state == "COMPLETED":
                progress.update(0.9, "rendering complete")
                break
            if state in ("FAILED", "ERROR"):
                raise ProviderError(f"fal job failed: {st.json()}")
            progress.update(min(0.85, 0.1 + 0.75 * (i / 250)), f"fal: {state}")
        out = client.get(result_url, headers=headers)
        out.raise_for_status()
        return out.json()


def replicate_call(model: str, inp: dict, progress: JobProgress) -> dict:
    """Create a prediction on the model's latest version, poll, return it."""
    import httpx

    if not config.REPLICATE_API_TOKEN:
        raise ProviderError("REPLICATE_API_TOKEN is not set. Add it to backend/.env.")
    headers = {"Authorization": f"Bearer {config.REPLICATE_API_TOKEN}",
               "Content-Type": "application/json"}
    progress.update(0.05, "submitting to replicate")
    with httpx.Client(timeout=60) as client:
        # The /models/{m}/predictions shortcut only works for "official" models.
        # For community models it 404s, so resolve the latest version and post
        # to /v1/predictions. Try the shortcut first, fall back on 404.
        resp = client.post(
            f"https://api.replicate.com/v1/models/{model}/predictions",
            headers=headers, json={"input": inp},
        )
        if resp.status_code == 404:
            meta = client.get(f"https://api.replicate.com/v1/models/{model}",
                              headers=headers)
            meta.raise_for_status()
            version = (meta.json().get("latest_version") or {}).get("id")
            if not version:
                raise ProviderError(f"replicate model {model} has no runnable version")
            resp = client.post("https://api.replicate.com/v1/predictions",
                               headers=headers, json={"version": version, "input": inp})
        if resp.status_code == 402:
            raise ProviderError(
                "Replicate needs a payment method for this model. Add one at "
                "replicate.com/account/billing, or use fal / a local GPU.")
        if resp.status_code == 429:
            raise ProviderError(
                "Replicate rate-limited this request (no payment method on the "
                "account). Add billing at replicate.com/account/billing to run "
                "at full speed, or use a local GPU.")
        resp.raise_for_status()
        pred = resp.json()
        get_url = pred["urls"]["get"]
        for i in range(900):
            time.sleep(1)
            p = client.get(get_url, headers=headers)
            p.raise_for_status()
            pred = p.json()
            status = pred.get("status")
            if status == "succeeded":
                progress.update(0.9, "rendering complete")
                break
            if status in ("failed", "canceled"):
                raise ProviderError(f"replicate failed: {pred.get('error')}")
            progress.update(min(0.85, 0.1 + 0.75 * (i / 250)), f"replicate: {status}")
        return pred


def extract_url(data: dict, keys: tuple[str, ...]) -> str | None:
    """Pull a media URL out of a fal/replicate payload.

    Handles the common shapes: {"video": {"url": ...}}, {"audio": {"url": ...}},
    lists of those, and replicate's top-level {"output": url | [url, ...]}.
    """
    # replicate style
    output = data.get("output")
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url")
    # fal style
    for k in keys:
        v = data.get(k)
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
        if isinstance(v, list) and v and isinstance(v[0], dict) and v[0].get("url"):
            return v[0]["url"]
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None
