"""Tests for switching the inference client to an OpenAI-compatible engine."""

from __future__ import annotations

import json
import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from ollama_client import OllamaClient
from schemas import EvidenceVerification


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [{"message": {"content": json.dumps({"decisions": []})}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4},
        }


def test_openai_compatible_provider_uses_chat_completions(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return _Response()

    monkeypatch.setattr("ollama_client.requests.post", fake_post)
    client = OllamaClient(
        base_url="http://127.0.0.1:8001/v1",
        model="Qwen/Qwen2.5-7B-Instruct",
        provider="openai-compatible",
    )

    result, error, metrics = client.generate_json(
        "system prompt",
        "user prompt",
        EvidenceVerification,
        max_retries=1,
    )

    assert error is None
    assert result.decisions == []
    assert metrics.prompt_tokens == 12
    assert calls[0][0] == "http://127.0.0.1:8001/v1/chat/completions"
    payload = calls[0][1]["json"]
    assert payload["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]
    assert payload["response_format"] == {"type": "json_object"}
