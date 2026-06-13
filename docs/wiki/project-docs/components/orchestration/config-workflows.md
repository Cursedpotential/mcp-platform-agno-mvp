---
title: Config-Driven Workflows
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - orchestration
  - workflows
summary: Reference note for the Python-side config-driven workflow system and its role in the workflows-as-tools model.
repo_usage_state: active
repo_version: workflow configuration under py-mcp-server/config/workflows.json
upstream_version: repo-defined internal workflow system reviewed 2026-03-30
official_docs:
  - "local source: mcp-servers/py-mcp-server/config/workflows.json"
  - "local source: mcp-servers/py-mcp-server/src/tools/workflow_tools.py"
---

# Config-Driven Workflows

## At a Glance

- **What it is**: The internal workflow engine that composes atomic tools into configurable workflow tools.
- **Current role in `dial-stack`**: Main implementation of the “workflows are tools” architecture rule.
- **Why it matters**: It keeps orchestration declarative and changeable instead of burying sequences inside brittle code paths.

## How `dial-stack` Uses It

Current local anchors:

- [workflows.json](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/config/workflows.json)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)

Current use:

- register workflow modules
- compose named workflows from atomic tools
- expose workflow execution through the MCP tool surface
- allow workflow changes without rewriting every orchestration path

## Why It Matters to the Platform Model

This is one of the strongest current anchors for the platform design principle that:

- atomic tools are first-class
- workflows are also first-class
- clients should be able to call either without needing a separate system

## How We Could Expand Its Use

- clearer versioning and change tracking for workflow definitions
- more workflow notes in the wiki tied to named workflow configs
- analyst-specific workflow lanes for review, triage, and verification
- stronger schema validation and runtime safety checks

## What We Need to Watch

- workflow config should not become a dumping ground for undocumented business logic
- docs must distinguish real modules from placeholder ones
- workflow changes should be treated as behavior changes and documented accordingly

## Key Repo Files

- [workflows.json](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/config/workflows.json)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)

## Related Notes

- [[skills/nlp/fastmcp|FastMCP]]
- [[skills/nlp/semantica|Semantica]]
- [[skills/orchestration/mcp-protocol|Model Context Protocol]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
