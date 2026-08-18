"""Workbench submission tests for the neutral Horizon ingest port.

Byline: Codex · GPT-5 · 2026-08-16
Byline: Codex · GPT-5 · 2026-08-18 (conversation source-boundary forwarding)
"""

from __future__ import annotations

import json

from app.service import runs


class _Response:
    def json(self) -> dict:
        return {"run_id": "receipt-1", "workflow": "framework-neutral-ingest", "mode": "auto"}


def test_sms_submission_uses_neutral_ingest_and_sbv_coverage(monkeypatch) -> None:
    seen = {}

    def fake_request(method, path, **kwargs):
        seen.update(method=method, path=path, kwargs=kwargs)
        return _Response()

    monkeypatch.setattr(runs, "_spine_request", fake_request)
    result = runs.start_run(
        workflow="sms-xml",
        domain="evidence",
        file_bytes=b"<smses/>",
        filename="sms.xml",
        source_meta={"case_id": "matter-a"},
        message_corpus="first_party",
        source_principal="owner-phone",
        caller_owns_conversation=True,
    )

    assert result["run_id"] == "receipt-1"
    assert seen["path"] == "/v1/ingest"
    assert seen["kwargs"]["data"] == {
        "lane": "evidence",
        "matter_id": "matter-a",
        "engine": "auto",
        "allow_fallback": "false",
        "custody_tier": "full",
        "coverage_hint": "smsbackuprestore-xml",
        "source_identity": json.dumps({"case_id": "matter-a"}),
        "message_corpus": "first_party",
        "source_principal": "owner-phone",
        "caller_owns_conversation": "true",
    }


def test_chat_submission_maps_legacy_domain_to_neutral_lane(monkeypatch) -> None:
    seen = {}

    def fake_request(method, path, **kwargs):
        seen.update(path=path, kwargs=kwargs)
        return _Response()

    monkeypatch.setattr(runs, "_spine_request", fake_request)
    runs.start_run(
        workflow="chat-transcript",
        domain="platform_design",
        file_bytes=b"hello",
        filename="chat.md",
        message_corpus="first_party",
        source_principal="owner-account",
        caller_owns_conversation=True,
    )
    assert seen["path"] == "/v1/ingest"
    assert seen["kwargs"]["data"]["lane"] == "platform"
    assert seen["kwargs"]["data"]["custody_tier"] == "light"


def test_acquired_third_party_forwards_authenticated_acquisition(monkeypatch) -> None:
    seen = {}

    def fake_request(method, path, **kwargs):
        seen.update(path=path, kwargs=kwargs)
        return _Response()

    monkeypatch.setattr(runs, "_spine_request", fake_request)
    acquisition = {
        "acquired_at": "2026-08-18T12:00:00Z",
        "method": "legal_process",
        "authority": "court_order",
        "asserted_by_category": "human",
        "asserted_by": "owner",
    }
    runs.start_run(
        workflow="chat-transcript",
        domain="evidence",
        file_bytes=b"third party",
        filename="thread.txt",
        message_corpus="acquired_third_party",
        source_principal="exported-account",
        caller_owns_conversation=False,
        acquisition=acquisition,
    )

    form = seen["kwargs"]["data"]
    assert form["message_corpus"] == "acquired_third_party"
    assert form["source_principal"] == "exported-account"
    assert json.loads(form["acquisition"])["asserted_by"] == "owner"


def test_first_party_rejects_missing_ownership_confirmation() -> None:
    try:
        runs.start_run(
            workflow="chat-transcript",
            domain="evidence",
            file_bytes=b"text",
            filename="thread.txt",
            message_corpus="first_party",
            source_principal="owner-account",
            caller_owns_conversation=False,
        )
    except runs.RunsError as error:
        assert error.status_code == 400
        assert "ownership confirmation" in error.detail
    else:
        raise AssertionError("missing ownership confirmation was accepted")
