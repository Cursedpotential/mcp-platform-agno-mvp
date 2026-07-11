# 07 — Platform mapping: answers, unused capabilities, decision agenda

> _Byline: Claude Code · Fable 5 · 2026-07-11 (Phase R2 synthesis of R1a–R1f)_
> Method: parallel lenses — capability facts (docs), verified behavior (source), our wiring
> (file:line) — synthesized per topic. **This document decides nothing.** Per owner directive it is
> the evidence base + a 7-topic agenda to be discussed bit by bit; each concluded topic gets a
> DECISION_LOG entry or ADR.

## A. The seven discrepancies — answered

| # | Question | Answer (evidence) |
|---|---|---|
| 1 | Graphiti `group_id`: `platform` vs `casebible`? | **`casebible` has ZERO episodes** (live check 2026-07-11). Historical episodes live in `platform`; recent ones in `agno-platform` (skill convention). `semantica_wiring.py`'s `casebible` assertion points at a never-written namespace. Three groups now need a deliberate policy → Topic 5. |
| 2 | Three embedding regimes — intentional? | **Yes, per-substrate, but under-documented.** Knowledge/Milvus = bge-m3 1024-d text + codestral 1536-d code (`session.py`, one collection per embedder, ADR-0010); Graphiti/Neo4j = nv-embed-v1 4096-d **dim-locked** (litellm-config); `settings.py:_EMBEDDER_IDS` is **stale/decorative** — never imported for embedding. Fix = delete/annotate the stale map → Topic 7. |
| 3 | LearningMachine on SurrealDb — parity? | **None.** `agno/db/surrealdb/surrealdb.py:1990-2034` stubs all four learning methods (`NotImplementedError`, source-verified). **`user_profile`/`user_memory`/`session_context`/`entity_memory` are silent no-ops in production**; only `learned_knowledge` works (bypasses db via Knowledge/Milvus). PostgresDb implements them fully. → Topic 1. |
| 4 | contents_db: PG vs SurrealDB? | **Design choice, not necessity.** SurrealDb fully implements the `knowledge_table` role; agno docs give no comparative guidance. PG co-location with evidence work + migration helpers is the current rationale. |
| 5 | Milvus reranking: hooks vs native RRF? | Hybrid always fuses with **hardcoded `RRFRanker(k=60)`**; the optional `reranker=` param adds a **post-hoc Python pass on top**. Caveat: agno's Milvus **sparse half is a local hashed-TF-IDF approximation**, not a real sparse-embedding model — hybrid quality expectations should be set accordingly. |
| 6 | Milvus schema + filter pushdown? | Hybrid schema = explicit `dense_vector`/`sparse_vector`/JSON-string `meta_data` fields (non-hybrid uses dynamic fields). **Dict filters push server-side via `_build_expr`** — so `store.py`'s `metadata.domain` filtering **is enforceable** (closes the DEBT.md flag). Gotchas: `List[FilterExpr]` silently **dropped** by Milvus; `SearchType.keyword` silently **ignored**. |
| 7 | MemoryManager vs LearningMachine? | **Coexist** in 2.6.13 as independent, non-interoperating systems. No supersession. (`enable_user_memories` is deprecated → `update_memory_on_run`.) |

## B. Verified doc-vs-source discrepancies worth remembering

- pgvector "hybrid" = **SQL weighted-linear-combination, not RRF** (docs claim RRF across backends; only Milvus truly RRFs).
- `Curator.prune()/.deduplicate()` is a **shipped no-op** (wrong store/attribute).
- `entity_memory`/`user_profile` **silently degrade PROPOSE→ALWAYS** (log-warning only) — our `# HITL` comment on entity_memory is wrong today; `learned_knowledge`'s PROPOSE is a genuine HITL gate.
- `Agent(learning=True)` / `get_learning_machine()` doc examples **don't exist** in source.
- KnowledgeTools docs use nonexistent kwargs (real: `enable_think/enable_search/enable_analyze`).
- Tool caching: real params `cache_results`/`cache_ttl`/`cache_dir`; generators never cached; non-serializable results silently not persisted.
- BaseDb has **12 table roles** (docs say 8); SurrealDb lacks `components/schedules/approvals`; SurrealDb *Db* is **sync-only** (its *vectordb* is async — distinct classes).
- LanceDB filters **client-side after `.limit()`** (recall loss); LangChain/LlamaIndex store pages are TBD stubs; `add_content()` deprecated in favor of `insert()`.

## C. Unused capabilities (candidates, not commitments)

