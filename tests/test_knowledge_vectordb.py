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


# --- update_metadata: agno 2.8.0 vs weaviate-client 4.22.0 kwarg regression ---
# Byline: Claude Code · Opus 5 · 2026-08-01


def test_update_metadata_uses_filters_not_where(monkeypatch):
    """REGRESSION (live 2026-08-01): agno 2.8.0 calls fetch_objects(where=...),
    but weaviate-client 4.22.0 takes filters=. The TypeError propagated out of
    ainsert() and aborted a whole reindex on its first file (POST
    /v1/knowledge/reindex -> 500, zero new vectors written).
    """
    from server.core.knowledge_vectordb import VerifiedWeaviate

    captured = {}

    class FakeQuery:
        def fetch_objects(self, **kwargs):
            captured.update(kwargs)
            if "where" in kwargs:  # the upstream bug, reproduced
                raise TypeError("fetch_objects() got an unexpected keyword argument 'where'")

            class R:
                objects = []

            return R()

    class FakeCollection:
        query = FakeQuery()
        data = None

    class FakeClient:
        class collections:
            @staticmethod
            def get(_name):
                return FakeCollection()

    db = VerifiedWeaviate.__new__(VerifiedWeaviate)
    db.collection = "Platform_knowledge"
    monkeypatch.setattr(type(db), "get_client", lambda self: FakeClient(), raising=False)

    db.update_metadata("content-123", {"domain": "platform"})

    assert "filters" in captured, "must pass filters= (v4), never where= (v3)"
    assert "where" not in captured
    assert captured["limit"] == 1000


# --- async client must be CUSTOM, never agno's localhost fallback -------------
# Byline: Claude Code · Opus 5 · 2026-08-01


async def _get_async(db):
    return await db.get_async_client()


def test_async_client_uses_injected_factory_not_localhost():
    """REGRESSION (root cause of "knowledge never populates", live 2026-08-01):
    agno's Weaviate has no async_client constructor param and its
    get_async_client() falls back to use_async_with_local() -> localhost:8080.
    The ingest path is fully async, so writes hit localhost while sync search
    worked, and every content row landed FAILED with "Could not upsert
    embedding" and no hint the host was wrong.
    """
    import asyncio

    from server.core.knowledge_vectordb import VerifiedWeaviate

    class FakeAsyncClient:
        def __init__(self):
            self.connected = False

        def is_connected(self):
            return self.connected

        async def connect(self):
            self.connected = True

    made = FakeAsyncClient()
    db = VerifiedWeaviate.__new__(VerifiedWeaviate)
    db.async_client = None
    db._async_client_factory = lambda: made

    got = asyncio.run(_get_async(db))
    assert got is made, "must use the injected custom client, not agno's localhost default"
    assert got.connected is True, "must lazily connect the async client"

    # second call reuses it rather than reconnecting
    assert asyncio.run(_get_async(db)) is made


def test_session_wires_the_async_client_factory():
    """create_knowledge() must pass async_client_factory — without it the
    subclass silently falls back to agno's localhost behavior."""
    import inspect

    import server.core.session as session

    src = inspect.getsource(session.create_knowledge)
    assert "async_client_factory" in src, "create_knowledge must inject the async client factory"
    assert hasattr(session, "get_weaviate_async_client")


# --- meta_data is a TEXT property: must be written as a JSON string -----------
# Byline: Claude Code · Opus 5 · 2026-08-01


def test_merged_json_property_returns_a_string():
    """REGRESSION (live 2026-08-01): writing a dict to the `meta_data` text
    property gave weaviate 422 "not a string, but map[string]interface {}",
    which failed the whole reindex.
    """
    import json as _json

    from server.core.knowledge_vectordb import _merged_json_property

    out = _merged_json_property('{"domain": "platform", "keep": 1}', {"category": "docs"})
    assert isinstance(out, str), "must be a JSON string, never a dict"
    assert _json.loads(out) == {"domain": "platform", "keep": 1, "category": "docs"}


def test_merged_json_property_handles_dict_and_junk():
    import json as _json

    from server.core.knowledge_vectordb import _merged_json_property

    assert _json.loads(_merged_json_property({"a": 1}, {"b": 2})) == {"a": 1, "b": 2}
    # legacy/garbage values must not blow up an otherwise good ingest
    assert _json.loads(_merged_json_property("not json at all", {"b": 2})) == {"b": 2}
    assert _json.loads(_merged_json_property(None, {"b": 2})) == {"b": 2}


def test_update_metadata_patches_only_meta_keys_as_strings(monkeypatch):
    from server.core.knowledge_vectordb import VerifiedWeaviate

    sent = {}

    class Obj:
        uuid = "u-1"
        properties = {"meta_data": '{"domain":"platform"}', "content": "big text", "name": "doc"}

    class FakeQuery:
        def fetch_objects(self, **kwargs):
            class R:
                objects = [Obj()]

            return R()

    class FakeData:
        def update(self, uuid, properties):
            sent["uuid"] = uuid
            sent["properties"] = properties

    class FakeCollection:
        query = FakeQuery()
        data = FakeData()

    class FakeClient:
        class collections:
            @staticmethod
            def get(_n):
                return FakeCollection()

    db = VerifiedWeaviate.__new__(VerifiedWeaviate)
    db.collection = "Platform_knowledge"
    monkeypatch.setattr(type(db), "get_client", lambda self: FakeClient(), raising=False)

    db.update_metadata("c-1", {"category": "docs"})

    props = sent["properties"]
    assert set(props) == {"meta_data", "filters"}, "must PATCH only the meta keys"
    # Different schema types, verified live: meta_data is `text`, filters is `object`.
    assert isinstance(props["meta_data"], str), "meta_data is text -> JSON string"
    assert isinstance(props["filters"], dict), "filters is object -> dict, NOT a string"
    assert "content" not in props, "must not resend unrelated properties"


def test_filters_is_a_dict_not_a_string():
    """REGRESSION (live 2026-08-01): `filters` is an `object` property while
    `meta_data` is `text`. Serializing both gave
    422 "invalid object property 'filters'". Probed live: filters=str FAIL,
    filters=dict OK.
    """
    from server.core.knowledge_vectordb import _merged_dict, _merged_json_property

    assert isinstance(_merged_dict('{"a":1}', {"b": 2}), dict)
    assert _merged_dict('{"a":1}', {"b": 2}) == {"a": 1, "b": 2}
    assert isinstance(_merged_json_property({"a": 1}, {"b": 2}), str)
