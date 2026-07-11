# Research log — Agno memory/storage/retrieval expertise sweep

> _Byline: Claude Code · Fable 5 · 2026-07-11_
> Purpose: durable record of the research run (agent reports, verifications, decisions-in-flight)
> so it can be revisited later, per owner directive ("persist all of these tool calls and reports").
> Plan: `~/.claude/plans/squishy-purring-simon.md` · Branch: `docs/agno-memory-expertise`.

## Run shape

- **Inputs:** owner's Tab Porter export of 110 Agno-docs tabs → 102 unique URLs (`_url-checklist.md`);
  owner clarified mid-run the list is a **floor, not a ceiling** ("ran out of steam opening tabs") —
  all doc researchers were re-scoped to enumerate entire sections.
- **Phase 1 exploration** (2 Explore agents): platform stack inventory + agno 2.6.13 installed-surface
  inventory. Produced the 7 open discrepancies the synthesis must answer (listed in `INDEX.md` /
  plan file).
- **Phase R1:** 6 Sonnet researchers, one file each, incremental writes, no git ops (main thread
  commits checkpoints).
- **Infrastructure incident:** the `claude.ai agno` docs MCP server disconnected right after launch
  and **never reconnected**. R1a/R1c/R1d fell back to direct `WebFetch` of docs.agno.com + raw
  `sitemap.xml` via curl (WebFetch's summarizer silently drops sitemap entries) + `llms.txt`.
  R1b stalled retrying the dead MCP and was re-scoped by SendMessage to the same fallback.
  All fallbacks are declared in each file's Coverage/Sourcing sections — nothing hidden.
- **Fleet triage note:** owner saw "failed tasks" in the panel; authoritative `TaskOutput` checks
  showed none of the six failed — panel entries were earlier-session corpses (resume-killed agents,
  by-design timed-out watchers). Triage ground truth = file-on-disk growth + TaskOutput status.

## Researcher completion reports (verbatim summaries)

### R1e — Substrates beyond Agno (`05-substrates-beyond-agno.md`, 507 lines) — banked `880fdca`

Covered SurrealDB v3.x (SurrealQL multi-model, HNSW/DISKANN/MTREE, FULLTEXT+BM25, live queries,
RBAC/record-user auth, transactions, bitemporal fit for ADR-0024), Milvus 3.0 (schema/dynamic
fields, partitions vs partition-key, hybrid + RRF/weighted rerankers, BM25 function, filter
pushdown, index menu, consistency levels, TTL, RBAC, Milvus Lite), Graphiti/Zep on Neo4j (episode
model, bitemporal edge invalidation, community nodes, group_id namespacing, retrieval recipes,
custom entity types, MCP surface vs graphiti-core), pgvector+pg_duckdb on PG18. Each section ends
"How WE run it" tied to compose files/configs.

**Top unused capabilities:** (1) **Milvus partition keys** for per-domain/per-case isolation
(forensic collections have candidate fields `subject_type`/`category_id`, no partition key today);
(2) **Graphiti custom entity/edge types** (Pydantic in config.yaml — none defined today; would align
extraction with the behavioral-category ontology); (3) **SurrealDB one-statement
vector+graph+full-text hybrid** + DISKANN (we use Surreal only for sessions/state).
**Conflict confirmed:** `docker/graphiti/config.yaml` group_id `platform` vs
`semantica_wiring.py` hardcoded `casebible`.

### R1f — Semantica VIP (`06-semantica.md`) — banked `ebe3f6c`

Vendored general-purpose knowledge-engineering framework (upstream Hawksight-AI, MIT, ~615 files,
24 modules): ingestion, parsing, NER/relation/triplet extraction (spaCy default, LLM optional),
KG construction/analytics, graph/vector/triplet storage, PROV-O provenance, versioning, conflict
detection, dedup, ontology generation, reasoning, thin `context/` agent-memory. **Alpha maturity:**
version drift 0.3.0-alpha (pyproject) vs 0.2.7 (`__init__`), `evals/` stub, orchestrator imports
commented out, torch/spaCy/transformers/faiss are mandatory core deps (why its tests are opt-in
and `vendored/` is excluded from gates). Integration = seed-first hybrid per `semantica_wiring.py`
(design-only, approvals-gated, zero writes): Milvus lane dim-locked bge-m3/1024 overriding
Semantica's 768 default (locked by passing `tests/test_semantica_wiring.py` incl secrets-never-
inlined assertion); Neo4j `role: read_derive` only — Graphiti sole writer (ADR-0014); PG seeds
`extend_not_replace=True`. **Strongest for our entity/detection lane:** `conflicts/` (cross-source
conflict detection), `deduplication/` (multi-metric entity merge), `kg.EntityResolver` +
`context.entity_linker` (fuzzy cross-doc resolution as a proposal layer downstream of PG).
**Risks:** group_id conflict; **phantom citation** "ADR ~0035 Semantica placement" (the real 0035
is tools sub-namespacing) — doc debt; the planned `GraphWriteAdapter` write-gate **does not exist
as code**; heavy/unstable dep surface.

