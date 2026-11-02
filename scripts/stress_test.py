#!/usr/bin/env python3
"""Repeatable local load smoke test for the SpecCheck API."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time

import requests


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "test_pdfs" / "05_valid_invoice.pdf"
CROSS_FIXTURE = ROOT / "data" / "test_pdfs" / "02_freshbooks_invoice.pdf"


def _health(base_url: str, headers: dict[str, str]) -> int:
    return requests.get(f"{base_url}/health", headers=headers, timeout=15).status_code


def _sync_inspection(base_url: str, headers: dict[str, str]) -> int:
    with FIXTURE.open("rb") as handle:
        response = requests.post(
            f"{base_url}/api/v1/inspect",
            files={"file": (FIXTURE.name, handle, "application/pdf")},
            data={"specification": "Invoice must contain a total amount."},
            headers=headers,
            timeout=180,
        )
    if response.status_code != 201:
        raise RuntimeError(f"sync inspection failed: {response.status_code} {response.text[:200]}")
    return response.json()["summary"]["passed"]


def _async_inspection(base_url: str, headers: dict[str, str]) -> str:
    with FIXTURE.open("rb") as handle:
        response = requests.post(
            f"{base_url}/api/v1/jobs/inspect",
            files={"file": (FIXTURE.name, handle, "application/pdf")},
            data={"specification": "Invoice must contain a total amount."},
            headers=headers,
            timeout=30,
        )
    if response.status_code != 202:
        raise RuntimeError(f"async submission failed: {response.status_code} {response.text[:200]}")
    return response.json()["job_id"]


def _poll(base_url: str, headers: dict[str, str], job_id: str) -> dict:
    deadline = time.time() + 240
    while time.time() < deadline:
        response = requests.get(f"{base_url}/api/v1/jobs/{job_id}", headers=headers, timeout=15)
        response.raise_for_status()
        record = response.json()
        if record["status"] in {"completed", "failed"}:
            return record
        time.sleep(1)
    raise TimeoutError(f"job did not finish: {job_id}")


def _cross_reference(base_url: str, headers: dict[str, str]) -> int:
    with FIXTURE.open("rb") as first, CROSS_FIXTURE.open("rb") as second:
        response = requests.post(
            f"{base_url}/api/v1/cross-reference",
            files=[
                ("files", (FIXTURE.name, first, "application/pdf")),
                ("files", (CROSS_FIXTURE.name, second, "application/pdf")),
            ],
            data={"specification": "Amounts and invoice identifiers should be consistent."},
            headers=headers,
            timeout=180,
        )
    if response.status_code != 201:
        raise RuntimeError(f"cross-reference failed: {response.status_code} {response.text[:200]}")
    return len(response.json()["report"]["findings"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--health-requests", type=int, default=20)
    parser.add_argument("--sync-workers", type=int, default=2)
    parser.add_argument("--async-jobs", type=int, default=2)
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()
    headers = {"X-API-Key": args.api_key} if args.api_key else {}

    with ThreadPoolExecutor(max_workers=max(args.health_requests, args.sync_workers)) as pool:
        health = list(pool.map(lambda _: _health(args.base_url, headers), range(args.health_requests)))
        sync = list(pool.map(lambda _: _sync_inspection(args.base_url, headers), range(args.sync_workers)))
    job_ids = [_async_inspection(args.base_url, headers) for _ in range(args.async_jobs)]
    jobs = [_poll(args.base_url, headers, job_id) for job_id in job_ids]
    findings = _cross_reference(args.base_url, headers)
    result = {
        "health_ok": sum(status == 200 for status in health),
        "health_total": len(health),
        "sync_passed": len(sync),
        "sync_total": len(sync),
        "async_completed": sum(job["status"] == "completed" for job in jobs),
        "async_total": len(jobs),
        "cross_reference_findings": findings,
    }
    print(json.dumps(result, indent=2))
    return 0 if (
        result["health_ok"] == result["health_total"]
        and result["sync_passed"] == result["sync_total"]
        and result["async_completed"] == result["async_total"]
        and findings > 0
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
