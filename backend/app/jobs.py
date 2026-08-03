"""In-memory async job manager.

Long-running work (ffmpeg renders, Wan generations) runs in a small thread
pool so the HTTP layer stays responsive. Clients submit a job, get an id back,
then poll ``GET /api/jobs/{id}`` for progress until it is ``done`` or ``error``.

This is deliberately dependency-free (no Redis/Celery) — fine for a local,
single-user tool. State lives in the process and resets on restart.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Optional

from . import config


@dataclass
class Job:
    id: str
    kind: str  # e.g. "video.trim", "generate.t2v"
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0  # 0..1
    message: str = ""
    result: Optional[dict] = None  # e.g. {"output": "outputs/xyz.mp4"}
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class JobManager:
    def __init__(self, max_workers: int) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def _touch(self, job: Job, **updates: Any) -> None:
        with self._lock:
            for k, v in updates.items():
                setattr(job, k, v)
            job.updated_at = time.time()

    def submit(self, kind: str, fn: Callable[["JobProgress"], dict]) -> Job:
        """Register a job and run ``fn(progress)`` in the pool.

        ``fn`` receives a JobProgress handle and must return a result dict.
        """
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        with self._lock:
            self._jobs[job.id] = job

        def _run() -> None:
            self._touch(job, status="running", message="starting")
            handle = JobProgress(self, job)
            try:
                result = fn(handle)
                self._touch(job, status="done", progress=1.0, result=result,
                            message="complete")
            except Exception as exc:  # noqa: BLE001 - surface any failure to UI
                self._touch(
                    job,
                    status="error",
                    error=f"{type(exc).__name__}: {exc}",
                    message="failed",
                )
                traceback.print_exc()

        self._pool.submit(_run)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [j.to_dict() for j in jobs]


class JobProgress:
    """Passed to worker functions so they can report progress + messages."""

    def __init__(self, mgr: JobManager, job: Job) -> None:
        self._mgr = mgr
        self._job = job

    def update(self, progress: Optional[float] = None, message: Optional[str] = None) -> None:
        updates: dict[str, Any] = {}
        if progress is not None:
            updates["progress"] = max(0.0, min(1.0, progress))
        if message is not None:
            updates["message"] = message
        if updates:
            self._mgr._touch(self._job, **updates)


# Singleton used by the routes.
manager = JobManager(max_workers=config.MAX_WORKERS)