### R1a — Memory + Learning (`01-memory-and-learning.md`, 964 lines) — banked `9d71a68`

All 35 pages read (4 beyond the checklist: memory-search, mongodb-memory, redis-memory,
learning/quickstart). **Critical production bug — main-thread source-verified before acceptance:**
agno 2.6.13 `agno/db/surrealdb/surrealdb.py:1990-2034` stubs
`get_learning/upsert_learning/delete_learning/get_learnings` as `NotImplementedError`. Our
LearningMachine is wired to SurrealDb ⇒ **`user_profile`, `user_memory`, `session_context`,
`entity_memory` are silent no-ops in production; only `learned_knowledge` works** (bypasses db via
Knowledge/Milvus). Additional discrepancies: `Curator.prune()/deduplicate()` is a shipped no-op
(wrong store/attr); `Agent(learning=True)`/`get_learning_machine()` doc example doesn't exist in
source; `entity_memory`/`user_profile` **silently degrade PROPOSE→ALWAYS** (log-warning only) — our
`# HITL` comment on entity_memory is wrong independent of the DB gap (learned_knowledge's PROPOSE
is a genuine HITL gate). Answers: MemoryManager & LearningMachine **coexist** (no supersession);
SurrealDb has **zero LearningMachine parity** with PostgresDb; `decision_log` store exists,
unconfigured, same gap if enabled.

### R1c — Storage + VectorDBs + Gateways (`03-storage-and-vector-backends.md`) — banked `95c66e5`

BaseDb contract actually has **12 table roles** (docs say 8; SurrealDb lacks
components/schedules/approvals; parity on the core 8). SurrealDb *Db* backend is **sync-only**
(its *vectordb* is async — distinct classes). Milvus/PgVector/SurrealDB-vectordb/LanceDB deep-dive
against source; **Milvus hybrid's sparse half is a local hashed-TF-IDF approximation, not a real
sparse-embedding model**. All 8 gateways covered incl LiteLLM SDK-vs-proxy modes and a
LiteLLM→Portkey migration analysis. Answers: contents_db on PG is a **design choice, not a
technical necessity** (SurrealDb fully implements `knowledge_table`); Agno's documented multi-domain
pattern is `isolate_vector_search` (one collection + `linked_to` filter, **cannot mix
embedders/dims**) — our separate-collections-per-embedder plan is a stronger-isolation pattern
that agno supports mechanically but doesn't document.

### R1d — RAG patterns + Tools + Context (`04-rag-patterns-tools-context.md`, 807 lines) — banked `95c66e5`

All 22 assigned URLs + 13 extras via enumeration; skipped-adjacent pages listed with rationale.
Discrepancies: KnowledgeTools docs example uses **nonexistent kwargs** (real:
`enable_think/enable_search/enable_analyze`); caching docs omit `cache_ttl`/`cache_dir` and
behaviors (generators never cached; non-serializable results silently not persisted).
Recommendations: don't retrofit KnowledgeTools onto the existing three agents; default it for the
first AI-Legal-Team research agent (multi-hop + audit trail); leave Graphiti/SBV MCP tools
**uncached** (mixed read/write tools in one MCPTools instance); adopt **materialized-view**
caching of validated recurring queries inside the existing `apply_db_modification` HITL gate;
skip the docs' Analyst/Engineer/Leader role split (we have equivalent safety layers).

