"""MediaForge API — FastAPI app entrypoint.

Run:  uvicorn app.main:app --reload   (from the backend/ directory)
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .jobs import manager
from .routes import edit, generate, media, settings

app = FastAPI(title="MediaForge", version="0.1.0")

# Allow the Vite dev server (any localhost port) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(media.router, prefix="/api")
app.include_router(generate.router, prefix="/api/generate")
app.include_router(edit.router, prefix="/api/edit")
app.include_router(settings.router, prefix="/api")

# Serve uploads + outputs so the browser can preview/download results.
app.mount("/files", StaticFiles(directory=str(config.DATA_DIR)), name="files")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "provider": config.WAN_PROVIDER,
            "device": config.DEVICE, "has_gpu": config.HAS_GPU}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = manager.get(job_id)
    if not job:
        return {"error": "not found"}
    return job.to_dict()


@app.get("/api/jobs")
async def list_jobs() -> dict:
    return {"jobs": manager.list()}
