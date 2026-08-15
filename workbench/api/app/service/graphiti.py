# Byline: Claude Code · Sonnet (agent) · 2026-07-23 (C4: Knowledge browser + Graphiti pane)
"""Search + browse against Graphiti (Neo4j-backed knowledge-graph memory) for
the C4 Knowledge page's "Graph memory" pane. Read-only: search_memory_facts,
search_nodes, get_episodes — the same three read tools the `grc` CLI
(graphiti-client skill) exposes over the identical MCP endpoint.
add_memory/clear_graph/delete_* are deliberately NOT wired here — console-
driven writes to Graphiti are out of scope for C4 (owner write-discipline:
one focused episode per durable fact, `grc add` stays the only writer).

Default group_id "platform" matches grc.py's DEFAULT_GROUP. Caller-provided
groups are accepted only when present in the server-side allowlist; a Graphiti
namespace is never treated as authorization.

get_episodes over-fetches (floor 50) and sorts client-side by created_at
descending before slicing to the requested count: Graphiti's get_episodes
does NOT return results in created_at order (verified live — see the
graphiti-client skill's references/failure-modes.md gotcha #2), so trusting
the first N as "the newest N" silently drops real recent episodes. Same fix
grc.py's cmd_episodes already applies; duplicated here rather than imported
since this module can't reach into a CLI script.
"""

from __future__ import annotations

from app.config import settings
from app.repo import graphiti_client
from app.repo.graphiti_client import McpError as GraphitiError

__all__ = ["GraphitiError", "search_facts", "search_nodes", "get_episodes"]

_DEFAULT_GROUP = "platform"
_EPISODES_FETCH_FLOOR = 50


def _call(name: str, arguments: dict) -> dict:
    return graphiti_client.call_tool(settings.graphiti_mcp_url, name, arguments)


def _authorized_groups(group_ids: list[str] | None) -> list[str]:
    requested = group_ids or [_DEFAULT_GROUP]
    normalized = [group.strip() for group in requested if group.strip()]
    if not normalized:
        raise ValueError("at least one Graphiti group is required")
    allowed = settings.graphiti_allowed_group_set
    denied = sorted(set(normalized) - allowed)
    if denied:
        raise ValueError("Graphiti group is not authorized")
    return normalized


def _bounded_count(value: int | None, *, default: int) -> int:
    effective = default if value is None else value
    if effective < 1 or effective > 100:
        raise ValueError("Graphiti result limit must be between 1 and 100")
    return effective


def search_facts(query: str, *, group_ids: list[str] | None = None, max_facts: int | None = None) -> dict:
    """search_memory_facts -> {facts: [{uuid, fact, valid_at, group_id, ...}]}."""
    return _call(
        "search_memory_facts",
        {
            "query": query,
            "group_ids": _authorized_groups(group_ids),
            "max_facts": _bounded_count(max_facts, default=10),
        },
    )


def search_nodes(query: str, *, group_ids: list[str] | None = None, max_nodes: int | None = None) -> dict:
    """search_nodes -> {nodes: [{uuid, name, labels, summary, ...}]}."""
    return _call(
        "search_nodes",
        {
            "query": query,
            "group_ids": _authorized_groups(group_ids),
            "max_nodes": _bounded_count(max_nodes, default=10),
        },
    )


def get_episodes(*, group_ids: list[str] | None = None, last: int | None = None) -> dict:
    """get_episodes -> {episodes: [...]}, freshest `last` first (client-sorted
    — see module docstring for why the raw server order can't be trusted)."""
    n = _bounded_count(last, default=10)
    fetch_n = max(n, _EPISODES_FETCH_FLOOR)
    result = _call("get_episodes", {"group_ids": _authorized_groups(group_ids), "max_episodes": fetch_n})
    episodes = result.get("episodes", [])
    episodes = sorted(episodes, key=lambda e: e.get("created_at", ""), reverse=True)[:n]
    return {**result, "episodes": episodes}
