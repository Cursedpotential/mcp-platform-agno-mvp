"""agents/tools/ — agno ``@tool`` wrappers that expose cross-domain
capabilities (the ``server.tools`` parser registry, SBV's REST API) to
agents/MCP clients.

Distinct from ``server/tools/`` (the atomic-parser registry itself) and
``server/tools/gateway/`` (the G4 progressive-disclosure meta-op
logic) — this package holds the thin agno-facing adapters, kept next to the
agents/providers that wire them in (``server/agents/providers.py``).
"""

from __future__ import annotations
