"""Unit tests for the C0 operator-console run ledger.

Two things under test, both DB-free (fake-engine doubles, same style as
test_custody.py):

  1. server/evidence/run_ledger.py — the SQL round-trips (create_run,
     seed_stages, stage_start/finish, finish_run, get_run, list_runs).
  2. server/evidence/workflows.py — the ledger instrumentation added to
     run_chat_transcript/run_sms_xml: `run_id=None` must be a strict no-op
     (zero behavior change, the ledger is never imported/touched), and
     `run_id=<id>` must wrap every step + call finish_run in a `finally`.

No live Postgres, no real agno Workflow execution (that would fire agno's
telemetry HTTP call and needs Step executors that hit custody/registry/store)
— the Workflow class itself is monkeypatched with a lightweight fake so the
runner's own control flow (wrap-if-run_id / try-finally / summary shape) is
exercised without the spine underneath it.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-20

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from agno.workflow.types import StepOutput

import server.evidence.workflows as workflows_mod
from server.evidence import run_ledger

# --- sql/0005_workflow_run_ledger.sql -----------------------------------------

_SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "0005_workflow_run_ledger.sql"


def test_migration_file_exists():
    assert _SQL_PATH.is_file()


def test_migration_sql_parses():
    """SQL file parses — sqlparse if available, else skip (per task spec)."""
    sqlparse = pytest.importorskip("sqlparse")
    sql_text = _SQL_PATH.read_text(encoding="utf-8")
    statements = [s for s in sqlparse.parse(sql_text) if str(s).strip()]
    # 2x CREATE TABLE + 2x CREATE INDEX, at minimum.
    assert len(statements) >= 4


def test_migration_defines_both_tables_idempotently_with_uuidv7_pk():
    sql_text = _SQL_PATH.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS analysis.workflow_run " in sql_text
    assert "CREATE TABLE IF NOT EXISTS analysis.workflow_run_stage " in sql_text
    assert "DEFAULT uuidv7()" in sql_text
    assert "REFERENCES analysis.workflow_run(run_id)" in sql_text


# STUB: minimal fake SQLAlchemy engine used as a test double (no real DB) ---
# Mirrors tests/test_custody.py's _FakeEngine/_FakeConn/_FakeResult pattern.


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row

    def all(self):
        return self._row if isinstance(self._row, list) else []

    def scalar(self):
        return self._row


class _FakeConn:
    def __init__(self, engine):
        self._engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, stmt, params=None):
        self._engine.calls.append((str(stmt), params))
        return _FakeResult(self._engine._next_row())


class _FakeEngine:
    """Returns the queued rows in order, one per execute() call, and records
    every (sql_text, params) pair it was asked to run."""

    def __init__(self, rows):
        self._rows = list(rows)
        self._i = 0
        self.calls: list[tuple[str, object]] = []

    def _next_row(self):
        row = self._rows[self._i]
        self._i += 1
        return row

    def connect(self):
        return _FakeConn(self)

    def begin(self):
        return _FakeConn(self)


# --- run_ledger.py -----------------------------------------------------------


def test_run_ledger_importable():
    for name in ("create_run", "seed_stages", "stage_start", "stage_finish", "finish_run", "get_run", "list_runs"):
        assert callable(getattr(run_ledger, name))


def test_create_run_returns_run_id(monkeypatch):
    fake = _FakeEngine(["11111111-1111-1111-1111-111111111111"])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_id = run_ledger.create_run("chat-transcript", mode="auto", source_name="f.txt", domain="platform_design")

    assert run_id == "11111111-1111-1111-1111-111111111111"
    _, params = fake.calls[0]
    assert params["workflow"] == "chat-transcript"
    assert params["mode"] == "auto"
    assert params["source_name"] == "f.txt"


def test_seed_stages_empty_is_noop(monkeypatch):
    fake = _FakeEngine([])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.seed_stages("run-1", [])

    assert fake.calls == []  # never touches the engine for an empty stage list


def test_seed_stages_seeds_one_row_per_name_in_order(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.seed_stages("run-1", ["custody", "parse", "store", "knowledge"])

    assert len(fake.calls) == 1  # one bulk insert
    _, rows = fake.calls[0]
    assert [r["seq"] for r in rows] == [1, 2, 3, 4]  # 1-based (matches workflows.py's enumerate(..., start=1))
    assert [r["name"] for r in rows] == ["custody", "parse", "store", "knowledge"]
    assert all(r["run_id"] == "run-1" for r in rows)


def test_stage_start_sets_running(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.stage_start("run-1", 2)

    stmt, params = fake.calls[0]
    assert "running" in stmt
    assert params == {"run_id": "run-1", "seq": 2}


def test_stage_finish_serializes_output_and_content(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.stage_finish("run-1", 2, "success", content="parse: 3 records", output={"record_count": 3})

    _, params = fake.calls[0]
    assert params["status"] == "success"
    assert params["content"] == "parse: 3 records"
    assert json.loads(params["output"]) == {"record_count": 3}


def test_stage_finish_none_output_stays_none(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.stage_finish("run-1", 1, "failed", content="boom", output=None)

    _, params = fake.calls[0]
    assert params["output"] is None


def test_finish_run_serializes_summary(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.finish_run("run-1", "completed", summary={"records_stored": 5}, sha256="abc", artifact_id="7")

    _, params = fake.calls[0]
    assert params["status"] == "completed"
    assert json.loads(params["summary"]) == {"records_stored": 5}
    assert params["sha256"] == "abc"
    assert params["artifact_id"] == "7"


def test_get_run_missing_returns_none(monkeypatch):
    fake = _FakeEngine([None])  # run lookup -> no row
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    assert run_ledger.get_run("nope") is None


def test_get_run_found_parses_jsonb_and_orders_stages(monkeypatch):
    run_row = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "workflow": "chat-transcript",
        "status": "completed",
        "summary": '{"records_stored": 3}',  # raw jsonb text (some drivers hand back text)
    }
    stage_rows = [
        {
            "run_id": "11111111-1111-1111-1111-111111111111",
            "seq": 1,
            "name": "custody",
            "status": "success",
            "output": {"sha256": "abc"},  # already-parsed dict (other drivers do this)
        },
        {
            "run_id": "11111111-1111-1111-1111-111111111111",
            "seq": 2,
            "name": "parse",
            "status": "success",
            "output": None,
        },
    ]
    fake = _FakeEngine([run_row, stage_rows])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    result = run_ledger.get_run("11111111-1111-1111-1111-111111111111")

    assert result["run_id"] == "11111111-1111-1111-1111-111111111111"
    assert result["summary"] == {"records_stored": 3}
    assert [s["name"] for s in result["stages"]] == ["custody", "parse"]
    assert result["stages"][0]["output"] == {"sha256": "abc"}
    assert result["stages"][1]["output"] is None


def test_list_runs_groups_stages_per_run(monkeypatch):
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
            "status": "completed",
            "summary": {"x": 1},
            "error": None,
            "created_at": "t1",
            "updated_at": "t1",
            "seq": 1,
            "stage_name": "custody",
            "stage_status": "success",
        },
        {
            "run_id": "run-1",
            "workflow": "chat-transcript",
            "mode": "auto",
            "source_name": "a.txt",
            "source_path": "/tmp/a.txt",
            "sha256": "aa",
            "artifact_id": "1",
            "domain": "platform_design",
            "status": "completed",
            "summary": {"x": 1},
            "error": None,
            "created_at": "t1",
            "updated_at": "t1",
            "seq": 2,
            "stage_name": "parse",
            "stage_status": "success",
        },
    ]
    fake = _FakeEngine([rows])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    out = run_ledger.list_runs(limit=10)

    assert len(out) == 1
    assert out[0]["run_id"] == "run-1"
    assert [s["name"] for s in out[0]["stages"]] == ["custody", "parse"]


# --- workflows.py: stage-name/seq contract ------------------------------------


@pytest.mark.parametrize(
    "workflow_key,builder",
    [
        ("chat-transcript", workflows_mod.build_chat_transcript_workflow),
        ("sms-xml", workflows_mod.build_sms_xml_workflow),
    ],
)
def test_workflow_stage_names_match_actual_step_order(workflow_key, builder):
    wf, _ctx = builder("does-not-need-to-exist.txt")
    assert [s.name for s in wf.steps] == workflows_mod.WORKFLOW_STAGE_NAMES[workflow_key]


# --- workflows.py: _wrap_step_for_ledger / _ledger_stage_output / _terminal_status


def test_wrap_step_for_ledger_success_calls_start_then_finish(monkeypatch):
    calls = []
    monkeypatch.setattr(run_ledger, "stage_start", lambda run_id, seq: calls.append(("start", run_id, seq)))
    monkeypatch.setattr(
        run_ledger,
        "stage_finish",
        lambda run_id, seq, status, content=None, output=None: calls.append(("finish", run_id, seq, status, content)),
    )

    def original(step_input):
        return StepOutput(content="custody: ok", success=True)

    step = SimpleNamespace(name="custody", executor=original, active_executor=original)
    workflows_mod._wrap_step_for_ledger(step, 1, "run-1", {"artifact": None})

    assert inspect.iscoroutinefunction(step.executor)
    result = asyncio.run(step.executor("step-input"))

    assert result.content == "custody: ok"
    assert calls[0] == ("start", "run-1", 1)
    assert calls[1] == ("finish", "run-1", 1, "success", "custody: ok")


def test_wrap_step_for_ledger_failure_status_maps_from_success_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: None)
    monkeypatch.setattr(
        run_ledger,
        "stage_finish",
        lambda run_id, seq, status, content=None, output=None: calls.append(status),
    )

    def original(step_input):
        return StepOutput(content="parse: no candidates", success=False, stop=True)

    step = SimpleNamespace(name="parse", executor=original, active_executor=original)
    workflows_mod._wrap_step_for_ledger(step, 2, "run-1", {})

    asyncio.run(step.executor("x"))
    assert calls == ["failed"]


def test_wrap_step_for_ledger_exception_is_recorded_and_reraised(monkeypatch):
    calls = []
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: calls.append("start"))
    monkeypatch.setattr(
        run_ledger,
        "stage_finish",
        lambda run_id, seq, status, content=None, output=None: calls.append((status, content)),
    )

    def failing(step_input):
        raise ValueError("boom")

    step = SimpleNamespace(name="custody", executor=failing, active_executor=failing)
    workflows_mod._wrap_step_for_ledger(step, 1, "run-1", {})

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(step.executor("x"))

    assert calls == ["start", ("failed", "boom")]


def test_wrap_step_for_ledger_preserves_async_executor(monkeypatch):
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "stage_finish", lambda *a, **k: None)

    async def original(step_input):
        return StepOutput(content="knowledge: 1 doc", success=True)

    step = SimpleNamespace(name="knowledge", executor=original, active_executor=original)
    workflows_mod._wrap_step_for_ledger(step, 4, "run-1", {"domain": "platform_design"})

    result = asyncio.run(step.executor("x"))
    assert result.content == "knowledge: 1 doc"


def test_ledger_stage_output_custody_none_when_no_artifact():
    assert workflows_mod._ledger_stage_output("custody", {}) is None


def test_ledger_stage_output_parse_trims_samples_and_flags_schema():
    ctx = {
        "raw_records": [{"content": "x" * 600}] * 4,
        "parser_id": "messages.sms-xml",
        "attempts": [{"tool": "messages.sms-xml", "ok": True}],
        "parse_stats": {"n": 4},
    }
    out = workflows_mod._ledger_stage_output("parse", ctx)
    assert out["schema_recognized"] is True
    assert out["record_count"] == 4
    assert len(out["sample_records"]) == 3  # only first 3
    assert all(len(s) <= 500 for s in out["sample_records"])


def test_ledger_stage_output_store_and_knowledge():
    assert workflows_mod._ledger_stage_output("store", {"stored": 5}) == {
        "rows_stored": 5,
        "table": "analysis.normalized_record",
    }
    assert workflows_mod._ledger_stage_output(
        "knowledge", {"knowledge_docs": 2, "domain": "platform_design", "knowledge_skipped": False}
    ) == {"docs_ingested": 2, "domain": "platform_design", "skipped": False}


class _FakeRunResult:
    """Duck-types agno's WorkflowRunOutput just enough for _terminal_status:
    a `.status` (str or enum-like — agno's RunStatus doesn't override
    __str__, so a real member stringifies to 'RunStatus.completed') and
    `.step_results` (each with `.success`)."""

    def __init__(self, status, step_results=None):
        self.status = status
        self.step_results = step_results or []


class _FakeStepResult:
    def __init__(self, success=True):
        self.success = success


def test_terminal_status_paused_beats_everything():
    ctx = {"paused_decision": {"reason": "x"}}
    assert workflows_mod._terminal_status(ctx, _FakeRunResult("completed")) == "paused"


def test_terminal_status_none_result_is_failed():
    assert workflows_mod._terminal_status({}, None) == "failed"


def test_terminal_status_strips_enum_repr_before_mapping():
    # agno's RunStatus doesn't override __str__: str(status) == 'RunStatus.completed'
    assert workflows_mod._terminal_status({}, _FakeRunResult("RunStatus.completed")) == "completed"


def test_terminal_status_error_and_cancelled_map_to_failed():
    assert workflows_mod._terminal_status({}, _FakeRunResult("error")) == "failed"
    assert workflows_mod._terminal_status({}, _FakeRunResult("cancelled")) == "failed"


def test_terminal_status_pending_and_running_map_to_running():
    assert workflows_mod._terminal_status({}, _FakeRunResult("pending")) == "running"
    assert workflows_mod._terminal_status({}, _FakeRunResult("running")) == "running"


def test_terminal_status_unknown_status_defaults_to_failed():
    assert workflows_mod._terminal_status({}, _FakeRunResult("something-unexpected")) == "failed"


def test_terminal_status_completed_but_a_step_failed_is_still_failed():
    # agno marks the whole run 'completed' even when a step returned
    # success=False/stop=True (our parse-step's "no parser accepted this
    # file" path) — a clean agno status must not paper over a failed step.
    result = _FakeRunResult("completed", step_results=[_FakeStepResult(True), _FakeStepResult(False)])
    assert workflows_mod._terminal_status({}, result) == "failed"


# --- runners: run_id=None is a strict no-op; run_id=<id> wraps + finishes ----


class _FakeWorkflowResult:
    def __init__(self, status="COMPLETED"):
        self.status = status
        self.step_results: list = []


class _FakeWorkflow:
    """Stands in for agno.workflow.Workflow: keeps the Step list (so wrapping
    logic can be exercised/asserted) but never actually invokes a step
    executor, so none of custody/parse/store/knowledge ever touches a real
    DB or the tool registry, and agno's own telemetry never fires."""

    def __init__(self, name=None, description=None, steps=None):
        self.name = name
        self.description = description
        self.steps = steps or []

    async def arun(self, input):  # noqa: A002 - matches agno's kwarg name
        return _FakeWorkflowResult()


