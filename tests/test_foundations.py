"""Tests for deterministic report reconciliation and invoice validation."""

from __future__ import annotations

import importlib.util
import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_BACKEND_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


schemas = _load("foundation_schemas", "schemas.py")
profiles = _load("foundation_profiles", "rule_profiles.py")
consistency = _load("report_consistency", "report_consistency.py")
invoice = _load("invoice_validator", "invoice_validator.py")


def test_report_counts_are_recomputed_from_checks():
    report = profiles.get_report_schema("commercial-invoice")(
        document_name="invoice.pdf",
        total_checks=99,
        passed=99,
        failed=0,
        flagged_for_review=0,
        overall_status="PASS",
        checks=[
            {
                "check_id": "CHK-001",
                "clause_reference": "Seller ID",
                "requirement": "Seller ID must be present.",
                "status": "PASS",
                "confidence_score": 1.0,
            },
            {
                "check_id": "CHK-002",
                "clause_reference": "Totals",
                "requirement": "Totals must be present.",
                "status": "FAIL",
                "confidence_score": 0.7,
                "needs_human_review": True,
            },
        ],
    )

    consistency.normalize_report_counts(report)

    assert report.total_checks == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.flagged_for_review == 1
    assert report.overall_status == "FAIL"


def test_valid_invoice_fields_and_tax_are_detected():
    text = """
    SELLER: Acme Components Ltd.
    Seller ID: ACME-123456
    BUYER: Northstar Manufacturing Inc.
    Buyer ID: NSM-987654
    LINE ITEMS
    Item: Widget | Quantity: 2 | Unit Price: $25.00 | Line Total: $50.00
    Subtotal: $100.00
    Tax Rate: 10%
    Tax Calculation: $100.00 x 10% = $10.00
    Tax: $10.00
    Total: $110.00
    """

    result = invoice.validate_invoice_text(text)

    assert result.fields == {
        "Seller ID": True,
        "Buyer ID": True,
        "Line Items": True,
        "Quantities": True,
        "Unit Prices": True,
        "Totals": True,
        "Tax Calculation": True,
    }
    assert result.is_valid is True


def test_blank_invoice_is_rejected_by_deterministic_checks():
    result = invoice.validate_invoice_text("Invoice template\nSeller ID:\nBuyer ID:\n")

    assert result.is_valid is False
    assert result.fields["Seller ID"] is False
    assert result.fields["Buyer ID"] is False
    assert result.fields["Line Items"] is False
    assert result.fields["Tax Calculation"] is False
