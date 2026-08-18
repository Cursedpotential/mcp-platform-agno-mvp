"""Production composition root for native evidence vectors (no Agno).

Construction is connection-lazy: PostgreSQL, Weaviate, and the embedding API
are contacted only when an operation runs.  ``close`` owns every resource the
factory creates and is intended for the application lifespan.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy import create_engine

from server.core.evidence_vector_store import (
    EVIDENCE_EMBED_DIM,
    EVIDENCE_EMBED_MODEL,
    EVIDENCE_VECTOR_COLLECTION,
    NativeEvidenceVectorStore,
    validate_evidence_vector_activation,
)
from server.core.url import db_url
from server.evidence.vector_projection import NativeEvidenceProjector

logger = logging.getLogger(__name__)


class NativeEvidenceEmbedder:
    """Lazy OpenAI-compatible embedding callable pinned to the evidence model."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = EVIDENCE_EMBED_MODEL,
        dimensions: int = EVIDENCE_EMBED_DIM,
        client: Any | None = None,
    ) -> None:
        if model != EVIDENCE_EMBED_MODEL or dimensions != EVIDENCE_EMBED_DIM:
            raise ValueError("native evidence embedder model/dimension contract mismatch")
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimensions = dimensions
        self.version = f"{model}@openai-compatible-v1"
        self._client = client

    def __call__(self, content: str) -> Sequence[float]:
        if not content:
            raise ValueError("evidence embedding content must not be empty")
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("native evidence embedder is not configured")
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = self._client.embeddings.create(model=self.model, input=content)
        vector = response.data[0].embedding if response.data else None
        if vector is None or len(vector) != self.dimensions:
            actual = "none" if vector is None else str(len(vector))
            raise RuntimeError(f"native evidence embedder returned {actual} dimensions; expected {self.dimensions}")
        return vector

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()


@dataclass(slots=True)
class NativeEvidenceRuntime:
    """Owned native dependencies shared by ingest, replay, and search."""

    client: Any
    engine: Any
    embedder: NativeEvidenceEmbedder
    store: NativeEvidenceVectorStore
    projector: NativeEvidenceProjector

    def drain(self, *, limit: int = 100) -> Any:
        return self.projector.drain(limit=limit)

    def close(self) -> None:
        self.embedder.close()
        self.client.close()
        self.engine.dispose()


def create_native_evidence_runtime(
    *,
    weaviate_client: Any | None = None,
    engine: Any | None = None,
    embedding_client: Any | None = None,
    worker_id: str | None = None,
    validate_activation: bool = True,
) -> NativeEvidenceRuntime:
    """Build the native runtime, gated by validated collection/alias state."""

    if weaviate_client is None:
        from server.core.session import get_weaviate_client

        weaviate_client = get_weaviate_client()
    if validate_activation:
        validate_evidence_vector_activation(weaviate_client)
    owned_engine = engine or create_engine(db_url, pool_pre_ping=True)
    embedder = NativeEvidenceEmbedder(
        api_key=os.getenv("EMBED_API_KEY") or os.getenv("NVIDIA_API_KEY") or "",
        base_url=os.getenv("EMBED_BASE_URL") or os.getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1",
        model=EVIDENCE_EMBED_MODEL,
        dimensions=EVIDENCE_EMBED_DIM,
        client=embedding_client,
    )
    store = NativeEvidenceVectorStore(weaviate_client)
    writer_store = NativeEvidenceVectorStore(weaviate_client, collection=EVIDENCE_VECTOR_COLLECTION)
    projector = NativeEvidenceProjector(
        owned_engine,
        writer_store,
        embedder,
        embedder_version=embedder.version,
        worker_id=worker_id or f"{socket.gethostname()}:{os.getpid()}",
    )
    return NativeEvidenceRuntime(weaviate_client, owned_engine, embedder, store, projector)


def native_evidence_enabled() -> bool:
    """Return the explicit production cutover gate; absence is fail-closed."""

    return os.getenv("NATIVE_EVIDENCE_ENABLED", "").strip().lower() in {"1", "true", "yes"}


async def run_native_projection_worker(
    runtime: NativeEvidenceRuntime,
    stop: asyncio.Event,
    *,
    batch_limit: int = 100,
    idle_interval_s: float = 5.0,
    error_backoff_s: float = 15.0,
    max_error_backoff_s: float = 60.0,
) -> None:
    """Drain crash-persisted jobs immediately, then poll with bounded work."""

    if batch_limit < 1 or idle_interval_s <= 0 or error_backoff_s <= 0 or max_error_backoff_s < error_backoff_s:
        raise ValueError("native projection worker limits/backoffs must be positive")
    consecutive_failures = 0
    while not stop.is_set():
        delay = idle_interval_s
        try:
            result = await asyncio.to_thread(runtime.drain, limit=batch_limit)
            if result.failed:
                consecutive_failures += 1
                logger.error(
                    "native evidence projection batch completed with failures: claimed=%s failed=%s",
                    result.claimed,
                    result.failed,
                )
                delay = min(error_backoff_s * (2 ** (consecutive_failures - 1)), max_error_backoff_s)
            elif result.claimed:
                consecutive_failures = 0
                logger.info(
                    "native evidence projection drained claimed=%s completed=%s deactivated=%s",
                    result.claimed,
                    result.completed,
                    result.deactivated,
                )
                continue
            else:
                consecutive_failures = 0
        except asyncio.CancelledError:
            raise
        except Exception:
            consecutive_failures += 1
            logger.exception("native evidence projection worker failed; retrying after backoff")
            delay = min(error_backoff_s * (2 ** (consecutive_failures - 1)), max_error_backoff_s)
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            pass
