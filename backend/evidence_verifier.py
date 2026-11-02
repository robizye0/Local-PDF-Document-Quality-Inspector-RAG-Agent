"""Bounded evidence-verification helpers for uncertain inspection checks."""

from __future__ import annotations

from typing import Any, Iterable


def select_verification_targets(report: Any, max_targets: int = 3) -> list[Any]:
    """Select a small, deterministic set of risky checks for a verifier pass."""
    candidates = [
        check
        for check in report.checks
        if check.needs_human_review
        or check.confidence_score < 0.85
        or check.severity_level >= 4
    ]
    candidates.sort(
        key=lambda check: (
            not check.needs_human_review,
            check.confidence_score,
            check.check_id,
        )
    )
    return candidates[: max(0, max_targets)]


def apply_verification_decisions(report: Any, decisions: Iterable[Any]) -> Any:
    """Apply verifier decisions without hiding disagreements from reviewers."""
    by_id = {check.check_id: check for check in report.checks}
    for decision in decisions:
        check = by_id.get(decision.check_id)
        if check is None:
            continue

        confidence = float(decision.confidence_score)
        evidence = (decision.evidence or "").strip()
        reason = (decision.reason or "").strip()
        if decision.verdict == "UNCERTAIN" or confidence < 0.85:
            check.needs_human_review = True
            check.review_reason = (
                reason or "Evidence verifier returned an uncertain result."
            )
            continue

        if decision.verdict not in {"PASS", "FAIL"}:
            check.needs_human_review = True
            check.review_reason = "Evidence verifier returned an invalid verdict."
            continue

        changed = check.status != decision.verdict
        check.status = decision.verdict
        # A verifier disagreement is precisely the case that must remain visible
        # to a human; never silently auto-resolve it.
        check.needs_human_review = bool(check.needs_human_review or changed)
        if changed:
            check.review_reason = (
                "Evidence verifier contradicted the initial result. "
                f"Verifier evidence: {evidence or 'not provided'}."
            )
        elif reason and not check.review_reason:
            check.review_reason = reason

    from report_consistency import normalize_report_counts

    return normalize_report_counts(report)
