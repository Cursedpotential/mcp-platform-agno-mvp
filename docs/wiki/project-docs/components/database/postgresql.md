---
title: PostgreSQL
aliases:
  - PostgreSQL with pgvector
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - database
  - postgresql
  - pgvector
summary: Reference note for PostgreSQL as the canonical normalized evidence and application data store in dial-stack.
repo_usage_state: core-mvp
repo_version: custom image dial-stack/postgres-forensics:pg16 in docker-compose.yml
upstream_version: PostgreSQL 18.3 current docs reviewed 2026-03-30; repo intentionally targets pg16
official_docs:
  - https://www.postgresql.org/docs/current/index.html
official_repo:
  - https://github.com/postgres/postgres
official_downloads:
  - https://www.postgresql.org/download/
  - https://github.com/pgvector/pgvector
---

# PostgreSQL

## At a Glance

- **What it is**: The canonical relational store for normalized evidence and app data.
- **Current role in `dial-stack`**: Canonical storage after DuckDB first-touch intake, and canonical home again after enrichment returns.
- **Why it matters**: This is the durable, queryable center of the platform’s structured evidence model.

## How `dial-stack` Uses It

PostgreSQL is where normalized evidence records live.

Current local anchors:

- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)
- [00-extension-bootstrap.sql](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/init/postgres/00-extension-bootstrap.sql)
- [01-init.sql](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/init/postgres/01-init.sql)
- [PostgresWriter.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/tools/PostgresWriter.ts)

Current responsibilities:

- canonical normalized message, document, and conversation storage
- application state tables
- cross-tier linkage anchors
- post-enrichment persistence for Semantica and other derived outputs

## Pipeline Position

The working pipeline is:

`DuckDB -> PostgreSQL -> Semantica + LanceDB in parallel -> PostgreSQL enrichment`

That means PostgreSQL is both:

- the first canonical relational write after evidence-safe intake
- the place where enriched or verified outputs return for durable normalization

## Repo Version vs Upstream Version

| Posture | Value | Notes |
|---|---|---|
| Repo image | `dial-stack/postgres-forensics:pg16` | Custom repo image built from local Dockerfile |
| Upstream current docs | `18.3` | PostgreSQL site reviewed 2026-03-30 |
| Repo design choice | `pg16` | Intentional compatibility posture in current compose |

## How We Use It Today

We use PostgreSQL for:

- normalized evidence entities
- conversations and messages
- analyst/review data
- audit logging and app-side operational tables

It is not the first-touch evidence vault. That job belongs to DuckDB.

## How We Could Expand Its Use

- migrate more provenance and verification tables into explicit first-class schemas
- tighten UUIDv7 usage across evidence-facing tables
- add stronger append-only or event-style audit patterns for sensitive updates
- add row-level policies if we introduce stronger multi-user separation
- formalize enriched analysis tables for NER, sentiment, abuse screening, and later contradiction work

## What We Need to Watch

- older docs still blur canonical relational storage with first-touch intake
- some schema assumptions still reference older UUID patterns and tier numbering
- raw query interfaces need tight limits and auditability
- normalization must not drop raw fields that were available during intake

## Key Repo Files

- [01-init.sql](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/init/postgres/01-init.sql)
- [00-extension-bootstrap.sql](C:/Users/matts/Projects/TheBigOne/dial-stack/infrastructure/init/postgres/00-extension-bootstrap.sql)
- [PostgresWriter.ts](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/ts-mcp-server/src/tools/PostgresWriter.ts)
- [docker-compose.yml](C:/Users/matts/Projects/TheBigOne/dial-stack/docker-compose.yml)

## Official Sources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/current/index.html)
- [PostgreSQL Downloads](https://www.postgresql.org/download/)
- [PostgreSQL GitHub Mirror](https://github.com/postgres/postgres)
- [pgvector GitHub](https://github.com/pgvector/pgvector)

## Related Notes

- [[skills/database/duckdb|DuckDB]]
- [[skills/database/lancedb|LanceDB]]
- [[skills/database/neo4j|Neo4j]]
- [[skills/nlp/semantica|Semantica]]
- [[INDEX|dial-stack Wiki Index]]
