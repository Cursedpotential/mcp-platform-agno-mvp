"""Unit tests for server/api/inspect_routes.py — the C3 operator-console
inspectors + curation routes (records browser, PG/Milvus schema introspection,
hash verify + H1/H2/H3 chain-walk, parse-dryrun, record/flag curation).

Same style as tests/test_run_ledger.py and tests/test_custody.py: a fake
SQLAlchemy engine test double (no live Postgres), FastAPI TestClient for the
route-level contracts, and monkeypatched registry/run_ledger collaborators
for parse-dryrun so no real parser/tool-registry state is required.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-22

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import server.api.inspect_routes as inspect_routes
from server.api.inspect_routes import register_inspect_routes

# --- sql/0007_curation_and_flags.sql (mirrors tests/test_run_ledger.py's
# migration-file checks for 0005/0006) -----------------------------------

_SQL_0007_PATH = Path(__file__).resolve().parents[1] / "sql" / "0007_curation_and_flags.sql"


def test_migration_0007_file_exists():
    assert _SQL_0007_PATH.is_file()


def test_migration_0007_sql_parses():
    sqlparse = pytest.importorskip("sqlparse")
    sql_text = _SQL_0007_PATH.read_text(encoding="utf-8")
    statements = [s for s in sqlparse.parse(sql_text) if str(s).strip()]
    # 1x CREATE TABLE + 3x CREATE INDEX, at minimum.
    assert len(statements) >= 4


def test_migration_0007_defines_corroboration_flag_idempotently():
    sql_text = _SQL_0007_PATH.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS analysis.corroboration_flag " in sql_text
    assert "DEFAULT uuidv7()" in sql_text
    assert "CHECK (target_kind IN ('record','knowledge','run'))" in sql_text
    assert "CHECK (status IN ('open','partial','corroborated','unobtainable'))" in sql_text
    assert "CREATE INDEX IF NOT EXISTS idx_corroboration_flag_status" in sql_text
    assert "CREATE INDEX IF NOT EXISTS idx_corroboration_flag_target" in sql_text
    assert "CREATE INDEX IF NOT EXISTS idx_normrec_attrs" in sql_text
    # No new columns on normalized_record — attrs is reused (see file header).
    assert "ALTER TABLE working.normalized_record ADD COLUMN" not in sql_text


# --- fake SQLAlchemy engine (mirrors tests/test_run_ledger.py's _FakeEngine) --


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def mappings(self):
        return self

    def first(self):
        return self._value

    def all(self):
        return self._value

    def scalar(self):
        return self._value


class _FakeConn:
    def __init__(self, engine):
        self._engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        self._engine.calls.append((str(stmt), params))
        return _FakeResult(self._engine._next_value())


class _FakeEngine:
    """Returns the queued values in order, one per execute() call."""

    def __init__(self, values):
        self._values = list(values)
        self._i = 0
        self.calls: list[tuple[str, object]] = []

    def _next_value(self):
        v = self._values[self._i]
        self._i += 1
        return v

    def connect(self):
        return _FakeConn(self)

    def begin(self):
        return _FakeConn(self)


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    register_inspect_routes(app, knowledge=None)
    return TestClient(app)


# =============================================================================
# _row_to_record — text truncation / full_len / seq passthrough
# =============================================================================


def test_row_to_record_truncates_text_and_reports_full_len():
    long_text = "x" * 3000
    row = {
        "id": "11111111-1111-1111-1111-111111111111",
        "seq": 1,
        "artifact_id": "22222222-2222-2222-2222-222222222222",
        "record_type": "message",
        "source": "chatgpt-export",
        "conversation_id": "conv-1",
        "role": "user",
        "participants": ["me"],
        "occurred_at": "2026-01-01T00:00:00Z",
        "knowledge_time": "2026-01-02T00:00:00Z",
        "disclosure_tier": "contemporaneous",
        "content": long_text,
        "attrs": {"parser_tool": "x"},
        "created_at": "2026-01-02T00:00:00Z",
    }
    out = inspect_routes._row_to_record(row)
    assert out["text"] == long_text[:2000]
    assert out["full_len"] == 3000
    assert "content" not in out  # renamed, not duplicated
    assert out["seq"] == 1
    assert out["attrs"] == {"parser_tool": "x"}


def test_row_to_record_handles_none_content_and_jsonb_strings():
    row = {
        "id": "1",
        "seq": None,
        "artifact_id": "2",
        "record_type": "message",
        "source": "s",
        "conversation_id": None,
        "role": None,
        "participants": "[]",  # some drivers hand back raw jsonb text
        "occurred_at": None,
        "knowledge_time": None,
        "disclosure_tier": "contemporaneous",
        "content": None,
        "attrs": "{}",
        "created_at": None,
    }
    out = inspect_routes._row_to_record(row)
    assert out["text"] == ""
    assert out["full_len"] == 0
    assert out["participants"] == []
    assert out["attrs"] == {}


# =============================================================================
# _resolve_artifact_id
# =============================================================================


def test_resolve_artifact_id_prefers_explicit_artifact_id():
    assert inspect_routes._resolve_artifact_id("art-1", None) == "art-1"


def test_resolve_artifact_id_neither_given_is_422():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        inspect_routes._resolve_artifact_id(None, None)
    assert exc_info.value.status_code == 422


def test_resolve_artifact_id_resolves_via_run_id(monkeypatch):
    monkeypatch.setattr(
        "server.evidence.run_ledger.get_run",
        lambda run_id: {"artifact_id": "art-from-run"} if run_id == "run-1" else None,
    )
    assert inspect_routes._resolve_artifact_id(None, "run-1") == "art-from-run"


def test_resolve_artifact_id_unknown_run_is_404(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: None)
    with pytest.raises(HTTPException) as exc_info:
        inspect_routes._resolve_artifact_id(None, "nope")
    assert exc_info.value.status_code == 404


def test_resolve_artifact_id_run_without_artifact_is_404(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: {"artifact_id": None})
    with pytest.raises(HTTPException) as exc_info:
        inspect_routes._resolve_artifact_id(None, "run-1")
    assert exc_info.value.status_code == 404


# =============================================================================
# GET /v1/records
# =============================================================================


def test_list_records_422_without_artifact_or_run(client):
    resp = client.get("/v1/records")
    assert resp.status_code == 422


def test_list_records_happy_path(client, monkeypatch):
    row = {
        "id": "r1",
        "artifact_id": "art-1",
        "record_type": "message",
        "source": "s",
        "conversation_id": "c1",
        "role": "user",
        "participants": [],
        "content": "hello",
        "occurred_at": None,
        "knowledge_time": None,
        "disclosure_tier": "contemporaneous",
        "attrs": {},
        "created_at": None,
        "seq": 1,
    }
    fake = _FakeEngine([3, [row]])  # total, then rows
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.get("/v1/records", params={"artifact_id": "art-1", "limit": 10, "offset": 0})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["artifact_id"] == "art-1"
    assert body["records"][0]["text"] == "hello"
    assert body["records"][0]["seq"] == 1


def test_list_records_q_adds_ilike_filter(client, monkeypatch):
    fake = _FakeEngine([0, []])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.get("/v1/records", params={"artifact_id": "art-1", "q": "needle"})

    assert resp.status_code == 200
    # second call is the SELECT (first is the COUNT) — both must carry q
    assert fake.calls[0][1]["q"] == "%needle%"
    assert "content ILIKE :q" in fake.calls[0][0]


# =============================================================================
# GET /v1/inspect/schemas
# =============================================================================


def test_inspect_pg_schemas_exact_count_for_small_tables(monkeypatch):
    table_rows = [{"schema": "analysis", "table_name": "workflow_run", "est_rows": 5}]
    column_rows = [
        {
            "table_schema": "analysis",
            "table_name": "workflow_run",
            "column_name": "run_id",
            "data_type": "uuid",
            "ordinal_position": 1,
        }
    ]
    fake = _FakeEngine([table_rows, column_rows, 42])  # tables, columns, exact count
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    out = inspect_routes._inspect_pg_schemas()

    assert out["analysis"][0]["table"] == "workflow_run"
    assert out["analysis"][0]["row_count"] == 42
    assert out["analysis"][0]["row_count_is_estimate"] is False
    assert out["analysis"][0]["columns"] == [{"name": "run_id", "type": "uuid"}]


def test_inspect_pg_schemas_estimate_for_large_tables(monkeypatch):
    table_rows = [{"schema": "evidence", "table_name": "huge", "est_rows": 500_000}]
    fake = _FakeEngine([table_rows, []])  # tables, columns (no exact-count call expected)
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    out = inspect_routes._inspect_pg_schemas()

    assert out["evidence"][0]["row_count"] == 500_000
    assert out["evidence"][0]["row_count_is_estimate"] is True
    assert len(fake.calls) == 2  # no third (exact count) call


def test_inspect_weaviate_collections_guards_failures(monkeypatch):
    # Force the "no knowledge instance -> build a fresh Weaviate client" path
    # to fail deterministically (this sandbox's network may or may not actually
    # reach a live Weaviate at the default tailnet address, so the test must
    # not rely on ambient reachability either way).
    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr("server.core.session.get_weaviate_client", _boom, raising=False)

    out = inspect_routes._inspect_weaviate_collections(None)

    assert isinstance(out, dict) and "error" in out


def test_inspect_weaviate_collections_happy_path():
    class _FakeProperty:
        name = "content"
        data_type = "TEXT"

    class _FakeCfg:
        properties = [_FakeProperty()]

    class _FakeAgg:
        total_count = 7

    class _FakeAggregate:
        def over_all(self, total_count=True):
            return _FakeAgg()

    class _FakeCollectionHandle:
        aggregate = _FakeAggregate()

    class _FakeCollections:
        def list_all(self):
            return {"Platform_knowledge": _FakeCfg()}

        def get(self, name):
            return _FakeCollectionHandle()

    class _FakeClient:
        collections = _FakeCollections()

    class _FakeVectorDb:
        collection = "platform_knowledge"

        def get_client(self):
            return _FakeClient()

    class _FakeKnowledge:
        vector_db = _FakeVectorDb()

    out = inspect_routes._inspect_weaviate_collections(_FakeKnowledge())

    assert out == [{"name": "Platform_knowledge", "fields": [{"name": "content", "type": "TEXT"}], "num_entities": 7}]


# =============================================================================
# _walk_h3_chain — the corrected canonicalization (chain_0 = "", NOT H1)
# =============================================================================


def _h3_step(prev_hex: str, h2_hex: str) -> str:
    return hashlib.sha256((prev_hex + "\n" + h2_hex).encode("utf-8")).hexdigest()


def test_walk_h3_chain_single_record_matches_manual_computation():
    h2 = hashlib.sha256(b"<sms/>").hexdigest()
    expected_final = _h3_step("", h2)

    links = inspect_routes._walk_h3_chain([h2], expected_final)

    assert len(links) == 1
    assert links[0] == {"seq": 1, "ok": True, "expected": expected_final, "actual": expected_final}


def test_walk_h3_chain_multi_record_folds_left_to_right():
    h2a = hashlib.sha256(b"<sms a/>").hexdigest()
    h2b = hashlib.sha256(b"<sms b/>").hexdigest()
    chain1 = _h3_step("", h2a)
    chain2 = _h3_step(chain1, h2b)

    links = inspect_routes._walk_h3_chain([h2a, h2b], chain2)

    assert links[0]["actual"] == chain1
    assert links[0]["expected"] is None  # only the LAST link has a stored comparison
    assert links[0]["ok"] is True  # nothing to falsify yet
    assert links[1]["actual"] == chain2
    assert links[1]["expected"] == chain2
    assert links[1]["ok"] is True


def test_walk_h3_chain_detects_mismatch_on_final_link():
    h2 = hashlib.sha256(b"<sms/>").hexdigest()
    wrong_stored = "0" * 64

    links = inspect_routes._walk_h3_chain([h2], wrong_stored)

    assert links[0]["ok"] is False
    assert links[0]["expected"] == wrong_stored


def test_walk_h3_chain_no_stored_h3_is_ok_true_uncompared():
    h2 = hashlib.sha256(b"<sms/>").hexdigest()
    links = inspect_routes._walk_h3_chain([h2], None)
    assert links[0]["ok"] is True
    assert links[0]["expected"] is None


# =============================================================================
# POST /v1/verify/{sha256}
# =============================================================================


def test_verify_422_bad_hex(client):
    resp = client.post("/v1/verify/not-hex")
    assert resp.status_code == 422


def test_verify_404_unknown_sha256(client, monkeypatch):
    fake = _FakeEngine([None])  # H1 lookup -> no row
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.post("/v1/verify/" + "ab" * 32)
    assert resp.status_code == 404


def test_verify_light_tier_hash_only_ok(client, monkeypatch, tmp_path):
    blob = tmp_path / "blobs" / "ab" / "abc123" / "f.txt"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"hello evidence")
    real_sha = hashlib.sha256(b"hello evidence").hexdigest()
    monkeypatch.setattr(inspect_routes, "blob_root", lambda: tmp_path / "blobs")

    h1_row = {
        "id": "h1-id",
        "source_id": "src-1",
        "blob_key": "ab/abc123/f.txt",
        "meta": {"custody_tier": "light"},
        "hashed_at": "2026-01-01T00:00:00Z",
    }
    fake = _FakeEngine([h1_row])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.post(f"/v1/verify/{real_sha}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sha256_match"] is True
    assert body["custody_tier"] == "light"
    assert body["chain"] is None
    assert body["verdict"] == "hash-only-ok"


def test_verify_full_tier_no_chain_rows_is_hash_only_ok(client, monkeypatch, tmp_path):
    blob = tmp_path / "blobs" / "ab" / "abc123" / "f.txt"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"hello evidence")
    real_sha = hashlib.sha256(b"hello evidence").hexdigest()
    monkeypatch.setattr(inspect_routes, "blob_root", lambda: tmp_path / "blobs")

    h1_row = {
        "id": "h1-id",
        "source_id": "src-1",
        "blob_key": "ab/abc123/f.txt",
        "meta": {"custody_tier": "full"},
        "hashed_at": "2026-01-01T00:00:00Z",
    }
    fake = _FakeEngine([h1_row, []])  # H1, then H2 rows (empty — never reconciled)
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.post(f"/v1/verify/{real_sha}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["chain"] is None
    assert body["verdict"] == "hash-only-ok"


def test_verify_full_tier_chain_intact(client, monkeypatch, tmp_path):
    blob = tmp_path / "blobs" / "ab" / "abc123" / "f.txt"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"hello evidence")
    real_sha = hashlib.sha256(b"hello evidence").hexdigest()
    monkeypatch.setattr(inspect_routes, "blob_root", lambda: tmp_path / "blobs")

    h2_hex = hashlib.sha256(b"<sms/>").hexdigest()
    h3_hex = _h3_step("", h2_hex)

    h1_row = {
        "id": "h1-id",
        "source_id": "src-1",
        "blob_key": "ab/abc123/f.txt",
        "meta": {"custody_tier": "full"},
        "hashed_at": "2026-01-01T00:00:00Z",
    }
    h2_rows = [{"digest": bytes.fromhex(h2_hex), "record_locator": {"record_index": 0}}]
    h3_row = {"digest": bytes.fromhex(h3_hex)}
    fake = _FakeEngine([h1_row, h2_rows, h3_row])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.post(f"/v1/verify/{real_sha}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] == "intact"
    assert body["chain"][0]["ok"] is True


def test_verify_broken_on_sha_mismatch(client, monkeypatch, tmp_path):
    blob = tmp_path / "blobs" / "ab" / "abc123" / "f.txt"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"TAMPERED BYTES")
    monkeypatch.setattr(inspect_routes, "blob_root", lambda: tmp_path / "blobs")

    recorded_sha = hashlib.sha256(b"hello evidence").hexdigest()  # NOT what's on disk
    h1_row = {
        "id": "h1-id",
        "source_id": "src-1",
        "blob_key": "ab/abc123/f.txt",
        "meta": {"custody_tier": "light"},
        "hashed_at": "2026-01-01T00:00:00Z",
    }
    fake = _FakeEngine([h1_row])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.post(f"/v1/verify/{recorded_sha}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sha256_match"] is False
    assert body["verdict"] == "broken"


def test_verify_missing_blob_file_is_broken(client, monkeypatch, tmp_path):
    monkeypatch.setattr(inspect_routes, "blob_root", lambda: tmp_path / "blobs-do-not-exist")
    recorded_sha = hashlib.sha256(b"hello evidence").hexdigest()
    h1_row = {
        "id": "h1-id",
        "source_id": "src-1",
        "blob_key": "ab/abc123/f.txt",
        "meta": {"custody_tier": "light"},
        "hashed_at": "2026-01-01T00:00:00Z",
    }
    fake = _FakeEngine([h1_row])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.post(f"/v1/verify/{recorded_sha}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["computed"] is None
    assert body["sha256_match"] is False
    assert body["verdict"] == "broken"


# =============================================================================
# POST /v1/runs/{run_id}/parse-dryrun
# =============================================================================


class _FakeTool:
    def __init__(self, tool_id, ok=True, records=None, stats=None, error="boom"):
        self.id = tool_id
        self._ok = ok
        self._records = records or []
        self._stats = stats or {}
        self._error = error

    def run(self, payload):
        if not self._ok:
            raise ValueError(self._error)
        return {"records": self._records, "stats": self._stats}


def test_parse_dryrun_422_when_neither_file_nor_sha256(client, monkeypatch):
    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: {"workflow": "chat-transcript"})
    resp = client.post("/v1/runs/run-1/parse-dryrun")
    assert resp.status_code == 422


def test_parse_dryrun_422_when_both_file_and_sha256(client, monkeypatch):
    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: {"workflow": "chat-transcript"})
    resp = client.post(
        "/v1/runs/run-1/parse-dryrun",
        files={"file": ("f.txt", b"hi", "text/plain")},
        data={"sha256": "ab" * 32},
    )
    assert resp.status_code == 422


def test_parse_dryrun_404_unknown_run(client, monkeypatch):
    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: None)
    resp = client.post("/v1/runs/run-1/parse-dryrun", files={"file": ("f.txt", b"hi", "text/plain")})
    assert resp.status_code == 404


def test_parse_dryrun_tries_next_candidate_on_failure_and_reports_attempts(client, monkeypatch):
    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: {"workflow": "chat-transcript"})
    monkeypatch.setattr("server.tools.registry.load_builtin_tools", lambda: None)

    failing = _FakeTool("transcripts.bad", ok=False, error="wrong format")
    winning = _FakeTool("transcripts.good", ok=True, records=[{"content": "hi"}], stats={"confidence": 0.9})
    monkeypatch.setattr(
        "server.tools.registry.registry.resolve",
        lambda capability, media_hint="", size_bytes=0: [failing, winning],
    )

    resp = client.post("/v1/runs/run-1/parse-dryrun", files={"file": ("f.txt", b"hello", "text/plain")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["attempts"] == [
        {"tool": "transcripts.bad", "ok": False, "error": "wrong format"},
        {"tool": "transcripts.good", "ok": True, "confidence": 0.9},
    ]
    assert body["winning_parser_id"] == "transcripts.good"
    assert body["record_count"] == 1
    assert len(body["sample_records"]) == 1


def test_parse_dryrun_no_candidates_reports_empty(client, monkeypatch):
    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: {"workflow": "sms-xml"})
    monkeypatch.setattr("server.tools.registry.load_builtin_tools", lambda: None)
    monkeypatch.setattr("server.tools.registry.registry.resolve", lambda capability, media_hint="", size_bytes=0: [])

    resp = client.post("/v1/runs/run-1/parse-dryrun", files={"file": ("f.xml", b"<smses/>", "text/xml")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["attempts"] == []
    assert body["winning_parser_id"] is None
    assert body["record_count"] == 0


def test_parse_dryrun_via_sha256_reads_custody_blob(client, monkeypatch, tmp_path):
    blob = tmp_path / "blobs" / "ab" / "abc123" / "f.txt"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"hi")
    monkeypatch.setattr(inspect_routes, "blob_root", lambda: tmp_path / "blobs")

    h1_row = {"id": "h1", "source_id": "s1", "blob_key": "ab/abc123/f.txt", "meta": {}, "hashed_at": "t"}
    fake = _FakeEngine([h1_row])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)
    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: {"workflow": "chat-transcript"})
    monkeypatch.setattr("server.tools.registry.load_builtin_tools", lambda: None)
    monkeypatch.setattr(
        "server.tools.registry.registry.resolve",
        lambda capability, media_hint="", size_bytes=0: [_FakeTool("t", ok=True, records=[])],
    )

    resp = client.post("/v1/runs/run-1/parse-dryrun", data={"sha256": "ab" * 32})

    assert resp.status_code == 200


def test_parse_dryrun_sha256_not_in_custody_is_404(client, monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)
    monkeypatch.setattr("server.evidence.run_ledger.get_run", lambda run_id: {"workflow": "chat-transcript"})

    resp = client.post("/v1/runs/run-1/parse-dryrun", data={"sha256": "ab" * 32})

    assert resp.status_code == 404


# =============================================================================
# PATCH /v1/records/{record_id}/meta
# =============================================================================


def test_patch_record_meta_merges_title_labels_and_attrs_patch(client, monkeypatch):
    returned_row = {
        "id": "rec-1",
        "artifact_id": "art-1",
        "record_type": "message",
        "source": "s",
        "conversation_id": None,
        "role": None,
        "participants": [],
        "content": "hi",
        "occurred_at": None,
        "knowledge_time": None,
        "disclosure_tier": "contemporaneous",
        "attrs": {"title": "New Title", "labels": ["a", "b"], "custom": 1},
        "created_at": None,
    }
    fake = _FakeEngine([returned_row])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.patch(
        "/v1/records/rec-1/meta",
        json={"title": "New Title", "labels": ["a", "b"], "attrs_patch": {"custom": 1}},
    )

    assert resp.status_code == 200
    _, params = fake.calls[0]
    sent_patch = json.loads(params["patch"])
    assert sent_patch == {"title": "New Title", "labels": ["a", "b"], "custom": 1}
    body = resp.json()
    assert body["text"] == "hi"  # content/text is untouched by curation


def test_patch_record_meta_404_when_missing(client, monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.patch("/v1/records/nope/meta", json={"title": "x"})
    assert resp.status_code == 404


def test_patch_record_meta_422_when_empty(client):
    resp = client.patch("/v1/records/rec-1/meta", json={})
    assert resp.status_code == 422


# =============================================================================
# /v1/flags CRUD
# =============================================================================


def _flag_row(**overrides):
    row = {
        "flag_id": "flag-1",
        "target_kind": "record",
        "target_id": "rec-1",
        "claim": "X happened on 2026-01-01",
        "claim_date_start": "2026-01-01",
        "claim_date_end": None,
        "evidence_wanted": ["sms"],
        "status": "open",
        "linked_artifacts": [],
        "notes": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_create_flag_happy_path(client, monkeypatch):
    fake = _FakeEngine([_flag_row()])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.post(
        "/v1/flags",
        json={"target_kind": "record", "target_id": "rec-1", "claim": "X happened on 2026-01-01"},
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "open"


def test_create_flag_422_unknown_target_kind(client):
    resp = client.post("/v1/flags", json={"target_kind": "bogus", "target_id": "x", "claim": "c"})
    assert resp.status_code == 422


def test_create_flag_422_unknown_status(client):
    resp = client.post("/v1/flags", json={"target_kind": "record", "target_id": "x", "claim": "c", "status": "bogus"})
    assert resp.status_code == 422


def test_list_flags_filters_and_paginates(client, monkeypatch):
    fake = _FakeEngine([2, [_flag_row(), _flag_row(flag_id="flag-2")]])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.get("/v1/flags", params={"status": "open", "target_kind": "record", "limit": 10})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["flags"]) == 2
    _, count_params = fake.calls[0]
    assert count_params == {"status": "open", "target_kind": "record"}


def test_patch_flag_status_and_notes(client, monkeypatch):
    fake = _FakeEngine([_flag_row(status="corroborated", notes="found it")])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.patch("/v1/flags/flag-1", json={"status": "corroborated", "notes": "found it"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "corroborated"
    stmt, params = fake.calls[0]
    assert "status = :status" in stmt
    assert "notes = :notes" in stmt
    assert "linked_artifacts" not in stmt


def test_patch_flag_linked_artifacts_append_uses_jsonb_concat(client, monkeypatch):
    fake = _FakeEngine([_flag_row(linked_artifacts=[{"artifact_id": "a1"}])])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.patch("/v1/flags/flag-1", json={"linked_artifacts_append": [{"artifact_id": "a1"}]})

    assert resp.status_code == 200
    stmt, params = fake.calls[0]
    assert "linked_artifacts = linked_artifacts || CAST(:append AS jsonb)" in stmt
    assert json.loads(params["append"]) == [{"artifact_id": "a1"}]


def test_patch_flag_404_when_missing(client, monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(inspect_routes, "_get_engine", lambda: fake)

    resp = client.patch("/v1/flags/nope", json={"status": "open"})
    assert resp.status_code == 404


def test_patch_flag_422_when_empty(client):
    resp = client.patch("/v1/flags/flag-1", json={})
    assert resp.status_code == 422


def test_patch_flag_422_unknown_status(client):
    resp = client.patch("/v1/flags/flag-1", json={"status": "bogus"})
    assert resp.status_code == 422
