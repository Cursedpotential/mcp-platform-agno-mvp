"""agents/tools/gateway_tools.py — agno ``@tool`` wrappers over the G4
progressive-disclosure meta-ops (``server/evidence/tool_finder/toolfinder.py``).
Exposes the 23-tool parser registry to agents/MCP clients as five thin
functions instead of one ``FunctionTool`` per parser, so the catalog never
floods context (locked decision, ``docs/COORDINATION.md:98-100``).

Error convention (OQ-8): these wrappers do NOT catch exceptions raised by the
underlying meta-ops (``KeyError`` for an unknown ``tool_id``, ``ValueError``
for a bad ref, whatever the atomic parser itself raises on a bad payload,
etc.) — same "raise, don't swallow" convention already used one layer down
(``server/tools/registry.py``'s ``ToolRegistry.get``/``FunctionTool.run`` and
``toolfinder.py``'s ``describe_tool``/``execute_tool``, which the docstrings
there document as raising rather than returning an error shape). agno's own
``Function.execute()`` (``agno/tools/function.py``) already catches any
exception raised inside a ``@tool``-decorated entrypoint and reports it back
to the calling agent as a structured tool-call failure
(``FunctionExecutionResult(status="failure", error=str(e))``) — so there is
no need to re-catch and re-shape errors here; doing so would only throw away
the ``status="failure"`` signal agno already gives the model for free.
"""

from __future__ import annotations

from typing import Any

from agno.tools import tool

from server.evidence.tool_finder import toolfinder as _tf
from server.evidence.tool_finder.content_store import ContentStore

# Module-level singleton so REFs written by execute_tool are retrievable by a
# later get_ref call in the same process (toolfinder.py itself defaults
# store=None -> ContentStore() per-call; the wrapper needs one shared
# instance across calls or every REF would die with the call that made it).
# Safe today: agentos-mcp runs as a single uvicorn process, no --workers
# (compose.exec.yaml). Would need a shared backend (Redis/DB) if agentos-mcp
# is ever scaled to multiple workers/replicas (OQ-7).
_store = ContentStore()


@tool
def get_tool_categories() -> list[dict[str, Any]]:
    """List every parser capability (category) with its tool count. Start here."""
    return _tf.get_tool_categories()


@tool
def search_tools(query: str = "", category: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Search parser tools by keyword, optionally scoped to one category."""
    return _tf.search_tools(query=query, category=category, limit=limit)


@tool
def describe_tool(tool_id: str) -> dict[str, Any]:
    """Full contract for one parser tool (payload shape, substitution candidates)."""
    return _tf.describe_tool(tool_id)


@tool
def execute_tool(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run a parser tool. Small results return inline; large ones return a REF
    (retrieve pages with get_ref) so a single call can't blow the context budget."""
    return _tf.execute_tool(tool_id, payload, store=_store)


@tool
def get_ref(ref: str, page: int = 0, page_size: int | None = None) -> dict[str, Any]:
    """Paged retrieval of a stored large result from execute_tool."""
    return _tf.get_ref(ref, page=page, page_size=page_size, store=_store)


GATEWAY_TOOLS: list[Any] = [get_tool_categories, search_tools, describe_tool, execute_tool, get_ref]
