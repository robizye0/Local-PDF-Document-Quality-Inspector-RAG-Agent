"""Optional Celery/Redis job adapter; importing this module needs no Celery install."""

from __future__ import annotations

import base64
import importlib
import os
from typing import Any, Callable

_BYTES_MARKER = "__speccheck_bytes__"


def encode_payload(value: Any) -> Any:
    if isinstance(value, bytes):
        return {_BYTES_MARKER: base64.b64encode(value).decode("ascii")}
    if isinstance(value, tuple):
        return [encode_payload(item) for item in value]
    if isinstance(value, list):
        return [encode_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: encode_payload(item) for key, item in value.items()}
    return value


def decode_payload(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {_BYTES_MARKER}:
        return base64.b64decode(value[_BYTES_MARKER])
    if isinstance(value, list):
        return [decode_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: decode_payload(item) for key, item in value.items()}
    return value


def _load_function(module_name: str, function_name: str) -> Callable[..., Any]:
    module = importlib.import_module(module_name)
    function = getattr(module, function_name)
    if not callable(function):
        raise TypeError(f"Celery target is not callable: {module_name}.{function_name}")
    return function


class CeleryJobManager:
    """Thin adapter around Celery AsyncResult with JSON-safe task payloads."""

    def __init__(self, broker_url: str, result_backend: str) -> None:
        from celery import Celery

        self.app = Celery(
            "speccheck",
            broker=broker_url,
            backend=result_backend,
        )
        self.app.conf.task_serializer = "json"
        self.app.conf.result_serializer = "json"
        self.app.conf.accept_content = ["json"]

        @self.app.task(name="speccheck.run_job")
        def run_job(
            module_name: str, function_name: str, args: Any, kwargs: Any
        ) -> Any:
            function = _load_function(module_name, function_name)
            return function(*decode_payload(args), **decode_payload(kwargs))

        self._run_job = run_job

    def submit(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        task = self._run_job.apply_async(
            args=[
                function.__module__,
                function.__name__,
                encode_payload(list(args)),
                encode_payload(kwargs),
            ]
        )
        return str(task.id)

    def get(self, job_id: str) -> dict[str, Any] | None:
        result = self.app.AsyncResult(job_id)
        status = result.status.lower()
        record: dict[str, Any] = {
            "job_id": job_id,
            "status": "completed" if status == "success" else status,
            "backend": "celery",
        }
        if status == "success":
            value = result.result
            record["result"] = (
                value.model_dump() if hasattr(value, "model_dump") else value
            )
        elif status == "failure":
            record["error"] = str(result.result)
        return record


def build_celery_manager() -> CeleryJobManager | None:
    broker_url = os.getenv("CELERY_BROKER_URL", "").strip()
    result_backend = os.getenv("CELERY_RESULT_BACKEND", broker_url).strip()
    if not broker_url:
        return None
    try:
        return CeleryJobManager(broker_url, result_backend)
    except ImportError:
        return None
