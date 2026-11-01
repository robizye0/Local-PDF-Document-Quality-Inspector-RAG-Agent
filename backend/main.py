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

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from audit_logger import log_audit
from ollama_client import OllamaClient, InspectionMetrics
from pdf_reader import extract_text
from report_exporter import export_report_pdf
from review_queue import enqueue_review, list_open_tickets
from rule_profiles import get_profile, list_profiles
from schemas import QualityInspectionReport

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")
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

ollama = OllamaClient(base_url=OLLAMA_URL, model=OLLAMA_MODEL)


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    model: str
    model_pulled: bool


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
    return HealthResponse(
        status="ok" if model_pulled else "degraded",
        ollama_reachable=model_pulled,
        model=OLLAMA_MODEL,
        model_pulled=model_pulled,
    )


@app.get("/api/v1/profiles", response_model=list[ProfileResponse])
async def list_profiles_endpoint():
    return list_profiles()


@app.post("/api/v1/inspect", response_model=InspectResponse)
async def inspect_document(
    file: UploadFile = File(...),
    specification: str = "General manufacturing quality standards (ISO 9001 §8.6)",
    profile_id: str | None = None,
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    profile = None
    if profile_id:
        try:
            profile = get_profile(profile_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    upload_id = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    upload_path = UPLOADS_DIR / upload_id
    content = await file.read()
    upload_path.write_bytes(content)
    logger.info("Uploaded %s (%d bytes)", upload_id, len(content))

    try:
        doc_text = extract_text(upload_path, max_chars=20_000)
    except Exception as exc:
        raise HTTPException(500, f"PDF extraction failed: {exc}")

    if len(doc_text.strip()) < 50:
        raise HTTPException(400, "Document appears to be empty or image-only (no text layer).")

    start_time = time.perf_counter()
    report, error, metrics = ollama.run_compliance_check(doc_text, specification, profile)
    total_time_ms = (time.perf_counter() - start_time) * 1000

    if error:
        log_audit("inspection_failed", document=file.filename, profile=profile_id, error=error)
        raise HTTPException(502, f"Ollama inference failed: {error}")

    review_tickets = []
    for check in report.checks:
        if check.needs_human_review:
            ticket = enqueue_review(check, file.filename, check.review_reason)
            review_tickets.append({
                "ticket_id": ticket.ticket_id,
                "reason": ticket.reason,
                "confidence": check.confidence_score,
            })

    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    report_path = REPORTS_DIR / f"{report_id}.json"
    report_path.write_text(report.model_dump_json(indent=2))

    pdf_path = None
    try:
        pdf_path = REPORTS_DIR / f"{report_id}.pdf"
        export_report_pdf(report, pdf_path)
    except Exception as exc:
        logger.warning("PDF export failed: %s", exc)

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


@app.post("/api/v1/reviews/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, resolution: dict):
    path = REVIEW_DIR / f"{ticket_id}.json"
    if not path.exists():
        raise HTTPException(404, "Ticket not found.")
    data = json.loads(path.read_text())
    data["status"] = "resolved"
    data["resolution"] = resolution
    data["resolved_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return {"ticket_id": ticket_id, "status": "resolved"}
