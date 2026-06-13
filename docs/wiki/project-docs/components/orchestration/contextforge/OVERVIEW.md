---
title: ContextForge Overview
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - contextforge
  - gateway
  - orchestration
summary: Detailed overview of ContextForge and how dial-stack intends to use it as the main ingress, registry, and policy-aware gateway layer.
repo_usage_state: planned
repo_version: not yet wired into root docker-compose
upstream_version: v1.0.0-RC2 latest GitHub release reviewed 2026-03-30
official_docs:
  - https://ibm.github.io/mcp-context-forge/
official_repo:
  - https://github.com/IBM/mcp-context-forge
official_downloads:
  - https://github.com/IBM/mcp-context-forge/releases
  - https://pypi.org/project/mcp-contextforge-gateway/
---

# ContextForge Overview

## What ContextForge Is

Upstream, ContextForge is an MCP gateway that can federate servers, expose multiple transports, apply plugins, manage auth and teams, and add observability around tool traffic.

For `dial-stack`, that makes it a strong fit for the **gateway layer**, not for the evidence-processing core itself.

## Why It Fits `dial-stack`

The architecture direction in this repo is:

- tool-first
- workflows-as-tools
- multiple backend services
- evidence-first
- one governed ingress above the tool mesh

ContextForge matches that shape better than a monolithic app boundary because it offers:

- MCP federation
- transport mediation
- plugin hooks
- observability
- admin and catalog patterns
- a natural place for discovery and policy

## How We Intend to Use It

### Primary Responsibilities

- main ingress for external clients
- tool registry and lazy discovery layer
- auth and governance boundary
- policy and tagging plugins
- request tracing and operational observability

### Evidence-Safe Constraint

ContextForge should:

- tag
- classify
- route
- inspect
- govern

It should **not**:

- rewrite evidence truth
- discard source fields
- bypass DuckDB-first evidence handling
- become a hidden transformation layer that breaks provenance

## Likely Placement in the Platform

Expected flow:

`UI / LLM / operator -> ContextForge -> MCP tools and workflow tools -> storage and analysis services`

That makes ContextForge a good fit for:

- routing requests to TS, Python, and JS MCP servers
- exposing workflow tools and atomic tools through one ingress
- attaching security, telemetry, rate limits, and tagging behavior

## How It Relates to DIAL

The current working split is:

- **ContextForge**: external ingress, registry, gateway, policy
- **DIAL**: internal orchestration and chat surface

That means ContextForge is not simply “more DIAL.” It is a better fit for the outer boundary of the tool ecosystem.

## How We Could Expand Its Use

Once the base ingress is working, ContextForge could also cover:

- MCP catalog and service discovery
- REST and gRPC adapters where we already have non-MCP utilities
- external plugin execution for moderation, PII checks, and tagging
- A2A and multi-agent routing for specialized tool surfaces
- observability exports for tool and workflow executions

## Watch-Outs

- release-candidate drift is real
- over-plugining can create hidden business logic
- a gateway can accidentally become a second orchestration monolith
- any pre-ingest or permissive tagging must stay reversible and attributable

## Key Local References

- [INDEX.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/skills/orchestration/contextforge/INDEX.md)
- [PROPOSED_ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/skills/orchestration/contextforge/PROPOSED_ARCHITECTURE.md)
- [IMPLEMENTATION_ANALYSIS.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/skills/orchestration/contextforge/IMPLEMENTATION_ANALYSIS.md)
- [ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)

## Official Sources

- [ContextForge Docs](https://ibm.github.io/mcp-context-forge/)
- [ContextForge GitHub](https://github.com/IBM/mcp-context-forge)
- [ContextForge Releases](https://github.com/IBM/mcp-context-forge/releases)
- [ContextForge PyPI Package](https://pypi.org/project/mcp-contextforge-gateway/)

## Related Notes

- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/orchestration/mcp-protocol|Model Context Protocol]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
