"""Restricted subprocess wrapper for deterministic document validators.

This worker executes only application-owned validators; it never evaluates
LLM-generated code. It is a local safety boundary, not a Firecracker VM.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


class SandboxValidationError(RuntimeError):
    """Raised when the restricted validator cannot produce a result."""


def run_invoice_validation(
    document_text: str, timeout_seconds: float = 3.0
) -> dict[str, Any]:
    payload = json.dumps({"text": document_text[:50_000]}, ensure_ascii=False)
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=timeout_seconds,
            cwd=str(Path(__file__).resolve().parent),
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxValidationError(f"validator worker failed: {exc}") from exc
    if completed.returncode != 0:
        raise SandboxValidationError(
            completed.stderr.strip() or "validator worker failed"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SandboxValidationError("validator worker returned invalid JSON") from exc


def _worker() -> int:
    from invoice_validator import validate_invoice_text

    request = json.load(sys.stdin)
    result = validate_invoice_text(request["text"])
    json.dump(result._asdict(), sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(_worker())
