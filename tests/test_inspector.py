"""
Tests for inspector logic — retry, JSON repair, metrics, rule profiles.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")

def _load(name, filename):
    import sys
    if _BACKEND_DIR not in sys.path:
        sys.path.insert(0, _BACKEND_DIR)
    spec = importlib.util.spec_from_file_location(name, os.path.join(_BACKEND_DIR, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ollama_client = _load("ollama_client", "ollama_client.py")
rule_profiles = _load("rule_profiles", "rule_profiles.py")

_repair_json = ollama_client._repair_json
InspectionMetrics = ollama_client.InspectionMetrics
get_profile = rule_profiles.get_profile
list_profiles = rule_profiles.list_profiles
get_report_schema = rule_profiles.get_report_schema
BUILTIN_PROFILES = rule_profiles.BUILTIN_PROFILES


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


def test_repair_json_normalizes_model_status_synonyms():
    raw = '{"status": "FAILED", "overall_status": "PASSED"}'
    fixed = _repair_json(raw)
    assert '"status": "FAIL"' in fixed
    assert '"overall_status": "PASS"' in fixed


def test_repair_json_noop_on_clean():
    raw = '{"a": 1}'
    assert _repair_json(raw) == raw


def test_retrieve_can_scope_to_document():
    rag_mod = _load("rag_chromadb_scope", os.path.join("rag", "chromadb_rag.py"))

    class FakeEmbeddingModel:
        class Encoded:
            def tolist(self):
                return [[0.1]]

        def encode(self, values):
            return self.Encoded()

    class FakeCollection:
        def __init__(self):
            self.query_kwargs = None

        def query(self, **kwargs):
            self.query_kwargs = kwargs
            return {
                "documents": [["current document chunk"]],
                "metadatas": [[{"doc_id": "current-doc"}]],
                "distances": [[0.1]],
            }

    rag = rag_mod.SemanticRAG.__new__(rag_mod.SemanticRAG)
    rag.embedding_model = FakeEmbeddingModel()
    rag.collection = FakeCollection()

    results = rag.retrieve("invoice totals", top_k=1, doc_id="current-doc")

    assert results[0]["metadata"]["doc_id"] == "current-doc"
    assert rag.collection.query_kwargs["where"] == {"doc_id": "current-doc"}


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
