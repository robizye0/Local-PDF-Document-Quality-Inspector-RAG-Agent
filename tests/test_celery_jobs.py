from backend.celery_jobs import decode_payload, encode_payload


def test_celery_payload_round_trip_preserves_binary_uploads():
    payload = {"filename": "invoice.pdf", "content": b"%PDF-1.7", "nested": [b"x"]}

    assert decode_payload(encode_payload(payload)) == payload
