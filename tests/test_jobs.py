"""Tests for asynchronous job state tracking."""

from __future__ import annotations

import os
import sys
import time

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from jobs import JobManager


def test_job_manager_transitions_to_completed():
    manager = JobManager(max_workers=1)
    job_id = manager.submit(lambda: {"report_id": "RPT-1"})

    deadline = time.time() + 3
    status = manager.get(job_id)
    while status["status"] not in {"completed", "failed"} and time.time() < deadline:
        time.sleep(0.01)
        status = manager.get(job_id)

    assert status["status"] == "completed"
    assert status["result"] == {"report_id": "RPT-1"}
    manager.shutdown()


def test_job_manager_captures_failures():
    manager = JobManager(max_workers=1)
    job_id = manager.submit(lambda: (_ for _ in ()).throw(ValueError("boom")))

    deadline = time.time() + 3
    status = manager.get(job_id)
    while status["status"] not in {"completed", "failed"} and time.time() < deadline:
        time.sleep(0.01)
        status = manager.get(job_id)

    assert status["status"] == "failed"
    assert "boom" in status["error"]
    manager.shutdown()
