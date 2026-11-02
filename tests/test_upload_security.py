import pytest

from backend.upload_security import MAX_UPLOAD_BYTES, validate_pdf_upload


def test_pdf_filename_is_reduced_to_safe_basename():
    result = validate_pdf_upload("../../private/report.pdf", b"%PDF-1.7\nvalid")

    assert result.filename == "report.pdf"
    assert result.content == b"%PDF-1.7\nvalid"


def test_non_pdf_content_is_rejected_even_with_pdf_extension():
    with pytest.raises(ValueError, match="valid PDF"):
        validate_pdf_upload("report.pdf", b"not really a pdf")


def test_oversized_upload_is_rejected():
    with pytest.raises(ValueError, match="too large"):
        validate_pdf_upload("report.pdf", b"%PDF-" + b"x" * MAX_UPLOAD_BYTES)


def test_missing_or_invalid_filename_is_rejected():
    with pytest.raises(ValueError, match="PDF filename"):
        validate_pdf_upload("report.txt", b"%PDF-1.7")
