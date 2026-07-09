"""
server/tools/registry.py — the atomic-tool registry (polyglot orchestration mesh).
Cross-domain capability layer (D-026): consumed by evidence, analysis, agents,
workflows, and the CLI — not owned by any single domain.

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
    """AUTO-DISCOVER tool modules: import every public module in this package
    (server.tools — the cross-domain capability layer, D-026 — used by
    evidence/analysis/agents/workflows/CLI alike) so each self-registers (one
    parser = one swappable module — owner architecture). Underscore-prefixed
    modules are shared helpers, not tools. Idempotent: re-imports are no-ops,
    duplicate ids raise at import time.

    Package-name-AGNOSTIC on purpose (uses __package__, not a hardcoded
    "server.tools"): this same module is also volume-mounted standalone into
    the docker/tools platform-tools facade container, where it's imported as
    the top-level `tools` package (no `server` package exists there) — see
    docker/tools/tools/facade.py's module docstring for the mount<->import
    contract."""
    import importlib
    import pkgutil

    pkg_name = __package__  # "server.tools" in-repo; "tools" in the facade container
    assert pkg_name, "load_builtin_tools() requires registry.py to be imported as a package module"
    tools_pkg = importlib.import_module(pkg_name)

    for mod in pkgutil.iter_modules(tools_pkg.__path__):
        if not mod.name.startswith("_"):
            importlib.import_module(f"{pkg_name}.{mod.name}")
    return len(registry.all())
