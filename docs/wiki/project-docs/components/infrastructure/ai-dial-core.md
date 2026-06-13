---
title: AI DIAL Core
aliases:
  - DIAL Core
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - infrastructure
  - dial
  - orchestration
summary: Reference note for AI DIAL Core as an internal orchestration and chat surface inside dial-stack, with source-grounded version posture and usage boundaries.
repo_usage_state: partial
repo_version: docker.io/epam/ai-dial-core:0.25.1 in docker-compose.yml
upstream_version: 0.41.0 latest GitHub release reviewed 2026-03-30
official_docs:
  - https://docs.dialx.ai/platform/core/about-core
official_repo:
  - https://github.com/epam/ai-dial-core
official_downloads:
  - https://github.com/epam/ai-dial-core/releases
---

# AI DIAL Core

## At a Glance

- **What it is**: The main DIAL backend that exposes a unified OpenAI-compatible API for models, assistants, and applications.
- **Current role in `dial-stack`**: Internal orchestration and chat surface, not the long-term external ingress.
- **Why it still matters**: It gives us a working internal chat/application layer while the rest of the system stays tool-first and evidence-first.

## How `dial-stack` Uses It

The current repo uses DIAL Core as an internal platform component:

- `core` in [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- config under [infrastructure/core/config.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/core/config.json)
- settings under [infrastructure/settings/settings.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/settings/settings.json)
- paired with DIAL Chat and themes for internal operator-facing access

In practice, DIAL is currently serving as:

- internal chat and operator tooling
- an OpenAI-compatible bridge to configured model providers
- an internal integration layer for MCP-backed tools
- a useful internal control surface while ContextForge remains the main ingress direction

## What We Are Not Using It For

These boundaries matter:

- DIAL is **not** the canonical future public ingress
- DIAL should **not** redefine evidence semantics
- DIAL should **not** be used to bypass tool-mediated ingest or provenance handling
- DIAL should **not** become the monolithic center of platform logic

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo image | `0.25.1` | Pinned in [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml) |
| Related repo images | Chat `0.26.0`, Themes `0.9.1` | Internal UI stack is version-skewed across services |
| Upstream latest reviewed | `0.41.0` | Latest GitHub release reviewed on 2026-03-30 |

This gap matters. The repo is behind upstream DIAL Core, so behavior assumptions should be checked against the pinned version, not against current upstream docs alone.

## How We Could Expand Its Use

Reasonable expansion lanes:

- keep it as a stable internal chat and operator surface
- use it for controlled internal tool invocation where OpenAI-compatible behavior is useful
- keep it as an internal application bridge while ContextForge matures as ingress
- evaluate newer DIAL features only after version drift is reviewed intentionally

## What to Watch

- version drift between repo-pinned DIAL and upstream docs
- coupling evidence workflows too tightly to chat surfaces
- auth duplication between DIAL and the future ContextForge boundary
- hidden model-provider assumptions inside DIAL configs

## Key Repo Files

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [infrastructure/core/config.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/core/config.json)
- [infrastructure/settings/settings.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/settings/settings.json)
- [docs/wiki/architecture/ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)

## Official Sources

- [DIAL Core Docs](https://docs.dialx.ai/platform/core/about-core)
- [DIAL Core GitHub](https://github.com/epam/ai-dial-core)
- [DIAL Core Releases](https://github.com/epam/ai-dial-core/releases)

## Related Notes

- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[skills/orchestration/mcp-protocol|Model Context Protocol]]
- [[skills/infrastructure/docker-compose|Docker Compose]]
- [[skills/security/keycloak|Keycloak]]
- [[INDEX|dial-stack Wiki Index]]
