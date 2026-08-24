"""Contract tests for the INERT Temporal P1 skeleton (server/temporal/).

Byline: Claude Code . Opus 5 . 2026-08-23

These run with NO Temporal server, NO worker and NO database. They pin the four
properties that make the skeleton reviewable before anything dispatches to it:

  1. the four Activities are real ``@activity.defn``s with the expected names;
  2. ``ChatTranscriptIngest`` is a real ``@workflow.defn`` with a run method, a
     gate signal and a status query;
  3. every payload dataclass survives a round-trip through temporalio's DEFAULT
     payload converter (a workflow whose params do not serialize fails at
     dispatch, not at review time);
  4. the harness selector picks by env, defaults to agno, and the pydantic_ai
     side raises the install-extra error rather than silently degrading.

They also pin the determinism boundary: importing ``server.temporal.workflows``
must not drag ``server.core.url`` / ``server.core.session`` (module-level env
reads) into the process, per the plan's replay-determinism constraint.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import subprocess
import sys

import pytest

from server.temporal import activities as acts
from server.temporal import knowledge_harness as kh
from server.temporal import workflows as twf


# ---------------------------------------------------------------------------
# 1. Activities
# ---------------------------------------------------------------------------

_EXPECTED_ACTIVITIES = {
    "custody_activity": acts.custody_activity,
    "parse_activity": acts.parse_activity,
    "store_activity": acts.store_activity,
    "knowledge_activity": acts.knowledge_activity,
}


@pytest.mark.parametrize("name", sorted(_EXPECTED_ACTIVITIES))
def test_activity_is_a_registered_defn_with_the_expected_name(name):
    from temporalio.activity import _Definition

    fn = _EXPECTED_ACTIVITIES[name]
    defn = _Definition.from_callable(fn)
    assert defn is not None, f"{name} is not an @activity.defn"
    assert defn.name == name


def test_all_activities_export_matches_the_four_stages():
    assert [getattr(fn, "__name__", None) for fn in acts.ALL_ACTIVITIES] == [
        "custody_activity",
        "parse_activity",
        "store_activity",
        "knowledge_activity",
    ]


def test_knowledge_activity_is_async_the_others_are_sync():
    # The knowledge harness contract is async (it awaits _knowledge_step_impl);
    # custody/parse/store call sync platform functions and must stay sync so the
    # worker runs them off the event loop.
    assert asyncio.iscoroutinefunction(acts.knowledge_activity)
    assert not asyncio.iscoroutinefunction(acts.custody_activity)
    assert not asyncio.iscoroutinefunction(acts.parse_activity)
    assert not asyncio.iscoroutinefunction(acts.store_activity)


# ---------------------------------------------------------------------------
# 2. Workflow
# ---------------------------------------------------------------------------


def test_chat_transcript_ingest_is_a_workflow_defn():
    from temporalio.workflow import _Definition

    defn = _Definition.from_class(twf.ChatTranscriptIngest)
    assert defn is not None, "ChatTranscriptIngest is not a @workflow.defn"
    assert defn.name == "ChatTranscriptIngest"
    assert defn.run_fn is not None


def test_workflow_exposes_the_gate_signal_and_status_query():
    from temporalio.workflow import _Definition

    defn = _Definition.from_class(twf.ChatTranscriptIngest)
    assert "gate_decision" in defn.signals
    assert "status" in defn.queries


def test_gate_signal_ignores_an_unrecognized_decision(monkeypatch):
    # A signal handler that raises fails the whole workflow task; an operator
    # typo must not be able to kill a run.
    #
    # workflow.logger refuses to emit outside a workflow event loop (it asks the
    # runtime whether history is replaying), so the reject branch gets a plain
    # stdlib logger here. That is a test seam only — production keeps the
    # replay-aware logger.
    monkeypatch.setattr(twf.workflow, "logger", logging.getLogger("test.temporal.gate"))
    wf = twf.ChatTranscriptIngest()
    wf.gate_decision("banana")
    assert wf.status()["gate"] is None
    wf.gate_decision("  ABORT ")
    assert wf.status()["gate"] == twf.GATE_ABORT
    wf.gate_decision(twf.GATE_APPROVE)
    assert wf.status()["gate"] == twf.GATE_APPROVE


def test_workflow_module_does_not_import_env_reading_modules():
    """Replay determinism: workflow code must not touch env/network at import.

    server/core/url.py:27 and server/core/session.py read env at MODULE level,
    so neither may appear in the import graph of the workflow module. Checked in
    a clean interpreter because the rest of this test session imports plenty."""
    code = (
        "import sys; import server.temporal.workflows;"
        "bad=[m for m in ('server.core.url','server.core.session') if m in sys.modules];"
        "print(','.join(bad))"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "", f"workflow module import pulled in {proc.stdout.strip()}"


# ---------------------------------------------------------------------------
# 3. Payload round-trip through temporalio's default converter
# ---------------------------------------------------------------------------


def _round_trip(value):
    from temporalio.converter import DataConverter

    converter = DataConverter.default.payload_converter
    payloads = converter.to_payloads([value])
    return converter.from_payloads(payloads, [type(value)])[0]


_PAYLOAD_SAMPLES = [
    acts.CustodyParams(path="/tmp/x.json", source_meta={"k": "v"}, custody_tier="light"),
    acts.CustodyResult(
        artifact_id="a-1",
        sha256="0" * 64,
        source_ref="/tmp/x.json",
        blob_key="blobs/ab/cd",
        size_bytes=12,
        duplicate=False,
        ingested_at="2026-08-23T00:00:00+00:00",
        custody_tier="light",
    ),
    acts.ParseParams(path="/tmp/x.json", source_meta={}),
    acts.ParseResult(
        parser_id="parse.transcript.chatgpt",
        record_count=1,
        records=[{"record_type": "message", "text": "hi"}],
        attempts=[{"tool": "parse.transcript.chatgpt", "ok": True}],
        stats={"conversations": 1},
    ),
    acts.StoreParams(artifact_id="a-1", records=[{"record_type": "message"}], parser_id="p"),
    acts.StoreResult(stored=3, record_count=3, dedupe_noop=False, detail="store: 3 rows"),
    acts.KnowledgeParams(artifact_id="a-1", lane="context", run_meta={"run_id": "r-1"}),
    kh.KnowledgeResult(
        docs_ingested=2,
        skipped=False,
        detail="knowledge: 2 conversation doc(s)",
        harness="agno",
        lane="context",
    ),
    kh.RecordsRef(artifact_id="a-1", record_ids=["r1", "r2"]),
    twf.ChatTranscriptInput(path="/tmp/x.json", supervised=True),
    twf.ChatTranscriptOutput(status="completed", artifact_id="a-1", docs_ingested=2),
]


@pytest.mark.parametrize("value", _PAYLOAD_SAMPLES, ids=lambda v: type(v).__name__)
def test_payload_dataclass_round_trips_through_the_default_converter(value):
    assert _round_trip(value) == value


@pytest.mark.parametrize("value", _PAYLOAD_SAMPLES, ids=lambda v: type(v).__name__)
def test_payload_types_are_dataclasses(value):
    assert dataclasses.is_dataclass(value)


# ---------------------------------------------------------------------------
# 4. The bake selector
# ---------------------------------------------------------------------------


def test_get_harness_defaults_to_agno(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_HARNESS", raising=False)
    from server.temporal.knowledge_harness import agno_harness

    assert kh.get_harness() is agno_harness.run_knowledge_step
    assert kh.DEFAULT_HARNESS == "agno"


def test_get_harness_selects_pydantic_ai_by_name():
    from server.temporal.knowledge_harness import pydantic_ai_harness

    assert kh.get_harness("pydantic_ai") is pydantic_ai_harness.run_knowledge_step


def test_blank_env_value_is_treated_as_unset():
    from server.temporal.knowledge_harness import agno_harness

    assert kh.get_harness("   ") is agno_harness.run_knowledge_step


def test_unknown_harness_is_a_hard_error():
    with pytest.raises(ValueError, match="unknown KNOWLEDGE_HARNESS"):
        kh.get_harness("crewai")


def test_knowledge_activity_reads_the_env_and_dispatches(monkeypatch):
    """knowledge_activity itself holds no projection logic — it selects."""
    seen: dict = {}

    async def fake_step(records_ref, lane, run_meta):
        seen["args"] = (records_ref.artifact_id, lane, run_meta)
        return kh.KnowledgeResult(docs_ingested=7, skipped=False, detail="fake", harness="fake", lane=lane)

    monkeypatch.setenv("KNOWLEDGE_HARNESS", "pydantic_ai")
    monkeypatch.setattr(acts, "get_harness", lambda name: (_assert_name(seen, name), fake_step)[1])

    result = asyncio.run(acts.knowledge_activity(acts.KnowledgeParams(artifact_id="a-1", lane="context")))
    assert result.docs_ingested == 7
    assert seen["args"][0] == "a-1"
    assert seen["selector"] == "pydantic_ai"


def _assert_name(seen: dict, name: str) -> None:
    seen["selector"] = name


def test_pydantic_ai_harness_names_the_extra_when_the_package_is_absent():
    try:
        import pydantic_ai  # noqa: F401
    except ImportError:
        pass
    else:
        pytest.skip("pydantic-ai is installed; the install-extra path cannot be exercised")

    from server.temporal.knowledge_harness import pydantic_ai_harness

    with pytest.raises(RuntimeError, match="temporal-bake"):
        asyncio.run(pydantic_ai_harness.run_knowledge_step(kh.RecordsRef(artifact_id="a-1"), "context", {}))
