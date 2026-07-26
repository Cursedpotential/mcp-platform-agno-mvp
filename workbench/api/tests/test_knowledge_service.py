# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
"""Unit tests for app/service/knowledge.py — the spine's HTTP calls are
mocked out (monkeypatch on app.service.knowledge.spine_json), so these never
touch the network. Covers: search() body construction (domain filter,
max_results), and list_contents()'s offset->page conversion.
"""

from __future__ import annotations

from app.service import knowledge


def test_search_minimal_body(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["kwargs"] = kwargs
        return {"data": [], "meta": {"total_count": 0}}

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    result = knowledge.search("what happened")

    assert captured["method"] == "POST"
    assert captured["path"] == "/knowledge/search"
    assert captured["kwargs"]["json"] == {"query": "what happened"}
    assert result == {"data": [], "meta": {"total_count": 0}}


def test_search_with_domain_and_limit(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured["kwargs"] = kwargs
        return {"data": []}

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    knowledge.search("custody chain", domain="legal_strategy", limit=5)

    body = captured["kwargs"]["json"]
    assert body["query"] == "custody chain"
    assert body["max_results"] == 5
    assert body["filters"] == {"domain": "legal_strategy"}


def test_search_domain_none_omits_filters(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        knowledge, "spine_json", lambda method, path, **kwargs: captured.setdefault("kwargs", kwargs) or {"data": []}
    )
    knowledge.search("q", domain=None)
    assert "filters" not in captured["kwargs"]["json"]


def test_list_contents_default_page(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["kwargs"] = kwargs
        return {"data": [], "meta": {"page": 1}}

    monkeypatch.setattr(knowledge, "spine_json", fake_spine_json)
    knowledge.list_contents()

    assert captured["method"] == "GET"
    assert captured["path"] == "/knowledge/content"
    assert captured["kwargs"]["params"] == {"limit": 20, "page": 1}


def test_list_contents_offset_converts_to_page(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        knowledge, "spine_json", lambda method, path, **kwargs: captured.setdefault("kwargs", kwargs) or {}
    )
    knowledge.list_contents(limit=20, offset=40)
    assert captured["kwargs"]["params"] == {"limit": 20, "page": 3}


def test_list_contents_offset_rounds_down_to_containing_page(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        knowledge, "spine_json", lambda method, path, **kwargs: captured.setdefault("kwargs", kwargs) or {}
    )
    knowledge.list_contents(limit=10, offset=25)  # midway through page 3 (0-based rows 20-29)
    assert captured["kwargs"]["params"] == {"limit": 10, "page": 3}
