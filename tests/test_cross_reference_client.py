"""Tests for the structured cross-reference inference call."""

from __future__ import annotations

import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from ollama_client import OllamaClient
from schemas import CrossReferenceReport


def test_cross_reference_uses_both_documents(monkeypatch):
    captured = {}
    client = OllamaClient(base_url="http://127.0.0.1:11434", model="qwen2.5:7b")

    def fake_generate(system, user, response_schema, max_retries=3):
        captured["system"] = system
        captured["user"] = user
        captured["schema"] = response_schema
        captured["retries"] = max_retries
        return "report", None, "metrics"

    monkeypatch.setattr(client, "generate_json", fake_generate)
    result = client.run_cross_reference(
        [
            {"name": "contract.pdf", "text": "Liability limit 100 units."},
            {"name": "datasheet.pdf", "text": "Maximum operating limit 120 units."},
        ],
        "Operating limit must not exceed the contract limit.",
    )

    assert result == ("report", None, "metrics")
    assert captured["schema"] is CrossReferenceReport
    assert "contract.pdf" in captured["user"]
    assert "datasheet.pdf" in captured["user"]
    assert captured["retries"] == 2
