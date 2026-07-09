"""
evidence/registry.py — the atomic-tool registry (polyglot orchestration mesh).

A tool = ONE capability implemented by ONE library/runtime, registered with a
contract. Workflows resolve steps by CAPABILITY, not by hard-coded function:
when a step fails, the executor can surface same-capability alternatives for
an agent to swap in (re-composition happens in the sandbox; ADR/canon §5).

Python-native tools register in-process via @register. Polyglot tools (TS/Go
binaries, MCP servers, HTTP services like SBV) register with a runner that
shells out / calls HTTP — same contract, different transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class ToolPlugin(Protocol):
    """Contract every atomic tool satisfies."""

    id: str
    capability: str  # e.g. 'parse.transcript', 'parse.sms-xml'
    description: str

    def accepts(self, media_hint: str, size_bytes: int) -> bool: ...
    def run(self, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class FunctionTool:
    """In-process Python tool: wraps a callable under the ToolPlugin contract."""

    id: str
    capability: str
    description: str
    fn: Callable[[dict[str, Any]], dict[str, Any]]
    accept: Callable[[str, int], bool] = field(default=lambda hint, size: True)
    provenance: str = ""  # where the implementation came from (port source)

    def accepts(self, media_hint: str, size_bytes: int) -> bool:
        return self.accept(media_hint, size_bytes)

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.fn(payload)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolPlugin] = {}

    def register(self, tool: ToolPlugin) -> ToolPlugin:
        if tool.id in self._tools:
            raise ValueError(f"registry: duplicate tool id {tool.id!r}")
        self._tools[tool.id] = tool
        return tool

    def get(self, tool_id: str) -> ToolPlugin:
        if tool_id not in self._tools:
            raise KeyError(f"registry: unknown tool {tool_id!r}")
        return self._tools[tool_id]

    def all(self) -> list[ToolPlugin]:
        return list(self._tools.values())

    def resolve(self, capability: str, media_hint: str = "", size_bytes: int = 0) -> list[ToolPlugin]:
        """All tools matching a capability that accept the input, in
        registration order (first = preferred; rest = substitution candidates)."""
        return [t for t in self._tools.values() if t.capability == capability and t.accepts(media_hint, size_bytes)]

    def manifest(self) -> list[dict[str, str]]:
        return [
            {
                "id": t.id,
                "capability": t.capability,
                "description": t.description,
                "provenance": getattr(t, "provenance", ""),
            }
            for t in self._tools.values()
        ]


# The process-wide registry. Built-in tools self-register on import.
registry = ToolRegistry()


def register(
    *,
    id: str,
    capability: str,
    description: str,
    accept: Callable[[str, int], bool] | None = None,
    provenance: str = "",
) -> Callable:
    """Decorator: register a payload->payload function as an atomic tool."""

    def _wrap(fn: Callable[[dict[str, Any]], dict[str, Any]]) -> Callable:
        registry.register(
            FunctionTool(
                id=id,
                capability=capability,
                description=description,
                fn=fn,
                accept=accept or (lambda hint, size: True),
                provenance=provenance,
            )
        )
        return fn

    return _wrap


def load_builtin_tools() -> int:
    """AUTO-DISCOVER tool modules: import every public module in evidence.tools
    so each self-registers (one parser = one swappable module — owner
    architecture). Underscore-prefixed modules are shared helpers, not tools.
    Idempotent: re-imports are no-ops, duplicate ids raise at import time."""
    import importlib
    import pkgutil

    import server.evidence.tools as tools_pkg

    for mod in pkgutil.iter_modules(tools_pkg.__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"server.evidence.tools.{mod.name}")
    # General cross-domain PLATFORM tools (top-level `tools/` package) — discovered
    # alongside the evidence parsers so a tool like `extract.text` is reachable by ANY
    # domain/surface, not nested under evidence. Optional: absent in slim deploys.
    try:
        import server.evidence.tools as platform_tools_pkg

        for mod in pkgutil.iter_modules(platform_tools_pkg.__path__):
            if not mod.name.startswith("_"):
                importlib.import_module(f"server.evidence.tools.{mod.name}")
    except ModuleNotFoundError:
        pass
    return len(registry.all())
