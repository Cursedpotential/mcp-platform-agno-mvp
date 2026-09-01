# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
"""Unit tests for app/service/graphiti.py — the MCP transport is mocked out
(monkeypatch on app.service.graphiti.graphiti_client.call_tool), so these
never touch the network. Covers: default group_id, tool-name/argument
wiring for search_facts/search_nodes, and get_episodes' over-fetch +
client-side sort-by-created_at-descending + slice.
"""

from __future__ import annotations

import pytest

from app.service import graphiti


def test_search_facts_default_group(monkeypatch):
    captured = {}

    def fake_call(name, arguments):
        captured["name"] = name
        captured["arguments"] = arguments
        return {"facts": [{"uuid": "f1", "fact": "X is Y"}]}

    monkeypatch.setattr(graphiti.graphiti_client, "call_tool", lambda url, name, arguments: fake_call(name, arguments))
    result = graphiti.search_facts("what is X")

    assert captured["name"] == "search_memory_facts"
    assert captured["arguments"] == {"query": "what is X", "group_ids": ["platform"], "max_facts": 10}
    assert result["facts"][0]["fact"] == "X is Y"


def test_search_facts_custom_group_and_max(monkeypatch):
    captured = {}
    monkeypatch.setattr(graphiti.settings, "graphiti_allowed_groups", "platform,case-bible")
    monkeypatch.setattr(
        graphiti.graphiti_client,
        "call_tool",
        lambda url, name, arguments: captured.setdefault("arguments", arguments) or {"facts": []},
    )
    graphiti.search_facts("q", group_ids=["case-bible"], max_facts=5)
    assert captured["arguments"] == {"query": "q", "group_ids": ["case-bible"], "max_facts": 5}


def test_search_rejects_group_outside_server_allowlist(monkeypatch):
    monkeypatch.setattr(graphiti.settings, "graphiti_allowed_groups", "platform")
    monkeypatch.setattr(
        graphiti.graphiti_client,
        "call_tool",
        lambda *args, **kwargs: pytest.fail("denied group must not reach Graphiti"),
    )

    with pytest.raises(ValueError, match="not authorized"):
        graphiti.search_facts("q", group_ids=["guessed-case-group"])


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_search_rejects_out_of_bounds_limit(limit):
    with pytest.raises(ValueError, match="between 1 and 100"):
        graphiti.search_nodes("q", max_nodes=limit)


def test_search_nodes_default_group(monkeypatch):
    captured = {}

    def fake_call(url, name, arguments):
        captured["name"] = name
        captured["arguments"] = arguments
        return {"nodes": [{"uuid": "n1", "name": "Matt"}]}

    monkeypatch.setattr(graphiti.graphiti_client, "call_tool", fake_call)
    result = graphiti.search_nodes("who is Matt")

    assert captured["name"] == "search_nodes"
    assert captured["arguments"] == {"query": "who is Matt", "group_ids": ["platform"], "max_nodes": 10}
    assert result["nodes"][0]["name"] == "Matt"


def test_get_episodes_overfetches_and_sorts_descending(monkeypatch):
    captured = {}
    episodes = [
        {"uuid": "e1", "created_at": "2026-07-01T00:00:00Z"},
        {"uuid": "e2", "created_at": "2026-07-20T00:00:00Z"},  # newest, but NOT first in raw order
        {"uuid": "e3", "created_at": "2026-07-10T00:00:00Z"},
    ]

    def fake_call(url, name, arguments):
        captured["name"] = name
        captured["arguments"] = arguments
        return {"episodes": episodes}

    monkeypatch.setattr(graphiti.graphiti_client, "call_tool", fake_call)
    result = graphiti.get_episodes(last=2)

    assert captured["name"] == "get_episodes"
    # requested last=2, but must over-fetch to the floor (50) upstream —
    # trusting a small max_episodes upstream can silently drop true recents
    # (server does not return created_at order — see module docstring).
    assert captured["arguments"] == {"group_ids": ["platform"], "max_episodes": 50}
    assert [e["uuid"] for e in result["episodes"]] == ["e2", "e3"]  # newest-first, sliced to 2


def test_get_episodes_respects_last_above_floor(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        graphiti.graphiti_client,
        "call_tool",
        lambda url, name, arguments: captured.setdefault("arguments", arguments) or {"episodes": []},
    )
    graphiti.get_episodes(last=100)
    assert captured["arguments"]["max_episodes"] == 100


def test_get_episodes_rejects_negative_last():
    with pytest.raises(ValueError, match="between 1 and 100"):
        graphiti.get_episodes(last=-1)
