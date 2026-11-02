import json

from backend.webhooks import WebhookDispatcher, build_webhook_request


def test_webhook_request_has_stable_delivery_id():
    body, headers = build_webhook_request("inspection.completed", {}, "secret")

    envelope = json.loads(body)
    assert envelope["event_id"]
    assert headers["X-SpecCheck-Event-Id"] == envelope["event_id"]
    assert headers["X-SpecCheck-Idempotency-Key"] == envelope["event_id"]


def test_webhook_send_retries_transient_failure(monkeypatch):
    attempts = []

    class Response:
        status_code = 202

        def raise_for_status(self):
            return None

    def fake_post(*args, **kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise RuntimeError("temporary")
        return Response()

    monkeypatch.setattr("backend.webhooks.requests.post", fake_post)
    dispatcher = WebhookDispatcher("http://example.test", max_retries=1, retry_backoff=0)

    result = dispatcher.send("inspection.completed", {})

    assert result["delivered"] is True
    assert len(attempts) == 2
