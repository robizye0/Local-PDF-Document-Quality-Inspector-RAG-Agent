"""
Langfuse tracing integration for SpecCheck.
Wraps Ollama calls, PDF extraction, and inspection pipeline with distributed tracing.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable

try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None
logger = logging.getLogger(__name__)

# Initialize Langfuse client
# Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env
try:
    langfuse_client = Langfuse()
    LANGFUSE_ENABLED = True
except Exception as exc:
    logger.warning("Langfuse initialization failed: %s", exc)
    langfuse_client = None
    LANGFUSE_ENABLED = False


def trace_ollama_call(operation_name: str = "ollama.generate"):
    """
    Decorator to trace Ollama API calls with Langfuse.
    Records: prompt tokens, completion tokens, latency, model version.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not LANGFUSE_ENABLED or langfuse_client is None:
                return func(*args, **kwargs)

            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000

                # Extract metrics from result tuple (report, error, metrics)
                report, error, metrics = result if isinstance(result, tuple) else (result, None, None)

                # Create trace span
                span = langfuse_client.span(
                    name=operation_name,
                    input={
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                    metadata={
                        "model": kwargs.get("model", "unknown"),
                        "temperature": kwargs.get("temperature", 0.1),
                    },
                )

                if error:
                    span.end(
                        output={"error": str(error)},
                        metadata={"status": "error", "latency_ms": round(elapsed_ms, 2)},
                        level="ERROR",
                    )
                else:
                    output_data = {
                        "status": "success",
                        "latency_ms": round(elapsed_ms, 2),
                    }
                    if metrics:
                        output_data.update({
                            "prompt_tokens": metrics.prompt_tokens,
                            "completion_tokens": metrics.completion_tokens,
                            "tokens_per_second": metrics.tokens_per_second,
                            "model_version": metrics.model_version,
                        })
                    span.end(output=output_data)

                langfuse_client.flush()
                return result

            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                if LANGFUSE_ENABLED and langfuse_client is not None:
                    span = langfuse_client.span(
                        name=f"{operation_name}.error",
                        metadata={"status": "exception", "latency_ms": round(elapsed_ms, 2)},
                        level="ERROR",
                    )
                    span.end(output={"error": str(exc)})
                    langfuse_client.flush()
                raise

        return wrapper
    return decorator


def trace_inspection_pipeline(document_name: str, profile_id: str | None = None):
    """
    Create a Langfuse trace for the full inspection pipeline.
    Call this at the start of an inspection request.
    """
    if not LANGFUSE_ENABLED or langfuse_client is None:
        return None

    trace = langfuse_client.trace(
        name="inspection.pipeline",
        input={
            "document_name": document_name,
            "profile_id": profile_id,
        },
        tags=["inspection", "compliance"],
        metadata={
            "service": "speccheck-backend",
            "component": "fastapi",
        },
    )
    return trace


def trace_pdf_extraction(file_path: str, pages: int, chars_extracted: int):
    """Log PDF extraction metrics to Langfuse."""
    if not LANGFUSE_ENABLED or langfuse_client is None:
        return

    span = langfuse_client.span(
        name="pdf.extraction",
        input={"file_path": file_path},
        output={
            "pages": pages,
            "chars_extracted": chars_extracted,
        },
    )
    langfuse_client.flush()


def trace_review_routing(ticket_count: int, confidence_threshold: float):
    """Log HITL review routing metrics."""
    if not LANGFUSE_ENABLED or langfuse_client is None:
        return

    span = langfuse_client.span(
        name="review.routing",
        output={
            "tickets_created": ticket_count,
            "confidence_threshold": confidence_threshold,
        },
        tags=["human-in-the-loop"],
    )
    langfuse_client.flush()
