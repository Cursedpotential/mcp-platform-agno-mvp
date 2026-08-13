"""Unit tests for C2.6 "resilience + observability".

Covers, all DB-free (fake-engine / stub doubles, same style as
tests/test_run_ledger.py and tests/test_custody.py):

  1. server/evidence/store.py — transient-error classification, the
     bounded-backoff retry wrappers (_retry_async/_retry_sync), and
     load_records_for_artifact()'s round-trip from raw rows to
     NormalizedRecord objects.
  2. server/evidence/workflows.py — _store_step_impl's dedupe +
     parent-knowledge-failed auto-route (the actual prod-bug fix),
     run_knowledge_from_store's skip-then-ingest sequencing, and the
     on_error='fail' override on every Step this module builds (agno's
     actual Step.on_error default is OnError.skip, not the 'fail' its own
     docstring claims — see the module's C2.6 note).
  3. server/api/run_routes.py — POST /v1/runs/{id}/retry's new
     {"from_stage": "knowledge"} branch (validation + happy path) and
     GET /v1/health/deps (parallel pg/milvus checks, both mocked).

No live Postgres, no live Milvus, no real agno Workflow execution.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-21

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from agno.workflow.types import OnError

import server.evidence.workflows as workflows_mod
from server.evidence import run_ledger, store as store_mod
from server.evidence.custody import ArtifactRef
from server.contracts.records import NormalizedRecord

# =============================================================================
# run_ledger.py — list_runs() surfaces truncated stage content (requirement 3)
# =============================================================================


def test_list_runs_includes_truncated_stage_content(monkeypatch):
    rows = [
        {
            "run_id": "run-1",
            "workflow": "chat-transcript",
            "mode": "auto",
            "source_name": "a.txt",
            "source_path": "/tmp/a.txt",
            "sha256": "aa",
            "artifact_id": "1",
            "domain": "platform_design",
            "status": "failed",
            "gate_state": None,
            "parent_run_id": None,
            "custody_tier": "light",
            "summary": None,
            "error": None,
            "created_at": "t1",
            "updated_at": "t1",
            "seq": 4,
            "stage_name": "knowledge",
            "stage_status": "failed",
            "stage_content": "x" * 600,
        },
    ]

    class _FakeConn2:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, stmt, params=None):
            class _R:
                def mappings(self_inner):
                    return self_inner

                def all(self_inner):
                    return rows

            return _R()

    class _FakeEngine2:
        def connect(self):
            return _FakeConn2()

    monkeypatch.setattr(run_ledger, "_get_engine", lambda: _FakeEngine2())

    out = run_ledger.list_runs(limit=10)

    assert len(out[0]["stages"][0]["content"]) == 500
    assert out[0]["stages"][0]["content"] == "x" * 500


# =============================================================================
# store.py — transient-error classification
# =============================================================================


class _FakeMilvusException(Exception):
    """Duck-typed like pymilvus.MilvusException (module + class name +
    .code) WITHOUT importing pymilvus — matches store.py's classification,
    which is itself duck-typed for the same reason (pymilvus isn't always
    installed on every path that imports this module)."""

    __module__ = "pymilvus.exceptions"

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


_FakeMilvusException.__name__ = "MilvusException"


def test_transient_milvus_503_by_code():
    exc = _FakeMilvusException("service unavailable", code=503)
    assert store_mod._is_transient_error(exc) is True


def test_transient_milvus_by_text_marker_when_no_code():
    exc = _FakeMilvusException("rpc error: UNAVAILABLE")
    assert store_mod._is_transient_error(exc) is True


def test_transient_connection_and_timeout_errors():
    assert store_mod._is_transient_error(ConnectionError("refused")) is True
    assert store_mod._is_transient_error(ConnectionRefusedError("refused")) is True
    assert store_mod._is_transient_error(TimeoutError("timed out")) is True
    assert store_mod._is_transient_error(asyncio.TimeoutError()) is True


def test_transient_text_markers_on_generic_exception():
    assert store_mod._is_transient_error(RuntimeError("Connection reset by peer")) is True
    assert store_mod._is_transient_error(RuntimeError("deadline exceeded")) is True


def test_non_transient_errors_are_not_retried():
    # FileNotFoundError/PermissionError are OSError subclasses — must NOT be
    # swept up by a bare `isinstance(exc, OSError)` check (a real trap this
    # module deliberately avoids).
    assert store_mod._is_transient_error(FileNotFoundError("no such file")) is False
    assert store_mod._is_transient_error(PermissionError("denied")) is False
    assert store_mod._is_transient_error(ValueError("bad record shape")) is False
    assert store_mod._is_transient_error(KeyError("artifact")) is False


def test_non_transient_milvus_exception_by_code():
    exc = _FakeMilvusException("collection not found", code=1)
    assert store_mod._is_transient_error(exc) is False


# =============================================================================
# store.py — _retry_async / _retry_sync
# =============================================================================


def test_retry_async_succeeds_first_try_no_delay(monkeypatch):
    sleeps = []
    monkeypatch.setattr(store_mod, "_sleep_backoff_async", _record_sleep_async(sleeps))
    attempts: list[dict] = []

    async def ok():
        return "done"

    result = asyncio.run(store_mod._retry_async("label", ok, attempts))

    assert result == "done"
    assert attempts == [{"n": 1, "error": None, "waited_s": 0.0}]
    assert sleeps == []


def _record_sleep_async(bucket):
    async def _fake(seconds):
        bucket.append(seconds)

    return _fake


def test_retry_async_retries_transient_then_succeeds(monkeypatch):
    sleeps = []
    monkeypatch.setattr(store_mod, "_sleep_backoff_async", _record_sleep_async(sleeps))
    attempts: list[dict] = []
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("refused")
        return "recovered"

    result = asyncio.run(store_mod._retry_async("label", flaky, attempts))

    assert result == "recovered"
    assert calls["n"] == 3
    assert sleeps == [2.0, 8.0]  # waited before attempts 2 and 3
    assert [a["n"] for a in attempts] == [1, 2, 3]
    assert attempts[0]["error"] == "refused"
    assert attempts[-1]["error"] is None


def test_retry_async_non_transient_raises_immediately_no_retry(monkeypatch):
    sleeps = []
    monkeypatch.setattr(store_mod, "_sleep_backoff_async", _record_sleep_async(sleeps))
    attempts: list[dict] = []

    async def boom():
        raise ValueError("bad shape")

    with pytest.raises(ValueError, match="bad shape"):
        asyncio.run(store_mod._retry_async("label", boom, attempts))

    assert sleeps == []  # no backoff wait for a non-transient error
    assert attempts == [{"n": 1, "error": "bad shape", "waited_s": 0.0}]


def test_retry_async_exhausts_all_backoff_slots_then_raises(monkeypatch):
    sleeps = []
    monkeypatch.setattr(store_mod, "_sleep_backoff_async", _record_sleep_async(sleeps))
    attempts: list[dict] = []

    async def always_503():
        raise _FakeMilvusException("unavailable", code=503)

    with pytest.raises(_FakeMilvusException):
        asyncio.run(store_mod._retry_async("label", always_503, attempts))

    # 1 initial + 3 backed-off retries = 4 total attempts; delays 2/8/30.
    assert len(attempts) == 4
    assert sleeps == [2.0, 8.0, 30.0]
    assert [a["n"] for a in attempts] == [1, 2, 3, 4]
    assert all(a["error"] == "unavailable" for a in attempts)


def test_retry_async_truncates_error_to_200_chars(monkeypatch):
    monkeypatch.setattr(store_mod, "_sleep_backoff_async", _record_sleep_async([]))
    attempts: list[dict] = []

    async def boom():
        raise ValueError("x" * 500)

    with pytest.raises(ValueError):
        asyncio.run(store_mod._retry_async("label", boom, attempts))

    assert len(attempts[0]["error"]) == 200


def test_retry_sync_mirrors_async_semantics(monkeypatch):
    sleeps = []
    monkeypatch.setattr(store_mod, "_sleep_backoff_sync", lambda s: sleeps.append(s))
    attempts: list[dict] = []
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise TimeoutError("timed out")
        return "ok"

    result = store_mod._retry_sync("label", flaky, attempts)

    assert result == "ok"
    assert sleeps == [2.0]
    assert [a["n"] for a in attempts] == [1, 2]


def test_retry_without_attempts_log_still_works(monkeypatch):
    """attempts_log is optional (default None) — callers that don't care
    about the audit trail (or existing/future callers of store_records/
    ingest_into_knowledge with no attempts_log) must not be forced to
    supply one."""
    monkeypatch.setattr(store_mod, "_sleep_backoff_async", _record_sleep_async([]))

    async def ok():
        return 42

    assert asyncio.run(store_mod._retry_async("label", ok, None)) == 42


# =============================================================================
# store.py — store_records / ingest_into_knowledge wired to retry
# =============================================================================


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return self._row if isinstance(self._row, list) else []


class _FakeConn:
    def __init__(self, engine):
        self._engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        self._engine.calls.append((str(stmt), params))
        if self._engine.raise_times > 0:
            self._engine.raise_times -= 1
            raise self._engine.exc_to_raise
        return _FakeResult(self._engine.row)


class _FakeEngine:
    def __init__(self, row=None, raise_times=0, exc_to_raise=None):
        self.calls: list[tuple] = []
        self.row = row
        self.raise_times = raise_times
        self.exc_to_raise = exc_to_raise or ConnectionError("db down")

    def connect(self):
        return _FakeConn(self)

    def begin(self):
        return _FakeConn(self)


def _artifact(artifact_id="1", sha256="a" * 64) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        sha256=sha256,
        source_ref="/tmp/x.txt",
        blob_key="aa/deadbeef/x.txt",
        size_bytes=10,
        duplicate=False,
        ingested_at="2026-07-21T00:00:00Z",
    )


def test_store_records_empty_list_is_noop():
    assert store_mod.store_records([], _artifact()) == 0


def test_store_records_retries_transient_db_error_then_succeeds(monkeypatch):
    fake = _FakeEngine(raise_times=1, exc_to_raise=ConnectionError("db down"))
    monkeypatch.setattr(store_mod, "_get_engine", lambda: fake)
    monkeypatch.setattr(store_mod, "_sleep_backoff_sync", lambda s: None)
    attempts: list[dict] = []

    rec = NormalizedRecord(source="chat", content="hi")
    n = store_mod.store_records([rec], _artifact(), attempts_log=attempts)

    assert n == 1
    assert len(attempts) == 2  # 1 failure + 1 success
    assert attempts[0]["error"] == "db down"
    assert attempts[1]["error"] is None


def test_store_records_non_transient_error_does_not_retry(monkeypatch):
    fake = _FakeEngine(raise_times=5, exc_to_raise=ValueError("bad column"))
    monkeypatch.setattr(store_mod, "_get_engine", lambda: fake)
    attempts: list[dict] = []

    rec = NormalizedRecord(source="chat", content="hi")
    with pytest.raises(ValueError, match="bad column"):
        store_mod.store_records([rec], _artifact(), attempts_log=attempts)

    assert len(fake.calls) == 1  # exactly one attempt — no retry loop entered
    assert len(attempts) == 1


def test_ingest_into_knowledge_retries_transient_then_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(store_mod, "_sleep_backoff_async", _record_sleep_async([]))
    calls = {"n": 0}

    class _FakeKnowledge:
        async def ainsert(self, **kwargs):
            calls["n"] += 1
            if calls["n"] < 2:
                raise TimeoutError("timed out")

    rec = NormalizedRecord(source="chat", conversation_id="A", role="user", content="hi")
    attempts: list[dict] = []
    n = asyncio.run(
        store_mod.ingest_into_knowledge(
            _FakeKnowledge(), [rec], _artifact(), "context", derived_dir=tmp_path, attempts_log=attempts
        )
    )

    assert n == 1
    assert calls["n"] == 2
    assert len(attempts) == 2
    assert attempts[0]["error"] == "timed out"
    assert attempts[1]["error"] is None


# =============================================================================
# store.py — load_records_for_artifact
# =============================================================================


def test_load_records_for_artifact_rebuilds_normalized_records(monkeypatch):
    rows = [
        {
            "record_type": "message",
            "source": "chat",
            "conversation_id": "A",
            "role": "user",
            "participants": json.dumps(["matt"]),  # raw jsonb text form
            "content": "hello",
            "occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "knowledge_time": datetime(2026, 1, 2, tzinfo=timezone.utc),
            "disclosure_tier": "contemporaneous",
            "attrs": {"parser_tool": "chatminer"},  # already-parsed dict form
        }
    ]
    fake = _FakeEngine(row=rows)
    monkeypatch.setattr(store_mod, "_get_engine", lambda: fake)

    records = store_mod.load_records_for_artifact("artifact-1")

    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, NormalizedRecord)
    assert rec.source == "chat"
    assert rec.conversation_id == "A"
    assert rec.participants == ["matt"]
    assert rec.attrs == {"parser_tool": "chatminer"}
    assert rec.content == "hello"


def test_load_records_for_artifact_empty(monkeypatch):
    fake = _FakeEngine(row=[])
    monkeypatch.setattr(store_mod, "_get_engine", lambda: fake)

    assert store_mod.load_records_for_artifact("no-such-artifact") == []


# =============================================================================
# workflows.py — on_error='fail' override (agno's actual default is 'skip')
# =============================================================================


def test_all_workflow_steps_override_on_error_to_fail():
    """agno's Step.on_error field defaults to OnError.skip (its class
    docstring claims 'fail' is the default — verified false against
    agno/workflow/step.py). Under that default, an uncaught exception in a
    step executor is silently converted into a 'skipped' StepOutput and the
    workflow keeps running with broken ctx state. Every Step this module
    builds must explicitly override to 'fail' so an uncaught exception
    halts the workflow immediately."""
    for builder in (workflows_mod.build_chat_transcript_workflow, workflows_mod.build_sms_xml_workflow):
        wf, _ctx = builder("does-not-need-to-exist.txt")
        for step in wf.steps:
            assert step.on_error == OnError.fail, f"{builder.__name__}: step {step.name!r} must set on_error='fail'"


def test_terminal_status_covers_agno_skip_converted_step_output():
    """Simulates exactly what agno's `_create_skipped_step_output` produces
    when on_error='skip' converts an uncaught step exception into a skipped
    step (StepOutput(success=False, error=str(exc), ...)) — _terminal_status
    must still map a 'completed'-status agno result to 'failed', so a stage
    that failed can never surface as a completed run even if on_error
    handling ever regresses back to agno's 'skip' default somewhere."""

    class _FakeStepResult:
        def __init__(self, success):
            self.success = success

    class _FakeRunResult:
        def __init__(self, status, step_results):
            self.status = status
            self.step_results = step_results

    skipped_due_to_error = _FakeStepResult(success=False)  # what _create_skipped_step_output produces
    result = _FakeRunResult("completed", [_FakeStepResult(True), skipped_due_to_error])

    assert workflows_mod._terminal_status({}, result) == "failed"


