import json
from pathlib import Path

from backend.evaluation import evaluate_rag_case


FIXTURE = Path(__file__).parent / "fixtures" / "benchmark_cases.json"


def test_committed_rag_benchmark_meets_quality_gate():
    benchmark = json.loads(FIXTURE.read_text(encoding="utf-8"))
    thresholds = benchmark["thresholds"]
    scores = []

    for case in benchmark["cases"]:
        score = evaluate_rag_case(
            case["query"],
            case["contexts"],
            case["expected_terms"],
            case["answer"],
        )
        scores.append(score)

    assert scores
    assert min(score.faithfulness for score in scores) >= thresholds["faithfulness"]
    assert min(score.context_recall for score in scores) >= thresholds["context_recall"]
    assert min(score.overall for score in scores) >= thresholds["overall"]
