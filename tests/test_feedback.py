"""Tests for turning resolved review tickets into preference-training records."""

from __future__ import annotations

import importlib.util
import json
import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_BACKEND_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


feedback = _load("feedback", "feedback.py")
schemas = _load("schemas", "schemas.py")
review_queue = _load("review_queue", "review_queue.py")


def test_resolved_review_becomes_preference_pair(tmp_path):
    ticket = {
        "ticket_id": "REV-12345678",
        "document_name": "invoice.pdf",
        "reason": "Missing buyer ID",
        "check": {
            "check_id": "CHK-002",
            "clause_reference": "Buyer ID",
            "status": "FAIL",
            "confidence_score": 0.72,
        },
        "profile_id": "commercial-invoice",
    }
    resolution = {
        "corrected_check": {
            "check_id": "CHK-002",
            "clause_reference": "Buyer ID",
            "status": "PASS",
            "confidence_score": 0.99,
            "deviation_found": "",
        },
        "operator": "alice",
        "notes": "Buyer ID is present in the source document.",
    }

    path = tmp_path / "preference_pairs.jsonl"
    record = feedback.append_preference_pair(ticket, resolution, path)

    saved = json.loads(path.read_text())
    assert saved["ticket_id"] == "REV-12345678"
    assert saved["profile_id"] == "commercial-invoice"
    assert saved["rejected"] == ticket["check"]
    assert saved["chosen"] == resolution["corrected_check"]
    assert record["metadata"]["operator"] == "alice"


def test_resolve_ticket_updates_audit_record_and_exports_pair(tmp_path, monkeypatch):
    review_dir = tmp_path / "reviews"
    review_dir.mkdir()
    preference_path = tmp_path / "feedback" / "preference_pairs.jsonl"
    monkeypatch.setattr(review_queue, "REVIEW_DIR", review_dir)
    monkeypatch.setattr(review_queue, "PREFERENCE_PAIRS_PATH", preference_path)
    ticket = {
        "ticket_id": "REV-87654321",
        "document_name": "invoice.pdf",
        "reason": "Incorrect result",
        "check": {"check_id": "CHK-001", "status": "FAIL"},
        "profile_id": "commercial-invoice",
        "status": "open",
    }
    (review_dir / "REV-87654321.json").write_text(json.dumps(ticket))

    result = review_queue.resolve_review_ticket(
        "REV-87654321",
        {"corrected_check": {"check_id": "CHK-001", "status": "PASS"}, "operator": "alice"},
    )

    assert result["status"] == "resolved"
    assert json.loads((review_dir / "REV-87654321.json").read_text())["status"] == "resolved"
    assert len(preference_path.read_text().splitlines()) == 1

