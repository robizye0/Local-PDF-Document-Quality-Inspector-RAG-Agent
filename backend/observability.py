"""Minimal process-local request metrics for a transparent local deployment."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from uuid import uuid4


def new_request_id() -> str:
    return f"REQ-{uuid4().hex.upper()}"


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._total = 0
        self._routes: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"count": 0, "last_status": 0, "last_latency_ms": 0.0}
        )

    def record(self, method: str, path: str, status: int, latency_ms: float) -> None:
        with self._lock:
            self._total += 1
            route = self._routes[f"{method} {path}"]
            route["count"] = int(route["count"]) + 1
            route["last_status"] = status
            route["last_latency_ms"] = round(latency_ms, 2)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {"requests_total": self._total, "routes": dict(self._routes)}

    def timer(self) -> float:
        return time.perf_counter()