# =============================================================================
# workflows.py — _store_step_impl: the actual prod-bug fix (requirement 1)
# =============================================================================


def _dup_artifact(artifact_id="art-1") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        sha256="deadbeef" * 8,
        source_ref="/tmp/x.txt",
        blob_key="de/deadbeef/x.txt",
        size_bytes=10,
        duplicate=True,
        ingested_at="2026-07-21T00:00:00Z",
    )


def test_store_step_dedupe_no_parent_stays_the_old_silent_noop(monkeypatch):
    """No parent_run_id (a brand-new run, or a retry that isn't tracking a
    parent) — dedupe still just reports 0 rows / empty records, UNCHANGED
    pre-C2.6 behavior."""
    monkeypatch.setattr(workflows_mod, "record_counts", lambda artifact_id: {"records": 3})
    ctx = {"artifact": _dup_artifact(), "parent_run_id": None}

    result = workflows_mod._store_step_impl(ctx)

    assert result.success is True
    assert "skipped re-store" in result.content
    assert ctx["records"] == []
    assert ctx["stored"] == 0


def test_store_step_dedupe_parent_knowledge_ok_stays_the_old_silent_noop(monkeypatch):
    """parent_run_id IS set, but the parent's knowledge stage actually
    succeeded (e.g. this dedupe is from an unrelated duplicate upload, not a
    knowledge-stage-failure retry) — must NOT auto-route; nothing was lost."""
    monkeypatch.setattr(workflows_mod, "record_counts", lambda artifact_id: {"records": 3})
    monkeypatch.setattr(workflows_mod, "_parent_knowledge_failed", lambda parent_run_id: False)
    ctx = {"artifact": _dup_artifact(), "parent_run_id": "parent-1"}

    result = workflows_mod._store_step_impl(ctx)

    assert "skipped re-store" in result.content
    assert ctx["records"] == []