| Capability | Where | Why it matters here |
|---|---|---|
| **Milvus partition keys** | forensic + KB collections | near-free per-domain/per-case search isolation (`subject_type`/`category_id` are natural keys) |
| **Graphiti custom entity/edge types** | `docker/graphiti/config.yaml` | align extraction with the behavioral-category ontology (none defined today) |
| **SurrealDB one-statement vector+graph+FTS hybrid** + DISKANN | native SurrealQL | the "first/last stop" KB idea; requires custom `knowledge_retriever` (agno's Surreal vectordb is vector-only) |
| `decision_log` learning store | LearningMachine | exists, unconfigured; blocked on Topic 1 fix |
| Materialized-view caching of validated queries | `analysis` schema via existing HITL gate | R1d recommendation; no new tooling |
| KnowledgeTools (think/search/analyze) | future AI-Legal-Team researcher | multi-hop retrieval + audit trail; **not** for the existing 3 agents |
| Graphiti retrieval recipes / community nodes | Graphiti MCP | richer recall for the consolidation/story layer |
| SurrealDB live queries + RBAC/record auth | consolidation space | reactive story-layer updates; per-case access control |

## D. Decision agenda — 7 topics (to discuss bit by bit; nothing decided here)

### Topic 1 — Fix the silent memory lanes (LearningMachine × SurrealDb)
**Now:** 4 of 5 lanes no-op. **Options:** (a) point LearningMachine `db=` at PostgresDb (works today; splits operational stores across two DBs); (b) implement the four SurrealDb learning methods ourselves (keeps one store; we own a patch/fork of agno); (c) defer lanes we don't yet need and enable only `learned_knowledge` + (a/b) later. **Also in scope:** the PROPOSE→ALWAYS degrade means entity-HITL needs its own answer regardless. **Decides it:** how much we value one-operational-store vs shipping now vs patch ownership.

### Topic 2 — KB substrate: Milvus incumbent vs SurrealDB challenger ("first/last stop")
**For Surreal:** native one-statement vector+graph+FTS/BM25, DISKANN, live queries. **Against:** agno's Surreal vectordb is vector-only → Surreal hybrid = custom `knowledge_retriever` we own; thinnest agno integration surface (sync-only Db, the Topic-1 bug); Milvus is ADR-0026/27-locked with working (true-RRF) hybrid + partition keys — though its sparse is the TF-IDF approximation. **Options:** (a) Milvus stays KB substrate, revisit later; (b) Surreal for AI-chat/code KBs via custom retriever (pilot one domain); (c) hybrid: Milvus for vectors, Surreal for the graph/story side only (Topic 3). **Decides it:** how much the one-statement hybrid is worth in owned code + who wins a retrieval-quality bake-off on one real domain.

### Topic 3 — Surreal consolidation space (owner-affirmed role)
The **story-assembly layer over finished outputs**: after normalization → detections → heavy-tool analysis, everything converges here (findings ↔ evidence-refs ↔ timeline ↔ narratives). Evidence lands **only at the end**. Matches ADR-0024 intent + ADR-0032 "surreal is analysis sink". **To design:** the record/graph shape (RELATE edges for finding→evidence-ref→timeline-entry), write path (agno-mediated vs native SurrealQL adapter), bitemporality, and how retrieval over conclusions works (Surreal FTS/vector? or mirror to KB?). **Decides it:** a schema sketch reviewed topic-by-topic with owner; likely its own ADR.

### Topic 4 — Per-domain vector DBs + specialized embedders (legal / code / timeline)
**Validated:** separate-collections-per-domain(+embedder) is mechanically supported and matches agno's own distributed-RAG example; `isolate_vector_search` is the wrong tool (single collection, single embedder/dim). **Middle path:** Milvus **partition keys** give per-domain isolation *within* one collection when the embedder is shared. **Options:** (a) separate collection per domain, per-domain embedder (max specialization; N configs); (b) shared embedder + partition-key domains (one config; no per-domain models); (c) mix: per-embedder collections, partition keys for sub-domains/cases. **Inputs:** chunking strategy per domain (see `docs/planning/agno-chunking-strategy.md`), symmetric-model house rule, dims fixed per collection, re-embed cost on model change. **Decides it:** how real the per-domain-model win is (bench on legal vs code samples) vs operational simplicity.

### Topic 5 — Graphiti tuning (groups, ontology, recipes)
**Groups:** live = `platform` (historical) + `agno-platform` (recent); `casebible` asserted-but-empty. **Options:** (a) consolidate on one platform group + reserve `casebible` for case-evidence episodes when that lane starts; (b) formalize the two-group split (platform-ops vs case) and fix `semantica_wiring.py`/skill conventions to match; (c) leave as-is documented. **Plus:** define **custom entity/edge types** from the behavioral-category ontology (none today); adopt retrieval recipes for the story layer. **Decides it:** the case-evidence lane's namespace needs (RESTART-0001 timing) + ontology maturity.

### Topic 6 — Semantica adoption path (the VIP)
**Strengths for our lane:** `conflicts/` (cross-source conflict detection), `deduplication/` (multi-metric entity merge), `EntityResolver`/`entity_linker` (fuzzy cross-doc resolution as a **proposal layer** downstream of PG). **Blockers:** alpha maturity (version drift, stub evals, torch/spaCy/transformers mandatory), **`GraphWriteAdapter` doesn't exist** (the planned Neo4j write gate), phantom "ADR ~0035 Semantica placement" citation to clean up. **Options:** (a) build GraphWriteAdapter + pilot conflicts/dedup on the PG seed data (contained, read-derive honored); (b) use only its extraction/resolution as a library inside our pipeline (no graph writes at all); (c) park until after RESTART-0001 ingest exists (its inputs are the raw tables). **Decides it:** whether entity/conflict work starts before or after the ingest rework lands.

### Topic 7 — Quick wins (low-risk, mostly housekeeping-class)
1. Delete/annotate the stale `settings.py:_EMBEDDER_IDS` map (points at wrong models).
2. Correct the `entity_memory` `# HITL` comment (PROPOSE degrades to ALWAYS) — or gate differently.
3. Fix the phantom Semantica ADR citation in the forensic-DB draft.
4. Add Milvus **partition keys** to the forensic collection definitions (they're define-only — free to amend).
5. Adopt materialized-view caching inside the existing `apply_db_modification` HITL gate.
6. Keep Graphiti/SBV MCP tools **uncached** (mixed read/write toolkits) — record as a convention.
7. Resolve `casebible` group assertion (ties to Topic 5).
Each is small; several are pure doc/comment fixes executable under the housekeeping mandate once the related topic is discussed.

## E. Confidence + what would change it

High confidence on everything source-verified (stubs, filters, RRF, schema). Medium on doc-only
claims where the MCP outage forced summarized WebFetch (flagged per file). The bake-off questions
(Topics 2 & 4) are empirical — no amount of docs reading decides them; small benchmarks on real
platform data would.
