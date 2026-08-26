# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""D-082 permanent AI-chat evidence fence (GAP-032/WP-C01) at the Workbench
promote service. A chat_export-detected staged file must be denied locally —
no HTTP call to the platform spine at all — while a doc-detected file keeps
its existing spine-promotion behavior unchanged."""

from __future__ import annotations

import httpx
from app.service import promote


def test_chat_export_is_denied_without_any_network_call(monkeypatch):
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("no HTTP call should be made for a chat_export promote attempt")

    monkeypatch.setattr(httpx.Client, "post", _must_not_be_called)
    monkeypatch.setattr(httpx.Client, "get", _must_not_be_called)

    result = promote._promote_chat_export({"id": "sha", "name": "x.json"}, client=object())

    assert result["status"] == "failed"
    assert result["denied"] is True
    assert "D-082" in result["error"]
    assert "permanent" in result["error"].lower()


def test_promote_dispatches_chat_export_to_the_denial_path(monkeypatch):
    monkeypatch.setattr(
        promote.staging,
        "get",
        lambda file_id: {
            "id": file_id,
            "name": "conversations.json",
            "detected_type": "chat_export",
            "meta": {},
            "r2_key": "irrelevant",
            "text": "",
        },
    )
    updates = []
    monkeypatch.setattr(
        promote.staging,
        "update_status",
        lambda file_id, status, promote_result=None: (
            updates.append((status, promote_result))
            or {"id": file_id, "status": status, "promote_result": promote_result}
        ),
    )

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("no HTTP call should be made for a chat_export promote attempt")

    monkeypatch.setattr(httpx.Client, "post", _must_not_be_called)
    monkeypatch.setattr(httpx.Client, "get", _must_not_be_called)

    result = promote.promote("sha")

    assert result["status"] == "failed"
    assert result["error"] is not None
    assert "D-082" in result["error"]
    # First update_status call is the "promoting" transition; second is the
    # terminal denial — confirms the denial is recorded, not silently dropped.
    assert updates[-1][0] == "failed"
    assert updates[-1][1]["denied"] is True


def test_doc_promote_path_is_unaffected(monkeypatch):
    """Regression guard: the fence must not touch the doc promote path."""
    calls = []

    def _fake_post(self, url, **kwargs):
        calls.append(url)

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"content_id": "abc123"}

        return _Resp()

    def _fake_get(self, url, **kwargs):
        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "completed"}

        return _Resp()

    monkeypatch.setattr(httpx.Client, "post", _fake_post)
    monkeypatch.setattr(httpx.Client, "get", _fake_get)
    monkeypatch.setattr(promote, "_load_file_bytes", lambda record: (b"hello", record["name"]))

    with httpx.Client() as client:
        result = promote._promote_doc({"id": "sha", "name": "doc.txt", "meta": {}}, client)

    assert result["status"] == "promoted"
    assert calls  # the spine WAS called for a doc — unlike chat_export
