# Architecture Decision Records (ADRs)

Lightweight [MADR](https://adr.github.io/madr/)-style records of decisions that are **locked** —
so they are not silently re-litigated or forgotten across sessions/agents.

**Rule:** any decision that changes architecture, a dependency, a data boundary, or a security/HITL
guarantee gets an ADR. One short record. Supersede (don't edit) when a decision changes.

**Status values:** Proposed · Accepted · Superseded by ADR-XXXX · Deprecated.

## Index
| # | Title | Status |
|---|---|---|
| 0001 | Build fresh from the Agno skeleton; abandon the v1 repo | Accepted |
| 0002 | Native Agno HITL (requires_confirmation + continue_run); approval_request is the audit record | Accepted |
| 0003 | PostgreSQL 18 (native uuidv7), pgvector-only, no DuckDB; FalkorDB deferred | Accepted |
| 0004 | Memory = native LearningMachine; no hand-rolled learned_knowledge table | Accepted |
| 0005 | Context Providers as the source-access layer (ports-and-adapters) | Accepted |
| 0006 | Two-layer team topology: root Router (route) over coordinate families | Accepted |
| 0007 | Incorporate n8n + Cloudflare R2; R2 = blob/object landing zone | Accepted |
| 0008 | Provider-agnostic model factory, no hard default, pinned IDs | Accepted (D7 closed by 0011/0015) |
| 0009 | Build & run on the OVH Debian VPS; author locally, sync over SSH | Accepted |
| 0010 | Per-task embeddings = one vector collection per embedder | Accepted (text embedder superseded by 0011) |
| 0011 | NVIDIA NIM provider; embedder dimension contract (text 2048-d / code 4096-d) | Accepted (runtime LLM choice superseded by 0015) |
| 0012 | Phase-0 decisions locked | Accepted |
| 0013 | pg_duckdb inside a custom PG18 image (DuckDB native in Postgres) | Accepted (supersedes 0003's no-DuckDB) |
| 0014 | Neo4j for the Graphiti temporal graph (not FalkorDB) | Accepted |
| 0015 | LiteLLM gateway; Ollama Cloud primary LLM, NVIDIA = embed/rerank/backup | Accepted (supersedes 0011 runtime choice; closes 0008 D7) |
| 0016 | Consolidated tool containers (platform-tools / sandbox / gateway) + Kasm desktop | Accepted |
| 0017 | Evidence = polyglot orchestration mesh (custody → workflows → atomic tools) | Accepted |
| 0018 | Bitemporal evidence memory + disclosure-tier (multi-pass cognition substrate) | Accepted (extends 0014) |
| 0019 | Three agent families — add the AI Legal Team (Part 3) | Accepted (extends 0006) |
| 0020 | Multi-domain knowledge engine — domain-separated, any-agent queryable | Accepted (extends 0010/0011) |
| 0021 | Engineering conventions — no-stub discipline, harness-first tests | Accepted |
| 0022 | Comprehensive living wiki — dual-purpose (AI + human), covers everything | Accepted (vision; build deferred) |
| 0023 | Universal exposure — API-first, MCP-wrapped (every tool/agent/workflow) | Accepted (pairs with 0017) |
| 0024 | SurrealDB = store/session/Knowledge/memory layer; Graphiti stays cognition | Accepted (vector/Knowledge role moved to Milvus by 0027) |
| 0025 | Topology: Agno core + IBM ContextForge tool gateway + LiteLLM model gateway; minimize custom | Accepted (clarifies 0015; reinforces 0017) |
| 0026 | Self-hosted Milvus (Coolify) = shared semantic store (code + Case Bible); off managed EU Zilliz | Accepted (LIVE on ovh2; extended by 0027) |
| 0027 | Milvus = platform-wide vector/ANN substrate (Knowledge engine included) | Accepted (supersedes-in-part 0024 + 0010/0011 vector storage) |
| 0028 | Windmill = CaseBible orchestration substrate (replaces FileFlows); execution layer under Agno | Superseded by ADR-0029 (2026-06-23 — Windmill dead) |
| 0029 | CaseBible execution substrate = a dedicated persistent resource on the Agno stack | Accepted (supersedes 0028) |
| 0030 | Agno R2 access = pg_duckdb account-wide S3 secret (SQL) + rclone bucket mount (files); creds in Coolify | Accepted (extends 0007/0013) |
| 0031 | CaseBible entity/temporal-graph layer = Neo4j + Graphiti, isolated by group_id | Accepted (extends 0014/0018) |
| 0032 | Drop the PG Multicorn FDW federation hub; cross-source reach = pg_duckdb + native drivers | Accepted (supersedes 2026-06-14 federation-hub stance) |
| 0033 | `server/` package layout (Option A repack) | Accepted (merged + deployed; amended 2026-07-09 — tools promoted to `server/tools/`, `vendored/` scope broadened) |
| 0035 | Tools sub-namespacing, tool_finder extraction, and the record contract's home | Accepted & Implemented (merged `8240205`, deployed + verified 2026-07-10; supersedes/relates ADR-0033) |
| 0036 | DozerDB multi-DB RBAC — memory/evidence isolation | Accepted (owner 2026-07-29; execution pending) |
| 0037 | Graphiti MCP via ContextForge, write-enabled | Accepted (owner 2026-07-29; blocker cleared per D-028; retire `:8071` door pending) |
| 0038 | Agno agents ↔ Graphiti as native library | Accepted (owner 2026-07-29) |
| 0039 | Graphiti extraction LLM = hosted structured-output model | Accepted (owner 2026-07-29; implemented in practice 2026-07-04 via NIM nemotron, lane now Portkey) |
| 0040 | Vector substrate revisit — Weaviate LOCKED (vs pgvector / keep-Milvus) | Accepted (2026-07-27; supersedes 0026/0027 engine choice; migration pending, Milvus sidelined) |
| 0041 | Memgraph = additive temporal GraphRAG layer, read-side only (Neo4j/DozerDB stays) | Accepted (2026-07-28; Variant B) |
| 0042 | Portkey replaces LiteLLM as THE model gateway; LiteLLM retired | Accepted (2026-07-29; supersedes 0015; teardown pending) |

> The full vision, current stack, roadmap, access, and gotchas live in
> [`docs/PROJECT_CANON.md`](../PROJECT_CANON.md) (the durable source of truth).
> The live stub/debt register is [`docs/DEBT.md`](../DEBT.md).

## Template
```md
# ADR-XXXX: <title>
- Status: Accepted | Proposed | Superseded by ADR-YYYY
- Date: YYYY-MM-DD
## Context
<the forces / problem>
## Decision
<what we decided, in one or two sentences>
## Consequences
<what becomes easier/harder; obligations this creates>
## Alternatives considered
<what we rejected and why>
```
