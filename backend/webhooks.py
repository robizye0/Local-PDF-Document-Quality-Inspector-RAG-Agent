"""Signed, asynchronous webhook notifications for enterprise integrations."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


def build_webhook_request(
    event: str,
    payload: dict[str, Any],
    secret: str | None = None,
) -> tuple[bytes, dict[str, str]]:
    envelope = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SpecCheck-Webhooks/1.0",
        "X-SpecCheck-Event": event,
    }
    if secret:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        headers["X-SpecCheck-Signature"] = f"sha256={digest}"
    return body, headers


class WebhookDispatcher:
    """Fire-and-forget webhook delivery with bounded request timeouts."""

    def __init__(
        self,
        url: str | None = None,
        secret: str | None = None,
        timeout: float = 5.0,
        max_workers: int = 2,
    ) -> None:
        self.url = url if url is not None else os.getenv("WEBSPEC_WEBHOOK_URL", os.getenv("WEBHOOK_URL", ""))
        self.secret = secret if secret is not None else os.getenv("WEBHOOK_SECRET", "")
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="speccheck-webhook")

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def send(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.url:
            return {"delivered": False, "reason": "not_configured"}
        body, headers = build_webhook_request(event, payload, self.secret)
        response = requests.post(self.url, data=body, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return {"delivered": True, "status_code": response.status_code, "event": event}

    def dispatch(self, event: str, payload: dict[str, Any]) -> Future | None:
        if not self.enabled:
            return None
        future = self._executor.submit(self.send, event, payload)
        future.add_done_callback(self._log_result)
        return future

    @staticmethod
    def _log_result(future: Future) -> None:
        try:
            result = future.result()
            logger.info("Webhook delivered: %s", result)
        except Exception as exc:
            logger.warning("Webhook delivery failed: %s", exc)
