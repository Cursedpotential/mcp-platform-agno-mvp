---
title: Directus Integration
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - orchestration
  - directus
  - planned
summary: Reference note for Directus as a planned file/admin workflow layer and possible MCP-adjacent integration surface for dial-stack.
repo_usage_state: planned
repo_version: not currently integrated into the root runtime
upstream_version: Directus 11.17.1 latest GitHub release reviewed 2026-03-30
official_docs:
  - https://docs.directus.io/self-hosted/quickstart.html
official_repo:
  - https://github.com/directus/directus
official_downloads:
  - https://github.com/directus/directus/releases
  - https://www.npmjs.com/package/@directus/content-mcp
---

# Directus Integration

## At a Glance

- **What it is**: Open-source data platform and admin/UI layer for SQL-backed applications.
- **Current role in `dial-stack`**: Planned file/admin workflow surface, not a live runtime component.
- **Why it matters**: It could give the platform a structured upload/admin surface without forcing all operations through a custom UI from day one.

## How `dial-stack` Would Use It

Most likely roles:

- intake-facing file and collection management
- admin and operational surfaces for evidence-adjacent data
- flow automation around uploads and post-ingest actions
- possible MCP-adjacent access through the Directus MCP package

## Current Repo Status

Directus is not currently in the root compose runtime.

This note should be read as:

- a serious integration option
- not a claim of current implementation

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo integration | not yet wired | Planned only |
| Upstream latest reviewed | `11.17.1` | Latest GitHub release reviewed 2026-03-30 |
| MCP resource | `@directus/content-mcp` | Relevant add-on resource, not current repo runtime |

## How We Could Expand Its Use

- operator/admin file-management surface
- ingestion-trigger flows
- collection-backed dashboards and internal ops views
- MCP-aware admin or content tooling if it reduces custom glue

## What We Need to Watch

- Directus should not become a silent evidence-transformation layer
- file metadata and upload workflows must still respect evidence handling rules
- any MCP integration needs the same source and provenance discipline as the rest of the platform
- planned status should remain explicit until runtime wiring exists

## Official Sources

- [Directus Self-Hosted Quickstart](https://docs.directus.io/self-hosted/quickstart.html)
- [Directus GitHub](https://github.com/directus/directus)
- [Directus Releases](https://github.com/directus/directus/releases)
- [Directus Content MCP Package](https://www.npmjs.com/package/@directus/content-mcp)

## Related Notes

- [[skills/database/postgresql|PostgreSQL]]
- [[skills/orchestration/contextforge/INDEX|ContextForge Integration]]
- [[skills/orchestration/wundergraph-cosmo/INTEGRATION|WunderGraph Cosmo Integration]]
- [[INDEX|dial-stack Wiki Index]]
