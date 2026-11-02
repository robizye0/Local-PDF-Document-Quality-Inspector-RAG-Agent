"""Tests for webhook payloads and signing."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from webhooks import WebhookDispatcher, build_webhook_request


def test_webhook_request_contains_event_and_hmac_signature():
    body, headers = build_webhook_request("inspection.completed", {"report_id": "RPT-1"}, "secret")

    assert json.loads(body)["event"] == "inspection.completed"
    expected = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert headers["X-SpecCheck-Signature"] == f"sha256={expected}"
    assert headers["X-SpecCheck-Event"] == "inspection.completed"


def test_dispatcher_delivers_json_post(monkeypatch):
    calls = []

    class Response:
        status_code = 204

        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr("webhooks.requests.post", fake_post)
    dispatcher = WebhookDispatcher("http://127.0.0.1:9999/hook", "secret")
    result = dispatcher.send("review.flagged", {"ticket_id": "REV-1"})

    assert result["status_code"] == 204
    assert calls[0][0].endswith("/hook")
    assert json.loads(calls[0][1]["data"])["payload"]["ticket_id"] == "REV-1"
