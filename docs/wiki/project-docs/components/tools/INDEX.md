---
title: Tools Hub
type: hub
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - tools
  - mcp
summary: Active entrypoint for tool-surface documentation, MCP server notes, and tool inventory status.
---

# Tools Hub

This section gathers the active tool documentation entrypoints for `dial-stack`. Treat the MCP server docs and the architecture tool catalog as the current source of truth for what is actually exposed today.

## Current Tool References

- [Architecture Tool Catalog](../architecture/TOOL_CATALOG.md) — current inventory with `built`, `partial`, and `planned` status
- [TS MCP Server Tools](./ts-mcp-server.md) — parser, storage, and review queue tools
- [Py MCP Server Tools](./py-mcp-server.md) — Semantica, workflow, graph, and vector tooling
- [JS MCP Server Tools](./js-mcp-server.md) — current JS MCP status and planned document-processing tools

## Supporting Tool Reference Areas

- [Utility Tools](./utility/INDEX.md) — utility-script documentation retained for current reference
- [Legacy Tool Porting Notes](./legacy/mcp-tool-platform-porting-guide.md) — migration context from archived tooling
- `forensic-tools/`, `mcp-servers/`, and `ai-workspace-tools/` contain narrower tool-specific notes that may still be useful, but they are not the canonical “what is live now” inventory.

## Documentation Rule

When documenting or updating a tool:

1. Update the active tool doc.
2. Update [Architecture Tool Catalog](../architecture/TOOL_CATALOG.md) if status or scope changed.
3. Archive superseded tool docs under `docs/wiki/archive/` instead of deleting them.

## Related Notes

- [[INDEX|dial-stack Wiki Index]]
- [[architecture/TOOL_CATALOG|Architecture Tool Catalog]]
- [[guides/WIKI_CANON_MIGRATION|Wiki Canon Migration]]
