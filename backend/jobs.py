"""Asynchronous job state tracking with a local worker pool.

The local backend keeps development usable without Redis. The API shape is
compatible with a future Celery/Redis worker deployment.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import threading
import uuid
from typing import Any, Callable


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        requested_backend = os.getenv("JOB_BACKEND", "thread").lower()
        self.backend = "thread"
        if requested_backend == "celery":
            # Keep local development deterministic until a Redis/Celery worker
            # is explicitly configured and deployed.
            import logging

            logging.getLogger(__name__).warning(
                "JOB_BACKEND=celery requested; Celery/Redis adapter is not configured, using thread backend."
            )
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="speccheck-job")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def submit(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        job_id = f"JOB-{uuid.uuid4().hex[:10].upper()}"
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "backend": self.backend,
                "created_at": self._now(),
                "updated_at": self._now(),
            }
        self._executor.submit(self._run, job_id, function, args, kwargs)
        return job_id

    def _run(self, job_id: str, function: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self._update(job_id, status="running")
        try:
            result = function(*args, **kwargs)
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            self._update(job_id, status="completed", result=result)
        except Exception as exc:
            self._update(job_id, status="failed", error=str(exc))

    def _update(self, job_id: str, **values: Any) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(values, updated_at=self._now())

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            return dict(record) if record else None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


job_manager = JobManager()
