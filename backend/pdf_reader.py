"""
PDF text extraction layer.
Supports PyMuPDF (fitz) and pdfminer as fallback.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: str | Path, max_chars: int = 20_000) -> str:
    """
    Extract plain text from a PDF file.

    Tries PyMuPDF first (fitz), then pdfminer.six, then pdftotext.
    Returns up to `max_chars` characters.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    # Try PyMuPDF (fast, reliable)
    try:
        import fitz  # type: ignore[import-untyped]

        doc = fitz.open(path)
        pages = [page.get_text() for page in doc]
        doc.close()
        text = "\n".join(pages)
        logger.info("Extracted %d chars with PyMuPDF (%d pages)", len(text), len(pages))
        return text[:max_chars]
    except ImportError:
        logger.debug("PyMuPDF not installed, trying pdfminer")
    except Exception as exc:
        logger.warning("PyMuPDF failed: %s", exc)

    # Try pdfminer.six
    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-untyped]

        text = extract_text(str(path)) or ""
        logger.info("Extracted %d chars with pdfminer", len(text))
        return text[:max_chars]
    except ImportError:
        logger.debug("pdfminer not installed, trying pdftotext")
    except Exception as exc:
        logger.warning("pdfminer failed: %s", exc)

    # Try pdftotext (poppler)
    try:
        import subprocess

        result = subprocess.run(
            ["pdftotext", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        text = result.stdout
        logger.info("Extracted %d chars with pdftotext", len(text))
        return text[:max_chars]
    except FileNotFoundError:
        logger.error("No PDF extraction backend available")
        raise RuntimeError(
            "Install at least one of: PyMuPDF, pdfminer.six, or poppler utils."
        )
    except Exception as exc:
        logger.error("pdftotext failed: %s", exc)
        raise RuntimeError(f"PDF extraction failed: {exc}")
