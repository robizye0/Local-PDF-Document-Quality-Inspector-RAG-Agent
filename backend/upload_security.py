"""Validation and normalization helpers for uploaded PDF documents."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))
PDF_MAGIC = b"%PDF-"


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    content: bytes


def _safe_basename(filename: str | None) -> str:
    if not filename:
        raise ValueError("PDF filename is required.")
    # Normalize both URL-style and Windows path separators before taking the
    # basename because multipart clients can submit either representation.
    normalized = filename.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1].strip()
    if not basename or basename in {".", ".."}:
        raise ValueError("PDF filename is required.")
    basename = re.sub(r"[^A-Za-z0-9._ -]", "_", basename)
    if not basename.lower().endswith(".pdf"):
        raise ValueError("Only PDF filenames are accepted.")
    return basename[:180]


def validate_pdf_upload(filename: str | None, content: bytes) -> ValidatedUpload:
    """Validate a bounded PDF payload and return a path-safe filename."""
    safe_name = _safe_basename(filename)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"PDF upload is too large; maximum size is {MAX_UPLOAD_BYTES} bytes."
        )
    if not content.startswith(PDF_MAGIC):
        raise ValueError("Upload is not a valid PDF (missing PDF signature).")
    return ValidatedUpload(filename=safe_name, content=content)
