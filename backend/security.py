"""Small, dependency-free API security primitives."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable


def api_key_is_valid(configured_key: str, supplied_key: str | None) -> bool:
    """Allow unauthenticated local development, require exact configured keys."""
    if not configured_key:
        return True
    return supplied_key == configured_key


class RateLimiter:
    """In-memory fixed-window limiter suitable for one local API process."""

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = max(0, limit)
        self.window_seconds = window_seconds
        self.clock = clock
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.limit:
                return False
            timestamps.append(now)
            return True
