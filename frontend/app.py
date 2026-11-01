"""
SpecCheck Frontend — Streamlit UI consuming the FastAPI backend.
"""

from __future__ import annotations

import io
import os
from datetime import datetime

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="SpecCheck — PDF Compliance Checker",
    page_icon="🔍",
    layout="wide",
)

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    .metric-card {background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:1rem;}
    .badge-pass {background:#d4edda;color:#155724;padding:4px 8px;border-radius:4px;font-size:12px;font-weight:700;}
    .badge-fail {background:#f8d7da;color:#721c24;padding:4px 8px;border-radius:4px;font-size:12px;font-weight:700;}
    .badge-review {background:#fff3cd;color:#856404;padding:4px 8px;border-radius:4px;font-size:12px;font-weight:700;}
</style>
""",
    unsafe_allow_html=True,
)

st.title("🔍 SpecCheck")
st.caption("PDF Specification Compliance Checker — AI-powered audit with Pydantic validation")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙ Settings")
    api_url = st.text_input("API URL", value=API_URL)
    try:
        health = requests.get(f"{api_url}/health", timeout=5).json()
        if health.get("status") == "ok":
            st.success(f"✅ API connected\nModel: {health.get('model')}")
        else:
            st.warning("⚠ API reachable but model not loaded")
    except Exception:
        st.error("❌ Cannot reach API. Is `docker compose up` running?")

    st.divider()
    st.header("📋 Inspection Profile")
    try:
        profiles = requests.get(f"{api_url}/api/v1/profiles", timeout=5).json()
        profile_options = {p["name"]: p["profile_id"] for p in profiles}
        selected_name = st.selectbox("Select profile", list(profile_options.keys()))
        profile_id = profile_options[selected_name]
        st.caption(f"Profile ID: `{profile_id}`")
    except Exception:
        profile_id = None
        st.caption("Could not load profiles. Using default schema.")

# ── Main UI ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. Upload PDF")
    uploaded_file = st.file_uploader("Drop a technical PDF here", type=["pdf"])
    if uploaded_file:
        st.success(f"📎 {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

with col2:
    st.header("2. Specification")
    specification = st.text_area(
        "Specification to check against",
        value="ISO 9001 §8.6 — All inspection reports must include deviation details, severity levels (1-5), and recommended fixes.",
        height=120,
    )

run_btn = st.button("▶ Run Compliance Check", type="primary", use_container_width=True)

# ── Results ──────────────────────────────────────────────────────────────────
if run_btn and uploaded_file:
    with st.spinner("Running compliance check via Ollama…"):
        files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
        data = {
            "specification": specification,
            "profile_id": profile_id or "",
        }
        try:
            resp = requests.post(
                f"{api_url}/api/v1/inspect",
                files=files,
                data=data,
                timeout=180,
            )
            resp.raise_for_status()
            result = resp.json()
            st.session_state["last_result"] = result
        except requests.exceptions.RequestException as exc:
            st.error(f"Request failed: {exc}")
            st.stop()

    result = st.session_state["last_result"]
    summary = result["summary"]
    metrics = result.get("metrics")

    # KPI row
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Checks", summary["total_checks"])
    k2.metric("Passed", summary["passed"], delta_color="normal")
    k3.metric("Failed", summary["failed"], delta_color="inverse")
    k4.metric("Flagged", summary["flagged_for_review"], delta_color="off")
    k5.metric("Overall", summary["overall_status"])

    # System Performance panel
    if metrics:
        with st.expander("📊 System Performance", expanded=False):
            perf_cols = st.columns(4)
            perf_cols[0].metric("Processing Time", f"{metrics.get('processing_time_ms', 0):.0f} ms")
            perf_cols[1].metric("Throughput", f"{metrics.get('tokens_per_second') or '—'} tok/s")
            perf_cols[2].metric("Model", metrics.get("model_version", "—"))
            total_tokens = (metrics.get("prompt_tokens") or 0) + (metrics.get("completion_tokens") or 0)
            perf_cols[3].metric("Total Tokens", total_tokens)

    # Check details table
    st.subheader("Check Details")
    try:
        report_data = requests.get(f"{api_url}/api/v1/reports/{result['report_id']}", timeout=10).json()
        checks = report_data.get("checks", [])
        for check in checks:
            status_class = "badge-pass" if check["status"] == "PASS" else "badge-fail"
            review_badge = '<span class="badge-review">⚠ Review</span>' if check.get("needs_human_review") else ""
            with st.expander(
                f"{check['check_id']} — {check['clause_reference']} "
                f"<span class='{status_class}'>{check['status']}</span> {review_badge}",
                expanded=False,
            ):
                st.write(f"**Requirement:** {check['requirement']}")
                st.write(f"**Severity:** {check['severity_level']}/5")
                st.write(f"**Confidence:** {check['confidence_score']:.0%}")
                if check.get("deviation_found"):
                    st.error(f"**Deviation:** {check['deviation_found']}")
                if check.get("recommended_fix"):
                    st.info(f"**Fix:** {check['recommended_fix']}")
    except Exception as exc:
        st.warning(f"Could not load check details: {exc}")

    # Download buttons
    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "📥 Download JSON Report",
            data=open(result["report_path"], "rb").read() if os.path.exists(result["report_path"]) else b"{}",
            file_name=f"{result['report_id']}.json",
            mime="application/json",
        )
    with dl_col2:
        if result.get("pdf_path") and os.path.exists(result["pdf_path"]):
            st.download_button(
                "📄 Download PDF Certificate",
                data=open(result["pdf_path"], "rb").read(),
                file_name=f"{result['report_id']}.pdf",
                mime="application/pdf",
            )

# ── Review Queue ─────────────────────────────────────────────────────────────
with st.expander("⚠ Human Review Queue", expanded=False):
    try:
        reviews = requests.get(f"{api_url}/api/v1/reviews", timeout=10).json()
        if not reviews:
            st.caption("No open review tickets.")
        for ticket in reviews:
            st.warning(f"**{ticket['ticket_id']}** — {ticket['document_name']}")
            st.caption(ticket["reason"])
            st.json(ticket["check"])
    except Exception as exc:
        st.caption(f"Could not load review queue: {exc}")

# ── Audit Log Viewer ─────────────────────────────────────────────────────────
with st.expander("📜 Audit Log (last 20 entries)", expanded=False):
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "audit.log"))
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]
        for line in lines:
            try:
                entry = __import__("json").loads(line)
                st.json(entry)
            except Exception:
                st.text(line.strip())
    else:
        st.caption("No audit log found.")
