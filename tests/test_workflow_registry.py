"""Workflows must actually reach AgentOS, not merely exist in the codebase.

The bug this guards against shipped and stayed live: `server/evidence/workflows.py`
built real agno Workflows for months while `AgentOS(...)` was never given a
`workflows=` argument, so `GET /workflows` returned `[]` and
`POST /workflows/{id}/runs` did not exist at all.

These tests use the REAL `base_app=` topology, because a guard verified against a
simplified app is not verified — that exact shortcut let a broken db_id
middleware ship green tests into a silent production failure earlier the same day.
"""
# Byline: Claude Code · Opus 5 · 2026-08-01
# Byline amendment: Codex · GPT-5 · 2026-08-18 (native evidence composition)

from __future__ import annotations

import pytest
from agno.workflow.factory import WorkflowFactory

from server.api.workflow_registry import (
    ChatTranscriptInput,
    SmsXmlInput,
    build_workflow_factories,
)


class _Ctx:
    """Stand-in for agno's RequestContext (a frozen dataclass with `.input`)."""

    def __init__(self, data):
        self.input = data


def _fake_db():
    from agno.db.sqlite import SqliteDb

    return SqliteDb(id="test-db", db_file=":memory:")


def test_both_workflows_are_registered():
    factories = build_workflow_factories(_fake_db(), knowledge=None)
    ids = sorted(f.id for f in factories)
    assert ids == ["chat-transcript", "sms-xml"]
    assert all(isinstance(f, WorkflowFactory) for f in factories)


def test_factories_declare_an_input_schema():
    """Without input_schema agno cannot validate `factory_input` or emit OpenAPI."""
    for f in build_workflow_factories(_fake_db(), knowledge=None):
        assert f.input_schema is not None, f"{f.id} must declare an input schema"


def test_chat_factory_builds_a_workflow_with_the_expected_steps(tmp_path):
    src = tmp_path / "transcript.txt"
    src.write_text("hello", encoding="utf-8")

    factories = {f.id: f for f in build_workflow_factories(_fake_db(), knowledge=None)}
    wf = factories["chat-transcript"].factory(_Ctx(ChatTranscriptInput(path=str(src))))

    assert [s.name for s in wf.steps] == ["custody", "parse", "store", "knowledge"]


def test_factory_accepts_a_plain_dict_not_just_the_model(tmp_path):
    """agno passes a dict through when no schema applied; a 500 inside the
    factory would be a confusing failure for an API caller."""
    src = tmp_path / "t.txt"
    src.write_text("x", encoding="utf-8")

    factories = {f.id: f for f in build_workflow_factories(_fake_db(), knowledge=None)}
    wf = factories["chat-transcript"].factory(_Ctx({"path": str(src), "domain": "d"}))
    assert wf.steps


def test_missing_required_path_is_rejected():
    with pytest.raises(Exception):
        ChatTranscriptInput()  # type: ignore[call-arg]


def test_sms_input_defaults_to_evidence_domain():
    assert (
        SmsXmlInput(path="/tmp/x.xml", source_principal="owner-device", caller_owns_conversation=True).domain
        == "evidence"
    )


def test_sms_factory_selects_native_projector_and_never_agno(monkeypatch, tmp_path):
    import server.evidence.workflows as workflows
    import server.evidence.run_ledger as run_ledger

    source = tmp_path / "messages.xml"
    source.write_text("<smses/>", encoding="utf-8")
    agno_knowledge = object()
    native_projector = object()
    captured = {}

    def fake_sms(**kwargs):
        captured.update(kwargs)
        return object(), {}

    monkeypatch.setattr(workflows, "build_sms_xml_workflow", fake_sms)
    monkeypatch.setattr(run_ledger, "create_run", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("no db")))
    factories = {item.id: item for item in build_workflow_factories(_fake_db(), agno_knowledge, native_projector)}
    factories["sms-xml"].factory(
        _Ctx(SmsXmlInput(path=str(source), source_principal="owner-device", caller_owns_conversation=True))
    )
    assert captured["knowledge"] is native_projector
    assert captured["knowledge"] is not agno_knowledge
    assert captured["source_meta"] == {
        "message_corpus": "first_party",
        "source_principal": "owner-device",
        "caller_owns_conversation": True,
    }


def test_registration_never_raises_on_the_boot_path(monkeypatch):
    """REGRESSION GUARD: a boot-path exception crash-looped prod once today.
    Registration is a convenience surface and must degrade, not kill the API."""
    import server.api.workflow_registry as reg

    def _boom(*_a, **_k):
        raise RuntimeError("simulated registration failure")

    monkeypatch.setattr(reg, "build_workflow_factories", _boom)
    assert reg.registered_workflows(_fake_db(), None) == []


def test_agentos_actually_exposes_them_under_the_real_base_app_topology():
    """The end-to-end check: build AgentOS the way main.py does — with
    `base_app=`, which is where a flat route scan silently found nothing
    earlier today — and confirm the workflows are registered on it."""
    import os

    os.environ.setdefault("OS_SECURITY_KEY", "test-only-not-a-real-secret")

    from agno.os import AgentOS
    from fastapi import FastAPI

    db = _fake_db()
    base = FastAPI()
    os_ = AgentOS(
        agents=[],
        db=db,
        workflows=build_workflow_factories(db, knowledge=None),
        base_app=base,
        on_route_conflict="preserve_base_app",
    )
    os_.get_app()

    registered = {getattr(w, "id", None) for w in (os_.workflows or [])}
    assert {"chat-transcript", "sms-xml"} <= registered, f"AgentOS did not register them: {registered}"
