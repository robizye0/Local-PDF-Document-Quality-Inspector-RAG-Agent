# SpecCheck — PDF Specification Compliance Checker

[![CI/CD](https://github.com/robizye0/Local-PDF-Document-Quality-Inspector-RAG-Agent-/workflows/CI/CD/badge.svg)](https://github.com/robizye0/Local-PDF-Document-Quality-Inspector-RAG-Agent-/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Docker Ready](https://img.shields.io/badge/docker-ready-brightgreen)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Portfolio-grade local AI compliance checker built with FastAPI, Streamlit, Ollama, and Pydantic.

---

## The Problem

Manual specification-compliance checking is **slow, expensive, and error-prone**.

| Issue | Impact |
|---|---|
| Human fatigue | Missed deviations on page 180 |
| Inconsistent severity grading | Two engineers rate the same defect Level 2 vs Level 5 |
| No audit trail | Cannot prove which clauses were checked |
| Slow turnaround | Days to produce a compliance report |

The result: **costly rework, customer rejections, and regulatory fines**.

---

## The Solution

SpecCheck automates clause-by-clause compliance verification using a local LLM (Ollama) and **enforces structured output via Pydantic** — so every result is machine-readable, traceable, and reviewable.

```mermaid
graph LR
    A[User] --> B[Streamlit UI]
    B --> C[FastAPI REST API]
    C --> D[PDF Text Extraction]
    D --> E[Semantic Chunking + RAG]
    E --> F[Ollama LLM]
    F --> G[Pydantic Validation]
    G --> H{Confidence >= 85%?}
    H -->|Yes| I[Structured Report]
    H -->|No| J[Human Review Queue]
    I --> K[JSON / PDF Certificate]
    J --> K
    C --> L[Langfuse Tracing]
    L --> M[OpenTelemetry Metrics]
```

---

## Architecture

```
User -> Streamlit UI -> FastAPI REST API -> Local Ollama Engine -> Pydantic Validation
```

---

## Key Features

### 1. Strict Structured Outputs (Pydantic / JSON Mode)

Every LLM response is parsed and validated against an exact schema:

```python
class ComplianceCheck(BaseModel):
    check_id: str          # CHK-001
    clause_reference: str  # §4.2.1
    requirement: str       # "Voltage must not exceed 240V"
    status: Literal["PASS", "FAIL"]
    deviation_found: str   # "Measured 260V on line 3"
    severity_level: int    # 1-5
    recommended_fix: str   # "Install voltage regulator VR-200"
    confidence_score: float # 0.0-1.0
    needs_human_review: bool
    review_reason: str
```

### 2. Semantic Chunking & Vector Search (RAG)

- Documents are chunked semantically and stored in **ChromaDB**
- A local embedding model (`all-MiniLM-L6-v2`) powers retrieval
- Only relevant clauses are sent to the LLM, enabling analysis of 100+ page documents
- `rag/` module with `SemanticRAG` class

### 3. Dynamic Schema & Rule Selection

Multiple inspection profiles with per-profile Pydantic schemas:

| Profile | Use Case | Schema |
|---|---|---|
| `pcb-manufacturing` | IPC-A-610, Gerber specs | `PcbInspectionReport` |
| `iso-compliance` | ISO 9001 §8.6 | `IsoInspectionReport` |
| `commercial-invoice` | Invoice completeness | `InvoiceInspectionReport` |

### 4. Confidence Score & Human-in-the-Loop

- Model self-reports `confidence_score` per check
- `< 85%` -> `needs_human_review = True` -> `data/reviews/REV-XXXXXXXX.json`
- Review queue API: `GET /api/v1/reviews`, `POST /api/v1/reviews/{id}/resolve`

### 5. OpenTelemetry & Structured Tracing (Langfuse)

- Every Ollama call traced with **Langfuse**
- Tracks: prompt tokens, completion tokens, latency, model version
- Full inspection pipeline tracing for observability

### 6. Fallback Strategy & Retry Logic

- 3 retries with JSON repair and temperature decay
- Handles model failures gracefully in production

### 7. Inspection Metrics & Performance Benchmarks

```json
{
  "processing_time_ms": 3421.5,
  "tokens_per_second": 18.3,
  "model_version": "qwen2.5:7b",
  "prompt_tokens": 1240,
  "completion_tokens": 450
}
```

### 8. Audit Logging & Exportable Reports

- Structured JSON audit log: `logs/audit.log`
- PDF Certificate of Inspection via ReportLab

### 9. Deterministic Validation, Bounded Verification, and Feedback

- Report totals and `overall_status` are recomputed from individual checks.
- Commercial invoices use deterministic field and tax arithmetic validation; the LLM cannot override a proven arithmetic result.
- Risky checks receive at most one bounded evidence-verifier pass over the source document.
- Resolving a review ticket preserves the audit record and appends a JSONL preference pair to `data/feedback/preference_pairs.jsonl`.
- Feedback export API: `GET /api/v1/feedback/preferences`.

### 10. Webhooks, Cross-Document Validation, and Async Jobs

- Configurable signed webhooks emit `inspection.completed`, `review.flagged`, `review.resolved`, and `cross_reference.completed` events.
- Set `WEBHOOK_URL` and optional `WEBHOOK_SECRET` to enable delivery.
- `POST /api/v1/cross-reference` accepts exactly two PDFs and returns structured `XRF-###` contradiction findings.
- `POST /api/v1/jobs/inspect` returns HTTP 202 with a `JOB-...` ID; poll `GET /api/v1/jobs/{job_id}` for completion.
- The local queue uses a bounded worker pool so development does not require Redis. The job API is intentionally compatible with a future Celery/Redis worker deployment.
- For a durable worker experiment, install `backend/requirements-celery.txt`, set `JOB_BACKEND=celery`, `CELERY_BROKER_URL=redis://redis:6379/0`, and start the `durable-jobs` Compose profile. Without those prerequisites the application deliberately falls back to threads.

### 11. Traceable Evidence and Secure API Controls

- Each generated check includes bounded RAG evidence citations with a chunk ID, best-effort PDF page, and source quote.
- Uploads are limited to 25 MiB by default, require a PDF signature, and never use an untrusted path as a storage location.
- Set `SPECCHECK_API_KEY` to protect `/api/*`, `RATE_LIMIT_PER_MINUTE` to limit requests, and `CORS_ORIGINS` to allow only known frontends.
- Uploaded documents can be explicitly deleted with `DELETE /api/v1/uploads/{upload_id}` and are cleaned up after `UPLOAD_RETENTION_HOURS`.

### 12. Pluggable Inference Engines and Restricted Validators

Ollama remains the default. OpenAI-compatible servers such as vLLM can be selected without changing the inspection pipeline:

```bash
INFERENCE_PROVIDER=openai-compatible
INFERENCE_BASE_URL=http://127.0.0.1:8001/v1
OLLAMA_MODEL=Qwen/Qwen2.5-7B-Instruct
```

The invoice validator runs in an application-owned restricted subprocess. It does not execute LLM-generated code and is not a replacement for Firecracker/E2B isolation.

### 13. Deterministic Demo Mode

Recruiters can exercise the complete API flow without Ollama, GPU, model downloads, or external services:

```bash
DEMO_MODE=true uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Demo mode uses an in-memory page-aware retriever and deterministic structured reports. It is for demonstrations and smoke tests, not a replacement for local LLM evaluation.

---

## Advanced Reliability Pipeline

```text
PDF extraction
  -> document-scoped RAG
  -> structured local inference
  -> deterministic validators
  -> bounded evidence verification
  -> human review queue
  -> preference-pair feedback ledger
```

---

## Quick Start

### One-Command Setup (Docker)

```bash
git clone https://github.com/robizye0/Local-PDF-Document-Quality-Inspector-RAG-Agent-.git
cd Local-PDF-Document-Quality-Inspector-RAG-Agent-
docker compose up --build
```

Then open:
- Frontend UI: http://localhost:8501
- API Docs: http://localhost:8000/docs
- Ollama: http://localhost:11434
- Langfuse: http://localhost:3000

### Local Development

```bash
# 1. Start Ollama
ollama pull qwen2.5:7b
ollama serve

# 2. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Frontend (new terminal)
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

For a no-model smoke test, use `DEMO_MODE=true` and optionally configure:

```bash
SPECCHECK_API_KEY=[REDACTED]
CORS_ORIGINS=http://localhost:8501
RATE_LIMIT_PER_MINUTE=120
UPLOAD_RETENTION_HOURS=24
```

---

## API Reference

### GET /health
Returns API, Ollama, and RAG stats.

### GET /metrics
Returns process-local request counters and route latency snapshots for local observability.

### API authentication

When `SPECCHECK_API_KEY` is configured, send `X-API-Key` on every `/api/*` request. Health, metrics, and CORS preflight requests remain public. An absent key keeps local development convenient.

### GET /api/v1/profiles
List available inspection profiles.

### POST /api/v1/inspect
Upload PDF + specification + optional profile_id.

**Form data:**
| Field | Type | Description |
|---|---|---|
| file | PDF | The document to audit |
| specification | string | The spec clauses to check against |
| profile_id | string | Optional profile |

**Response (201 Created):**
```json
{
  "report_id": "RPT-A1B2C3D4",
  "document_name": "datasheet_v2.pdf",
  "upload_id": "9f4a2c1d_datasheet_v2.pdf",
  "profile_id": "pcb-manufacturing",
  "summary": { "total_checks": 8, "passed": 5, "failed": 2, "flagged_for_review": 1, "overall_status": "FAIL" },
  "metrics": { "processing_time_ms": 3421.5, "tokens_per_second": 18.3, "model_version": "qwen2.5:7b" },
  "report_path": "/app/data/reports/RPT-A1B2C3D4.json",
  "pdf_path": "/app/data/reports/RPT-A1B2C3D4.pdf",
  "review_tickets": []
}
```

Each report check may also contain:

```json
"evidence_citations": [
  {"chunk_id": "doc_..._3", "page": 4, "quote": "Maximum input voltage: 240V AC"}
]
```

### POST /api/v1/jobs/inspect
Queue an inspection and receive HTTP 202 with a `job_id`.

### GET /api/v1/jobs/{job_id}
Poll queued, running, completed, or failed inspection state.

### POST /api/v1/cross-reference
Upload exactly two PDFs plus a specification for cross-document contradiction analysis.

### GET /api/v1/feedback/preferences
Read the structured preference-pair feedback ledger.

### GET /api/v1/reports/{report_id}
Download JSON report.

### GET /api/v1/reports/{report_id}/pdf
Download PDF certificate.

### DELETE /api/v1/uploads/{upload_id}
Explicitly delete a stored upload. The endpoint rejects path traversal and only deletes direct children of the upload directory.

### GET /api/v1/reviews
List open human-review tickets.

### POST /api/v1/reviews/{ticket_id}/resolve
Resolve a review ticket.

---

## Project Structure

```
speccheck/
├── backend/
│   ├── main.py            # FastAPI server
│   ├── schemas.py         # Pydantic models
│   ├── ollama_client.py   # Ollama logic + retry wrappers + tracing
│   ├── pdf_reader.py      # Text extraction
│   ├── review_queue.py    # HITL ticket store
│   ├── rule_profiles.py   # Dynamic schema/rule selection
│   ├── audit_logger.py    # Structured JSON audit logging
│   ├── report_exporter.py # PDF certificate generation
│   ├── webhooks.py        # Signed event notifications
│   ├── jobs.py            # Async job state + worker pool
│   ├── cross_reference.py # Cross-document aggregation
│   ├── evaluation.py      # CI-safe RAG evaluation metrics
│   ├── citations.py        # Page/chunk evidence citation attachment
│   ├── demo_mode.py        # No-model deterministic demo adapter
│   ├── security.py         # API key and local rate-limit primitives
│   ├── retention.py        # Safe deletion and retention cleanup
│   ├── celery_jobs.py      # Optional Celery/Redis adapter
│   ├── tracing/
│   │   └── langfuse_tracing.py  # Langfuse OpenTelemetry integration
│   ├── rag/
│   │   └── chromadb_rag.py      # Semantic chunking + vector search
│   ├── requirements.txt
│   └── requirements-celery.txt   # Optional Redis/Celery deployment
├── frontend/
│   ├── app.py             # Streamlit UI consuming REST API
│   └── requirements.txt
├── tests/
│   ├── test_schemas.py
│   ├── test_inspector.py
│   └── evals/
│       └── test_evaluation.py   # LLM evaluation tests
├── .github/workflows/ci.yml     # Matrix testing: Python 3.10-3.12
├── docker-compose.yml
├── backend/Dockerfile
├── frontend/Dockerfile
├── docs/
│   └── postman_collection.json
├── data/                  # bind-mounted persistent dirs
├── logs/                  # bind-mounted audit logs
├── .env.example
├── LICENSE
├── SECURITY.md
├── CONTRIBUTING.md
└── README.md
```

---

## CI/CD

GitHub Actions runs on every push:
- **Matrix testing** across Python 3.10, 3.11, 3.12
- **Linting**: flake8, black, isort, mypy
- **Testing**: pytest plus a committed deterministic RAG benchmark gate
- **Security**: dependency and static security scans
- **Docker build**: API + Frontend images

---

## Why This Impresses

| Requirement | Implementation |
|---|---|
| **Microservices** | Separate `backend` (FastAPI) and `frontend` (Streamlit) |
| **Dynamic Schemas** | `rule_profiles.py` + `/api/v1/profiles` + per-profile Pydantic models |
| **RAG** | ChromaDB + sentence-transformers + semantic chunking |
| **Observability** | Langfuse tracing for every LLM call |
| **Retry & Repair** | 3-attempt loop with JSON repair and temperature decay |
| **Metrics** | `InspectionMetrics` with throughput and latency |
| **Audit Logging** | `logs/audit.log` structured JSON per request |
| **PDF Export** | ReportLab `Certificate of Inspection` |
| **Docker Compose** | `api`, `frontend`, `ollama`, `langfuse` — `docker compose up` |
| **CI/CD** | Matrix testing, linting, Docker build on every push |
| **Tests** | 20/20 pytest passing (schemas, retry/repair, profiles, RAG, evals) |
| **README** | Mermaid diagram, badges, problem/solution, Postman collection |

---

## Current Limitations and Production Roadmap

This repository is a verified local portfolio implementation, not a claim of a fully deployed multi-tenant SaaS product.

- The default job manager is an in-memory thread pool; the optional Celery/Redis adapter is the durable deployment path.
- Authentication is an optional API-key layer; production deployments should put it behind an identity provider, TLS, and RBAC.
- Rate limiting and retention cleanup are process-local controls and should be backed by shared infrastructure in a horizontally scaled deployment.
- Langfuse, vLLM, Ragas, DeepEval, and external monitoring are optional integrations rather than required local dependencies.
- Public deployment still requires a threat model, network policy, abuse monitoring, backup/restore testing, and a documented data-retention policy.

The committed CI suite, deterministic evaluation gate, Docker builds, safe-upload tests, webhook reliability tests, and local stress harness provide an auditable engineering baseline without overstating production readiness.

---

## License

MIT
