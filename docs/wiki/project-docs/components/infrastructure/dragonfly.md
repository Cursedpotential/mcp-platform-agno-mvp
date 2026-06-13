---
title: Dragonfly
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - infrastructure
  - dragonfly
  - cache
summary: Reference note for Dragonfly as the Redis-compatible cache currently used by the DIAL runtime in dial-stack.
repo_usage_state: active
repo_version: docker.dragonflydb.io/dragonflydb/dragonfly image in docker-compose.yml
upstream_version: current Dragonfly docs reviewed 2026-03-30
official_docs:
  - https://www.dragonflydb.io/docs
official_repo:
  - https://github.com/dragonflydb/dragonfly
official_downloads:
  - https://www.dragonflydb.io/docs/getting-started
---

# Dragonfly

## At a Glance

- **What it is**: Redis-compatible in-memory data store and cache.
- **Current role in `dial-stack`**: Cache/runtime support for the current DIAL stack.
- **Why it matters**: It provides the current ephemeral state and cache layer without changing the evidence-storage truth model.

## How `dial-stack` Uses It

Current local anchors:

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [infrastructure/core/config.json](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/core/config.json)

Current responsibilities:

- DIAL runtime cache support
- transient operational state
- fast non-canonical lookups where needed

## What It Is Not

Dragonfly is not:

- a canonical evidence store
- a provenance source of truth
- a substitute for PostgreSQL or DuckDB

## How We Could Expand Its Use

- bounded cache layers for expensive tool responses
- rate-limit counters or transient workflow state
- short-lived orchestration metadata

## What We Need to Watch

- ephemeral cache layers should never hold the only copy of evidence-affecting data
- image pinning is still worth tightening here
- cache invalidation rules need to be explicit if we rely on it more heavily

## Official Sources

- [Dragonfly Docs](https://www.dragonflydb.io/docs)
- [Dragonfly Getting Started](https://www.dragonflydb.io/docs/getting-started)
- [Dragonfly GitHub](https://github.com/dragonflydb/dragonfly)

## Related Notes

- [[skills/infrastructure/ai-dial-core|AI DIAL Core]]
- [[skills/infrastructure/docker-compose|Docker Compose]]
- [[INDEX|dial-stack Wiki Index]]
