"""Connection-order tests for deny-all Phase-1 Surreal sessions.

Byline: Codex · GPT-5 · 2026-08-17
"""

from typing import Any

import pytest

from horizon_surreal_phase1 import adapter
from horizon_surreal_phase1.identity import APPROVED_TARGET


class FakeSurreal:
    def __init__(self, endpoint: str) -> None:
        self.calls: list[tuple[str, Any]] = [("connect", endpoint)]

    async def __aenter__(self) -> "FakeSurreal":
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.calls.append(("close", None))

    async def signin(self, credentials: dict[str, str]) -> None:
        self.calls.append(("signin", credentials))

    async def authenticate(self, token: str) -> None:
        self.calls.append(("authenticate", token))

    async def use(self, namespace: str, database: str) -> None:
        self.calls.append(("use", (namespace, database)))


@pytest.mark.asyncio
async def test_record_token_authenticates_before_scoped_use(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSurreal("unused")
    monkeypatch.setattr(adapter, "AsyncSurreal", lambda _endpoint: connection)

    async with adapter.connect(APPROVED_TARGET, token="synthetic-token"):
        pass

    assert [name for name, _value in connection.calls] == [
        "connect",
        "authenticate",
        "use",
        "close",
    ]


@pytest.mark.asyncio
async def test_system_session_keeps_signin_before_scoped_use(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = FakeSurreal("unused")
    monkeypatch.setattr(adapter, "AsyncSurreal", lambda _endpoint: connection)

    credentials = {"username": "synthetic-root", "password": "synthetic-pass"}
    async with adapter.connect(APPROVED_TARGET, system_credentials=credentials):
        pass

    assert [name for name, _value in connection.calls] == [
        "connect",
        "signin",
        "use",
        "close",
    ]
