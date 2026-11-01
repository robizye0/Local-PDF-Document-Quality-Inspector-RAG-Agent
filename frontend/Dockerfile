FROM python:3.12-slim

RUN apt-get update -qq && apt-get install -y --no-install-recommends     build-essential     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend/ .

EXPOSE 8501

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s     CMD python -c "import requests; r=requests.get('http://localhost:8501/_stcore/health',timeout=5); exit(0 if r.status_code==200 else 1)"

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
