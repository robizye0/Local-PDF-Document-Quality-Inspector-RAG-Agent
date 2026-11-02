"""Structured human-feedback records for future DPO/LoRA training."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEEDBACK_DIR = Path(__file__).resolve().parent.parent / "data" / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
PREFERENCE_PAIRS_PATH = FEEDBACK_DIR / "preference_pairs.jsonl"


def build_preference_pair(ticket: dict[str, Any], resolution: dict[str, Any]) -> dict[str, Any]:
    """Build a training-ready rejected/chosen pair without discarding audit data."""
    chosen = (
        resolution.get("corrected_check")
        or resolution.get("approved_check")
        or resolution.get("resolution")
        or resolution
    )
    return {
        "schema_version": "1.0",
        "ticket_id": ticket.get("ticket_id"),
        "document_name": ticket.get("document_name"),
        "profile_id": ticket.get("profile_id"),
        "prompt": {
            "document_name": ticket.get("document_name"),
            "review_reason": ticket.get("reason", ""),
            "original_check": ticket.get("check", {}),
        },
        "rejected": ticket.get("check", {}),
        "chosen": chosen,
        "metadata": {
            "operator": resolution.get("operator"),
            "notes": resolution.get("notes", ""),
            "resolution": resolution,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def append_preference_pair(
    ticket: dict[str, Any],
    resolution: dict[str, Any],
    path: Path = PREFERENCE_PAIRS_PATH,
) -> dict[str, Any]:
    record = build_preference_pair(ticket, resolution)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