def test_store_step_dedupe_parent_knowledge_failed_auto_routes(monkeypatch):
    """THE FIX: parent_run_id set AND the parent's knowledge stage failed —
    reload the artifact's already-stored records and hand them to the
    knowledge step instead of silently reporting 0 records. This is what
    turns a would-be false-success (docs_ingested=0) into a real re-ingest."""
    monkeypatch.setattr(workflows_mod, "record_counts", lambda artifact_id: {"records": 2})
    monkeypatch.setattr(workflows_mod, "_parent_knowledge_failed", lambda parent_run_id: True)
    reloaded = [NormalizedRecord(source="chat", conversation_id="A", content="hi")]
    monkeypatch.setattr(workflows_mod, "load_records_for_artifact", lambda artifact_id: reloaded)
    ctx = {"artifact": _dup_artifact(artifact_id="art-9"), "parent_run_id": "parent-9"}

    result = workflows_mod._store_step_impl(ctx)

    assert result.success is True
    assert "auto-routing" in result.content
    assert "parent-9" in result.content
    assert ctx["records"] == reloaded
    assert ctx["stored"] == 0  # still 0 NEW rows stored — the records are inherited, not re-inserted


def test_store_step_fresh_artifact_stores_and_records_attempts(monkeypatch):
    """Non-dedupe path (a genuinely new artifact) — store_records is called
    with an attempts_log, and ctx['store_attempts'] carries it through for
    _ledger_stage_output."""
    monkeypatch.setattr(workflows_mod, "record_counts", lambda artifact_id: {"records": 0})

    captured = {}

    def fake_store_records(records, artifact, attempts_log=None):
        captured["attempts_log"] = attempts_log
        if attempts_log is not None:
            attempts_log.append({"n": 1, "error": None, "waited_s": 0.0})
        return len(records)

    monkeypatch.setattr(workflows_mod, "store_records", fake_store_records)
    artifact = ArtifactRef(
        artifact_id="new-1",
        sha256="c" * 64,
        source_ref="/tmp/y.txt",
        blob_key="cc/y.txt",
        size_bytes=5,
        duplicate=False,
        ingested_at="2026-07-21T00:00:00Z",
    )
    ctx = {
        "artifact": artifact,
        "parent_run_id": None,
        "raw_records": [{"source": "chat", "content": "hi"}],
        "parser_id": "chatminer",
    }

    result = workflows_mod._store_step_impl(ctx)

    assert result.success is True
    assert ctx["stored"] == 1
    assert ctx["store_attempts"] == [{"n": 1, "error": None, "waited_s": 0.0}]
    assert captured["attempts_log"] is ctx["store_attempts"]


