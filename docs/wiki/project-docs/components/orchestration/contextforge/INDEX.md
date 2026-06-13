---
title: ContextForge Integration
aliases:
  - IBM ContextForge
  - ContextForge MCP Gateway
type: hub
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - orchestration
  - contextforge
  - gateway
summary: Landing page for ContextForge as the main ingress and gateway direction for dial-stack.
repo_usage_state: planned
repo_version: not yet composed into the root runtime
upstream_version: v1.0.0-RC2 latest GitHub release reviewed 2026-03-30
official_docs:
  - https://ibm.github.io/mcp-context-forge/
official_repo:
  - https://github.com/IBM/mcp-context-forge
official_downloads:
  - https://github.com/IBM/mcp-context-forge/releases
  - https://pypi.org/project/mcp-contextforge-gateway/
---

# ContextForge Integration

## At a Glance

- **What it is**: IBM's MCP gateway and federation layer for tools, transports, plugins, auth, and observability.
- **Current role in `dial-stack`**: Main ingress and gateway direction.
- **Current repo status**: Architecture-driving, but not yet fully integrated into the root compose/runtime.

## Why It Matters Here

ContextForge lines up with the platform model we have been converging on:

- tool-first instead of monolith-first
- multiple backends behind one governed ingress
- plugin-based policy and enrichment
- registry and discovery patterns
- support for auth, observability, and transport mediation

It is the cleanest candidate for the front-door layer above our MCP servers and workflow tools.

## How We Plan to Use It

Target responsibilities:

- external ingress and gateway
- tool registry and discovery surface
- auth and policy enforcement boundary
- plugin-based tagging, moderation, or governance
- telemetry and trace collection across tool calls

Critical rule:

- ContextForge can govern, tag, route, and observe evidence flows, but it must not corrupt or silently mutate evidence truth.

## Current Documentation in This Section

- [Overview](OVERVIEW.md)
- [Proposed Architecture](PROPOSED_ARCHITECTURE.md)
- [Implementation Analysis](IMPLEMENTATION_ANALYSIS.md)

Historical drafts and superseded scans belong under the wiki archive when archived.

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo integration | not yet composed | Still a direction, not a live root service |
| Upstream latest reviewed | `v1.0.0-RC2` | Latest GitHub release reviewed 2026-03-30 |
| Upstream docs | current | Official docs site reviewed 2026-03-30 |

The upstream posture is release-candidate territory, so we should treat it as promising and fast-moving, not as “done forever.”

## How We Could Expand Its Use

- external-facing tool gateway for UIs and LLM consumers
- centralized plugin execution for rate limits, tagging, and safety checks
- identity brokering once auth boundaries are clearer
- lazy and dynamic discovery across atomic tools and workflows-as-tools
- transport bridge for MCP, REST, gRPC, and agent surfaces

## What to Watch

- do not let gateway plugins mutate evidence payloads
- keep MVP-critical flows able to fall back directly to core MCP services
- avoid duplicating DIAL responsibilities without a deliberate handoff
- review release-candidate drift before pinning it into the runtime

## Official Sources

- [ContextForge Docs](https://ibm.github.io/mcp-context-forge/)
- [ContextForge GitHub](https://github.com/IBM/mcp-context-forge)
- [ContextForge Releases](https://github.com/IBM/mcp-context-forge/releases)
- [ContextForge PyPI Package](https://pypi.org/project/mcp-contextforge-gateway/)

## Related Notes

- [[skills/orchestration/contextforge/OVERVIEW|ContextForge Overview]]
- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/orchestration/mcp-protocol|Model Context Protocol]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
