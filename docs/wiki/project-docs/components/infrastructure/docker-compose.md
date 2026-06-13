---
title: Docker Compose
aliases:
  - Docker Compose and Podman
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - infrastructure
  - compose
  - runtime
summary: Reference note for the root Docker Compose runtime, including what it actually starts today and how it differs from the intended future platform topology.
repo_usage_state: active
repo_version: compose file uses version 3.8 syntax; current runtime defined in root docker-compose.yml
upstream_version: Docker Compose v2 docs reviewed 2026-03-30
official_docs:
  - https://docs.docker.com/compose/
official_downloads:
  - https://docs.docker.com/compose/install/
---

# Docker Compose

## At a Glance

- **What it is**: The current root runtime composition for local development and integration testing.
- **Current role in `dial-stack`**: The main local stack definition for DIAL, auth, cache, PostgreSQL, MCP servers, and proxying.
- **Why it matters**: It is the most concrete source of truth for what the repo actually runs right now.

## What the Root Stack Actually Starts Today

Current root services include:

- DIAL Core, Chat, and Themes
- Keycloak and DIAL auth-helper
- Dragonfly
- PostgreSQL
- TS and Python MCP servers
- audit logger
- InfluxDB and analytics realtime
- Caddy

Important gaps or caveats:

- Neo4j is expected by the Python analysis layer but is not a root compose service
- ContextForge is an active architecture direction but is not yet part of the root compose file
- the root compose file does not represent the full future platform

## How `dial-stack` Uses It

Current local anchor:

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)

Current use:

- local integration runtime
- service wiring and baseline networking
- current version pin reference for several platform dependencies

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo compose syntax | `3.8` | Declared in the root compose file |
| Upstream docs reviewed | Docker Compose v2 docs | Reviewed 2026-03-30 |
| Operational truth | repo-specific | The root file is the best live runtime inventory for this repo |

## How We Could Expand Its Use

- add profiles for optional services instead of forcing one giant runtime
- separate stable MVP runtime from experimental services
- add explicit ContextForge, Neo4j, Directus, or other planned surfaces via controlled profiles
- pin currently unpinned images to reduce drift

## What We Need to Watch

- docs often overstate services that are not actually in the root compose runtime
- the runtime includes legacy or conflicting services that still need cleanup
- compose is a runtime truth source, but not a substitute for architecture docs
- planned services should be documented as planned until actually wired

## Key Repo Files

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)
- [ROADMAP.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/plans/ROADMAP.md)

## Official Sources

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Docker Compose Install Docs](https://docs.docker.com/compose/install/)

## Related Notes

- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/security/keycloak|Keycloak]]
- [[skills/infrastructure/caddy|Caddy]]
- [[skills/database/postgresql|PostgreSQL]]
- [[INDEX|dial-stack Wiki Index]]
