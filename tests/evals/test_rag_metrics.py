"""Automated retrieval-quality evaluation cases."""

from __future__ import annotations

import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from evaluation import evaluate_rag_case, optional_evaluation_frameworks


def test_rag_case_scores_grounded_retrieval():
    result = evaluate_rag_case(
        query="operating voltage",
        contexts=[
            "Electrical limits: maximum operating voltage is 240V AC.",
            "Revision history: version 2.0.",
        ],
        expected_terms=["240V AC"],
        answer="The maximum operating voltage is 240V AC.",
    )

    assert result.context_precision == 0.5
    assert result.context_recall == 1.0
    assert result.faithfulness == 1.0
    assert result.answer_relevance == 1.0
    assert result.overall >= 0.85


def test_optional_framework_detection_is_non_blocking():
    frameworks = optional_evaluation_frameworks()
    assert set(frameworks) == {"ragas", "deepeval"}
    assert all(isinstance(value, bool) for value in frameworks.values())
