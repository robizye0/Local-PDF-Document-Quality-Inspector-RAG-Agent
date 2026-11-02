"""Tests for the restricted document-validation worker."""

from __future__ import annotations

import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from sandbox_validator import run_invoice_validation


def test_invoice_validation_runs_in_restricted_worker():
    result = run_invoice_validation(
        """
        Seller ID: ACME-123
        Buyer ID: BUY-456
        Item: Widget | Quantity: 2 | Unit Price: $25.00
        Subtotal: $50.00
        Tax Rate: 10%
        Tax Calculation: $50.00 x 10% = $5.00
        Tax: $5.00
        Total: $55.00
        """
    )

    assert result["is_valid"] is True
    assert result["fields"]["Tax Calculation"] is True
