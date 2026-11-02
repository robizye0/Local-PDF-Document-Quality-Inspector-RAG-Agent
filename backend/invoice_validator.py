"""Deterministic validation for commercial invoice fields and arithmetic."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import NamedTuple


INVOICE_FIELDS = (
    "Seller ID",
    "Buyer ID",
    "Line Items",
    "Quantities",
    "Unit Prices",
    "Totals",
    "Tax Calculation",
)


class InvoiceValidation(NamedTuple):
    fields: dict[str, bool]
    is_valid: bool
    reasons: dict[str, str]


def _money(value: str) -> Decimal:
    return Decimal(value.replace(",", "").strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _has_value(text: str, label: str) -> bool:
    pattern = rf"(?im)^[ \t]*{re.escape(label)}[ \t]*[:#-][ \t]*([^\r\n]+?)[ \t]*$"
    match = re.search(pattern, text)
    return bool(match and match.group(1).strip())


def _has_line_item(text: str) -> bool:
    return bool(
        re.search(r"(?im)^\s*(?:item|description|product|service)\s*[:|]\s*\S+", text)
        or re.search(r"(?im)^\s*line\s+items?\s*$", text)
    )


def _has_quantity(text: str) -> bool:
    return bool(re.search(r"(?i)\b(?:quantity|qty)\s*[:=|]\s*\d+(?:\.\d+)?", text))


def _has_unit_price(text: str) -> bool:
    return bool(re.search(r"(?i)\bunit\s+price\s*[:=|]\s*\$?\s*\d+(?:[,.]\d{1,2})?", text))


def _has_total(text: str) -> bool:
    return bool(re.search(r"(?im)^\s*(?:subtotal|grand\s+total|total)\s*[:=]\s*\$?\s*\d", text))


def _tax_is_correct(text: str) -> bool:
    explicit = re.search(
        r"(?i)tax\s+calculation\s*:\s*\$?\s*([\d,.]+)\s*x\s*([\d.]+)%\s*=\s*\$?\s*([\d,.]+)",
        text,
    )
    if explicit:
        base, rate, stated = explicit.groups()
        try:
            expected = (_money(base) * Decimal(rate) / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            return expected == _money(stated)
        except (InvalidOperation, ValueError):
            return False

    subtotal = re.search(r"(?im)^\s*subtotal\s*[:=]\s*\$?\s*([\d,.]+)", text)
    rate = re.search(r"(?im)^\s*tax\s+rate\s*[:=]\s*([\d.]+)%", text)
    tax = re.search(r"(?im)^\s*tax\s*[:=]\s*\$?\s*([\d,.]+)", text)
    if not (subtotal and rate and tax):
        return False
    try:
        expected = (_money(subtotal.group(1)) * Decimal(rate.group(1)) / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return expected == _money(tax.group(1))
    except (InvalidOperation, ValueError):
        return False


def validate_invoice_text(text: str) -> InvoiceValidation:
    fields = {
        "Seller ID": _has_value(text, "Seller ID"),
        "Buyer ID": _has_value(text, "Buyer ID"),
        "Line Items": _has_line_item(text),
        "Quantities": _has_quantity(text),
        "Unit Prices": _has_unit_price(text),
        "Totals": _has_total(text),
        "Tax Calculation": _tax_is_correct(text),
    }
    reasons = {
        field: f"Deterministic invoice validation failed: {field}."
        for field, passed in fields.items()
        if not passed
    }
    return InvoiceValidation(fields=fields, is_valid=all(fields.values()), reasons=reasons)


def reconcile_invoice_report(
    report: Any,
    document_text: str,
    validation: InvoiceValidation | None = None,
) -> Any:
    """Reconcile invoice checks with deterministic document validation."""
    validation = validation or validate_invoice_text(document_text)
    for check in report.checks:
        clause = check.clause_reference.lower()
        field = next((name for name in INVOICE_FIELDS if name.lower() in clause), None)
        if field is None:
            continue

        if validation.fields[field]:
            check.status = "PASS"
            check.deviation_found = ""
            check.recommended_fix = ""
            check.needs_human_review = False
            check.review_reason = ""
        else:
            check.status = "FAIL"
            check.deviation_found = validation.reasons[field]
            check.recommended_fix = f"Provide or correct {field}."
            check.needs_human_review = True
            check.review_reason = validation.reasons[field]

    from report_consistency import normalize_report_counts

    return normalize_report_counts(report)
