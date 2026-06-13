---
title: DuckDB
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - database
  - duckdb
  - evidence
summary: Reference note for DuckDB as the first-touch evidence intake, forensic staging, and chain-of-custody anchor in dial-stack.
repo_usage_state: core-mvp
repo_version: @duckdb/node-api ^1.5.0-r.1 in ts-mcp-server package.json
upstream_version: DuckDB 1.5.1 current and 1.4.4 LTS reviewed 2026-03-30
official_docs:
  - https://duckdb.org/docs/
  - https://duckdb.org/docs/stable/clients/nodejs/overview
official_repo:
  - https://github.com/duckdb/duckdb
official_downloads:
  - https://duckdb.org/install/
  - https://github.com/duckdb/duckdb/releases
---

# DuckDB

## At a Glance

- **What it is**: Embedded analytical database with strong local-file ergonomics.
- **Current role in `dial-stack`**: First-touch evidence intake and forensic staging.
- **Why it matters**: It is the safest place in the current stack to establish hashes, UUID linkage, provenance anchors, and staging records before downstream enrichment.

## How `dial-stack` Uses It

DuckDB is the first storage stop for evidence-bearing intake.

Current local anchors:

- [DuckDbService.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/services/DuckDbService.ts)
- [DuckDbVault.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/tools/DuckDbVault.ts)
- [index.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/index.ts)

Current responsibilities:

- first-touch logging of evidence intake
- source-level hashing at ingest time
- staging normalized message records before or alongside canonical PostgreSQL writes
- write tracking across downstream tiers

## Current Evidence Handling Posture

DuckDB is the correct place in the current pipeline to establish:

- source file identity
- intake timestamps
- stable linkage IDs
- provenance-safe raw metadata capture

The intended pipeline remains:

`source evidence -> DuckDB -> PostgreSQL -> Semantica + LanceDB in parallel -> PostgreSQL enrichment`

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo package | `@duckdb/node-api ^1.5.0-r.1` | Declared in TS MCP package |
| Upstream current | `1.5.1` | Reviewed from DuckDB install/docs pages |
| Upstream LTS | `1.4.4` | Reviewed from DuckDB install/docs pages |

## How We Could Expand Its Use

High-value expansion paths:

- complete 3-level hashing:
  - source file hash
  - record/message-level hash
  - downstream transform or analysis hash
- add signed evidence manifests and verification helpers
- expose read-only query tooling for audit and verification workflows
- strengthen duplicate detection using raw-field preservation plus stable hashes
- widen first-touch storage so all parser-observed fields are preserved before normalization

## What We Need to Watch

- current code appears to be source-hash oriented, not yet the full 3-level hash design
- first-pass records should remain effectively immutable
- downstream systems should reference DuckDB-established identifiers instead of inventing replacements
- query tooling must not turn DuckDB into a casual mutable app store

## Key Repo Files

- [DuckDbService.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/services/DuckDbService.ts)
- [DuckDbVault.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/tools/DuckDbVault.ts)
- [index.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/index.ts)
- [ARCHITECTURE.md](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/architecture/ARCHITECTURE.md)

## Official Sources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [DuckDB Node.js API](https://duckdb.org/docs/stable/clients/nodejs/overview)
- [DuckDB Install and Downloads](https://duckdb.org/install/)
- [DuckDB GitHub](https://github.com/duckdb/duckdb)

## Related Notes

- [[skills/database/postgresql|PostgreSQL]]
- [[skills/nlp/semantica|Semantica]]
- [[skills/database/lancedb|LanceDB]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[INDEX|dial-stack Wiki Index]]
