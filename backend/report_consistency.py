"""Deterministic consistency rules for model-generated inspection reports."""

from __future__ import annotations

from typing import Any


def normalize_report_counts(report: Any) -> Any:
    """Recompute summary fields from the individual checks.

    The LLM is not trusted to self-report aggregate counts or overall status.
    The profile-specific Pydantic models all expose the same fields, so this
    helper can reconcile any inspection report shape.
    """
    checks = list(getattr(report, "checks", []))
    report.total_checks = len(checks)
    report.passed = sum(check.status == "PASS" for check in checks)
    report.failed = sum(check.status == "FAIL" for check in checks)
    report.flagged_for_review = sum(bool(check.needs_human_review) for check in checks)
    report.overall_status = "FAIL" if report.failed else "PASS"
    return report