# =============================================================================
# workflows.py — run_knowledge_from_store (the explicit from_stage='knowledge' path)
# =============================================================================


def test_run_knowledge_from_store_skips_first_three_stages_then_ingests(monkeypatch):
    stage_calls: list[tuple] = []
    monkeypatch.setattr(run_ledger, "stage_start", lambda run_id, seq: stage_calls.append(("start", seq)))
    monkeypatch.setattr(
        run_ledger,
        "stage_finish",
        lambda run_id, seq, status, content=None, output=None: stage_calls.append(("finish", seq, status, content)),
    )
    finish_calls = []
    monkeypatch.setattr(run_ledger, "finish_run", lambda *a, **k: finish_calls.append((a, k)))
    monkeypatch.setattr(
        workflows_mod,
        "load_records_for_artifact",
        lambda artifact_id: [NormalizedRecord(source="chat", conversation_id="A", content="hi")],
    )

    # ingest_into_knowledge itself (rendering markdown to disk + retry logic)
    # is unit-tested directly against store.py above — stub it here so this
    # test stays scoped to run_knowledge_from_store's OWN orchestration
    # (skip stages 1-3, run stage 4, build the summary) and never touches
    # the real filesystem via the default `knowledge/platform/transcripts`
    # derived_dir.
    async def fake_ingest(knowledge, records, artifact, domain, attempts_log=None):
        return len(records)

    monkeypatch.setattr(workflows_mod, "ingest_into_knowledge", fake_ingest)

    summary = asyncio.run(
        workflows_mod.run_knowledge_from_store(
            parent_run_id="parent-1",
            run_id="child-1",
            workflow="chat-transcript",
            domain="platform_design",
            knowledge=SimpleNamespace(),
            artifact_id="art-1",
            sha256="a" * 64,
            blob_key="aa/a/x.txt",
        )
    )

    # Stages 1-3 recorded skipped/"inherited from parent"; stage 4 ran for real.
    skipped = [c for c in stage_calls if c[0] == "finish" and c[1] in (1, 2, 3)]
    assert len(skipped) == 3
    assert all(c[2] == "skipped" and c[3] == "inherited from parent" for c in skipped)
    knowledge_finish = next(c for c in stage_calls if c[0] == "finish" and c[1] == 4)
    assert knowledge_finish[2] == "success"

    assert summary["status"] == "completed"
    assert summary["docs_ingested"] == 1
    assert summary["records_reused_from_parent"] == 1
    assert summary["parent_run_id"] == "parent-1"
    assert summary["retry_from_stage"] == "knowledge"
    assert "duration_ms" in summary

    assert finish_calls
    args, kwargs = finish_calls[0]
    assert args[0] == "child-1"
    assert args[1] == "completed"
    assert kwargs["artifact_id"] == "art-1"


