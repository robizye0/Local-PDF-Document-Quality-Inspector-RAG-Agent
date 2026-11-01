"""
Inspection rule profiles.
Each profile defines a custom Pydantic schema + system prompt for a specific domain.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

PROFILES_DIR = Path(__file__).resolve().parent.parent / "data" / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

# Built-in profiles ----------------------------------------------------------

class PcbCheckResult(BaseModel):
    check_id: str
    clause_reference: str
    requirement: str
    status: str
    deviation_found: str = ""
    severity_level: int = 3
    recommended_fix: str = ""
    confidence_score: float
    needs_human_review: bool = False
    review_reason: str = ""

class PcbInspectionReport(BaseModel):
    document_name: str
    total_checks: int
    passed: int
    failed: int
    flagged_for_review: int
    overall_status: str
    checks: list[PcbCheckResult]


class IsoCheckResult(BaseModel):
    check_id: str
    clause_reference: str
    requirement: str
    status: str
    deviation_found: str = ""
    severity_level: int = 3
    recommended_fix: str = ""
    confidence_score: float
    needs_human_review: bool = False
    review_reason: str = ""

class IsoInspectionReport(BaseModel):
    document_name: str
    total_checks: int
    passed: int
    failed: int
    flagged_for_review: int
    overall_status: str
    checks: list[IsoCheckResult]


class InvoiceCheckResult(BaseModel):
    check_id: str
    clause_reference: str
    requirement: str
    status: str
    deviation_found: str = ""
    severity_level: int = 3
    recommended_fix: str = ""
    confidence_score: float
    needs_human_review: bool = False
    review_reason: str = ""

class InvoiceInspectionReport(BaseModel):
    document_name: str
    total_checks: int
    passed: int
    failed: int
    flagged_for_review: int
    overall_status: str
    checks: list[InvoiceCheckResult]


# Profile registry -----------------------------------------------------------

class InspectionProfile(BaseModel):
    profile_id: str
    name: str
    description: str
    report_schema_name: str
    system_prompt: str
    fields: list[str] = []


BUILTIN_PROFILES: dict[str, InspectionProfile] = {
    "pcb-manufacturing": InspectionProfile(
        profile_id="pcb-manufacturing",
        name="PCB Manufacturing Specs",
        description="IPC-A-610, solder joint quality, trace width, drill sizing",
        report_schema_name="PcbInspectionReport",
        system_prompt=(
            "You are a PCB Quality Inspector. Verify the document against PCB manufacturing standards (IPC-A-610, Gerber spec). "
            "Focus on: solder joint quality, trace width, drill sizing, annular ring, surface finish. "
            "Output STRICT JSON only."
        ),
        fields=["trace_width", "solder_quality", "drill_sizes", "annular_ring"],
    ),
    "iso-compliance": InspectionProfile(
        profile_id="iso-compliance",
        name="ISO Compliance",
        description="ISO 9001 §8.6 — general quality management system compliance",
        report_schema_name="IsoInspectionReport",
        system_prompt=(
            "You are an ISO 9001 auditor. Verify the document against ISO 9001 §8.6 requirements. "
            "Focus on: documented evidence, inspection records, corrective actions, traceability. "
            "Output STRICT JSON only."
        ),
        fields=["documented_evidence", "inspection_records", "corrective_actions"],
    ),
    "commercial-invoice": InspectionProfile(
        profile_id="commercial-invoice",
        name="Commercial Invoice",
        description="Invoice completeness, tax IDs, line items, totals match",
        report_schema_name="InvoiceInspectionReport",
        system_prompt=(
            "You are a financial compliance auditor. Verify the document as a commercial invoice. "
            "Check: seller/buyer IDs, line items, quantities, unit prices, totals match, tax calculation. "
            "Output STRICT JSON only."
        ),
        fields=["seller_id", "buyer_id", "line_items", "totals_match", "tax_calc"],
    ),
}

# Mapping from schema name to actual Pydantic model
SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "PcbInspectionReport": PcbInspectionReport,
    "IsoInspectionReport": IsoInspectionReport,
    "InvoiceInspectionReport": InvoiceInspectionReport,
}


def get_profile(profile_id: str) -> InspectionProfile:
    if profile_id not in BUILTIN_PROFILES:
        raise ValueError(f"Unknown profile: {profile_id}. Available: {list(BUILTIN_PROFILES)}")
    return BUILTIN_PROFILES[profile_id]


def get_report_schema(profile_id: str) -> type[BaseModel]:
    profile = get_profile(profile_id)
    if profile.report_schema_name not in SCHEMA_MAP:
        raise ValueError(f"Schema not mapped: {profile.report_schema_name}")
    return SCHEMA_MAP[profile.report_schema_name]


def list_profiles() -> list[dict[str, Any]]:
    return [p.model_dump() for p in BUILTIN_PROFILES.values()]


def save_custom_profile(profile: InspectionProfile) -> Path:
    path = PROFILES_DIR / f"{profile.profile_id}.json"
    path.write_text(json.dumps(profile.model_dump(), indent=2))
    return path


def load_custom_profiles() -> list[InspectionProfile]:
    profiles = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            profiles.append(InspectionProfile.model_validate_json(f.read_text()))
        except Exception:
            continue
    return profiles
