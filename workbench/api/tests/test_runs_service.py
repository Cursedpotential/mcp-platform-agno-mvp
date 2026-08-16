"""Workbench submission tests for the neutral Horizon ingest port.

Byline: Codex · GPT-5 · 2026-08-16
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
    )
    assert seen["path"] == "/v1/ingest"
    assert seen["kwargs"]["data"]["lane"] == "platform"
    assert seen["kwargs"]["data"]["custody_tier"] == "light"
