"""server/core/knowledge_vectordb.py — fail loudly on a dead embedder.

THE BUG (measured live 2026-08-01): the AgentOS Knowledge panel showed content
rows reporting ``COMPLETED`` with ZERO vectors written. Root cause, traced
through agno 2.8.0's actual source (not assumed):

1. ``agno.knowledge.embedder.openai.OpenAIEmbedder.get_embedding_and_usage()``
   (and its async twin) catch ANY exception from the embeddings call — a dead
   API key, 402 out-of-credits, a 400 "model does not exist", a gateway
   outage — log a warning, and return ``(None, None)``. They never raise.
2. ``agno.knowledge.document.base.Document.embed()``/``async_embed()`` then
   just set ``self.embedding = None``. No exception either.
3. ``agno.vectordb.weaviate.Weaviate.insert()``/``async_insert()`` check
   ``if document.embedding is None: log_error(...); continue`` — they SKIP
   the document and keep going. Still no exception.
4. Control returns normally to ``agno.knowledge.Knowledge._handle_vector_db_insert``/
   ``_ahandle_vector_db_insert``, which only catches an exception FROM the
   vector-db call — since none was raised, it unconditionally sets
   ``content.status = ContentStatus.COMPLETED``.

Net effect: an embedding-provider outage is completely invisible at the
content-row level. This was VERIFIED as the live cause on 2026-08-01: the
platform's embed lane defaulted to OpenRouter for the text embedder
(``nvidia/nv-embed-v1``), which OpenRouter does not host (400 "Model
nvidia/nv-embed-v1 does not exist") — see the accompanying fix in
``server/core/session.py`` for the provider-routing half of this bug.

THE FIX (this module): ``VerifiedWeaviate`` wraps ``insert``/``async_insert``
(which ``agno.vectordb.weaviate.Weaviate.upsert``/``async_upsert`` delegate to
internally via ``self.insert``/``self.async_insert``, so overriding just these
two covers all four insert/upsert paths) and checks, AFTER the base
implementation returns, whether at least one document in the batch actually
got a vector. If EVERY document in the batch has ``embedding is None``, it
raises ``EmbeddingFailedError`` instead of returning normally. That exception
propagates straight into agno's own ``_handle_vector_db_insert``/
``_ahandle_vector_db_insert`` exception handler — the SAME code path that
already correctly marks content ``FAILED`` with a status message today. No
agno internals are patched; this only adds a post-condition check on top of
the public ``Weaviate`` API.

A PARTIAL failure (some but not all documents embedded) is not raised as an
error — agno's chunk-level retry story doesn't exist, so failing the whole
content row for a partial success would throw away real, usable vectors. It
is logged loudly instead so an operator can see the partial-embed rate.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from agno.vectordb.weaviate import Weaviate

if TYPE_CHECKING:
    from agno.knowledge.document import Document

logger = logging.getLogger("evidence.knowledge")


class EmbeddingFailedError(RuntimeError):
    """Raised when the embedder returned no vector for ANY document in an
    insert/upsert batch — a dead or misconfigured provider, not a partial or
    transient per-document hiccup. Deliberately a plain ``RuntimeError``
    subclass (not a custom exception hierarchy) so agno's existing
    ``except Exception`` handlers in ``Knowledge._handle_vector_db_insert``/
    ``_ahandle_vector_db_insert`` catch it with zero changes on their side.
    """


def _verify_embedded(documents: "List[Document]") -> None:
    """Raise ``EmbeddingFailedError`` iff NONE of ``documents`` got a vector."""
    if not documents:
        return
    embedded = sum(1 for d in documents if d.embedding is not None)
    if embedded == 0:
        raise EmbeddingFailedError(
            f"Embedder returned no vector for any of {len(documents)} document(s) in "
            "this batch — the embedding provider is dead or misconfigured (bad/expired "
            "key, out of credits, wrong model id for the configured base_url, or a "
            "gateway outage). No vectors were written to the store; this content will "
            "be marked FAILED instead of silently reporting COMPLETED with zero vectors."
        )
    if embedded < len(documents):
        logger.warning(
            "VerifiedWeaviate: only %s/%s document(s) in this batch got a vector — "
            "%s document(s) were silently skipped by the embedder. Partial content "
            "was written; the content row will still report COMPLETED.",
            embedded,
            len(documents),
            len(documents) - embedded,
        )


class VerifiedWeaviate(Weaviate):
    """``agno.vectordb.weaviate.Weaviate`` that fails loudly on a fully dead
    embedder instead of the upstream silent-skip-then-COMPLETED behavior.

    Only ``insert``/``async_insert`` need overriding: agno's own
    ``Weaviate.upsert``/``Weaviate.async_upsert`` call ``self.insert``/
    ``self.async_insert`` internally, so Python method resolution routes them
    through these overrides too — every insert/upsert path is covered.
    """

    def insert(
        self,
        content_hash: str,
        documents: "List[Document]",
        filters: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().insert(content_hash, documents, filters=filters)
        _verify_embedded(documents)

    async def async_insert(
        self,
        content_hash: str,
        documents: "List[Document]",
        filters: Optional[Dict[str, Any]] = None,
    ) -> None:
        await super().async_insert(content_hash, documents, filters=filters)
        _verify_embedded(documents)
