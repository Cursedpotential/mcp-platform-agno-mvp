"""AgentOS-launched workflows go through the ledger + HITL gate (Codex C-03).

Byline: Claude Code . Opus 5 . 2026-08-04

The WorkflowFactory path called build_*_workflow directly: no
ops.workflow_run row, and the parsed `mode` was thrown away — so
mode='supervised' validated, ran straight through, and never paused. Two
launch paths, one of them silently weaker than the other. These tests pin the
fix so the weaker path cannot come back.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from server.api import workflow_registry as wr


class _FakeStep:
    def __init__(self, name):
        self.name = name
        self.executor = lambda step_input: None


class _FakeWorkflow:
    def __init__(self):
        self.steps = [_FakeStep("custody"), _FakeStep("parse"), _FakeStep("store")]


@pytest.fixture
def captured(monkeypatch):
    """Intercept the ledger + wrapping so nothing touches a database."""
    seen: dict = {"created": None, "attached": None}

    def fake_create_run(**kwargs):
        seen["created"] = kwargs
        return "run-abc123"

    def fake_attach(wf, ctx, run_id, mode="auto"):
        seen["attached"] = {"run_id": run_id, "mode": mode, "steps": len(wf.steps)}

    import server.evidence.run_ledger as ledger
    import server.evidence.workflows as workflows

    monkeypatch.setattr(ledger, "create_run", fake_create_run)
    monkeypatch.setattr(workflows, "attach_ledger", fake_attach)
    monkeypatch.setattr(workflows, "build_sms_xml_workflow", lambda **kw: (_FakeWorkflow(), {"ctx": True}))
    monkeypatch.setattr(
        workflows,
        "build_chat_transcript_workflow",
        lambda **kw: (_FakeWorkflow(), {"ctx": True}),
    )
    return seen


class _FakeDb:
    """agno's BaseFactory requires a non-None db for session storage; these
    tests never execute a workflow, so a marker object is enough."""

    id = "test-db"


def _factories():
    return {f.id: f for f in wr.build_workflow_factories(db=_FakeDb(), knowledge=None)}


# ADR-0059 (governed conversations) made SmsXmlInput require an authenticated
# first-party owner assertion: `source_principal` and `caller_owns_conversation`.
# These tests never execute a workflow, so any non-empty principal satisfies the
# contract — but the fields must be present or the factory 500s inside
# `_input_of` (server/api/workflow_registry.py:99) before reaching the ledger.
_OWNER_ASSERTION = {
    "source_principal": "owner@test-device",
    "caller_owns_conversation": True,
}


def test_sms_factory_creates_a_ledger_run(captured):
    f = _factories()["sms-xml"]
    f.factory(SimpleNamespace(input={"path": "/tmp/a.xml", "domain": "evidence", **_OWNER_ASSERTION}))
    assert captured["created"] is not None, "AgentOS launch must create a run row"
    assert captured["created"]["workflow"] == "sms-xml"
    assert captured["created"]["source_name"] == "a.xml"
    assert captured["attached"]["run_id"] == "run-abc123"


def test_supervised_mode_reaches_the_gate(captured):
    """The whole point: mode must survive the factory, not be parsed and dropped."""
    f = _factories()["sms-xml"]
    f.factory(SimpleNamespace(input={"path": "/tmp/a.xml", "mode": "supervised", **_OWNER_ASSERTION}))
    assert captured["created"]["mode"] == "supervised"
    assert captured["attached"]["mode"] == "supervised"


def test_chat_factory_is_ledgered_too(captured):
    f = _factories()["chat-transcript"]
    f.factory(SimpleNamespace(input={"path": "/tmp/t.md", "mode": "supervised"}))
    assert captured["created"]["workflow"] == "chat-transcript"
    assert captured["attached"]["mode"] == "supervised"


def test_ledger_failure_does_not_block_the_ingest(monkeypatch):
    """A dead ledger must degrade to an unledgered run, never kill the ingest."""
    import server.evidence.run_ledger as ledger
    import server.evidence.workflows as workflows

    def boom(**kwargs):
        raise RuntimeError("postgres unreachable")

    monkeypatch.setattr(ledger, "create_run", boom)
    monkeypatch.setattr(workflows, "build_sms_xml_workflow", lambda **kw: (_FakeWorkflow(), {}))
    f = _factories()["sms-xml"]
    wf = f.factory(SimpleNamespace(input={"path": "/tmp/a.xml", **_OWNER_ASSERTION}))
    assert wf is not None and len(wf.steps) == 3
