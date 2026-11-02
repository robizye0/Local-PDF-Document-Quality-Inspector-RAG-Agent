"""
Ollama client with Tenacity retry, JSON repair, metrics, and dynamic schema support.
"""

from __future__ import annotations
from tracing.langfuse_tracing import trace_ollama_call

import json
import logging
import os
import time
from typing import Any, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from schemas import CrossReferenceReport, EvidenceVerification, QualityInspectionReport
from rule_profiles import get_report_schema, InspectionProfile
from evidence_verifier import select_verification_targets

# Build a concise JSON schema hint for the LLM from the Pydantic model
def _build_schema_hint() -> str:
    try:
        schema = QualityInspectionReport.model_json_schema()
        return json.dumps(schema, indent=2)
    except Exception:
        return (
            "{\n"
            '  "document_name": "string",\n'
            '  "total_checks": 1,\n'
            '  "passed": 1,\n'
            '  "failed": 0,\n'
            '  "flagged_for_review": 0,\n'
            '  "overall_status": "PASS",\n'
            '  "checks": [\n'
            "    {\n"
            '      "check_id": "CHK-001",\n'
            '      "clause_reference": "string",\n'
            '      "requirement": "string",\n'
            '      "status": "PASS",\n'
            '      "deviation_found": "string",\n'
            '      "severity_level": 1,\n'
            '      "recommended_fix": "string",\n'
            '      "confidence_score": 0.95,\n'
            '      "needs_human_review": false,\n'
            '      "review_reason": "string"\n'
            "    }\n"
            "  ]\n"
            "}"
        )


def _build_schema_hint_for_schema(schema_cls: type[BaseModel]) -> str:
    try:
        schema = schema_cls.model_json_schema()
        return json.dumps(schema, indent=2)
    except Exception:
        return _build_schema_hint()

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
    # Normalize common model synonyms to the strict schema vocabulary.
    text = re.sub(r'("(?:status|overall_status)"\s*:\s*)"PASSED"', r'\1"PASS"', text, flags=re.IGNORECASE)
    text = re.sub(r'("(?:status|overall_status)"\s*:\s*)"FAILED"', r'\1"FAIL"', text, flags=re.IGNORECASE)
    return text


