from backend.demo_mode import DemoInference, DemoRAG


def test_demo_inference_is_local_and_structured():
    rag = DemoRAG()
    rag.index_document("doc-1", "Invoice number INV-1\fAmount: 100 EUR")
    chunks = rag.retrieve("invoice amount", doc_id="doc-1")
    report, error, metrics = DemoInference().run_compliance_check(
        chunks[0]["text"], "Check invoice amount", None
    )

    assert error is None
    assert metrics is not None
    assert report.overall_status == "PASS"
    assert chunks[0]["metadata"]["page_number"] == 1
