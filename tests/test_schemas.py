"""
Tests for Pydantic schemas — edge cases and validation.
"""

from __future__ import annotations

import pytest

from schemas import ComplianceCheck, QualityInspectionReport, SeverityLevel


def test_compliance_check_valid():
    check = ComplianceCheck(
        check_id="CHK-001",
        clause_reference="§4.2.1",
        requirement="Voltage must not exceed 240V",
        status="PASS",
        deviation_found="",
        severity_level=SeverityLevel.LEVEL_3,
        recommended_fix="",
        confidence_score=0.95,
        needs_human_review=False,
        review_reason="",
    )
    assert check.status == "PASS"
    assert check.severity_level == 3


def test_compliance_check_status_case_insensitive():
    check = ComplianceCheck(
        check_id="CHK-002",
        clause_reference="§1.1",
        requirement="Document must have header",
        status="pass",
        severity_level=SeverityLevel.LEVEL_1,
        confidence_score=0.9,
        needs_human_review=False,
    )
    assert check.status == "PASS"


def test_compliance_check_invalid_status():
    with pytest.raises(Exception):
        ComplianceCheck(
            check_id="CHK-003",
            clause_reference="§1.1",
            requirement="Test",
            status="MAYBE",
            severity_level=SeverityLevel.LEVEL_1,
            confidence_score=0.5,
            needs_human_review=True,
        )


def test_compliance_check_invalid_confidence():
    with pytest.raises(Exception):
        ComplianceCheck(
            check_id="CHK-004",
            clause_reference="§1.1",
            requirement="Test",
            status="PASS",
            severity_level=SeverityLevel.LEVEL_1,
            confidence_score=1.5,  # out of range
            needs_human_review=False,
        )


def test_quality_inspection_report_valid():
    report = QualityInspectionReport(
        document_name="test.pdf",
        total_checks=1,
        passed=1,
        failed=0,
        flagged_for_review=0,
        overall_status="PASS",
        checks=[
            ComplianceCheck(
                check_id="CHK-001",
                clause_reference="§1.1",
                requirement="Has title",
                status="PASS",
                severity_level=SeverityLevel.LEVEL_1,
                confidence_score=0.9,
                needs_human_review=False,
            )
        ],
    )
    assert report.overall_status == "PASS"


def test_report_inconsistent_counts():
    """Overall status should still validate even if counts look inconsistent."""
    report = QualityInspectionReport(
        document_name="test.pdf",
        total_checks=2,
        passed=1,
        failed=1,
        flagged_for_review=0,
        overall_status="FAIL",
        checks=[
            ComplianceCheck(
                check_id="CHK-001",
                clause_reference="§1.1",
                requirement="A",
                status="PASS",
                severity_level=SeverityLevel.LEVEL_1,
                confidence_score=0.9,
                needs_human_review=False,
            ),
            ComplianceCheck(
                check_id="CHK-002",
                clause_reference="§1.2",
                requirement="B",
                status="FAIL",
                severity_level=SeverityLevel.LEVEL_3,
                confidence_score=0.8,
                needs_human_review=True,
            ),
        ],
    )
    assert report.failed == 1
