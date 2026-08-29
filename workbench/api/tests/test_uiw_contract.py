"""Focused contract tests for the Workbench UIW BFF adapter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

import asyncio

import httpx

from app.runtime import uiw as runtime
from app.service import uiw
from app.types.uiw import UIWDecisionRequest, UIWPreviewResponse, UIWStartRequest


def test_models_reject_unknown_fields() -> None:
    try:
        UIWStartRequest(
            request_id="r1",
            matter_id="00000000-0000-0000-0000-000000000001",
            court_case_id="00000000-0000-0000-0000-000000000002",
            source_ref="source-1",
            declared_format="pdf",
            parser_options_ref="opts-1",
            content="forbidden",
        )
    except Exception as error:
        assert "extra_forbidden" in str(error)
    else:
        raise AssertionError("unknown UIW start fields must be rejected")


def test_decision_route_rejects_without_reason() -> None:
    async def exercise():
        return await runtime.decision_endpoint(
            "workflow-1",
            UIWDecisionRequest(approved=False, reason="", decider="owner"),
        )

    try:
        asyncio.run(exercise())
    except Exception as error:
        assert getattr(error, "status_code", None) == 422
        assert "reason" in str(error.detail)
    else:
        raise AssertionError("blank rejection reason must be rejected")


def test_service_preserves_exact_upstream_contract(monkeypatch) -> None:
    class Response:
        def json(self):
            return {"workflow_id": "wf-1", "run_id": "run-1"}

    captured = {}
    monkeypatch.setattr(uiw.settings, "uiw_starter_url", "https://starter.internal")

    async def fake_request(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return Response()

    monkeypatch.setattr(uiw, "_request", fake_request)

    async def exercise():
        return await uiw.start(
            UIWStartRequest(
                request_id="r1",
                matter_id="00000000-0000-0000-0000-000000000001",
                court_case_id="00000000-0000-0000-0000-000000000002",
                source_ref="source-1",
                declared_format="pdf",
                parser_options_ref="opts-1",
            )
        )

    result = asyncio.run(exercise())
    assert result.workflow_id == "wf-1"
    assert result.run_id == "run-1"
    assert captured["method"] == "POST"
    assert captured["path"] == "/reference-import/start"
    assert captured["kwargs"]["json"]["source_ref"] == "source-1"
    assert captured["kwargs"]["json"]["matter_id"] == "00000000-0000-0000-0000-000000000001"
    assert captured["kwargs"]["json"]["court_case_id"] == "00000000-0000-0000-0000-000000000002"


def test_service_does_not_forward_authorization(monkeypatch) -> None:
    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, **kwargs):
            assert "Authorization" not in kwargs["headers"]
            assert "authorization" not in kwargs["headers"]
            return httpx.Response(200, json={"workflow_id": "wf-1", "run_id": "run-1"})

    monkeypatch.setattr(uiw.settings, "uiw_starter_url", "https://starter.internal")
    monkeypatch.setattr(uiw.httpx, "AsyncClient", Client)

    async def exercise():
        return await uiw._request(
            "GET", "/reference-import/wf-1/preview", headers={"Authorization": "forbidden"}
        )

    asyncio.run(exercise())


def test_preview_allows_blank_select_ref_before_selection() -> None:
    state = UIWPreviewResponse.model_validate({"phase": "awaiting_decision", "select_ref": ""})
    assert state.select_ref == ""


def test_service_fails_closed_without_dedicated_starter_configuration(monkeypatch) -> None:
    monkeypatch.setattr(uiw.settings, "uiw_starter_url", "")

    async def exercise():
        await uiw.start(
            UIWStartRequest(
                request_id="r1", source_ref="source-1", declared_format="pdf", parser_options_ref="opts-1"
                , matter_id="00000000-0000-0000-0000-000000000001", court_case_id="00000000-0000-0000-0000-000000000002"
            )
        )

    try:
        asyncio.run(exercise())
    except uiw.UIWError as error:
        assert error.status_code == 503
    else:
        raise AssertionError("UIW must fail closed when its dedicated settings are absent")


def test_start_rejects_malformed_matter_uuid() -> None:
    try:
        UIWStartRequest(
            request_id="r1",
            matter_id="not-a-uuid",
            court_case_id="00000000-0000-0000-0000-000000000002",
            source_ref="source-1",
            declared_format="pdf",
            parser_options_ref="opts-1",
        )
    except Exception as error:
        assert "valid UUID" in str(error)
    else:
        raise AssertionError("malformed matter_id must be rejected")