def test_run_knowledge_from_store_zero_parent_records_fails_loudly(monkeypatch):
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: None)
    stage_finish_calls = []
    monkeypatch.setattr(
        run_ledger,
        "stage_finish",
        lambda run_id, seq, status, content=None, output=None: stage_finish_calls.append((seq, status, content)),
    )
    finish_calls = []
    monkeypatch.setattr(run_ledger, "finish_run", lambda *a, **k: finish_calls.append((a, k)))
    monkeypatch.setattr(workflows_mod, "load_records_for_artifact", lambda artifact_id: [])

    summary = asyncio.run(
        workflows_mod.run_knowledge_from_store(
            parent_run_id="parent-2",
            run_id="child-2",
            workflow="chat-transcript",
            domain="platform_design",
            knowledge=SimpleNamespace(),
            artifact_id="art-empty",
            sha256="b" * 64,
            blob_key=None,
        )
    )

    knowledge_stage = next(c for c in stage_finish_calls if c[0] == 4)
    assert knowledge_stage[1] == "failed"
    assert "0 rows" in knowledge_stage[2]
    assert summary["status"] == "failed"
    args, kwargs = finish_calls[0]
    assert args[1] == "failed"
    assert kwargs["error"] is not None


def test_run_knowledge_from_store_ingest_exception_marks_stage_and_run_failed(monkeypatch):
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: None)
    stage_finish_calls = []
    monkeypatch.setattr(
        run_ledger,
        "stage_finish",
        lambda run_id, seq, status, content=None, output=None: stage_finish_calls.append((seq, status, output)),
    )
    finish_calls = []
    monkeypatch.setattr(run_ledger, "finish_run", lambda *a, **k: finish_calls.append((a, k)))
    monkeypatch.setattr(
        workflows_mod,
        "load_records_for_artifact",
        lambda artifact_id: [NormalizedRecord(source="chat", conversation_id="A", content="hi")],
    )

    # Same reasoning as the happy-path test above: stub ingest_into_knowledge
    # directly (its own retry/error behavior is unit-tested against store.py
    # elsewhere in this file) so this test never touches the real filesystem.
    async def fake_ingest_raises(knowledge, records, artifact, domain, attempts_log=None):
        if attempts_log is not None:
            attempts_log.append({"n": 1, "error": "schema mismatch", "waited_s": 0.0})
        raise ValueError("schema mismatch")  # non-transient — fails on attempt 1

    monkeypatch.setattr(workflows_mod, "ingest_into_knowledge", fake_ingest_raises)

    summary = asyncio.run(
        workflows_mod.run_knowledge_from_store(
            parent_run_id="parent-3",
            run_id="child-3",
            workflow="chat-transcript",
            domain="platform_design",
            knowledge=SimpleNamespace(),
            artifact_id="art-3",
            sha256="c" * 64,
            blob_key=None,
        )
    )

    knowledge_stage = next(c for c in stage_finish_calls if c[0] == 4)
    assert knowledge_stage[1] == "failed"
    assert knowledge_stage[2]["attempts"][0]["error"] == "schema mismatch"
    assert summary["status"] == "failed"
    args, kwargs = finish_calls[0]
    assert kwargs["error"] == "schema mismatch"


