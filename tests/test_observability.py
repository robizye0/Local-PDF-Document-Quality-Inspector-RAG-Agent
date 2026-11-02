from backend.observability import RequestMetrics, new_request_id


def test_request_ids_are_prefixed_and_metrics_are_snapshotable():
    request_id = new_request_id()
    metrics = RequestMetrics()
    metrics.record("GET", "/health", 200, 12.5)

    snapshot = metrics.snapshot()
    assert request_id.startswith("REQ-")
    assert snapshot["requests_total"] == 1
    assert snapshot["routes"]["GET /health"]["count"] == 1
    assert snapshot["routes"]["GET /health"]["last_status"] == 200
