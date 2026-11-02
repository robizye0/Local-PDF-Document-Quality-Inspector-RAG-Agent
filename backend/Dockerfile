# ─── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update -qq && apt-get install -y --no-install-recommends     build-essential     && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# ─── Runtime stage ───────────────────────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update -qq && apt-get install -y --no-install-recommends     poppler-utils     && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app

COPY backend/ backend/
RUN mkdir -p /app/data /app/logs

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1
ENV OLLAMA_URL=http://ollama:11434

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s     CMD python -c "import requests; r=requests.get('http://localhost:8000/health',timeout=5); exit(0 if r.status_code==200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
