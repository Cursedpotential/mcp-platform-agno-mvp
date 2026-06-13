---
title: Model Context Protocol
aliases:
  - MCP
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - orchestration
  - mcp
summary: Reference note for the Model Context Protocol as the shared tool contract across the dial-stack tool ecosystem.
repo_usage_state: core-mvp
repo_version: multiple local MCP servers and clients in active use
upstream_version: MCP specification version 2025-06-18 reviewed 2026-03-30
official_docs:
  - https://modelcontextprotocol.io/docs
  - https://modelcontextprotocol.io/specification/2025-06-18
official_repo:
  - https://github.com/modelcontextprotocol
---

# Model Context Protocol

## At a Glance

- **What it is**: The protocol contract used to expose tools, resources, and related capabilities to models and applications.
- **Current role in `dial-stack`**: The common tool surface across TS, Python, and JS MCP servers.
- **Why it matters**: It is the main reason the platform can stay tool-first instead of collapsing into one custom integration path per client.

## How `dial-stack` Uses It

Current local anchors:

- [mcp-servers/ts-mcp-server/src/index.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/index.ts)
- [mcp-servers/py-mcp-server/src/server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [mcp-servers/py-mcp-server/src/tools/workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)

Current uses:

- expose atomic tools
- expose workflows-as-tools
- keep clients decoupled from implementation language
- support multiple consumers:
  - UI surfaces
  - LLM surfaces
  - direct operator tooling

## Current Protocol Posture

`dial-stack` is not using MCP as a novelty layer. It is using MCP as the core reusable tool contract.

That supports:

- shared tooling across internal chat, future gateway, and future analyst UI
- lazy discovery and tool catalog patterns
- composable workflow surfaces

## How We Could Expand Its Use

- more formal resources/prompts support where it helps analysts or LLMs
- richer remote transport support through ContextForge
- stronger schema and version management for tool contracts
- more explicit discovery and registry behavior

## What We Need to Watch

- workflow tools should not become opaque monoliths just because they speak MCP
- tool contracts need to stay stable enough for multiple clients
- evidence-bearing tools must still respect DuckDB-first and provenance-first rules
- remote exposure should be added intentionally, not accidentally

## Official Sources

- [MCP Docs](https://modelcontextprotocol.io/docs)
- [MCP Specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18)
- [MCP GitHub Organization](https://github.com/modelcontextprotocol)

## Related Notes

- [[skills/nlp/fastmcp|FastMCP]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[tools/INDEX|Tools Hub]]
- [[INDEX|dial-stack Wiki Index]]
