# Agno memory / storage / retrieval — expert reference (INDEX)

> _Byline: Claude Code · Fable 5 · 2026-07-11_
> Commissioned by owner 2026-07-11 ("become a bona fide expert... read ALL the documentation to
> see what the capabilities are"). Built by 6 parallel researchers + main-thread synthesis on
> branch `docs/agno-memory-expertise`. Verified against installed `agno==2.6.13` source throughout;
> every doc-vs-source discrepancy is flagged in the owning file.

## Read me in this order

| File | Covers | Researcher |
|---|---|---|
| `07-platform-mapping.md` | **Start here** — answers, unused capabilities, the 7-topic decision agenda | synthesis |
| `01-memory-and-learning.md` | MemoryManager, **LearningMachine** (modes/stores/schemas), session summaries, Memori — incl. the SurrealDb no-op bug | R1a |
| `02-knowledge-and-retrieval.md` | Knowledge API, 19 readers, 18 embedders, 4 rerankers, filters/FilterExpr, isolate-vector-search, search types, agentic vs traditional RAG, custom retriever, 7 vector-db deep-dives | R1b |
| `03-storage-and-vector-backends.md` | Db contract (12 roles), SurrealDb-vs-Postgres parity, sessions/history, Milvus/PgVector/SurrealDB/LanceDB stores, all 8 gateways, LiteLLM→Portkey | R1c |
| `04-rag-patterns-tools-context.md` | Agent knowledge/memory knobs, KnowledgeTools/MemoryTools, tool caching, data-agent + deep-research patterns, context engineering, teams | R1d |
| `05-substrates-beyond-agno.md` | Native SurrealDB v3.x, Milvus 3.0, Graphiti/Zep temporal KG, pgvector + pg_duckdb | R1e |
| `06-semantica.md` | **The VIP** — full vendored capability map, benchmarks, seed-first integration, positioning | R1f |
| `_research-log.md` | Durable run record: agent reports, verifications, owner design directions, process directive | — |
| `_url-checklist.md` | Owner's 110-tab export (102 unique URLs), bucketed — a floor, not a ceiling | — |

## Coverage accounting

- Owner checklist: **102 unique docs.agno.com URLs** — assigned across R1a (31), R1b (32), R1c (17),
  R1d (22); every file ends with a Coverage section ticking its URLs.
- **Beyond the checklist** (floor-not-ceiling directive): R1a +4 pages (memory-search,
  mongodb/redis-memory, learning/quickstart); R1d +13 (use-cases/context siblings); R1b enumerated
  the full sitemap (~300 knowledge-adjacent URLs; 19 vector-store backends vs the checklist's 6 —
  22/32 checklist pages fetched verbatim, remainder covered from source and marked as such).
- **Sourcing caveat (honest):** the `claude.ai agno` docs MCP died at launch and never reconnected.
  R1a/R1b/R1c/R1d fell back to direct WebFetch of docs.agno.com + raw `sitemap.xml` via curl +
  `llms.txt`, and verified against installed source. Each file declares its sourcing.

## Headline findings (details in 07)

1. **Production bug:** LearningMachine's `user_profile`/`user_memory`/`session_context`/
   `entity_memory` lanes are silent no-ops on our SurrealDb backend (source-verified stubs);
   only `learned_knowledge` works. entity PROPOSE silently degrades to ALWAYS.
2. **Milvus dict filters push server-side** — per-domain metadata filtering is enforceable
   (closes a DEBT.md flag). Its hybrid is true RRF, but the sparse half is a hashed-TF-IDF
   approximation.
3. **Separate collections per domain/embedder** is the validated multi-domain pattern
   (`isolate_vector_search` can't mix embedders); Milvus **partition keys** are the middle path.
4. **No native Graphiti in agno** — our temporal-KG lane is entirely platform integration;
   `casebible` group is empty, live episodes span `platform` + `agno-platform`.
5. **Owner architecture directions recorded:** SurrealDB = (a) KB first/last-stop *candidate*
   (challenger to Milvus), (b) **post-analysis consolidation/story space** (affirmed), (c) current
   operational store. Evidence never lands in it until end-of-process.

## Process

Per owner directive: no monolithic plan. `07-platform-mapping.md` §D is the 7-topic agenda;
topics get discussed **bit by bit** (options → interview/brainstorm → owner decision →
DECISION_LOG/ADR) in a follow-up session.
