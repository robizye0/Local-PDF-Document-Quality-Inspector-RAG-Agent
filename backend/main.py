"""
FastAPI backend — microservice orchestration layer.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from audit_logger import log_audit
from rag.chromadb_rag import SemanticRAG
from tracing.langfuse_tracing import (
    trace_ollama_call,
    trace_inspection_pipeline,
    trace_pdf_extraction,
    trace_review_routing,
)
from ollama_client import OllamaClient, InspectionMetrics
from pdf_reader import extract_text
from report_exporter import export_report_pdf
from report_consistency import normalize_report_counts
from invoice_validator import InvoiceValidation, reconcile_invoice_report
from sandbox_validator import SandboxValidationError, run_invoice_validation
from evidence_verifier import apply_verification_decisions
from feedback import PREFERENCE_PAIRS_PATH
from review_queue import enqueue_review, list_open_tickets, resolve_review_ticket, REVIEW_DIR
from rule_profiles import get_profile, list_profiles
from schemas import QualityInspectionReport

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")
INFERENCE_PROVIDER = os.getenv("INFERENCE_PROVIDER", "ollama").lower()
INFERENCE_BASE_URL = os.getenv(
    "INFERENCE_BASE_URL",
    OLLAMA_URL if INFERENCE_PROVIDER == "ollama" else "http://localhost:8001/v1",
)
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"
for d in (REPORTS_DIR, UPLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SpecCheck API",
    description="PDF Specification Compliance Checker — microservice backend.",
    version="2.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ollama = OllamaClient(
    base_url=INFERENCE_BASE_URL,
    model=OLLAMA_MODEL,
    provider=INFERENCE_PROVIDER,
)
rag = SemanticRAG()


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    model: str
    model_pulled: bool
    inference_provider: str
    rag_stats: dict[str, Any] | None = None


class InspectResponse(BaseModel):
    report_id: str
    document_name: str
    profile_id: str | None
    summary: dict[str, Any]
    metrics: dict[str, Any] | None = None
    report_path: str
    pdf_path: str | None = None
    review_tickets: list[dict]


class ProfileResponse(BaseModel):
    profile_id: str
    name: str
    description: str
    fields: list[str]


@app.get("/health", response_model=HealthResponse)
async def health():
    model_pulled = ollama.health()
    rag_stats = rag.get_stats() if rag else None
    return HealthResponse(
        status="ok" if model_pulled else "degraded",
        ollama_reachable=model_pulled,
        model=OLLAMA_MODEL,
        model_pulled=model_pulled,
        inference_provider=INFERENCE_PROVIDER,
        rag_stats=rag_stats,
    )


@app.get("/api/v1/profiles", response_model=list[ProfileResponse])
async def list_profiles_endpoint():
    return list_profiles()


@app.post("/api/v1/inspect", response_model=InspectResponse, status_code=201)
async def inspect_document(
    file: UploadFile = File(...),
    specification: str = Form("General manufacturing quality standards (ISO 9001 §8.6)"),
    profile_id: str | None = Form(None),
):
    """
    Upload a PDF and receive a structured QualityInspectionReport.
    Uses RAG to retrieve only relevant chunks before sending to the LLM.
    Checks below the confidence threshold are enqueued for human review.
    """
    try:
        return await _inspect_document_impl(file, specification, profile_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled inspection error")
        raise HTTPException(status_code=500, detail=f"Inspection failed: {exc}")


async def _inspect_document_impl(
    file: UploadFile,
    specification: str,
    profile_id: str | None = None,
) -> InspectResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")

    profile = None
    if profile_id:
        try:
            profile = get_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    # Start Langfuse trace
    trace = trace_inspection_pipeline(file.filename, profile_id)

    # Save upload
    upload_id = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    upload_path = UPLOADS_DIR / upload_id
    content = await file.read()
    upload_path.write_bytes(content)
    logger.info("Uploaded %s (%d bytes)", upload_id, len(content))

    # Extract text
    try:
        doc_text = extract_text(upload_path, max_chars=50_000)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {exc}")

    if len(doc_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Document appears to be empty or image-only (no text layer).")

    # Index document in RAG vector store
    doc_id = f"doc_{upload_id}"
    rag.index_document(doc_id, doc_text, metadata={"filename": file.filename, "profile_id": profile_id or "default"})

    # Retrieve relevant chunks using semantic search
    retrieved_chunks = rag.retrieve(
        specification,
        top_k=5,
        profile_id=profile_id,
        doc_id=doc_id,
    )
    context_text = "\n\n".join([chunk["text"] for chunk in retrieved_chunks])

    # Log PDF extraction trace
    trace_pdf_extraction(str(upload_path), pages=doc_text.count("\f") + 1, chars_extracted=len(doc_text))

    # Run Ollama compliance check with RAG context
    start_time = time.perf_counter()
    report, error, metrics = ollama.run_compliance_check(context_text, specification, profile)
    total_time_ms = (time.perf_counter() - start_time) * 1000

    if error:
        log_audit("inspection_failed", document=file.filename, profile=profile_id, error=error)
        if trace:
            trace.update(metadata={"status": "failed", "error": error})
        raise HTTPException(status_code=502, detail=f"Ollama inference failed: {error}")

    # The uploaded filename is authoritative; never trust the model to name the document.
    report.document_name = file.filename
    if profile_id == "commercial-invoice":
        try:
            validation_payload = run_invoice_validation(doc_text)
            validation = InvoiceValidation(**validation_payload)
        except SandboxValidationError as exc:
            logger.warning("Restricted invoice validator unavailable; using in-process fallback: %s", exc)
            validation = None
        report = reconcile_invoice_report(report, doc_text, validation=validation)
    else:
        report = normalize_report_counts(report)

    # Run one bounded second-pass verifier only for risky or ambiguous checks.
    verification, verification_error, _verification_metrics = ollama.verify_evidence(
        doc_text,
        specification,
        report,
        max_targets=3,
    )
    if verification_error:
        logger.warning("Evidence verification skipped: %s", verification_error)
    if verification is not None:
        report = apply_verification_decisions(report, verification.decisions)

    # Human-in-the-Loop routing
    review_tickets = []
    for check in report.checks:
        if check.needs_human_review:
            ticket = enqueue_review(check, file.filename, check.review_reason, profile_id=profile_id)
            review_tickets.append({
                "ticket_id": ticket.ticket_id,
                "reason": ticket.reason,
                "confidence": check.confidence_score,
            })

    trace_review_routing(len(review_tickets), CONFIDENCE_THRESHOLD)

    # Persist report
    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    report_path = REPORTS_DIR / f"{report_id}.json"
    report_path.write_text(report.model_dump_json(indent=2))

    # Export PDF certificate
    pdf_path = None
    try:
        pdf_path = REPORTS_DIR / f"{report_id}.pdf"
        export_report_pdf(report, pdf_path)
    except Exception as exc:
        logger.warning("PDF export failed: %s", exc)

    # Audit log
    log_audit(
        "inspection_completed",
        report_id=report_id,
        document=file.filename,
        profile=profile_id,
        total_checks=report.total_checks,
        passed=report.passed,
        failed=report.failed,
        flagged=report.flagged_for_review,
        processing_time_ms=round(total_time_ms, 2),
        metrics=metrics.model_dump() if metrics else None,
        rag_chunks_retrieved=len(retrieved_chunks),
    )

    if trace:
        trace.update(
            output={
                "report_id": report_id,
                "status": "completed",
                "total_checks": report.total_checks,
                "passed": report.passed,
                "failed": report.failed,
                "flagged": report.flagged_for_review,
                "processing_time_ms": round(total_time_ms, 2),
            }
        )

    return InspectResponse(
        report_id=report_id,
        document_name=file.filename,
        profile_id=profile_id,
        summary={
            "total_checks": report.total_checks,
            "passed": report.passed,
            "failed": report.failed,
            "flagged_for_review": report.flagged_for_review,
            "overall_status": report.overall_status,
        },
        metrics=metrics.model_dump() if metrics else None,
        report_path=str(report_path),
        pdf_path=str(pdf_path) if pdf_path else None,
        review_tickets=review_tickets,
    )
@app.get("/api/v1/reports/{report_id}")
async def get_report(report_id: str):
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        raise HTTPException(404, "Report not found.")
    return FileResponse(path, media_type="application/json")


@app.get("/api/v1/reports/{report_id}/pdf")
async def get_report_pdf(report_id: str):
    path = REPORTS_DIR / f"{report_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "PDF certificate not found.")
    return FileResponse(path, media_type="application/pdf")


@app.get("/api/v1/reviews", response_model=list[dict])
async def get_review_queue():
    return list_open_tickets()


@app.get("/api/v1/feedback/preferences")
async def get_feedback_preferences():
    if not PREFERENCE_PAIRS_PATH.exists():
        return []
    records = []
    for line in PREFERENCE_PAIRS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


@app.post("/api/v1/reviews/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, resolution: dict):
    try:
        return resolve_review_ticket(ticket_id, resolution)
    except FileNotFoundError:
        raise HTTPException(404, "Ticket not found.")