def test_run_chat_transcript_run_id_none_never_touches_ledger(monkeypatch, tmp_path):
    def _boom(*_a, **_k):
        raise AssertionError("ledger must not be touched when run_id is None")

    monkeypatch.setattr(run_ledger, "stage_start", _boom)
    monkeypatch.setattr(run_ledger, "stage_finish", _boom)
    monkeypatch.setattr(run_ledger, "finish_run", _boom)
    monkeypatch.setattr(workflows_mod, "Workflow", _FakeWorkflow)
    monkeypatch.setattr(workflows_mod, "load_builtin_tools", lambda: None)

    f = tmp_path / "transcript.txt"
    f.write_text("hello")

    summary = asyncio.run(workflows_mod.run_chat_transcript(str(f), knowledge=None))

    assert summary["workflow"] == "chat-transcript"
    assert summary["status"] == "COMPLETED"


def test_run_sms_xml_run_id_set_wraps_steps_and_calls_finish_run(monkeypatch, tmp_path):
    finish_calls = []
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "stage_finish", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "finish_run", lambda *a, **k: finish_calls.append((a, k)))
    monkeypatch.setattr(workflows_mod, "Workflow", _FakeWorkflow)
    monkeypatch.setattr(workflows_mod, "load_builtin_tools", lambda: None)

    f = tmp_path / "sms.xml"
    f.write_text("<smses></smses>")

    summary = asyncio.run(workflows_mod.run_sms_xml(str(f), knowledge=None, run_id="run-xyz"))

    assert summary["workflow"] == "sms-xml"
    assert finish_calls, "finish_run should be called from the runner's `finally` when run_id is set"
    args, kwargs = finish_calls[0]
    assert args[0] == "run-xyz"
    assert args[1] == "completed"  # no paused_decision, status has no 'FAIL' substring
    assert kwargs["summary"]["workflow"] == "sms-xml"


# --- run_routes.py: importability ---------------------------------------------


def test_run_routes_importable():
    from server.api.run_routes import register_run_routes

    assert callable(register_run_routes)
