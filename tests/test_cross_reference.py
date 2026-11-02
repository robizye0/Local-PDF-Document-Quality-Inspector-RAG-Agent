"""Tests for cross-document report reconciliation."""

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


cross_reference = _load("cross_reference", "cross_reference.py")


def test_cross_reference_summary_is_recomputed():
    report = SimpleNamespace(
        findings=[
            SimpleNamespace(status="PASS", needs_human_review=False),
            SimpleNamespace(status="FAIL", needs_human_review=True),
            SimpleNamespace(status="UNCERTAIN", needs_human_review=True),
        ],
        total_findings=99,
        passed=99,
        failed=0,
        flagged_for_review=0,
        overall_status="PASS",
    )

    cross_reference.normalize_cross_reference_counts(report)

    assert report.total_findings == 3
    assert report.passed == 1
    assert report.failed == 1
    assert report.flagged_for_review == 2
    assert report.overall_status == "FAIL"


def test_cross_reference_is_review_when_only_uncertain():
    report = SimpleNamespace(
        findings=[SimpleNamespace(status="UNCERTAIN", needs_human_review=True)],
        total_findings=0,
        passed=0,
        failed=0,
        flagged_for_review=0,
        overall_status="PASS",
    )

    cross_reference.normalize_cross_reference_counts(report)

    assert report.overall_status == "REVIEW"