class OllamaClient:
    """Ollama wrapper with retry logic and structured output validation."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = 120,
        provider: str | None = None,
    ):
        self.provider = (provider or os.getenv("INFERENCE_PROVIDER", "ollama")).lower()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def openai_compatible(self) -> bool:
        return self.provider in {"openai-compatible", "vllm", "tensorrt-llm"}

    def health(self) -> bool:
        try:
            if self.openai_compatible:
                resp = requests.get(f"{self.base_url}/models", timeout=10)
                resp.raise_for_status()
                models = [m.get("id", "") for m in resp.json().get("data", [])]
            else:
                resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
            return any(self.model in model for model in models)
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.error("Inference health check failed: %s", exc)
            return False

    @trace_ollama_call(operation_name="ollama.generate")
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
        if self.openai_compatible:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
                "response_format": {"type": "json_object"},
            }
            endpoint = f"{self.base_url}/chat/completions"
        else:
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
            endpoint = f"{self.base_url}/api/generate"

        last_error = None
        for attempt in range(1, max_retries + 1):
            start = time.perf_counter()
            try:
                resp = requests.post(
                    endpoint,
                    json=payload,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                last_error = f"Inference request failed (attempt {attempt}): {exc}"
                logger.warning(last_error)
                continue

            elapsed_ms = (time.perf_counter() - start) * 1000
            response_body = resp.json()
            if self.openai_compatible:
                raw_text = response_body.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = response_body.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
            else:
                raw_text = response_body.get("response", "")
                prompt_tokens = response_body.get("prompt_eval_count")
                completion_tokens = response_body.get("eval_count")
            raw_text = _repair_json(raw_text.strip())

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
                if self.openai_compatible:
                    payload["temperature"] = max(0.0, payload["temperature"] - 0.05)
                else:
                    payload["options"]["temperature"] = max(0.0, payload["options"]["temperature"] - 0.05)

        return None, last_error or "Max retries exceeded", None

    def run_cross_reference(
        self,
        documents: list[dict[str, str]],
        specification: str,
    ) -> tuple[CrossReferenceReport | None, str | None, InspectionMetrics | None]:
        """Compare evidence from exactly two documents in one structured pass."""
        schema_hint = _build_schema_hint_for_schema(CrossReferenceReport)
        system = (
            "You are a cross-document compliance auditor. Compare exactly two source documents "
            "against the supplied specification. Identify matching requirements and contradictions. "
            "Never invent missing evidence. Return STRICT JSON only matching this schema:\n\n"
            f"{schema_hint}\n\n"
            "Rules:\n"
            "1. Use one XRF-### finding per material cross-document comparison.\n"
            "2. Quote evidence separately from each document.\n"
            "3. Use UNCERTAIN when either document lacks proof and set needs_human_review=true.\n"
            "4. Status FAIL means the documents contradict the specification or each other."
        )
        sections = []
        for index, document in enumerate(documents[:2], start=1):
            sections.append(
                f"## DOCUMENT {index}: {document['name']}\n"
                f"{document.get('context', document.get('text', ''))[:10000]}"
            )
        user = f"## SPECIFICATION\n{specification}\n\n" + "\n\n".join(sections)
        return self.generate_json(system, user, CrossReferenceReport, max_retries=2)

    def verify_evidence(
        self,
        document_text: str,
        specification: str,
        report: Any,
        max_targets: int = 3,
    ) -> tuple[EvidenceVerification | None, str | None, InspectionMetrics | None]:
        """Run one bounded verifier pass over only risky checks."""
        targets = select_verification_targets(report, max_targets=max_targets)
        if not targets:
            return None, None, None

        schema_hint = _build_schema_hint_for_schema(EvidenceVerification)
        system = (
            "You are an evidence verifier for a document compliance system. "
            "Check each requested result against the source document only. "
            "Do not infer missing facts. Return STRICT JSON only matching this schema:\n\n"
            f"{schema_hint}\n\n"
            "Rules:\n"
            "1. One decision per supplied check_id, maximum three decisions.\n"
            "2. Use UNCERTAIN when the source does not prove the result.\n"
            "3. Evidence must quote or precisely identify text from the source document.\n"
            "4. Confidence must reflect the supplied evidence."
        )
        checks = [check.model_dump() for check in targets]
        user = (
            f"## SPECIFICATION\n{specification}\n\n"
            f"## CANDIDATE CHECKS\n{json.dumps(checks, ensure_ascii=False)}\n\n"
            f"## SOURCE DOCUMENT\n{document_text[:12000]}\n\n"
            "Verify the candidate checks now."
        )
        return self.generate_json(system, user, EvidenceVerification, max_retries=2)

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
            schema_hint = _build_schema_hint_for_schema(get_report_schema(profile.profile_id))
            system = (
                f"{profile.system_prompt}\n\n"
                "Output a STRICT JSON object matching this schema:\n\n"
                f"{schema_hint}\n\n"
                "Rules:\n"
                "1. Output ONLY valid JSON — no markdown, no explanation.\n"
                "2. Set needs_human_review=true if spec is ambiguous or confidence < 0.85.\n"
                "3. severity_level: 1=cosmetic, 2=minor, 3=major, 4=safety, 5=regulatory.\n"
                "4. check_id format: CHK-001, CHK-002, etc.\n"
                "5. overall_status must be PASS or FAIL.\n"
            )
            report_schema = get_report_schema(profile.profile_id)
        else:
            schema_hint = _build_schema_hint()
            system = (
                "You are an expert Quality Assurance Inspector. "
                "You will receive a TECHNICAL DOCUMENT and a SPECIFICATION. "
                "Output a STRICT JSON object matching this schema:\n\n"
                f"{schema_hint}\n\n"
                "Rules:\n"
                "1. Output ONLY valid JSON — no markdown, no explanation.\n"
                "2. Set needs_human_review=true if spec is ambiguous or confidence < 0.85.\n"
                "3. severity_level: 1=cosmetic, 2=minor, 3=major, 4=safety, 5=regulatory.\n"
                "4. check_id format: CHK-001, CHK-002, etc.\n"
                "5. overall_status must be PASS or FAIL.\n"
            )
            report_schema = QualityInspectionReport

        user = (
            f"## SPECIFICATION\n{specification}\n\n"
            f"## DOCUMENT\n{document_text[:8000]}\n\n"
            "Perform the compliance check now and respond with JSON matching the agreed schema."
        )

        report, error, metrics = self.generate_json(system, user, report_schema)
        return report, error, metrics
