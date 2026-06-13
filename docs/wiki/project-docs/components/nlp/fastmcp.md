---
title: FastMCP
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - fastmcp
  - mcp
  - python
summary: Reference note for FastMCP as the Python MCP framework powering the dial-stack analysis and workflow server.
repo_usage_state: core-mvp
repo_version: unpinned `fastmcp` dependency in py-mcp-server requirements
upstream_version: FastMCP 3.2.0 latest PyPI and GitHub release reviewed 2026-03-30
official_docs:
  - https://gofastmcp.com/
official_repo:
  - https://github.com/PrefectHQ/fastmcp
official_downloads:
  - https://pypi.org/project/fastmcp/
  - https://github.com/PrefectHQ/fastmcp/releases
---

# FastMCP

## At a Glance

- **What it is**: Python framework for building MCP servers, clients, and related transport-aware tooling.
- **Current role in `dial-stack`**: Framework under the Python MCP server that exposes Semantica, LanceDB, Neo4j, workflow, and audit-adjacent tools.
- **Why it matters**: It is the core adapter that turns Python capabilities into reusable tools instead of one-off endpoints.

## How `dial-stack` Uses It

Current local anchors:

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [requirements.txt](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/requirements.txt)

We currently use FastMCP for:

- tool registration
- typed argument surfaces
- Python-side tool composition
- workflow-as-tool exposure

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo dependency | unpinned `fastmcp` | Drift risk in current requirements |
| Upstream latest reviewed | `3.2.0` | Reviewed from PyPI and GitHub releases on 2026-03-30 |
| Current repo usage style | server/tool patterns | Compatible with our existing tool registration approach, but version pinning is overdue |

## How We Could Expand Its Use

- promote more Python workflows into explicit workflow tools
- use FastMCP resources and prompts where they help analyst or LLM surfaces
- introduce more structured transport handling as ContextForge matures
- evaluate newer FastMCP app capabilities for controlled internal UI surfaces

## What We Need to Watch

- the repo should pin FastMCP explicitly to avoid accidental breaking changes
- upstream is moving fast; docs can outpace our usage quickly
- long-running tool behavior should remain observable and bounded
- tool schemas should stay stable enough for UIs and orchestration layers to depend on

## Key Repo Files

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [requirements.txt](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/requirements.txt)

## Official Sources

- [FastMCP Docs](https://gofastmcp.com/)
- [FastMCP PyPI](https://pypi.org/project/fastmcp/)
- [FastMCP GitHub](https://github.com/PrefectHQ/fastmcp)
- [FastMCP Releases](https://github.com/PrefectHQ/fastmcp/releases)

## Related Notes

- [[skills/orchestration/mcp-protocol|Model Context Protocol]]
- [[skills/nlp/semantica|Semantica]]
- [[skills/database/lancedb|LanceDB]]
- [[skills/database/neo4j|Neo4j]]
- [[INDEX|dial-stack Wiki Index]]
