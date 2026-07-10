"""Tests for agents/tools/gateway_tools.py — the agno @tool wrappers over the
G4 meta-ops (facade-collapse plan Batch A, §1).

``@tool`` turns each module-level function into an agno ``Function`` (a
pydantic model, not directly callable) — call ``.entrypoint(...)`` to invoke
the wrapped function synchronously, same as agno's own ``Function.execute()``
does internally. These tests exercise the wrapper layer itself (that it
delegates to ``toolfinder`` with the right arguments, and shares one
``ContentStore`` singleton across calls so REFs survive between an
execute_tool call and a later get_ref call) — the meta-ops' own logic is
already covered by ``tests/test_gateway.py``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from agno.tools.function import Function

from server.agents.tools import gateway_tools
from server.tools.registry import FunctionTool, load_builtin_tools


def _call(fn: Function, **kwargs: Any) -> Any:
    """Invoke a ``@tool``-wrapped ``Function`` synchronously, the same way
    agno's own ``Function.execute()`` does. ``.entrypoint`` is typed
    ``Optional[Callable]`` on the pydantic model (only ``None`` before
    ``process_entrypoint()`` runs, which ``@tool`` always calls) — assert
    narrows that for mypy instead of scattering ``# type: ignore``."""
    assert fn.entrypoint is not None
    return fn.entrypoint(**kwargs)


def test_gateway_tools_list_has_all_five():
    names = {f.name for f in gateway_tools.GATEWAY_TOOLS}
    assert names == {"get_tool_categories", "search_tools", "describe_tool", "execute_tool", "get_ref"}


def test_get_tool_categories_returns_real_categories():
    load_builtin_tools()
    cats = _call(gateway_tools.get_tool_categories)
    assert isinstance(cats, list) and len(cats) > 0
    assert any(c["category"] == "parse.sms-xml" for c in cats)


def test_search_tools_finds_sms_parser():
    load_builtin_tools()
    results = _call(gateway_tools.search_tools, query="sms")
    assert results and any("sms" in r["id"] for r in results)


def test_describe_tool_raises_for_unknown_id():
    load_builtin_tools()
    with pytest.raises(KeyError):
        _call(gateway_tools.describe_tool, tool_id="nope.nothing")


@pytest.fixture
def fake_registry(monkeypatch, tmp_path):
    """Fresh in-process registry + a fresh module-scoped ContentStore, so
    execute_tool/get_ref round-trip without touching the real parser catalog
    or the real on-disk data/content_store directory."""
    from server.tools import registry as registry_mod
    from server.evidence.tool_finder.content_store import ContentStore

    fresh = registry_mod.ToolRegistry()
    fresh.register(
        FunctionTool(
            id="test.small",
            capability="test.echo",
            description="small result",
            fn=lambda p: {"echo": p, "stats": {"record_count": 1}},
        )
    )
    fresh.register(
        FunctionTool(
            id="test.big",
            capability="test.echo",
            description="big result",
            fn=lambda p: {
                "records": [{"n": i, "body": "z" * 100} for i in range(200)],
                "stats": {"record_count": 200},
            },
        )
    )
    monkeypatch.setattr(registry_mod, "registry", fresh)
    monkeypatch.setattr("server.evidence.tool_finder.toolfinder.registry", fresh)
    monkeypatch.setattr("server.evidence.tool_finder.toolfinder._ensure_loaded", lambda: None)
    monkeypatch.setattr(gateway_tools, "_store", ContentStore(tmp_path / "cs"))
    return fresh


def test_execute_tool_small_result_inlines(fake_registry):
    out = _call(gateway_tools.execute_tool, tool_id="test.small", payload={"a": 1})
    assert out["inline"] is True
    assert out["result"]["echo"] == {"a": 1}


def test_execute_tool_large_result_refs_and_get_ref_roundtrips(fake_registry):
    out = _call(gateway_tools.execute_tool, tool_id="test.big", payload={})
    assert out["inline"] is False
    assert out["stats"]["record_count"] == 200

    # the module-level _store singleton is what makes this work across two
    # separate tool calls — a per-call ContentStore() would 404 here.
    pages, page = [], 0
    while True:
        p = _call(gateway_tools.get_ref, ref=out["ref"], page=page)
        pages.append(p["content"])
        if not p["has_more"]:
            break
        page += 1
    parsed = json.loads("".join(pages))
    assert len(parsed["records"]) == 200
