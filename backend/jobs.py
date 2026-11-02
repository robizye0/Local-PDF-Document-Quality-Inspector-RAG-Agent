"""Asynchronous job state tracking with a local worker pool.

The local backend keeps development usable without Redis. The API shape is
compatible with a future Celery/Redis worker deployment.
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

try:
    from .celery_jobs import build_celery_manager
except ImportError:
    from celery_jobs import build_celery_manager


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        requested_backend = os.getenv("JOB_BACKEND", "thread").lower()
        self.backend = "thread"
        self._celery = None
        if requested_backend == "celery":
            self._celery = build_celery_manager()
            if self._celery is not None:
                self.backend = "celery"
            else:
                # Keep local development deterministic until Redis/Celery is
                # explicitly configured and installed.
                import logging

                logging.getLogger(__name__).warning(
                    "JOB_BACKEND=celery requested without configured adapter; "
                    "using thread backend."
                )
        self._executor = (
            None
            if self._celery is not None
            else ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="speccheck-job"
            )
        )
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def submit(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        if self._celery is not None:
            return self._celery.submit(function, *args, **kwargs)
        job_id = f"JOB-{uuid.uuid4().hex[:10].upper()}"
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "backend": self.backend,
                "created_at": self._now(),
                "updated_at": self._now(),
            }
        assert self._executor is not None
        self._executor.submit(self._run, job_id, function, args, kwargs)
        return job_id

    def _run(
        self,
        job_id: str,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
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
        if self._celery is not None:
            return self._celery.get(job_id)
        with self._lock:
            record = self._jobs.get(job_id)
            return dict(record) if record else None

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)


job_manager = JobManager()
