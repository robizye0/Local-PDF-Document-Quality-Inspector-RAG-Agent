"""
Ollama client with Tenacity retry, JSON repair, metrics, and dynamic schema support.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

from schemas import QualityInspectionReport
from rule_profiles import get_report_schema, InspectionProfile

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b-instruct-q4_K_M"


class InspectionMetrics(BaseModel):
    processing_time_ms: float
    tokens_per_second: float | None = None
    model_version: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _repair_json(raw: str) -> str:
    """Best-effort JSON repair for common Ollama formatting issues."""
    text = raw.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()
    # Remove trailing commas before closing brackets/braces
    import re
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


class OllamaClient:
    """Ollama wrapper with retry logic and structured output validation."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def health(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return any(self.model in m for m in models)
        except requests.RequestException as exc:
            logger.error("Ollama health check failed: %s", exc)
            return False

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[T],
        max_retries: int = 3,
    ) -> tuple[T | None, str | None, InspectionMetrics | None]:
        """
        Call Ollama with retry logic and JSON repair.
        Returns (parsed_model, error_or_None, metrics_or_None).
        """
        payload = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "system": system_prompt,
            "prompt": user_prompt,
            "options": {
                "temperature": 0.1,
                "num_ctx": 8192,
            },
        }

        last_error = None
        for attempt in range(1, max_retries + 1):
            start = time.perf_counter()
            try:
                resp = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                last_error = f"Ollama request failed (attempt {attempt}): {exc}"
                logger.warning(last_error)
                continue

            elapsed_ms = (time.perf_counter() - start) * 1000
            raw_text = resp.json().get("response", "").strip()
            raw_text = _repair_json(raw_text)

            prompt_tokens = resp.json().get("prompt_eval_count")
            completion_tokens = resp.json().get("eval_count")
            tps = None
            if completion_tokens and elapsed_ms > 0:
                tps = completion_tokens / (elapsed_ms / 1000)

            metrics = InspectionMetrics(
                processing_time_ms=round(elapsed_ms, 2),
                tokens_per_second=round(tps, 2) if tps else None,
                model_version=self.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            try:
                parsed = response_schema.model_validate_json(raw_text)
                return parsed, None, metrics
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = f"Validation error (attempt {attempt}): {exc}"
                logger.warning("%s\nRaw: %s", last_error, raw_text[:400])
                payload["options"]["temperature"] = max(0.0, payload["options"]["temperature"] - 0.05)

        return None, last_error or "Max retries exceeded", None

    def run_compliance_check(
        self,
        document_text: str,
        specification: str,
        profile: InspectionProfile | None = None,
    ) -> tuple[BaseModel | None, str | None, InspectionMetrics | None]:
        """
        Full compliance-check pipeline.
        Uses dynamic profile if provided; falls back to generic system prompt.
        """
        if profile:
            system = profile.system_prompt
            report_schema = get_report_schema(profile.profile_id)
        else:
            system = (
                "You are an expert Quality Assurance Inspector. "
                "You will receive a TECHNICAL DOCUMENT and a SPECIFICATION. "
                "Output a STRICT JSON object matching the schema.\n\n"
                "Rules:\n"
                "1. Output ONLY valid JSON — no markdown, no explanation.\n"
                "2. Set needs_human_review=true if spec is ambiguous or confidence < 0.85.\n"
                "3. severity_level: 1=cosmetic, 2=minor, 3=major, 4=safety, 5=regulatory.\n"
            )
            report_schema = QualityInspectionReport

        user = (
            f"## SPECIFICATION\n{specification}\n\n"
            f"## DOCUMENT\n{document_text[:8000]}\n\n"
            "Perform the compliance check now and respond with JSON matching the agreed schema."
        )

        report, error, metrics = self.generate_json(system, user, report_schema)
        return report, error, metrics