# =============================================================================
# run_routes.py — POST /v1/runs/{id}/retry {"from_stage": "knowledge"}
# =============================================================================


@pytest.fixture
def run_routes_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import server.api.run_routes as run_routes

    app = FastAPI()
    run_routes.register_run_routes(app, knowledge=None)
    return run_routes, TestClient(app)


def test_retry_from_stage_422_unknown_value(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: {"status": "failed"})

    resp = client.post("/v1/runs/run-1/retry", json={"from_stage": "bogus"})
    assert resp.status_code == 422


def test_retry_from_stage_422_non_object_body(run_routes_client):
    run_routes, client = run_routes_client
    resp = client.post(
        "/v1/runs/run-1/retry",
        content=b'"just a string"',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


def test_retry_from_stage_knowledge_409_missing_artifact(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(
        run_routes,
        "get_run",
        lambda run_id: {"status": "failed", "artifact_id": None, "sha256": None, "stages": []},
    )

    resp = client.post("/v1/runs/run-1/retry", json={"from_stage": "knowledge"})
    assert resp.status_code == 409
    assert "artifact_id" in resp.json()["detail"]


def test_retry_from_stage_knowledge_409_parse_not_success(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(
        run_routes,
        "get_run",
        lambda run_id: {
            "status": "failed",
            "artifact_id": "art-1",
            "sha256": "a" * 64,
            "stages": [
                {"name": "custody", "status": "success", "output": {"blob_key": "aa/a/x.txt"}},
                {"name": "parse", "status": "failed"},
                {"name": "store", "status": "pending"},
                {"name": "knowledge", "status": "failed"},
            ],
        },
    )

    resp = client.post("/v1/runs/run-1/retry", json={"from_stage": "knowledge"})
    assert resp.status_code == 409
    assert "parse" in resp.json()["detail"]


def test_retry_from_stage_knowledge_202_happy_path(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(
        run_routes,
        "get_run",
        lambda run_id: {
            "status": "failed",
            "workflow": "chat-transcript",
            "domain": "platform_design",
            "mode": "auto",
            "custody_tier": "light",
            "source_name": "f.txt",
            "artifact_id": "art-1",
            "sha256": "a" * 64,
            "stages": [
                {"name": "custody", "status": "success", "output": {"blob_key": "aa/a/x.txt"}},
                {"name": "parse", "status": "success"},
                {"name": "store", "status": "success"},
                {"name": "knowledge", "status": "failed"},
            ],
        },
    )
    create_run_calls = []
    monkeypatch.setattr(
        run_routes,
        "create_run",
        lambda **kwargs: (create_run_calls.append(kwargs), "new-run-id")[1],
    )
    monkeypatch.setattr(run_routes, "seed_stages", lambda run_id, names: None)
    created_tasks = []

    def fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()  # never actually run it — no live DB/knowledge in this test
        return None

    monkeypatch.setattr(run_routes.asyncio, "create_task", fake_create_task)

    resp = client.post("/v1/runs/run-1/retry", json={"from_stage": "knowledge"})

    assert resp.status_code == 202
    assert resp.json() == {"run_id": "new-run-id", "parent_run_id": "run-1"}
    assert create_run_calls[0]["parent_run_id"] == "run-1"
    assert create_run_calls[0]["custody_tier"] == "light"
    assert len(created_tasks) == 1


def test_retry_no_body_still_does_full_rerun_409_when_not_failed(run_routes_client, monkeypatch):
    """Regression check: adding the Request/from_stage parsing must not
    break a bodyless POST (the pre-C2.6 client behavior)."""
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: {"status": "running"})

    resp = client.post("/v1/runs/run-1/retry")
    assert resp.status_code == 409


# =============================================================================
# run_routes.py — GET /v1/health/deps
# =============================================================================


def test_health_deps_both_ok(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "ping", lambda: None)

    class _FakeWeaviateClient:
        def is_ready(self):
            return True

    # _check_weaviate falls back to session.get_weaviate_client when the route
    # has no live knowledge handle (this fixture registers with knowledge=None).
    monkeypatch.setattr("server.core.session.get_weaviate_client", lambda: _FakeWeaviateClient(), raising=False)

    resp = client.get("/v1/health/deps")

    assert resp.status_code == 200
    body = resp.json()
    assert body["pg"] == {"status": "ok"}
    assert body["weaviate"] == {"status": "ok"}
    assert body["milvus"] == {"status": "ok"}  # deprecated alias of the weaviate check
    assert "checked_at" in body


def test_health_deps_pg_error_surfaces_message(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client

    def _boom():
        raise ConnectionError("pg unreachable")

    monkeypatch.setattr(run_routes, "ping", _boom)

    def _weaviate_down():
        raise ConnectionError("weaviate down")

    monkeypatch.setattr("server.core.session.get_weaviate_client", _weaviate_down, raising=False)

    resp = client.get("/v1/health/deps")

    assert resp.status_code == 200
    body = resp.json()
    assert body["pg"]["status"] == "error"
    assert "pg unreachable" in body["pg"]["error"]
    assert body["weaviate"]["status"] == "error"
    assert body["milvus"]["status"] == "error"  # deprecated alias
