"""Focused contract tests for the Workbench UIW BFF adapter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from app.runtime import uiw as runtime
from app.service import uiw
from starlette.requests import Request

from app.types.uiw import UIWDecisionRequest, UIWPreviewResponse, UIWStartRequest


PREVIEW_HANDLE = "preview_handle_abcdefghijklmnopqrstuvwxyz"
OTHER_PREVIEW_HANDLE = "preview_handle_zyxwvutsrqponmlkjihgfedcba"


def preview_payload(preview_handle: str = PREVIEW_HANDLE) -> dict:
    return {
        "preview_handle": preview_handle,
        "phase": "awaiting_decision",
        "correlation": {
            "request_id": "request-1",
            "source_version_id": "00000000-0000-0000-0000-000000000011",
            "raw_generation_id": "00000000-0000-0000-0000-000000000012",
            "normalized_generation_id": "00000000-0000-0000-0000-000000000013",
        },
        "parser": {
            "parser_id": "messages.sbv-xml-v1",
            "parser_version": "1.0.0",
            "config_digest": "a" * 64,
        },
        "preview_digest": "b" * 64,
        "receipts": [],
    }


def authenticated_request() -> Request:
    request = Request({"type": "http", "headers": []})
    request.state.subject_uid = "authentik-subject-123"
    request.state.principal = "matt"
    return request


def test_models_reject_unknown_fields() -> None:
    try:
        UIWStartRequest(
            request_id="r1",
            matter_id="00000000-0000-0000-0000-000000000001",
            court_case_id="00000000-0000-0000-0000-000000000002",
            source_ref=f"upload://{'a' * 64}",
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
            PREVIEW_HANDLE,
            UIWDecisionRequest(approved=False, reason=""),
            authenticated_request(),
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
            return {"preview_handle": PREVIEW_HANDLE}

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
                source_ref="r2://casebible-sorted/intake/source.pdf",
                declared_format="pdf",
                parser_options_ref="opts-1",
            )
        )

    result = asyncio.run(exercise())
    assert result.preview_handle == PREVIEW_HANDLE
    assert captured["method"] == "POST"
    assert captured["path"] == "/reference-import/start"
    assert captured["kwargs"]["json"]["source_ref"] == "r2://casebible-sorted/intake/source.pdf"
    assert captured["kwargs"]["json"]["matter_id"] == "00000000-0000-0000-0000-000000000001"
    assert captured["kwargs"]["json"]["court_case_id"] == "00000000-0000-0000-0000-000000000002"


def test_start_fails_closed_when_upstream_has_only_temporal_ids(monkeypatch) -> None:
    class Response:
        def json(self):
            return {"workflow_id": "wf-1", "run_id": "run-1"}

    async def fake_request(*args, **kwargs):
        return Response()

    monkeypatch.setattr(uiw, "_request", fake_request)

    async def exercise():
        await uiw.start(
            UIWStartRequest(
                request_id="r1",
                matter_id="00000000-0000-0000-0000-000000000001",
                court_case_id="00000000-0000-0000-0000-000000000002",
                source_ref=f"upload://{'a' * 64}",
                declared_format="pdf",
                parser_options_ref="opts-1",
            )
        )

    try:
        asyncio.run(exercise())
    except uiw.UIWError as error:
        assert error.status_code == 502
        assert "invalid start response" in error.detail
    else:
        raise AssertionError("Temporal identifiers must never be relabeled as a preview handle")


def test_decision_identity_is_derived_from_authentik_request_state(monkeypatch) -> None:
    captured = {}

    async def fake_decide(preview_handle, body, actor):
        captured.update(handle=preview_handle, body=body.model_dump(), actor=actor.model_dump())
        return {"preview_handle": PREVIEW_HANDLE, "status": "accepted"}

    monkeypatch.setattr(runtime, "decide", fake_decide)

    result = asyncio.run(
        runtime.decision_endpoint(
            PREVIEW_HANDLE,
            UIWDecisionRequest(approved=True, reason=""),
            authenticated_request(),
        )
    )
    assert result == {"preview_handle": PREVIEW_HANDLE, "status": "accepted"}
    assert captured["body"] == {"approved": True, "reason": ""}
    assert captured["actor"] == {
        "subject_uid": "authentik-subject-123",
        "username": "matt",
    }


def test_decision_fails_closed_without_authenticated_subject() -> None:
    request = Request({"type": "http", "headers": []})

    try:
        asyncio.run(
            runtime.decision_endpoint(
                PREVIEW_HANDLE,
                UIWDecisionRequest(approved=True, reason=""),
                request,
            )
        )
    except Exception as error:
        assert getattr(error, "status_code", None) == 401
    else:
        raise AssertionError("decision must require immutable proxy-authenticated identity")


def test_decision_model_rejects_browser_supplied_actor_fields() -> None:
    for forbidden in ({"decider": "owner"}, {"role": "owner"}, {"subject_uid": "forged"}):
        try:
            UIWDecisionRequest(approved=True, reason="", **forbidden)
        except Exception as error:
            assert "extra_forbidden" in str(error)
        else:
            raise AssertionError(f"browser actor field accepted: {next(iter(forbidden))}")


def test_preview_events_fail_closed_on_non_monotonic_replay() -> None:
    event = {
        "event_id": 5,
        "event_type": "phase_changed",
        "occurred_at": "2026-08-29T18:00:00Z",
        "preview_handle": PREVIEW_HANDLE,
        "phase": "awaiting_decision",
    }
    raw = f"id: 5\ndata: {json.dumps(event)}\n\nid: 5\ndata: {json.dumps(event)}\n\n"
    response = httpx.Response(200, content=raw.encode(), headers={"content-type": "text/event-stream"})

    async def exercise():
        emitted = []
        async for item in uiw.validated_preview_events(
            response, preview_handle=PREVIEW_HANDLE, last_event_id=4
        ):
            emitted.append(item)
        return emitted

    try:
        asyncio.run(exercise())
    except uiw.UIWError as error:
        assert error.status_code == 502
        assert "not monotonic" in error.detail
    else:
        raise AssertionError("duplicate UIW preview event ids must fail closed")


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


def test_preview_requires_full_correlation_and_digest() -> None:
    try:
        UIWPreviewResponse.model_validate({"preview_handle": PREVIEW_HANDLE, "phase": "awaiting_decision"})
    except Exception as error:
        assert "correlation" in str(error)
        assert "preview_digest" in str(error)
    else:
        raise AssertionError("partial preview snapshots must fail closed")


def test_service_fails_closed_without_dedicated_starter_configuration(monkeypatch) -> None:
    monkeypatch.setattr(uiw.settings, "uiw_starter_url", "")

    async def exercise():
        await uiw.start(
            UIWStartRequest(
                request_id="r1", source_ref=f"upload://{'a' * 64}", declared_format="pdf", parser_options_ref="opts-1"
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
            source_ref=f"upload://{'a' * 64}",
            declared_format="pdf",
            parser_options_ref="opts-1",
        )
    except Exception as error:
        assert "valid UUID" in str(error)
    else:
        raise AssertionError("malformed matter_id must be rejected")


def test_start_accepts_only_upload_or_fixed_casebible_sorted_scope() -> None:
    common = {
        "request_id": "r1",
        "matter_id": "00000000-0000-0000-0000-000000000001",
        "court_case_id": "00000000-0000-0000-0000-000000000002",
        "declared_format": "pdf",
        "parser_options_ref": "opts-1",
    }
    upload_ref = f"upload://{'a' * 64}"
    assert UIWStartRequest(source_ref=upload_ref, **common).source_ref == upload_ref
    assert (
        UIWStartRequest(source_ref="r2://casebible-sorted/folder/source.pdf", **common).source_ref
        == "r2://casebible-sorted/folder/source.pdf"
    )
    for forbidden in (
        "file:///etc/passwd",
        "b2://casebible-sorted/source.pdf",
        "r2://another-bucket/source.pdf",
        "r2://casebible-sorted/../source.pdf",
    ):
        try:
            UIWStartRequest(source_ref=forbidden, **common)
        except Exception as error:
            assert "Case Bible Sorted" in str(error)
        else:
            raise AssertionError(f"forbidden source scope accepted: {forbidden}")


def test_preview_snapshot_requires_exact_requested_handle(monkeypatch) -> None:
    class Response:
        def json(self):
            return preview_payload(OTHER_PREVIEW_HANDLE)

    async def fake_request(*args, **kwargs):
        return Response()

    monkeypatch.setattr(uiw, "_request", fake_request)
    try:
        asyncio.run(uiw.preview(PREVIEW_HANDLE))
    except uiw.UIWError as error:
        assert error.status_code == 502
        assert "snapshot correlation failed" in error.detail
    else:
        raise AssertionError("a snapshot for another preview handle must fail closed")


def test_preview_messages_require_exact_requested_handle(monkeypatch) -> None:
    class Response:
        def json(self):
            return {
                "preview_handle": OTHER_PREVIEW_HANDLE,
                "participants": [],
                "messages": [],
                "next_cursor": None,
            }

    async def fake_request(*args, **kwargs):
        return Response()

    monkeypatch.setattr(uiw, "_request", fake_request)
    try:
        asyncio.run(uiw.preview_messages(PREVIEW_HANDLE, cursor=None, limit=100))
    except uiw.UIWError as error:
        assert error.status_code == 502
        assert "message correlation failed" in error.detail
    else:
        raise AssertionError("a message page for another preview handle must fail closed")


def test_malformed_json_is_normalized_to_502(monkeypatch) -> None:
    class Response:
        def json(self):
            raise json.JSONDecodeError("bad", "{", 1)

    async def fake_request(*args, **kwargs):
        return Response()

    monkeypatch.setattr(uiw, "_request", fake_request)
    try:
        asyncio.run(uiw.preview(PREVIEW_HANDLE))
    except uiw.UIWError as error:
        assert error.status_code == 502
        assert "malformed JSON for preview snapshot" in error.detail
    else:
        raise AssertionError("malformed upstream JSON must use the BFF error contract")


def test_decision_response_requires_exact_requested_handle(monkeypatch) -> None:
    class Response:
        def json(self):
            return {"preview_handle": OTHER_PREVIEW_HANDLE, "status": "accepted"}

    async def fake_request(*args, **kwargs):
        return Response()

    monkeypatch.setattr(uiw, "_request", fake_request)
    try:
        asyncio.run(
            uiw.decide(
                PREVIEW_HANDLE,
                UIWDecisionRequest(approved=True, reason=""),
                uiw.UIWDecisionActor(subject_uid="subject-1", username="owner"),
            )
        )
    except uiw.UIWError as error:
        assert error.status_code == 502
        assert "decision response correlation failed" in error.detail
    else:
        raise AssertionError("a decision response for another preview handle must fail closed")
