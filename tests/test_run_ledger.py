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


# =============================================================================
# C2 — supervised gates + retry/abort + two-tier custody
# (sql/0006_run_gates_and_custody_tier.sql)
# =============================================================================

# --- sql/0006_run_gates_and_custody_tier.sql -----------------------------------

_SQL_0006_PATH = Path(__file__).resolve().parents[1] / "sql" / "0006_run_gates_and_custody_tier.sql"


def test_migration_0006_file_exists():
    assert _SQL_0006_PATH.is_file()


def test_migration_0006_sql_parses():
    sqlparse = pytest.importorskip("sqlparse")
    sql_text = _SQL_0006_PATH.read_text(encoding="utf-8")
    statements = [s for s in sqlparse.parse(sql_text) if str(s).strip()]
    # 1x ALTER TABLE (3 columns) + 2x CREATE INDEX, at minimum.
    assert len(statements) >= 3


def test_migration_0006_adds_gate_state_parent_run_id_custody_tier_idempotently():
    sql_text = _SQL_0006_PATH.read_text(encoding="utf-8")
    assert "ALTER TABLE analysis.workflow_run" in sql_text
    assert "ADD COLUMN IF NOT EXISTS gate_state text" in sql_text
    assert "CHECK (gate_state IN ('waiting','released','abort') OR gate_state IS NULL)" in sql_text
    assert "ADD COLUMN IF NOT EXISTS parent_run_id uuid REFERENCES analysis.workflow_run(run_id)" in sql_text
    assert "ADD COLUMN IF NOT EXISTS custody_tier text NOT NULL DEFAULT 'full'" in sql_text
    assert "CHECK (custody_tier IN ('full','light'))" in sql_text


# --- run_ledger.py: create_run threads parent_run_id/custody_tier -------------


def test_create_run_defaults_custody_tier_full_and_no_parent(monkeypatch):
    fake = _FakeEngine(["11111111-1111-1111-1111-111111111111"])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.create_run("chat-transcript")

    _, params = fake.calls[0]
    assert params["custody_tier"] == "full"
    assert params["parent_run_id"] is None


def test_create_run_threads_parent_run_id_and_custody_tier(monkeypatch):
    fake = _FakeEngine(["22222222-2222-2222-2222-222222222222"])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.create_run(
        "chat-transcript",
        mode="supervised",
        parent_run_id="11111111-1111-1111-1111-111111111111",
        custody_tier="light",
    )

    _, params = fake.calls[0]
    assert params["parent_run_id"] == "11111111-1111-1111-1111-111111111111"
    assert params["custody_tier"] == "light"


# --- run_ledger.py: set_gate / read_gate / skip_remaining_stages --------------


