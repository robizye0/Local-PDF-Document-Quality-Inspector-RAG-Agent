"""
PDF export: generates a 'Certificate of Inspection' from a QualityInspectionReport.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from schemas import QualityInspectionReport

logger = logging.getLogger(__name__)


def export_report_pdf(report: QualityInspectionReport, output_path: str | Path) -> Path:
    """
    Render a formatted PDF certificate for `report` and write to `output_path`.
    Returns the output Path.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#1a1d28"),
        spaceAfter=6,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#4f8cff"),
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        spaceAfter=6,
    )

    story = []
    story.append(Paragraph("Certificate of Inspection", title))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Document: <b>{report.document_name}</b>", body))
    story.append(Paragraph(f"Issued: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", body))
    story.append(Spacer(1, 8))

    # Summary table
    summary_data = [
        ["Metric", "Value"],
        ["Total Checks", str(report.total_checks)],
        ["Passed", str(report.passed)],
        ["Failed", str(report.failed)],
        ["Flagged for Review", str(report.flagged_for_review)],
        ["Overall Status", report.overall_status],
    ]
    summary_table = Table(summary_data, colWidths=[80 * mm, 80 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f8cff")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9fa"), colors.white]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Check details
    story.append(Paragraph("Check Details", heading))
    for check in report.checks:
        story.append(Paragraph(f"<b>{check.check_id}</b> — {check.clause_reference}", body))
        story.append(Paragraph(f"Requirement: {check.requirement}", body))
        story.append(Paragraph(f"Status: <b>{check.status}</b> | Severity: {check.severity_level}", body))
        if check.deviation_found:
            story.append(Paragraph(f"Deviation: {check.deviation_found}", body))
        if check.recommended_fix:
            story.append(Paragraph(f"Fix: {check.recommended_fix}", body))
        story.append(Spacer(1, 4))

    doc.build(story)
    logger.info("PDF certificate exported to %s", path)
    return path
