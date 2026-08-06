"""Unit tests for server.tools.registry — the atomic-tool registry / substitution mesh.

Workflows resolve steps by *capability* and fall back to same-capability tools
when one rejects the input. That resolve/accepts/registration-order behavior is
the load-bearing contract, and it's pure Python — no DB, no network.
"""

from __future__ import annotations

import pytest

from server.tools import registry as registry_mod
from server.tools.registry import FunctionTool, ToolRegistry, load_builtin_tools, register


def _tool(tool_id, capability="parse.transcript", accept=None):
    return FunctionTool(
        id=tool_id,
        capability=capability,
        description=f"{tool_id} tool",
        fn=lambda payload: {"echo": payload, "by": tool_id},
        accept=accept or (lambda hint, size: True),
        provenance="test",
    )


def test_function_tool_run_and_default_accept():
    t = _tool("a")
    assert t.accepts("anything.md", 123) is True  # default accept
    assert t.run({"x": 1}) == {"echo": {"x": 1}, "by": "a"}


def test_function_tool_accept_delegates():
    t = _tool("only-md", accept=lambda hint, size: hint.endswith(".md") and size < 1000)
    assert t.accepts("chat.md", 500) is True
    assert t.accepts("chat.json", 500) is False  # wrong suffix
    assert t.accepts("chat.md", 5000) is False  # too big


def test_register_and_get():
    reg = ToolRegistry()
    t = _tool("x")
    assert reg.register(t) is t
    assert reg.get("x") is t
    assert reg.all() == [t]


def test_duplicate_id_raises():
    reg = ToolRegistry()
    reg.register(_tool("dup"))
    with pytest.raises(ValueError, match="duplicate tool id"):
        reg.register(_tool("dup"))


def test_get_unknown_raises():
    reg = ToolRegistry()
    with pytest.raises(KeyError, match="unknown tool"):
        reg.get("nope")


def test_resolve_filters_by_capability_and_accepts_in_order():
    reg = ToolRegistry()
    reg.register(_tool("first", accept=lambda h, s: True))
    reg.register(_tool("rejects", accept=lambda h, s: False))
    reg.register(_tool("second", accept=lambda h, s: True))
    reg.register(_tool("other-cap", capability="parse.sms-xml"))

    resolved = reg.resolve("parse.transcript", media_hint="x.md", size_bytes=10)
    # capability match + accepts True, preserving registration order; preferred first.
    assert [t.id for t in resolved] == ["first", "second"]


def test_manifest_shape():
    reg = ToolRegistry()
    reg.register(_tool("m"))
    [entry] = reg.manifest()
    assert entry == {
        "id": "m",
        "capability": "parse.transcript",
        "description": "m tool",
        "provenance": "test",
        "execution_policy": "manual_or_auto",
        "side_effect": "read_only",
    }


def test_register_decorator_registers_into_global(monkeypatch):
    fresh = ToolRegistry()
    monkeypatch.setattr(registry_mod, "registry", fresh)

    @register(id="deco", capability="parse.transcript", description="d", provenance="p")
    def my_tool(payload):
        return {"ok": True}

    # The decorator returns the original function unchanged...
    assert my_tool({"a": 1}) == {"ok": True}
    # ...and the tool is now resolvable from the (patched) global registry.
    [t] = fresh.resolve("parse.transcript")
    assert t.id == "deco"
    assert t.run({}) == {"ok": True}


def test_load_builtin_tools_discovers_transcript_parsers():
    # Auto-discovery imports every public server.tools module so each
    # self-registers. Must be idempotent (re-import = no-op, no duplicate-id).
    n1 = load_builtin_tools()
    n2 = load_builtin_tools()
    assert n1 == n2 and n1 >= 4
    caps = {t.capability for t in registry_mod.registry.all()}
    assert "parse.transcript" in caps
