"""CI-safe RAG evaluation metrics with optional framework discovery."""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RagEvaluation:
    faithfulness: float
    answer_relevance: float
    context_precision: float
    context_recall: float
    overall: float

    def as_dict(self) -> dict[str, float]:
        return {
            "faithfulness": round(self.faithfulness, 4),
            "answer_relevance": round(self.answer_relevance, 4),
            "context_precision": round(self.context_precision, 4),
            "context_recall": round(self.context_recall, 4),
            "overall": round(self.overall, 4),
        }


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+(?:[_.%-][a-z0-9]+)*", text.lower()))


def evaluate_rag_case(
    query: str,
    contexts: Iterable[str],
    expected_terms: Iterable[str],
    answer: str = "",
) -> RagEvaluation:
    """Score retrieval and answer grounding without an external model/API."""
    context_list = list(contexts)
    expected = [_tokens(term) for term in expected_terms]
    expected = [term for term in expected if term]
    context_tokens = [_tokens(context) for context in context_list]
    all_context = set().union(*context_tokens) if context_tokens else set()

    # A chunk is relevant when it contains at least one complete expected term.
    relevant_chunk_count = sum(
        any(term <= tokens for term in expected) for tokens in context_tokens
    )
    context_precision = (
        relevant_chunk_count / len(context_list) if context_list else 0.0
    )
    covered_terms = sum(term <= all_context for term in expected)
    context_recall = covered_terms / len(expected) if expected else 0.0

    answer_tokens = _tokens(answer)
    sentence_terms = _sentence_terms(answer)
    supported_claims = sum(
        any(term <= all_context and term <= sentence for term in expected)
        for sentence in sentence_terms
    )
    answer_claims = len(sentence_terms)
    faithfulness = supported_claims / answer_claims if answer_claims else 1.0
    answer_relevance = (
        sum(term <= answer_tokens for term in expected) / len(expected)
        if expected
        else 0.0
    )
    overall = (faithfulness + answer_relevance + context_precision + context_recall) / 4
    return RagEvaluation(
        faithfulness, answer_relevance, context_precision, context_recall, overall
    )


def _sentence_terms(answer: str) -> list[set[str]]:
    sentences = [part.strip() for part in re.split(r"[.!?\n]+", answer) if part.strip()]
    return [_tokens(sentence) for sentence in sentences]


def optional_evaluation_frameworks() -> dict[str, bool]:
    return {
        "ragas": importlib.util.find_spec("ragas") is not None,
        "deepeval": importlib.util.find_spec("deepeval") is not None,
    }
