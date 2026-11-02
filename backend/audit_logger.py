"""
Structured JSON audit logging.
Every inspection request is logged to logs/audit.log as a JSON line.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "audit.log"

logger = logging.getLogger("audit")
logger.setLevel(logging.INFO)
_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.propagate = False


def log_audit(event: str, **fields: Any) -> None:
    """Write a structured JSON audit log entry."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(entry, ensure_ascii=False))
