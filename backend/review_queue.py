"""
Human-in-the-Loop Review Queue.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from feedback import PREFERENCE_PAIRS_PATH, append_preference_pair
from schemas import ComplianceCheck

logger = logging.getLogger(__name__)

REVIEW_DIR = Path(__file__).resolve().parent.parent / "data" / "reviews"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ReviewTicket:
    ticket_id: str
    check: dict[str, Any]
    document_name: str
    reason: str
    created_at: str
    status: str = "open"
    profile_id: str | None = None

    @staticmethod
    def from_check(
        check: ComplianceCheck,
        document_name: str,
        reason: str,
        profile_id: str | None = None,
    ) -> "ReviewTicket":
        return ReviewTicket(
            ticket_id=f"REV-{uuid.uuid4().hex[:8].upper()}",
            check=check.model_dump(),
            document_name=document_name,
            reason=reason,
            created_at=datetime.now(timezone.utc).isoformat(),
            profile_id=profile_id,
        )

    def save(self) -> Path:
        path = REVIEW_DIR / f"{self.ticket_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
        logger.info("Saved review ticket %s", self.ticket_id)
        return path


def enqueue_review(
    check: ComplianceCheck,
    document_name: str,
    reason: str,
    profile_id: str | None = None,
) -> ReviewTicket:
    ticket = ReviewTicket.from_check(
        check, document_name, reason, profile_id=profile_id
    )
    ticket.save()
    return ticket


def resolve_review_ticket(ticket_id: str, resolution: dict[str, Any]) -> dict[str, Any]:
    """Resolve a ticket and append its human correction to the feedback ledger."""
    path = REVIEW_DIR / f"{ticket_id}.json"
    if not path.exists():
        raise FileNotFoundError(ticket_id)
    data = json.loads(path.read_text())
    was_open = data.get("status") == "open"
    data["status"] = "resolved"
    data["resolution"] = resolution
    data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    if was_open:
        append_preference_pair(data, resolution, PREFERENCE_PAIRS_PATH)
    return data


def list_open_tickets() -> list[dict]:
    tickets = []
    for f in REVIEW_DIR.glob("REV-*.json"):
        try:
            tickets.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue
    return [t for t in tickets if t.get("status") == "open"]
