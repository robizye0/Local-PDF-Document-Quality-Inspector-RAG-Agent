"""Deterministic aggregation for cross-document findings."""

from __future__ import annotations

from typing import Any


def normalize_cross_reference_counts(report: Any) -> Any:
    findings = list(getattr(report, "findings", []))
    report.total_findings = len(findings)
    report.passed = sum(finding.status == "PASS" for finding in findings)
    report.failed = sum(finding.status == "FAIL" for finding in findings)
    report.flagged_for_review = sum(
        bool(finding.needs_human_review) for finding in findings
    )
    if report.failed:
        report.overall_status = "FAIL"
    elif any(finding.status == "UNCERTAIN" for finding in findings):
        report.overall_status = "REVIEW"
    else:
        report.overall_status = "PASS"
    return report
