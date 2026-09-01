"""Authenticated conversation-intake runtime contracts.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.runtime import runs as runtime


class _Request:
    def __init__(self, payload: dict, principal: str | None = "owner"):
        self._payload = payload
        self.state = SimpleNamespace()
        if principal is not None:
            self.state.principal = principal

    async def json(self) -> dict:
        return self._payload


def test_json_intake_derives_acquisition_asserter(monkeypatch) -> None:
    captured = {}

    async def fake_start(**kwargs):
        captured.update(kwargs)
        return {"run_id": "r1"}

    monkeypatch.setattr(runtime, "start_run", fake_start)
    request = _Request(
        {
            "staged_id": "sha",
            "workflow": "chat-transcript",
            "domain": "evidence",
            "message_corpus": "acquired_third_party",
            "source_principal": "export-account",
            "acquisition": {
                "acquired_at": "2026-08-18T12:00:00Z",
                "method": "legal_process",
                "authority": "court_order",
            },
        }
    )

    result = asyncio.run(runtime._start_from_json(request))

    assert result == {"run_id": "r1"}
    assert captured["acquisition"]["asserted_by"] == "owner"
    assert captured["acquisition"]["asserted_by_category"] == "human"


def test_json_intake_does_not_accept_caller_asserted_by(monkeypatch) -> None:
    called = False

    async def fake_start(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(runtime, "start_run", fake_start)
    request = _Request(
        {
            "staged_id": "sha",
            "workflow": "chat-transcript",
            "message_corpus": "acquired_third_party",
            "source_principal": "export-account",
            "acquisition": {
                "acquired_at": "2026-08-18T12:00:00Z",
                "asserted_by": "spoofed",
            },
        }
    )

    try:
        asyncio.run(runtime._start_from_json(request))
    except Exception as error:
        assert getattr(error, "status_code", None) == 422
    else:
        raise AssertionError("caller-supplied asserted_by was accepted")
    assert called is False


def test_json_intake_requires_authenticated_owner() -> None:
    request = _Request(
        {
            "staged_id": "sha",
            "workflow": "chat-transcript",
            "message_corpus": "first_party",
            "source_principal": "owner-account",
            "caller_owns_conversation": True,
        },
        principal=None,
    )
    try:
        asyncio.run(runtime._start_from_json(request))
    except Exception as error:
        assert getattr(error, "status_code", None) == 401
    else:
        raise AssertionError("unauthenticated first-party assertion was accepted")
