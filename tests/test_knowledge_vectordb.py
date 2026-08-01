"""Unit tests for server/core/knowledge_vectordb.py — VerifiedWeaviate.

Regression coverage for the "COMPLETED with zero vectors" bug (measured live
2026-08-01): agno's own Weaviate.insert()/async_insert() silently skip any
document whose embedding is None and return normally, so a dead embedder
never raises — agno.knowledge.Knowledge then unconditionally marks the
content row COMPLETED even though nothing was written to the vector store.

These tests never touch a real Weaviate server or a real embedder: the base
``agno.vectordb.weaviate.Weaviate.insert``/``async_insert`` methods are
monkeypatched to simulate "the embedder already ran and left these documents'
``.embedding`` at whatever the test set" — exactly the post-condition
``VerifiedWeaviate`` checks.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import asyncio

import pytest
from agno.knowledge.document import Document
from agno.vectordb.weaviate import Weaviate

from server.core.knowledge_vectordb import EmbeddingFailedError, VerifiedWeaviate, _verify_embedded


def _make_docs(*embeddings: "list[float] | None") -> list[Document]:
    return [Document(content=f"doc {i}", embedding=emb) for i, emb in enumerate(embeddings)]


def _vw() -> VerifiedWeaviate:
    # No client/embedder needed — Weaviate.__init__ does no I/O, it only sets
    # attributes. A real client would only be touched by the base insert/
    # async_insert methods, which every test below monkeypatches out.
    return VerifiedWeaviate(client=object(), collection="test_collection", embedder=object())


# --- _verify_embedded (pure logic) -------------------------------------------


def test_verify_embedded_noop_on_empty_batch():
    _verify_embedded([])  # must not raise


def test_verify_embedded_raises_when_every_document_has_no_vector():
    docs = _make_docs(None, None, None)
    with pytest.raises(EmbeddingFailedError, match="no vector for any of 3 document"):
        _verify_embedded(docs)


def test_verify_embedded_passes_when_all_documents_embedded():
    docs = _make_docs([0.1, 0.2], [0.3, 0.4])
    _verify_embedded(docs)  # must not raise


def test_verify_embedded_passes_on_partial_success(caplog):
    # Partial embed failure is logged, not raised — failing the whole content
    # row would throw away real, usable vectors for a chunk-level hiccup.
    docs = _make_docs([0.1, 0.2], None)
    _verify_embedded(docs)  # must not raise


# --- VerifiedWeaviate.insert ---------------------------------------------------


def test_insert_raises_when_base_leaves_all_embeddings_none(monkeypatch):
    def _fake_insert(self, content_hash, documents, filters=None):
        pass  # simulates every document's embedder call returning None

    monkeypatch.setattr(Weaviate, "insert", _fake_insert)

    vw = _vw()
    docs = _make_docs(None, None)

    with pytest.raises(EmbeddingFailedError):
        vw.insert("content-hash", docs)


def test_insert_succeeds_when_base_embeds_documents(monkeypatch):
    def _fake_insert(self, content_hash, documents, filters=None):
        for doc in documents:
            doc.embedding = [0.1, 0.2, 0.3]

    monkeypatch.setattr(Weaviate, "insert", _fake_insert)

    vw = _vw()
    docs = _make_docs(None, None)

    vw.insert("content-hash", docs)  # must not raise
    assert all(d.embedding is not None for d in docs)


def test_upsert_delegates_through_verified_insert(monkeypatch):
    # agno's Weaviate.upsert() calls self.insert() internally — confirm that
    # VerifiedWeaviate's override is what actually runs (method resolution),
    # not the raw base-class insert.
    def _fake_content_hash_exists(self, content_hash):
        return False

    def _fake_insert(self, content_hash, documents, filters=None):
        pass  # leaves embeddings None -> should raise via VerifiedWeaviate.insert

    monkeypatch.setattr(Weaviate, "content_hash_exists", _fake_content_hash_exists)
    monkeypatch.setattr(Weaviate, "insert", _fake_insert)

    vw = _vw()
    docs = _make_docs(None)

    with pytest.raises(EmbeddingFailedError):
        vw.upsert("content-hash", docs)


# --- VerifiedWeaviate.async_insert ---------------------------------------------


def test_async_insert_raises_when_base_leaves_all_embeddings_none(monkeypatch):
    async def _fake_async_insert(self, content_hash, documents, filters=None):
        pass

    monkeypatch.setattr(Weaviate, "async_insert", _fake_async_insert)

    vw = _vw()
    docs = _make_docs(None, None)

    async def _run():
        with pytest.raises(EmbeddingFailedError):
            await vw.async_insert("content-hash", docs)

    asyncio.run(_run())


def test_async_insert_succeeds_when_base_embeds_documents(monkeypatch):
    async def _fake_async_insert(self, content_hash, documents, filters=None):
        for doc in documents:
            doc.embedding = [0.1, 0.2, 0.3]

    monkeypatch.setattr(Weaviate, "async_insert", _fake_async_insert)

    vw = _vw()
    docs = _make_docs(None)

    async def _run():
        await vw.async_insert("content-hash", docs)  # must not raise

    asyncio.run(_run())
    assert docs[0].embedding is not None
