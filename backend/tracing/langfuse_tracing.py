"""
Langfuse tracing integration for SpecCheck.
Wraps Ollama calls, PDF extraction, and inspection pipeline with distributed tracing.
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable

Langfuse: Any = None
try:
    from langfuse import Langfuse as _Langfuse

    Langfuse = _Langfuse
except ImportError:
    Langfuse = None

logger = logging.getLogger(__name__)

# Initialize Langfuse client
# Reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env
langfuse_client: Any = None
LANGFUSE_ENABLED = False

if Langfuse is not None:
    try:
        langfuse_client = Langfuse()
        # Verify the client has the required methods
        if hasattr(langfuse_client, "start_observation"):
            LANGFUSE_ENABLED = True
        else:
            logger.warning(
                "Langfuse client missing start_observation; tracing disabled."
            )
    except Exception as exc:
        logger.warning("Langfuse initialization failed: %s", exc)


def _get_observation(name: str, as_type: str = "span", **kwargs):
    """Create a Langfuse observation (span/trace) if enabled."""
    if not LANGFUSE_ENABLED or langfuse_client is None:
        return None
    try:
        # Langfuse v3+ removed the top-level ``tags`` argument from
        # ``start_observation``. Preserve tags as metadata so tracing works
        # across the supported client versions instead of failing silently.
        tags = kwargs.pop("tags", None)
        if tags:
            metadata = kwargs.get("metadata")
            if isinstance(metadata, dict):
                kwargs["metadata"] = {**metadata, "tags": tags}
            else:
                kwargs["metadata"] = {"tags": tags}
        return langfuse_client.start_observation(name=name, as_type=as_type, **kwargs)
    except Exception as exc:
        logger.warning("Langfuse observation creation failed: %s", exc)
        return None


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
                report, error, metrics = (
                    result if isinstance(result, tuple) else (result, None, None)
                )

                # Create trace span
                span = _get_observation(
                    name=operation_name,
                    as_type="span",
                    input={
                        "args_count": len(args),
                        "kwargs_keys": list(kwargs.keys()),
                    },
                    metadata={
                        "model": kwargs.get("model", "unknown"),
                        "temperature": kwargs.get("temperature", 0.1),
                    },
                )

                if span is None:
                    return result

                if error:
                    span.update(
                        output={"error": str(error)},
                        metadata={
                            "status": "error",
                            "latency_ms": round(elapsed_ms, 2),
                        },
                        level="ERROR",
                    )
                else:
                    output_data = {
                        "status": "success",
                        "latency_ms": round(elapsed_ms, 2),
                    }
                    if metrics:
                        output_data.update(
                            {
                                "prompt_tokens": metrics.prompt_tokens,
                                "completion_tokens": metrics.completion_tokens,
                                "tokens_per_second": metrics.tokens_per_second,
                                "model_version": metrics.model_version,
                            }
                        )
                    span.update(output=output_data)

                span.end()
                langfuse_client.flush()
                return result

            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start) * 1000
                span = _get_observation(
                    name=f"{operation_name}.error",
                    as_type="span",
                    metadata={
                        "status": "exception",
                        "latency_ms": round(elapsed_ms, 2),
                    },
                    level="ERROR",
                )
                if span is not None:
                    span.update(output={"error": str(exc)})
                    span.end()
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

    trace = _get_observation(
        name="inspection.pipeline",
        as_type="trace",
        input={
            "document_name": document_name,
            "profile_id": profile_id,
        },
        metadata={
            "service": "speccheck-backend",
            "component": "fastapi",
        },
        tags=["inspection", "compliance"],
    )
    return trace


def trace_pdf_extraction(file_path: str, pages: int, chars_extracted: int):
    """Log PDF extraction metrics to Langfuse."""
    if not LANGFUSE_ENABLED or langfuse_client is None:
        return

    span = _get_observation(
        name="pdf.extraction",
        as_type="span",
        input={"file_path": file_path},
        output={
            "pages": pages,
            "chars_extracted": chars_extracted,
        },
    )
    if span is not None:
        span.end()
        langfuse_client.flush()


def trace_review_routing(ticket_count: int, confidence_threshold: float):
    """Log HITL review routing metrics."""
    if not LANGFUSE_ENABLED or langfuse_client is None:
        return

    span = _get_observation(
        name="review.routing",
        as_type="span",
        output={
            "tickets_created": ticket_count,
            "confidence_threshold": confidence_threshold,
        },
        tags=["human-in-the-loop"],
    )
    if span is not None:
        span.end()
        langfuse_client.flush()
