"""Tests for bounded evidence-verification orchestration."""

from __future__ import annotations

import importlib.util
import os
import sys
from types import SimpleNamespace

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_BACKEND_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


verifier = _load("evidence_verifier", "evidence_verifier.py")


def _check(check_id: str, status: str, confidence: float, review: bool = False):
    return SimpleNamespace(
        check_id=check_id,
        status=status,
        confidence_score=confidence,
        needs_human_review=review,
        review_reason="",
        deviation_found="existing",
        recommended_fix="existing fix",
        severity_level=3,
    )


def test_targets_are_bounded_and_prioritize_reviewable_checks():
    report = SimpleNamespace(
        checks=[
            _check("CHK-001", "FAIL", 0.70),
            _check("CHK-002", "FAIL", 0.71),
            _check("CHK-003", "FAIL", 0.72),
            _check("CHK-004", "FAIL", 0.73),
            _check("CHK-005", "PASS", 0.99, review=True),
        ]
    )

    targets = verifier.select_verification_targets(report, max_targets=3)

    assert [check.check_id for check in targets] == ["CHK-005", "CHK-001", "CHK-002"]


def test_contradictory_verifier_decision_is_kept_for_human_review():
    report = SimpleNamespace(checks=[_check("CHK-001", "FAIL", 0.70)])
    decision = SimpleNamespace(
        check_id="CHK-001",
        verdict="PASS",
        evidence="Total matches the stated tax calculation.",
        confidence_score=0.96,
        reason="The source text supports the requirement.",
    )

    verifier.apply_verification_decisions(report, [decision])

    assert report.checks[0].status == "PASS"
    assert report.checks[0].needs_human_review is True
    assert "verifier" in report.checks[0].review_reason.lower()
