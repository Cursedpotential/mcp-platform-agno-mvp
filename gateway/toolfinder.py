"""The five meta-operations over the atomic-tool registry.

Progressive disclosure (port of gateway.ts): categories -> compact cards ->
full contract -> execute (large output => ref) -> paged retrieval. Consumers
(agents via ContextForge, the shell's tool-catalog page) never need the whole
catalog in context.

Category == registry capability ('parse.transcript', 'parse.sms-xml', ...) —
the same role the `category.action` name prefix played in the old platform.
"""

from __future__ import annotations

import json
from typing import Any

from evidence.registry import load_builtin_tools, registry
from gateway.content_store import ContentStore, parse_ref

INLINE_THRESHOLD_BYTES = 4096

# search scoring, ported from gateway.ts scoreToolCard: name x5 / desc x3 / tag x2
_W_ID, _W_DESC, _W_CAP = 5, 3, 2


def _ensure_loaded() -> None:
    load_builtin_tools()


def _card(tool: Any) -> dict[str, Any]:
    """Compact tool card — the search-result unit (token-cheap by design)."""
    return {
        "id": tool.id,
        "category": tool.capability,
        "description": tool.description,
    }


def get_tool_categories() -> list[dict[str, Any]]:
    """Every capability with its tool count — the entry point of disclosure."""
    _ensure_loaded()
    counts: dict[str, int] = {}
    for t in registry.all():
        counts[t.capability] = counts.get(t.capability, 0) + 1
    return [{"category": cap, "tool_count": n} for cap, n in sorted(counts.items())]


def search_tools(query: str = "", category: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Compact tool cards matching `query`, optionally within one category."""
    _ensure_loaded()
    tools = [t for t in registry.all() if category is None or t.capability == category]
    if not query:
        return [_card(t) for t in tools[:limit]]

    terms = [w for w in query.lower().split() if w]
    scored: list[tuple[int, Any]] = []
    for t in tools:
        tid, desc, cap = t.id.lower(), t.description.lower(), t.capability.lower()
        score = sum(
            (_W_ID if w in tid else 0) + (_W_DESC if w in desc else 0) + (_W_CAP if w in cap else 0) for w in terms
        )
        if score > 0:
            scored.append((score, t))
    scored.sort(key=lambda s: (-s[0], s[1].id))
    return [_card(t) for _, t in scored[:limit]]


def describe_tool(tool_id: str) -> dict[str, Any]:
    """Full contract for one tool — loaded on demand, never in bulk."""
    _ensure_loaded()
    t = registry.get(tool_id)  # raises KeyError for unknown ids
    return {
        **_card(t),
        "provenance": getattr(t, "provenance", ""),
        # FunctionTool contract: payload dict in -> dict out. Parsers take
        # {"path": <file>}; results follow records_out ({"records", "stats"}).
        "payload_contract": {"input": "dict (parsers: {'path': <file path>})", "output": "dict"},
        # same-capability mates regardless of accept-hints (resolve() would
        # filter on a media hint we don't have here)
        "substitution_candidates": [c.id for c in registry.all() if c.capability == t.capability and c.id != t.id],
    }


def execute_tool(
    tool_id: str,
    payload: dict[str, Any],
    store: ContentStore | None = None,
    inline_threshold: int = INLINE_THRESHOLD_BYTES,
) -> dict[str, Any]:
    """Invoke a tool. Small results return inline; large ones return a REF
    envelope (retrieve with get_ref) so callers never swallow a 50 MB parse."""
    _ensure_loaded()
    tool = registry.get(tool_id)
    result = tool.run(payload)
    body = json.dumps(result, ensure_ascii=False, default=str)

    if len(body.encode("utf-8")) <= inline_threshold:
        return {"tool_id": tool_id, "inline": True, "result": result}

    store = store or ContentStore()
    envelope = store.put(body, mime="application/json")
    summary: dict[str, Any] = {}
    if isinstance(result, dict) and isinstance(result.get("stats"), dict):
        summary = result["stats"]  # parsers: record_count etc. ride along
    return {"tool_id": tool_id, "inline": False, **envelope, "stats": summary}


def get_ref(ref: str, page: int = 0, page_size: int | None = None, store: ContentStore | None = None) -> dict[str, Any]:
    """Paged retrieval of a stored result (4 KB pages by default)."""
    store = store or ContentStore()
    kwargs: dict[str, Any] = {"page": page}
    if page_size is not None:
        kwargs["page_size"] = page_size
    return store.get_page(parse_ref(ref), **kwargs)
