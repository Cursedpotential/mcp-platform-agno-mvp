"""Optional Langfuse OTLP exporter for Agno's existing OTel provider.

This adds a diagnostic sink only. The durable workflow report and ADR-0047
audit chain remain authoritative and continue working when Langfuse is down.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger(__name__)
_configured = False


def configure_langfuse_exporter() -> bool:
    """Attach one batch OTLP exporter when explicit credentials are present."""
    global _configured
    if _configured:
        return True

    if os.getenv("LANGFUSE_ENABLED", "").lower() not in {"1", "true", "yes"}:
        return False

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    base_url = os.getenv("LANGFUSE_BASE_URL")
    if not (public_key and secret_key and base_url):
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("Langfuse credentials are set but the observability extra is not installed")
        return False

    provider = trace.get_tracer_provider()
    add_processor = getattr(provider, "add_span_processor", None)
    if add_processor is None:
        logger.warning("Langfuse exporter unavailable: active OTel provider cannot accept span processors")
        return False

    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    endpoint = os.getenv(
        "LANGFUSE_OTEL_TRACES_ENDPOINT",
        f"{base_url.rstrip('/')}/api/public/otel/v1/traces",
    )
    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers={
            "Authorization": f"Basic {token}",
            "x-langfuse-ingestion-version": "4",
        },
    )
    add_processor(BatchSpanProcessor(exporter))
    _configured = True
    logger.info("Langfuse OTLP export enabled for %s", endpoint)
    return True
