"""Signed, asynchronous webhook notifications for enterprise integrations."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)


def build_webhook_request(
    event: str,
    payload: dict[str, Any],
    secret: str | None = None,
    event_id: str | None = None,
) -> tuple[bytes, dict[str, str]]:
    delivery_id = event_id or f"EVT-{uuid4().hex.upper()}"
    envelope = {
        "event_id": delivery_id,
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    body = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SpecCheck-Webhooks/1.0",
        "X-SpecCheck-Event": event,
        "X-SpecCheck-Event-Id": delivery_id,
        "X-SpecCheck-Idempotency-Key": delivery_id,
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
        max_retries: int | None = None,
        retry_backoff: float | None = None,
        dead_letter_path: str | None = None,
    ) -> None:
        self.url = (
            url
            if url is not None
            else os.getenv("WEBSPEC_WEBHOOK_URL", os.getenv("WEBHOOK_URL", ""))
        )
        self.secret = secret if secret is not None else os.getenv("WEBHOOK_SECRET", "")
        self.timeout = timeout
        self.max_retries = (
            max_retries
            if max_retries is not None
            else int(os.getenv("WEBHOOK_MAX_RETRIES", "3"))
        )
        self.retry_backoff = (
            retry_backoff
            if retry_backoff is not None
            else float(os.getenv("WEBHOOK_RETRY_BACKOFF_SECONDS", "0.5"))
        )
        configured_dead_letter = dead_letter_path or os.getenv(
            "WEBHOOK_DEAD_LETTER_PATH", ""
        )
        self.dead_letter_path = (
            Path(configured_dead_letter) if configured_dead_letter else None
        )
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="speccheck-webhook"
        )

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def send(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.url:
            return {"delivered": False, "reason": "not_configured"}
        event_id = f"EVT-{uuid4().hex.upper()}"
        body, headers = build_webhook_request(event, payload, self.secret, event_id)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    self.url, data=body, headers=headers, timeout=self.timeout
                )
                response.raise_for_status()
                return {
                    "delivered": True,
                    "status_code": response.status_code,
                    "event": event,
                    "event_id": event_id,
                    "attempts": attempt + 1,
                }
            except Exception as exc:  # webhook failure must not affect inspection
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * (2**attempt))
        self._write_dead_letter(event, event_id, payload, last_error)
        raise RuntimeError(f"Webhook delivery failed after retries: {last_error}")

    def _write_dead_letter(
        self,
        event: str,
        event_id: str,
        payload: dict[str, Any],
        error: Exception | None,
    ) -> None:
        if not self.dead_letter_path:
            return
        self.dead_letter_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event_id": event_id,
            "event": event,
            "payload": payload,
            "error": str(error) if error else "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self.dead_letter_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

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
