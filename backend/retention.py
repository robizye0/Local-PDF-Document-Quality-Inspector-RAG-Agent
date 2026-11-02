"""Retention and safe deletion helpers for uploaded documents."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable


def delete_upload(directory: Path, upload_id: str) -> bool:
    """Delete one direct child upload; reject traversal and symlink escapes."""
    root = directory.resolve()
    candidate = (root / upload_id).resolve()
    if candidate.parent != root or candidate.name != upload_id:
        return False
    if not candidate.is_file():
        return False
    candidate.unlink()
    return True


def cleanup_expired_files(
    directory: Path,
    max_age_seconds: float,
    now: float | None = None,
    mtime: Callable[[Path], float] = lambda path: path.stat().st_mtime,
) -> int:
    """Remove old regular files directly under a directory and return the count."""
    if max_age_seconds <= 0:
        return 0
    current = time.time() if now is None else now
    removed = 0
    if not directory.exists():
        return removed
    for path in directory.iterdir():
        if path.is_file() and current - mtime(path) > max_age_seconds:
            path.unlink()
            removed += 1
    return removed
