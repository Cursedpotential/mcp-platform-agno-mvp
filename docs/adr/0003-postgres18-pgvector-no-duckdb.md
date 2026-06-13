# ADR-0003: PostgreSQL 18 (native uuidv7), pgvector-only, no DuckDB; FalkorDB deferred
- Status: Accepted
- Date: 2026-06-01

## Context
The MVP needs relational state, vector embeddings, and HITL audit tables. The handoff pins Postgres 18
for native `uuidv7()` (timestamp-ordered PKs, better index locality) and standardizes on pgvector.
DuckDB and a second graph engine add operational surface without MVP value.

## Decision
Custom **PostgreSQL 18** image (PostGIS + pgvector + pg_textsearch). PKs default to `uuidv7()`. Hashes
stored as `BYTEA`. **No DuckDB** anywhere in the Agno stack; **pgvector only** for vectors; **FalkorDB /
Graphiti deferred** to the platform (Semantica) stage. If PG18 builds of any extension are unavailable
at pin time, fall back to **PG17 + the `pg_uuidv7` extension** and note it.

## Consequences
- One datastore for relational + vector + audit; simpler ops.
- Embedder dimension is contractual: `VECTOR(1536)` ↔ `text-embedding-3-small`; changing embedder ⇒ re-embed.
- The TS MCP server's internal DuckDB vault is a black-box tool, not part of the Agno stack — not a contradiction.

## Alternatives considered
- DuckDB staging / `pg_duckdb` — rejected (Semantica owns ingestion; no external-lake join problem).
- Weaviate / second vector store — rejected for MVP (pgvectorscale is the in-DB scale path).
