# ADR-0050: Six-lane knowledge architecture + memory namespaces

- Status: **Accepted** — owner rulings 2026-08-10 (structured Q&A + plan approval, this session);
  design plan approved via plan mode (`https-docs-agno-com-features-storage-duc-glittery-summit`).
- Date: 2026-08-10
- _Byline: Claude Code · Fable 5 · 2026-08-10_
- Supersedes: ADR-0020's four-domain taxonomy (the multi-domain *shape* survives; the vocabulary
  and per-lane storage change). Amends: ADR-0030 (rclone role wording). Related: ADR-0010 (one
  collection per embedder — unchanged), ADR-0040 (Weaviate substrate — unchanged), ADR-0043
  (Postgres flatten — unchanged), ADR-0044 (evidence-vs-context boundary — now enforced in
  storage topology), ADR-0045 (horizon clocks — consumed by the evidence retrieval seam).

## Context

Audit 2026-08-10 (verified in code): 3 KBs registered but `evidence_knowledge` had NO writer
while custody-approved transcripts vectored into the *platform* collection; every KB's contents
rows landed in one hardcoded `platform_knowledge_contents` table; two incompatible `domain`
metadata vocabularies coexisted; zero `knowledge_filters` usage anywhere (lanes unscoped); no
chunking configured; LearningMachine ran one global namespace. Owner rulings 2026-08-10:
evidence is **entirely different** from legal (legal = strategy + documents only); personal
history and relationship history are **two different knowledge bases**; rclone was never
supposed to own ingestion — **pg_duckdb is the bulk-ingestion point**.

## Decision

### 1. Six lanes, one Knowledge instance each (separate Weaviate collections)

| Lane | Collection | Contents table (Postgres, schema `ai`) |
|---|---|---|
| `platform` | platform_knowledge | platform_knowledge_contents |
| `legal` | legal_knowledge | legal_knowledge_contents |
| `personal_history` | personal_history_knowledge | personal_history_knowledge_contents |
| `relationship_timeline` | relationship_timeline_knowledge | relationship_timeline_knowledge_contents |
| `context` | platform_context | platform_context_contents |
| `evidence` | evidence_knowledge | evidence_knowledge_contents |

NOT `isolate_vector_search` one-collection: evidence isolation must be **structural** — a missed
filter injection must never be able to leak evidence into platform/legal answers. Hybrid BM25
statistics stay per-corpus. Reuses `create_knowledge` + `KnowledgeHandle` unchanged.

Every `PostgresDb` instance passes explicit `id="agentos-db"` and stays in schema `ai`
(framework fact, agno 2.8.6: knowledge `contents_db` instances live in AgentOS's separate
`knowledge_dbs` dict and never arm the multi-db 400 gate; schema splits change the derived
db_id and DO arm it — never split schemas).

### 2. One embedder for all lanes — for now

All six lanes use `nvidia/nv-embed-v1` (4096-d). **Owner ruling 2026-08-10: per-lane embedders
are a future experiment; re-embed after tests.** Raw docs are the source of truth (ADR-0010),
so a lane can be re-embedded into a fresh collection at any time; nothing in this design
assumes embedder homogeneity.

### 3. Unified flat-scalar metadata (Weaviate dict filters only)

`lane` (exactly one of the six) · `doc_type` (transcript|doc|note|rubric|motion|sms|chat) ·
`source` · `case_id` (TEXT `"primary"`, never multi-case). Evidence lane adds `visible_from`
and `realization_event` (ADR-0045 surface). Migration map from the two legacy vocabularies:
`platform`/`platform_design`→`platform` · `legal`/`legal_strategy`→`legal` ·
`timeline_relationship`→`relationship_timeline` · `personal_history`→`personal_history`.
Existing vectors are **re-ingested, not migrated** (disposable derivatives).

### 4. Evidence lane contract

- Writer: EXCLUSIVELY custody-approved `NormalizedRecord`s via `ingest_into_knowledge` handed
  the evidence handle. No folder-walk ingest root for evidence, ever.
- Retrieval: ONLY through the horizon-gated seam (`server/evidence/retrieval.py`, Phase 3),
  which always injects the ADR-0045 dict pre-filter. **Pre-S6 default: deny records without
  `visible_from`** — horizon contamination destroys the analytical deliverable; every denial
  and every applied filter is audited to `ops.audit_ledger`.
- No agent ever holds the raw evidence handle.

### 5. Memory namespaces (LearningMachine only)

Keep the ADR-0043 flatten (one operational PostgresDb, `id="agentos-db"`); keep ONE
`agno_learnings` table (agno multiplexes six stores by indexed `learning_type`+`namespace` —
splitting tables breaks route resolution). `build_learning` gains a `namespace` parameter:
`user_profile`/`user_memory` stay global (single user); `learned_knowledge` namespace = the
agent family's primary lane. `decision_log` activates for the Legal family only, HITL-gated.
`enable_user_memories` stays exactly Root Router + Project PAL. **No MemoryManager** — it would
double-capture user memories in a parallel store.

### 6. pg_duckdb = the bulk-ingestion point; rclone = file transport ONLY

Owner ruling 2026-08-10 (emphatic): rclone is "only for moving shit" — it never owned
ingestion. Bulk data (CSV/Parquet/JSON, local or R2) lands via pg_duckdb
(`staging.raw_<source>_<batch>` tables) and flows through the existing normalize path into
custody.py — which remains the sole evidence-schema writer. pg_duckdb keeps its query role.
ADR-0030's "file-level ingestion → rclone" wording is corrected by amendment.

### 7. Agent→lane mapping (amends ADR-0020)

One primary lane per family via `knowledge=` (agno: an Agent holds exactly one Knowledge);
cross-lane via **team members**, not custom retrievers. Legal → `legal` + Evidence Analyst
member (horizon-gated) + relationship_timeline member. Analysis → `relationship_timeline` +
personal_history member. Builder/dev → `platform`. Digest/recall → `context`.
`enable_agentic_knowledge_filters` on Legal/Analysis families only, and only once per-KB
contents tables exist (agno's filter validation is a no-op without a correct contents_db).

## Consequences

- Cross-lane leakage becomes physically impossible at the storage layer; the horizon gate
  defends only within the evidence lane.
- Six collections re-ingest from originals when the vocabulary lands (Phase 2) — compute cost,
  no data loss.
- Chunking: explicit `RecursiveChunking` baseline first, A/B in `evals/`, then turn-aware
  semantic+fixed hybrid for transcript lanes (Chonkie arrives via agno's `SemanticChunking`,
  no new direct dependency) — governed by `docs/planning/agno-chunking-strategy.md` §6.
- Implementation phases 0-7 with per-phase observed-behavior verification live in the approved
  plan (`C:\Users\matts\.claude\plans\https-docs-agno-com-features-storage-duc-glittery-summit.md`);
  phase status is tracked in DECISION_LOG entries as phases land.

## Alternatives considered

- `isolate_vector_search` one-collection with `linked_to` partitions — rejected: filter-dependent
  evidence isolation, requires reindex anyway, degrades per-lane BM25.
- Custom retrievers for cross-lane agents — rejected: bypasses KnowledgeHandle boot-resilience
  and filter validation; team routing is the framework-native path.
- MemoryManager alongside LearningMachine — rejected: double-capture.
- Per-lane `agno_learnings` tables — rejected: breaks agno's `?table=` route resolution;
  the single table is indexed for exactly this multiplexing.