def test_set_gate_state_only(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.set_gate("run-1", "waiting")

    stmt, params = fake.calls[0]
    assert "gate_state = :state" in stmt
    assert "status = :status" not in stmt  # no status param given -> status untouched
    assert params == {"run_id": "run-1", "state": "waiting"}


def test_set_gate_with_status_updates_both_in_one_statement(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.set_gate("run-1", "waiting", status="paused")

    stmt, params = fake.calls[0]
    assert "gate_state = :state" in stmt and "status = :status" in stmt
    assert params == {"run_id": "run-1", "state": "waiting", "status": "paused"}


def test_set_gate_none_clears_gate(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.set_gate("run-1", None, status="running")

    _, params = fake.calls[0]
    assert params["state"] is None
    assert params["status"] == "running"


def test_read_gate_returns_value(monkeypatch):
    fake = _FakeEngine([("waiting",)])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    assert run_ledger.read_gate("run-1") == "waiting"


def test_read_gate_missing_run_returns_none(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    assert run_ledger.read_gate("nope") is None


def test_skip_remaining_stages_filters_pending_after_seq(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.skip_remaining_stages("run-1", from_seq=2)

    stmt, params = fake.calls[0]
    assert "status = 'skipped'" in stmt
    assert "status = 'pending'" in stmt
    assert params == {"run_id": "run-1", "from_seq": 2}


def test_skip_remaining_stages_default_from_seq_zero(monkeypatch):
    fake = _FakeEngine([None])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    run_ledger.skip_remaining_stages("run-1")

    _, params = fake.calls[0]
    assert params["from_seq"] == 0


# --- run_ledger.py: get_run / list_runs surface gate_state/parent_run_id/custody_tier


def test_get_run_casts_parent_run_id_to_str_when_present(monkeypatch):
    run_row = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "workflow": "chat-transcript",
        "status": "failed",
        "gate_state": None,
        "parent_run_id": "22222222-2222-2222-2222-222222222222",  # e.g. a uuid.UUID in real driver output
        "custody_tier": "light",
        "summary": None,
    }
    fake = _FakeEngine([run_row, []])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    result = run_ledger.get_run("11111111-1111-1111-1111-111111111111")

    assert result["parent_run_id"] == "22222222-2222-2222-2222-222222222222"
    assert result["custody_tier"] == "light"


def test_get_run_parent_run_id_none_stays_none(monkeypatch):
    run_row = {
        "run_id": "11111111-1111-1111-1111-111111111111",
        "workflow": "chat-transcript",
        "status": "running",
        "gate_state": "waiting",
        "parent_run_id": None,
        "custody_tier": "full",
        "summary": None,
    }
    fake = _FakeEngine([run_row, []])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    result = run_ledger.get_run("11111111-1111-1111-1111-111111111111")

    assert result["parent_run_id"] is None
    assert result["gate_state"] == "waiting"


def test_list_runs_surfaces_gate_state_parent_and_tier(monkeypatch):
    rows = [
        {
            "run_id": "run-1",
            "workflow": "chat-transcript",
            "mode": "supervised",
            "source_name": "a.txt",
            "source_path": "/tmp/a.txt",
            "sha256": "aa",
            "artifact_id": "1",
            "domain": "platform_design",
            "status": "paused",
            "gate_state": "waiting",
            "parent_run_id": None,
            "custody_tier": "light",
            "summary": {"x": 1},
            "error": None,
            "created_at": "t1",
            "updated_at": "t1",
            "seq": 1,
            "stage_name": "custody",
            "stage_status": "success",
        },
    ]
    fake = _FakeEngine([rows])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    out = run_ledger.list_runs(limit=10)

    assert out[0]["gate_state"] == "waiting"
    assert out[0]["parent_run_id"] is None
    assert out[0]["custody_tier"] == "light"


def test_list_runs_defaults_missing_c2_columns_gracefully(monkeypatch):
    # Simulate a row shape from before this task's edits (no gate_state/
    # parent_run_id/custody_tier keys) — list_runs must not KeyError.
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
    ]
    fake = _FakeEngine([rows])
    monkeypatch.setattr(run_ledger, "_get_engine", lambda: fake)

    out = run_ledger.list_runs(limit=10)

    assert out[0]["gate_state"] is None
    assert out[0]["parent_run_id"] is None
    assert out[0]["custody_tier"] == "full"


# --- workflows.py: ArtifactRef custody_tier default + custody_step threading --


def test_ledger_stage_output_custody_includes_custody_tier():
    from server.evidence.custody import ArtifactRef

    artifact = ArtifactRef(
        artifact_id="1",
        sha256="abc123",
        source_ref="/tmp/x.txt",
        blob_key="ab/abc123/x.txt",
        size_bytes=10,
        duplicate=False,
        ingested_at="2026-07-20T00:00:00Z",
        custody_tier="light",
    )
    out = workflows_mod._ledger_stage_output("custody", {"artifact": artifact})
    assert out["custody_tier"] == "light"


@pytest.mark.parametrize(
    "builder,workflow_name",
    [
        (workflows_mod.build_chat_transcript_workflow, "chat-transcript"),
        (workflows_mod.build_sms_xml_workflow, "sms-xml"),
    ],
)
def test_build_workflow_defaults_custody_tier_full(builder, workflow_name):
    _wf, ctx = builder("does-not-need-to-exist.txt")
    assert ctx["custody_tier"] == "full"


@pytest.mark.parametrize(
    "builder",
    [workflows_mod.build_chat_transcript_workflow, workflows_mod.build_sms_xml_workflow],
)
def test_build_workflow_threads_custody_tier_override(builder):
    _wf, ctx = builder("does-not-need-to-exist.txt", custody_tier="light")
    assert ctx["custody_tier"] == "light"


def test_custody_step_passes_tier_to_ingest_artifact(monkeypatch, tmp_path):
    calls = []

    def fake_ingest_artifact(path, meta, *, tier="full"):
        calls.append(tier)
        return SimpleNamespace(
            sha256="deadbeef",
            duplicate=False,
            blob_key="de/deadbeef/f.txt",
            artifact_id="1",
            custody_tier=tier,
        )

    monkeypatch.setattr(workflows_mod, "ingest_artifact", fake_ingest_artifact)
    monkeypatch.setattr(workflows_mod, "load_builtin_tools", lambda: None)

    f = tmp_path / "f.txt"
    f.write_text("hi")
    wf, ctx = workflows_mod.build_chat_transcript_workflow(str(f), custody_tier="light")
    custody_step = wf.steps[0].executor
    custody_step(step_input=None)

    assert calls == ["light"]
    assert ctx["artifact"].custody_tier == "light"


# --- workflows.py: _terminal_status honors gate_aborted -----------------------


def test_terminal_status_gate_aborted_beats_a_clean_completed_result():
    ctx = {"gate_aborted": {"stage": "parse", "message": "aborted by operator at gate after parse"}}
    assert workflows_mod._terminal_status(ctx, _FakeRunResult("completed")) == "failed"


def test_terminal_status_gate_aborted_beats_paused_decision():
    # Shouldn't co-occur in practice, but gate_aborted must win if it did —
    # an operator abort is more specific/definitive than a parse-stage pause.
    ctx = {"gate_aborted": {"stage": "parse", "message": "x"}, "paused_decision": {"reason": "y"}}
    assert workflows_mod._terminal_status(ctx, _FakeRunResult("completed")) == "failed"


# --- workflows.py: _wrap_step_for_run_control ---------------------------------


def _make_success_step(name="parse", content="ok"):
    async def original(step_input, **kwargs):
        return StepOutput(content=content, success=True)

    return SimpleNamespace(name=name, executor=original, active_executor=original)


def test_run_control_auto_mode_passthrough_when_no_abort(monkeypatch):
    monkeypatch.setattr(run_ledger, "read_gate", lambda run_id: None)
    step = _make_success_step()
    ctx = {}

    workflows_mod._wrap_step_for_run_control(step, 2, 4, "run-1", ctx, "auto")
    result = asyncio.run(step.executor("x"))

    assert result.content == "ok"
    assert "gate_aborted" not in ctx


def test_run_control_auto_mode_honors_abort_at_boundary(monkeypatch):
    skip_calls = []
    monkeypatch.setattr(run_ledger, "read_gate", lambda run_id: "abort")
    monkeypatch.setattr(run_ledger, "skip_remaining_stages", lambda run_id, seq: skip_calls.append((run_id, seq)))
    step = _make_success_step(name="parse")
    ctx = {}

    workflows_mod._wrap_step_for_run_control(step, 2, 4, "run-1", ctx, "auto")
    result = asyncio.run(step.executor("x"))

    assert result.success is False
    assert result.stop is True
    assert ctx["gate_aborted"]["stage"] == "parse"
    assert skip_calls == [("run-1", 2)]


def test_run_control_failed_stage_bypasses_gate_entirely(monkeypatch):
    """A stage that already failed on its own must never be gated (no pause,
    no abort check) — nothing to approve into."""

    def _boom(*_a, **_k):
        raise AssertionError("must not touch the gate when the stage already failed")

    monkeypatch.setattr(run_ledger, "read_gate", _boom)
    monkeypatch.setattr(run_ledger, "set_gate", _boom)

    async def failing_original(step_input, **kwargs):
        return StepOutput(content="parse: no candidates", success=False, stop=True)

    step = SimpleNamespace(name="parse", executor=failing_original, active_executor=failing_original)
    workflows_mod._wrap_step_for_run_control(step, 1, 4, "run-1", {}, "supervised")

    result = asyncio.run(step.executor("x"))
    assert result.success is False


def test_run_control_supervised_last_stage_never_pauses(monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("the last stage must never open a pause gate")

    monkeypatch.setattr(run_ledger, "set_gate", _boom)
    monkeypatch.setattr(run_ledger, "read_gate", lambda run_id: None)
    step = _make_success_step(name="knowledge")

    workflows_mod._wrap_step_for_run_control(step, 4, 4, "run-1", {}, "supervised")
    result = asyncio.run(step.executor("x"))

    assert result.content == "ok"


def test_run_control_supervised_pauses_then_release_resumes(monkeypatch):
    gate_calls = []
    monkeypatch.setattr(run_ledger, "set_gate", lambda run_id, state, status=None: gate_calls.append((state, status)))
    read_gate_values = iter(["waiting", "released"])
    monkeypatch.setattr(run_ledger, "read_gate", lambda run_id: next(read_gate_values))
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(workflows_mod, "_gate_sleep", fake_sleep)
    step = _make_success_step(name="parse")

    workflows_mod._wrap_step_for_run_control(step, 1, 4, "run-1", {}, "supervised")
    result = asyncio.run(step.executor("x"))

    assert result.content == "ok"  # resumed, original result returned unchanged
    assert gate_calls[0] == ("waiting", "paused")  # pause on entry
    assert gate_calls[-1] == (None, "running")  # release clears the gate
    assert len(sleep_calls) == 2  # polled twice before seeing 'released'


def test_run_control_supervised_pauses_then_abort_stops_and_skips(monkeypatch):
    gate_calls = []
    monkeypatch.setattr(run_ledger, "set_gate", lambda run_id, state, status=None: gate_calls.append((state, status)))
    monkeypatch.setattr(run_ledger, "read_gate", lambda run_id: "abort")
    skip_calls = []
    monkeypatch.setattr(run_ledger, "skip_remaining_stages", lambda run_id, seq: skip_calls.append((run_id, seq)))
    monkeypatch.setattr(workflows_mod, "_gate_sleep", lambda seconds: asyncio.sleep(0))
    ctx = {}
    step = _make_success_step(name="custody")

    workflows_mod._wrap_step_for_run_control(step, 1, 4, "run-1", ctx, "supervised")
    result = asyncio.run(step.executor("x"))

    assert result.success is False
    assert result.stop is True
    assert ctx["gate_aborted"]["stage"] == "custody"
    assert "aborted by operator at gate after custody" in ctx["gate_aborted"]["message"]
    assert skip_calls == [("run-1", 1)]
    assert gate_calls[0] == ("waiting", "paused")


def test_run_control_supervised_timeout_is_treated_as_abort(monkeypatch):
    monkeypatch.setattr(run_ledger, "set_gate", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "read_gate", lambda run_id: "waiting")  # never released/aborted
    skip_calls = []
    monkeypatch.setattr(run_ledger, "skip_remaining_stages", lambda run_id, seq: skip_calls.append((run_id, seq)))
    monkeypatch.setattr(workflows_mod, "_gate_sleep", lambda seconds: asyncio.sleep(0))
    # Shrink the ceiling so the timeout branch is reachable in a fast test.
    monkeypatch.setattr(workflows_mod, "_GATE_POLL_CEILING_S", 4)
    monkeypatch.setattr(workflows_mod, "_GATE_POLL_INTERVAL_S", 2)
    ctx = {}
    step = _make_success_step(name="store")

    workflows_mod._wrap_step_for_run_control(step, 3, 4, "run-1", ctx, "supervised")
    result = asyncio.run(step.executor("x"))

    assert result.success is False
    assert "timed out" in ctx["gate_aborted"]["message"]
    assert skip_calls == [("run-1", 3)]


# --- runners: mode threads through to _wrap_step_for_run_control --------------


def test_run_chat_transcript_supervised_mode_wraps_run_control(monkeypatch, tmp_path):
    wrap_calls = []
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "stage_finish", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "finish_run", lambda *a, **k: None)
    monkeypatch.setattr(workflows_mod, "Workflow", _FakeWorkflow)
    monkeypatch.setattr(workflows_mod, "load_builtin_tools", lambda: None)
    monkeypatch.setattr(
        workflows_mod,
        "_wrap_step_for_run_control",
        lambda step, seq, total, run_id, ctx, mode: wrap_calls.append((seq, total, run_id, mode)),
    )

    f = tmp_path / "transcript.txt"
    f.write_text("hello")

    asyncio.run(workflows_mod.run_chat_transcript(str(f), knowledge=None, run_id="run-1", mode="supervised"))

    assert wrap_calls == [(1, 4, "run-1", "supervised"), (2, 4, "run-1", "supervised"), (3, 4, "run-1", "supervised"), (4, 4, "run-1", "supervised")]


def test_run_chat_transcript_run_id_none_never_wraps_run_control(monkeypatch, tmp_path):
    def _boom(*_a, **_k):
        raise AssertionError("run-control wrapping must not happen when run_id is None")

    monkeypatch.setattr(workflows_mod, "_wrap_step_for_run_control", _boom)
    monkeypatch.setattr(workflows_mod, "Workflow", _FakeWorkflow)
    monkeypatch.setattr(workflows_mod, "load_builtin_tools", lambda: None)

    f = tmp_path / "transcript.txt"
    f.write_text("hello")

    asyncio.run(workflows_mod.run_chat_transcript(str(f), knowledge=None))  # run_id=None default


def test_run_sms_xml_gate_aborted_populates_finish_run_error(monkeypatch, tmp_path):
    """When the run aborts at a gate, finish_run's error comes from
    ctx['gate_aborted']['message'] even though no exception was raised."""
    finish_calls = []
    monkeypatch.setattr(run_ledger, "stage_start", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "stage_finish", lambda *a, **k: None)
    monkeypatch.setattr(run_ledger, "finish_run", lambda *a, **k: finish_calls.append((a, k)))
    monkeypatch.setattr(workflows_mod, "Workflow", _FakeWorkflow)
    monkeypatch.setattr(workflows_mod, "load_builtin_tools", lambda: None)

    def _fake_run_control(step, seq, total, run_id, ctx, mode):
        if seq == 1:
            ctx["gate_aborted"] = {"stage": "custody", "message": "aborted by operator at gate after custody"}

    monkeypatch.setattr(workflows_mod, "_wrap_step_for_run_control", _fake_run_control)

    f = tmp_path / "sms.xml"
    f.write_text("<smses></smses>")

    asyncio.run(workflows_mod.run_sms_xml(str(f), knowledge=None, run_id="run-1", mode="supervised"))

    assert finish_calls
    args, kwargs = finish_calls[0]
    assert args[1] == "failed"
    assert kwargs["error"] == "aborted by operator at gate after custody"


# =============================================================================
# C2 — run_routes.py endpoints (continue / abort / retry) via TestClient
# =============================================================================


@pytest.fixture
def run_routes_client(monkeypatch):
    """A FastAPI app with only the run-ledger routes registered, run-ledger
    functions monkeypatched at the run_routes module level (this module does
    `from server.evidence.run_ledger import ...`, so patching run_ledger.X
    would NOT affect run_routes's already-bound name — patch run_routes.X)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import server.api.run_routes as run_routes

    app = FastAPI()
    run_routes.register_run_routes(app, knowledge=None)
    return run_routes, TestClient(app)


def test_continue_404_unknown_run(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: None)

    resp = client.post("/v1/runs/nope/continue")
    assert resp.status_code == 404


def test_continue_409_when_not_paused(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: {"status": "running"})

    resp = client.post("/v1/runs/run-1/continue")
    assert resp.status_code == 409


def test_continue_200_releases_gate_and_sets_running(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: {"status": "paused"})
    set_gate_calls = []
    monkeypatch.setattr(run_routes, "set_gate", lambda run_id, state, status=None: set_gate_calls.append((run_id, state, status)))

    resp = client.post("/v1/runs/run-1/continue")

    assert resp.status_code == 200
    assert resp.json() == {"run_id": "run-1", "status": "running"}
    assert set_gate_calls == [("run-1", "released", "running")]


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_abort_409_on_terminal_runs(run_routes_client, monkeypatch, status):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: {"status": status})

    resp = client.post("/v1/runs/run-1/abort")
    assert resp.status_code == 409


@pytest.mark.parametrize("status", ["paused", "running"])
def test_abort_200_on_paused_or_running(run_routes_client, monkeypatch, status):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: {"status": status})
    set_gate_calls = []
    monkeypatch.setattr(run_routes, "set_gate", lambda run_id, state, status=None: set_gate_calls.append((run_id, state)))

    resp = client.post("/v1/runs/run-1/abort")

    assert resp.status_code == 200
    assert resp.json() == {"run_id": "run-1", "status": "failed"}
    assert set_gate_calls == [("run-1", "abort")]


def test_abort_404_unknown_run(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: None)

    resp = client.post("/v1/runs/nope/abort")
    assert resp.status_code == 404


def test_retry_404_unknown_run(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: None)

    resp = client.post("/v1/runs/nope/retry")
    assert resp.status_code == 404


@pytest.mark.parametrize("status", ["running", "paused", "completed"])
def test_retry_409_when_not_failed(run_routes_client, monkeypatch, status):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "get_run", lambda run_id: {"status": status})

    resp = client.post("/v1/runs/run-1/retry")
    assert resp.status_code == 409


def test_retry_410_when_blob_and_source_path_both_missing(run_routes_client, monkeypatch, tmp_path):
    run_routes, client = run_routes_client
    monkeypatch.setattr(run_routes, "blob_root", lambda: tmp_path / "nowhere")
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
            "source_path": str(tmp_path / "gone.txt"),  # never created
            "stages": [{"name": "custody", "output": {"blob_key": "de/deadbeef/f.txt"}}],
        },
    )

    resp = client.post("/v1/runs/run-1/retry")
    assert resp.status_code == 410


def test_retry_202_prefers_blob_over_source_path(run_routes_client, monkeypatch, tmp_path):
    run_routes, client = run_routes_client

    blob_root_dir = tmp_path / "blobs"
    blob_key = "de/deadbeef/f.txt"
    blob_path = blob_root_dir / blob_key
    blob_path.parent.mkdir(parents=True)
    blob_path.write_bytes(b"pristine original bytes")
    monkeypatch.setattr(run_routes, "blob_root", lambda: blob_root_dir)

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
            "source_path": str(tmp_path / "long-gone.txt"),  # deliberately absent — blob must win
            "stages": [{"name": "custody", "output": {"blob_key": blob_key}}],
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
        coro.close()  # never actually run it — no live DB/workflow execution in this test
        return None

    monkeypatch.setattr(run_routes.asyncio, "create_task", fake_create_task)

    resp = client.post("/v1/runs/run-1/retry")

    assert resp.status_code == 202
    assert resp.json() == {"run_id": "new-run-id", "parent_run_id": "run-1"}
    assert len(create_run_calls) == 1
    assert create_run_calls[0]["parent_run_id"] == "run-1"
    assert create_run_calls[0]["custody_tier"] == "light"
    assert create_run_calls[0]["workflow"] == "chat-transcript"
    assert len(created_tasks) == 1


def test_start_run_defaults_custody_tier_light_for_chat_transcript(run_routes_client, monkeypatch, tmp_path):
    run_routes, client = run_routes_client
    create_run_calls = []
    monkeypatch.setattr(
        run_routes,
        "create_run",
        lambda **kwargs: (create_run_calls.append(kwargs), "new-run-id")[1],
    )
    monkeypatch.setattr(run_routes, "seed_stages", lambda run_id, names: None)
    monkeypatch.setattr(run_routes.asyncio, "create_task", lambda coro: coro.close())

    resp = client.post(
        "/v1/runs",
        files={"file": ("f.txt", b"hello", "text/plain")},
        data={"workflow": "chat-transcript"},
    )

    assert resp.status_code == 202
    assert create_run_calls[0]["custody_tier"] == "light"


def test_start_run_defaults_custody_tier_full_for_sms_xml(run_routes_client, monkeypatch, tmp_path):
    run_routes, client = run_routes_client
    create_run_calls = []
    monkeypatch.setattr(
        run_routes,
        "create_run",
        lambda **kwargs: (create_run_calls.append(kwargs), "new-run-id")[1],
    )
    monkeypatch.setattr(run_routes, "seed_stages", lambda run_id, names: None)
    monkeypatch.setattr(run_routes.asyncio, "create_task", lambda coro: coro.close())

    resp = client.post(
        "/v1/runs",
        files={"file": ("f.xml", b"<smses></smses>", "text/xml")},
        data={"workflow": "sms-xml"},
    )

    assert resp.status_code == 202
    assert create_run_calls[0]["custody_tier"] == "full"


def test_start_run_explicit_custody_tier_overrides_default(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client
    create_run_calls = []
    monkeypatch.setattr(
        run_routes,
        "create_run",
        lambda **kwargs: (create_run_calls.append(kwargs), "new-run-id")[1],
    )
    monkeypatch.setattr(run_routes, "seed_stages", lambda run_id, names: None)
    monkeypatch.setattr(run_routes.asyncio, "create_task", lambda coro: coro.close())

    resp = client.post(
        "/v1/runs",
        files={"file": ("f.txt", b"hello", "text/plain")},
        data={"workflow": "chat-transcript", "custody_tier": "full"},
    )

    assert resp.status_code == 202
    assert create_run_calls[0]["custody_tier"] == "full"


def test_start_run_422_unknown_custody_tier(run_routes_client, monkeypatch):
    run_routes, client = run_routes_client

    resp = client.post(
        "/v1/runs",
        files={"file": ("f.txt", b"hello", "text/plain")},
        data={"workflow": "chat-transcript", "custody_tier": "bogus"},
    )

    assert resp.status_code == 422
