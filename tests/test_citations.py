from backend.citations import attach_evidence_citations
from backend.schemas import ComplianceCheck, QualityInspectionReport, SeverityLevel


def test_attaches_best_matching_chunk_with_page_and_quote():
    report = QualityInspectionReport(
        document_name="invoice.pdf",
        total_checks=1,
        passed=1,
        failed=0,
        flagged_for_review=0,
        overall_status="PASS",
        checks=[
            ComplianceCheck(
                check_id="CHK-001",
                clause_reference="voltage",
                requirement="Input voltage must be 240V AC",
                status="PASS",
                severity_level=SeverityLevel.LEVEL_2,
                confidence_score=0.95,
            )
        ],
    )
    chunks = [
        {
            "chunk_id": "doc_1_0",
            "text": "Input voltage: 240V AC. The unit passed inspection.",
            "metadata": {"page_number": 2},
        }
    ]

    updated = attach_evidence_citations(report, chunks)

    citation = updated.checks[0].evidence_citations[0]
    assert citation.chunk_id == "doc_1_0"
    assert citation.page == 2
    assert "240V AC" in citation.quote