### R1b — Knowledge + Retrieval (`02-knowledge-and-retrieval.md`) — IN FLIGHT at log time

Stalled at 73 lines retrying the dead MCP; re-scoped via SendMessage to the proven WebFetch +
raw-sitemap fallback with incremental flushes. Its completion report will be appended to this log.

## Owner design exchange (2026-07-11, mid-run)

Owner (voice, confirmed "SURREAL*"): **SurrealDB could be the first and last stop for
knowledge-side stuff** — AI-chat-transcript KB, code KB — **but evidence does NOT land there until
the end of the process.**

Assistant honest-broker read (recorded for the synthesis):
- Evidence instinct already matches the architecture: raw → PG (custody, bitemporal
  `analysis.normalized_record`); only derived/end-stage products reach any KB substrate. Keep.
- **For Surreal-as-KB-home:** native one-statement vector+graph+FTS/BM25 hybrid, DISKANN, live
  queries (ADR-0024 partly bought this).
- **Against (source-verified):** agno's SurrealDB vectordb is vector-only (Surreal hybrid ⇒ custom
  `knowledge_retriever` we own); agno's Surreal integration is the thinnest surface (sync-only Db +
  the learning-stub bug above); Milvus is ADR-0026/27-locked with working hybrid + partition keys
  (caveat: its sparse is the TF-IDF approximation).
- **Lean pending synthesis:** Milvus stays the vector workhorse; Surreal keeps operational/session
  (after the memory-bug fix); "Surreal-native hybrid via custom retriever" is the **challenger
  architecture** and gets a first-class decision section + comparison table in
  `07-platform-mapping.md`. If compelling → a proper ADR, not a silent pivot.

**Owner follow-up (same exchange) — Surreal's SECOND role:** SurrealDB is also the
**consolidation space for analysis** — after everything has run through normalization, the
individual detections, and the analysis passes, Surreal is where the **whole story is put
together**: all results, all analysis, all data brought together **after the heavy tools have done
their work**. I.e. Surreal = the narrative-assembly / story layer over *finished* outputs (which
is exactly why evidence doesn't land there until the end of the process — it's not an evidence
store, it's where derived findings, timelines, and conclusions consolidate). This matches
ADR-0024's original intent (Surreal as the bitemporal-record/analysis-sink layer, reaffirmed by
ADR-0032 "surreal is analysis sink") and plays to its multi-model strength: graph relations
linking findings↔evidence-refs↔timeline entries, documents for narratives, vectors over
conclusions. **Synthesis must treat Surreal's roles as: (a) KB first/last stop [candidate,
challenger architecture], (b) post-analysis consolidation/story space [owner-affirmed], (c)
operational/session store [current, needs the LearningMachine-stub fix decision].**

## Checkpoint commits (this branch)

| Commit | Content |
|---|---|
| `880fdca` | R1e substrates + `_url-checklist.md` |
| `ebe3f6c` | R1f Semantica |
| `9d71a68` | R1a memory+learning |
| `95c66e5` | R1c storage/vectordb + R1d RAG/tools |

## Still open for Phase R2 synthesis

1. The 7 discrepancies (plan file) — several already answered above (LearningMachine parity: NO;
   MemoryManager supersession: coexist; contents_db: design choice; multi-domain: separate
   collections undocumented-but-supported); remaining: group_id live-episode check, 3-embedding-
   regimes rationalization, Milvus reranker-hook vs RRF detail, Milvus schema/filter-pushdown detail.
2. The **LearningMachine-on-SurrealDb fix decision** (move to PostgresDb / implement stubs / split
   stores) — owner call, recommendation to be drafted.
3. The **Surreal-as-KB-home** decision section (owner direction above).
4. Phantom "ADR ~0035 Semantica placement" citation cleanup; `GraphWriteAdapter` absence.
5. INDEX.md with full coverage accounting (checklist + beyond-checklist pages per researcher).
