# ADR-0040: Vector substrate revisit — Weaviate vs pgvector vs keep-Milvus

> _Byline: Claude Code · Fable 5 · 2026-07-27_

**Status**: ACCEPTED — owner locked Weaviate 2026-07-27 (AskUserQuestion). ~~Migration plan still to be executed.~~ **Amendment 2026-08-09 (D-042): cutoVER VERIFIED — Milvus→Weaviate migration executed (pymilvus removed from the image); Weaviate is THE vector store. The `data-vector`/Milvus Coolify app is DOWN deliberately since 2026-08-10 (6th embedded-etcd corruption); Case Bible's own `casebible_ai_conversations` memsearch lane is a separate, intentionally-retained concern (see Remaining execution steps #4).**
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

1. ~~Weaviate resource profile~~ ✅ 2026-07-27: data node has 7.6 GiB total / 4.1 GiB available
   (Milvus itself only 760 MiB; Neo4j 1 GiB is the biggest tenant). Corpus is small — Weaviate
   footprint at this scale ≈ 300–500 MiB. Fits comfortably even with Milvus still standing.
2. Migration: re-embed-free export of existing 4096-d vectors Milvus → Weaviate (dims preserved).
3. Cutover platform consumers (knowledge pipeline) → verify search parity.
4. ~~**Milvus stays STOOD UP but sidelined** (owner 2026-07-27): at least one MCP (memsearch lane)
   still depends on it. No new platform writers; it serves only that MCP until that consumer is
   migrated or retired — then the convoy is decommissioned.~~ **Corrected 2026-08-09/10 (D-042):**
   the platform cutover to Weaviate is VERIFIED and pymilvus removed from the image; the platform
   `data-vector` Milvus app is DOWN deliberately since 2026-08-10. The **Case Bible** corpus has its
   OWN Milvus (`casebible_ai_conversations`, the memsearch lane) which ADR-0040 does NOT govern —
   that stays as a separate SORT-owned concern until its own migration/retirement.

## Amendment 2026-08-23 — memsearch Milvus is LIVE (local storage)

> _Byline: Claude Code · Opus 5 · 2026-08-23_

The memsearch-only Milvus described in "Remaining execution steps" #4 was designed and
committed 2026-08-12 but **never actually deployed** — Coolify showed only the old
`data-vector` app sitting `exited:unhealthy`. It is now live.

**Root cause of the crash loop: bind-mount permissions, not S3.** Boot died at
`[FATAL] paramtable/component_param.go:4721 "failed to mkdir" [localStoragePath=
/var/lib/milvus/data] [error="mkdir ...: permission denied"]` → panic → SIGABRT rc=134.
Docker auto-creates `/data/agno/volumes/milvus-memsearch` as root:root, but the
`milvusdb/milvus:3.0-*` image runs Milvus as a non-root user. Fix: `user: "0:0"` on the
service (matches upstream's standalone compose); attu needs it too. The 2026-08-12 R2 build
failed for the SAME reason, hit earlier on `ETCD_DATA_DIR` — which is why bucket
`milvus-memsearch` stayed at 0 objects throughout.

**R2/S3 backed out to local storage** (owner call, 2026-08-23) — `common.storageType: local`
+ `localStorage.path`, Storage V3 disabled. Fewer moving parts, and no R2 Class-A op per
binlog flush. The 6 historical corruptions were EMBEDDED ETCD, not the object store, so this
does not reintroduce that failure class. The R2 bucket is retained empty for a fast revert.

**Verified live:** Milvus healthz 200, Coolify `running:healthy`; memsearch re-indexed across
scopes (`agent_session_memory`, `ms_agno_mcp_platform_*`, `ms_legal_workspace_*`,
`ms_the_platform_workspace_*`) and semantic search returns real scored results.

**Open:** Milvus still uses the default credential `root:Milvus` — change it. And
`/data/agno/volumes/milvus-memsearch` is now the ONLY copy of these vectors — back it up.

Scope unchanged: this is the memsearch lane only. The Agno platform stays on Weaviate.

## Consequences

- Graphiti/agent memory unaffected (graph-side, see ADR-0041).
- ~~memsearch and any Milvus-pinned consumers need connection-string-level migration.~~
  **Corrected 2026-08-23 (Claude Code · Opus 5): connection-string-level migration was never
  possible.** memsearch's `store.py` is a single `MilvusStore` class — Milvus-only, no
  pluggable backend — so there is no connection string that reaches Weaviate. Reaching
  Weaviate would require writing a store adapter. This is why the step sat undone from
  2026-08-09 to 2026-08-23 while semantic recall was dead in 5/10 scopes.
- Attu retires with Milvus; Weaviate has its own console.
