"""Attach traceable RAG source locations to generated reports."""

from __future__ import annotations

import re
from typing import Any

try:
    from .schemas import EvidenceCitation, QualityInspectionReport
except ImportError:
    from schemas import EvidenceCitation, QualityInspectionReport

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[_.%-][a-z0-9]+)*")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.lower()))


def attach_evidence_citations(
    report: QualityInspectionReport, retrieved_chunks: list[dict[str, Any]]
) -> QualityInspectionReport:
    """Add the highest-overlap retrieved chunk as a bounded source citation."""
    updated = report.model_copy(deep=True)
    if not retrieved_chunks:
        return updated

    for check in updated.checks:
        query_tokens = _tokens(f"{check.clause_reference} {check.requirement}")
        ranked = []
        for chunk in retrieved_chunks:
            text = str(chunk.get("text", ""))
            score = len(query_tokens & _tokens(text))
            ranked.append((score, chunk))
        score, best = max(ranked, key=lambda item: item[0])
        if score <= 0:
            continue
        metadata = best.get("metadata") or {}
        page = metadata.get("page_number")
        check.evidence_citations = [
            EvidenceCitation(
                chunk_id=str(best.get("chunk_id", "unknown")),
                page=int(page) if page is not None else None,
                quote=str(best.get("text", ""))[:500],
            )
        ]
    return updated
