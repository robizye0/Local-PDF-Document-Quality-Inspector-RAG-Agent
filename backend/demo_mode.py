"""Deterministic local substitutes for recruiter-friendly demo mode."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

try:
    from .schemas import (
        ComplianceCheck,
        CrossReferenceFinding,
        CrossReferenceReport,
        QualityInspectionReport,
        SeverityLevel,
    )
except ImportError:
    from schemas import (
        ComplianceCheck,
        CrossReferenceFinding,
        CrossReferenceReport,
        QualityInspectionReport,
        SeverityLevel,
    )

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class DemoMetrics(BaseModel):
    processing_time_ms: float
    model_version: str


class DemoRAG:
    """In-memory page chunks; no model download, vector DB, or network needed."""

    def __init__(self) -> None:
        self.documents: dict[str, list[dict[str, Any]]] = {}

    def index_document(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> int:
        pages = text.split("\f")
        chunks = []
        for page_number, page in enumerate(pages, start=1):
            if page.strip():
                chunks.append(
                    {
                        "chunk_id": f"{doc_id}_{page_number - 1}",
                        "text": page.strip(),
                        "metadata": {"page_number": page_number, **(metadata or {})},
                    }
                )
        self.documents[doc_id] = chunks
        return len(chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        profile_id: str | None = None,
        doc_id: str | None = None,
    ) -> list[dict[str, Any]]:
        del profile_id
        chunks = self.documents.get(doc_id or "", [])
        query_tokens = set(_TOKEN_RE.findall(query.lower()))
        ranked = sorted(
            chunks,
            key=lambda chunk: len(
                query_tokens & set(_TOKEN_RE.findall(chunk["text"].lower()))
            ),
            reverse=True,
        )
        return ranked[:top_k]

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_chunks": sum(len(chunks) for chunks in self.documents.values()),
            "embedding_model": "demo-deterministic",
        }


class DemoInference:
    """Deterministic structured report generator for demos and smoke tests."""

    def health(self) -> bool:
        return True

    def run_compliance_check(
        self, context_text: str, specification: str, profile: Any = None
    ) -> tuple[QualityInspectionReport, None, DemoMetrics]:
        del profile
        has_context = bool(context_text.strip())
        report = QualityInspectionReport(
            document_name="demo-document.pdf",
            total_checks=2,
            passed=2 if has_context else 1,
            failed=0 if has_context else 1,
            flagged_for_review=0,
            overall_status="PASS" if has_context else "FAIL",
            checks=[
                ComplianceCheck(
                    check_id="CHK-001",
                    clause_reference="document.text-layer",
                    requirement="The document must contain extractable text.",
                    status="PASS" if has_context else "FAIL",
                    deviation_found="" if has_context else "No text context available.",
                    severity_level=SeverityLevel.LEVEL_2,
                    recommended_fix=(
                        "Provide a text-based PDF." if not has_context else ""
                    ),
                    confidence_score=1.0,
                ),
                ComplianceCheck(
                    check_id="CHK-002",
                    clause_reference="specification.context",
                    requirement=specification[:500],
                    status="PASS" if has_context else "FAIL",
                    severity_level=SeverityLevel.LEVEL_2,
                    confidence_score=0.98,
                ),
            ],
        )
        return (
            report,
            None,
            DemoMetrics(
                processing_time_ms=1.0,
                model_version="demo-deterministic",
            ),
        )

    def verify_evidence(self, *args: Any, **kwargs: Any) -> tuple[None, None, None]:
        del args, kwargs
        return None, None, None

    def run_cross_reference(
        self, documents: list[dict[str, str]], specification: str
    ) -> tuple[CrossReferenceReport, None, DemoMetrics]:
        names = [document["name"] for document in documents]
        report = CrossReferenceReport(
            document_names=names,
            total_findings=1,
            passed=1,
            failed=0,
            flagged_for_review=0,
            overall_status="PASS",
            findings=[
                CrossReferenceFinding(
                    finding_id="XRF-001",
                    source_document=names[0],
                    target_document=names[1],
                    clause_reference=specification[:200],
                    status="PASS",
                    source_evidence=documents[0]["context"][:1200],
                    target_evidence=documents[1]["context"][:1200],
                    confidence_score=1.0,
                )
            ],
        )
        return (
            report,
            None,
            DemoMetrics(
                processing_time_ms=1.0,
                model_version="demo-deterministic",
            ),
        )
