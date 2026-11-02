"""
Pydantic schemas for the inspection pipeline.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SeverityLevel(IntEnum):
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5


class ComplianceCheck(BaseModel):
    check_id: str = Field(pattern=r"^CHK-\d{3}$")
    clause_reference: str
    requirement: str = Field(max_length=500)
    status: str = Field(description="PASS or FAIL")
    deviation_found: str = Field(default="", max_length=1000)
    severity_level: SeverityLevel = Field(ge=1, le=5)
    recommended_fix: str = Field(default="", max_length=1000)
    confidence_score: float = Field(ge=0.0, le=1.0)
    needs_human_review: bool = False
    review_reason: str = Field(default="", max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value.upper() not in ("PASS", "FAIL"):
            raise ValueError("status must be PASS or FAIL")
        return value.upper()


class QualityInspectionReport(BaseModel):
    document_name: str
    total_checks: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    flagged_for_review: int = Field(ge=0)
    overall_status: str = Field(description="PASS or FAIL")
    checks: list[ComplianceCheck] = Field(min_length=1)

    @field_validator("overall_status")
    @classmethod
    def validate_overall(cls, value: str) -> str:
        if value.upper() not in ("PASS", "FAIL"):
            raise ValueError("overall_status must be PASS or FAIL")
        return value.upper()


class EvidenceDecision(BaseModel):
    check_id: str = Field(pattern=r"^CHK-\d{3}$")
    verdict: Literal["PASS", "FAIL", "UNCERTAIN"]
    evidence: str = Field(default="", max_length=1000)
    confidence_score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=500)


class EvidenceVerification(BaseModel):
    decisions: list[EvidenceDecision] = Field(default_factory=list, max_length=3)


class CrossReferenceFinding(BaseModel):
    finding_id: str = Field(pattern=r"^XRF-\d{3}$")
    source_document: str
    target_document: str
    clause_reference: str
    status: Literal["PASS", "FAIL", "UNCERTAIN"]
    source_evidence: str = Field(default="", max_length=1200)
    target_evidence: str = Field(default="", max_length=1200)
    contradiction: str = Field(default="", max_length=1200)
    confidence_score: float = Field(ge=0.0, le=1.0)
    needs_human_review: bool = False
    review_reason: str = Field(default="", max_length=500)


class CrossReferenceReport(BaseModel):
    document_names: list[str] = Field(min_length=2, max_length=2)
    total_findings: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    flagged_for_review: int = Field(ge=0)
    overall_status: Literal["PASS", "FAIL", "REVIEW"]
    findings: list[CrossReferenceFinding] = Field(default_factory=list)


ComplianceCheck.model_rebuild()
QualityInspectionReport.model_rebuild()
