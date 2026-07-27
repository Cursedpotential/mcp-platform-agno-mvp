# ADR-0040: Vector substrate revisit — Weaviate vs pgvector vs keep-Milvus

> _Byline: Claude Code · Fable 5 · 2026-07-27_

**Status**: ACCEPTED — owner locked Weaviate 2026-07-27 (AskUserQuestion). Migration plan still to be executed.
**Supersedes/amends**: ADR-0026 (self-hosted Milvus on Coolify), ADR-0027 (Milvus platform-wide substrate). ADR-0010 (two collections) and ADR-0011 (dimension contract) carry over unchanged — they govern shape, not engine.

## Context

- Self-hosted Milvus is a convoy (etcd + MinIO + MQ), RAM-hungry on VPS-scale hardware. Lived evidence: 2026-07-21→23 etcd crash loop, ~2-day outage, `platform_knowledge` collection wedged in perpetual `Loading` and dropped/recreated. Self-recovered, but the fragility class is documented.
- 2026-07-13 chat session ("Explaining complex topics simply" export) proposed demoting Milvus to pgvector, blocked on one crux: **embed contract is nv-embed-v1 @ 4096-d, and pgvector's HNSW cap is ~2000-d (4000 halfvec)** — 4096-d cannot be ANN-indexed in pgvector. Stepping down to a ≤2000-d embedder means re-embedding every store (global learning: mixed dims hard-error).
- Owner (2026-07-27) raised **Weaviate** as a candidate.
- FTS-first ships regardless (ADR lineage), so the vector layer is not on the critical path.

## Options

| | pgvector | Weaviate | keep Milvus |
|---|---|---|---|
| New services | 0 (in data-pg) | 1 single Go binary | 4-container convoy (status quo) |
| 4096-d nv-embed-v1 | ❌ re-embed to ≤2000-d required | ✅ no practical HNSW dim cap | ✅ |
| Hybrid BM25+vector | via PG FTS + join | ✅ native | ✅ (sparse+dense) |
| Ops risk | lowest | low (single process) | highest (proven) |
| Provenance locality | ✅ vectors beside `normalized_record` | external, needs id discipline | external, needs id discipline |

## Decision (proposed)

**Weaviate becomes the leading candidate** for primary vector substrate: it removes the ops-fragility that motivated the revisit *and* dissolves the 4096-d blocker (no re-embed). pgvector remains the fallback if the owner prefers zero new services and accepts a ≤2000-d re-embed. Milvus demoted to parked (FalkorDB status) once cutover is verified.

## Owner-reported Milvus symptoms (2026-07-27, decision basis)

Data corruption; general unreliability/outages (crash loops, collection wedging); heavy resource
footprint for components not even used (deployment does not use MinIO). Combined with the
documented 07-21→23 etcd outage this settles the demotion.

## Decision: **Weaviate — LOCKED**

## Remaining execution steps

1. Weaviate resource profile on the target node (verify RAM at current corpus scale).
2. Migration: re-embed-free export of existing 4096-d vectors Milvus → Weaviate (dims preserved).
3. Cutover platform consumers (knowledge pipeline) → verify search parity.
4. **Milvus stays STOOD UP but sidelined** (owner 2026-07-27): at least one MCP (memsearch lane)
   still depends on it. No new platform writers; it serves only that MCP until that consumer is
   migrated or retired — then the convoy is decommissioned.

## Consequences

- Graphiti/agent memory unaffected (graph-side, see ADR-0041).
- memsearch and any Milvus-pinned consumers need connection-string-level migration.
- Attu retires with Milvus; Weaviate has its own console.
