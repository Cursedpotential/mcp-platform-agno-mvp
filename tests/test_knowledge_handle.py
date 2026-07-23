"""Unit tests for server/core/knowledge_handle.py — the C3 spine boot
resilience primitive (operator-console-requirements.md addendum 9's boot-time
follow-through: make agentos-api survive Milvus being down at boot).

No live Milvus/DB — the factory is a plain Python callable the tests fully
control (raises on demand, or returns a sentinel "connected" object).
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-22

from __future__ import annotations

import asyncio

from server.core.knowledge_handle import KnowledgeHandle, resolve_knowledge


class _Sentinel:
    """Stands in for a real Knowledge instance — identity is all that matters."""


def test_try_connect_now_success():
    instance = _Sentinel()
    handle = KnowledgeHandle(lambda: instance)

    ok = handle.try_connect_now()

    assert ok is True
    assert handle.ready is True
    assert handle.instance is instance
    assert handle.last_error is None
    assert handle.attempts == 1


def test_try_connect_now_never_raises_on_factory_failure():
    def _boom():
        raise ConnectionError("Milvus unreachable")

    handle = KnowledgeHandle(_boom)

    ok = handle.try_connect_now()  # must NOT raise

    assert ok is False
    assert handle.ready is False
    assert handle.instance is None
    assert "Milvus unreachable" in handle.last_error
    assert handle.attempts == 1


def test_try_connect_now_is_idempotent_once_connected():
    calls = []

    def _factory():
        calls.append(1)
        return _Sentinel()

    handle = KnowledgeHandle(_factory)
    handle.try_connect_now()
    handle.try_connect_now()  # second call must be a no-op (factory not re-invoked)

    assert len(calls) == 1
    assert handle.attempts == 1


def test_try_connect_now_can_be_retried_after_failure():
    attempts_log = []

    def _factory():
        attempts_log.append(1)
        if len(attempts_log) < 2:
            raise ConnectionError("still down")
        return _Sentinel()

    handle = KnowledgeHandle(_factory)

    assert handle.try_connect_now() is False
    assert handle.try_connect_now() is True
    assert handle.ready is True
    assert handle.attempts == 2


# --- background retry loop ---------------------------------------------------


def test_start_background_retry_is_noop_when_already_connected():
    handle = KnowledgeHandle(lambda: _Sentinel())
    handle.try_connect_now()

    handle.start_background_retry()

    assert handle._retry_task is None  # never scheduled — nothing to retry


def test_background_retry_eventually_connects(monkeypatch):
    attempts_log = []

    def _factory():
        attempts_log.append(1)
        if len(attempts_log) < 3:
            raise ConnectionError("still down")
        return _Sentinel()

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    handle = KnowledgeHandle(_factory, retry_interval_s=60.0)
    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    assert handle.try_connect_now() is False  # attempt 1, fails

    async def _run():
        handle.start_background_retry()
        await handle._retry_task

    asyncio.run(_run())

    assert handle.ready is True
    assert handle.attempts == 3
    assert sleep_calls == [60.0, 60.0]  # slept before attempts 2 and 3


def test_stop_background_retry_cancels_pending_task():
    async def _never_succeeds():
        while True:
            await asyncio.sleep(1000)

    handle = KnowledgeHandle(lambda: (_ for _ in ()).throw(ConnectionError("down")))

    async def _run():
        handle.try_connect_now()
        handle._retry_task = asyncio.create_task(_never_succeeds())
        handle.stop_background_retry()
        await asyncio.sleep(0)  # let cancellation propagate
        assert handle._retry_task.cancelled() or handle._retry_task.cancelling()

    asyncio.run(_run())


# --- resolve_knowledge --------------------------------------------------------


def test_resolve_knowledge_reads_handle_instance_live():
    handle = KnowledgeHandle(lambda: None)
    assert resolve_knowledge(handle) is None  # not connected yet

    instance = _Sentinel()
    handle._instance = instance  # simulate a background reconnect swap
    assert resolve_knowledge(handle) is instance  # fresh read, not a stale snapshot


def test_resolve_knowledge_passes_through_non_handle_values():
    assert resolve_knowledge(None) is None
    raw = _Sentinel()
    assert resolve_knowledge(raw) is raw
