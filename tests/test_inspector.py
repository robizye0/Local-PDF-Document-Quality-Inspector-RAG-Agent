"""
Tests for inspector logic — retry, JSON repair, metrics, rule profiles.
"""

from __future__ import annotations

import json
import sys
import os

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest

from ollama_client import _repair_json, InspectionMetrics
from rule_profiles import get_profile, list_profiles, get_report_schema, BUILTIN_PROFILES


def test_repair_json_strips_fences():
    raw = "```json\n{ \"key\": \"value\" }\n```"
    fixed = _repair_json(raw)
    assert fixed.startswith("{")
    assert fixed.endswith("}")


def test_repair_json_removes_trailing_comma():
    raw = '{ "a": 1, "b": [2, 3,], }'
    fixed = _repair_json(raw)
    assert "]," not in fixed
    assert ",}" not in fixed


def test_repair_json_noop_on_clean():
    raw = '{"a": 1}'
    assert _repair_json(raw) == raw


def test_inspection_metrics_defaults():
    m = InspectionMetrics(processing_time_ms=123.4, model_version="test-model")
    assert m.processing_time_ms == 123.4
    assert m.tokens_per_second is None
    assert m.model_version == "test-model"


def test_list_profiles_returns_nonempty():
    profiles = list_profiles()
    assert len(profiles) >= 3
    ids = [p["profile_id"] for p in profiles]
    assert "pcb-manufacturing" in ids
    assert "iso-compliance" in ids
    assert "commercial-invoice" in ids


def test_get_profile_valid():
    p = get_profile("iso-compliance")
    assert p.name == "ISO Compliance"
    assert "ISO 9001" in p.system_prompt


def test_get_profile_invalid():
    with pytest.raises(ValueError):
        get_profile("nonexistent-profile")


def test_get_report_schema_mapping():
    schema = get_report_schema("pcb-manufacturing")
    assert schema.__name__ == "PcbInspectionReport"


def test_builtin_profiles_complete():
    expected = {"pcb-manufacturing", "iso-compliance", "commercial-invoice"}
    assert set(BUILTIN_PROFILES.keys()) == expected
