# Topic 2 decision brief — KB substrate: Milvus incumbent vs SurrealDB challenger

> _Byline: Claude Code · Fable 5 · 2026-07-11_
> Prepared for the bit-by-bit discussion (07-platform-mapping §D Topic 2). **Nothing decided here** —
> this is the evidence laid out for the interview. Every claim is sourced from files 02/03/05 of
> this reference set (all source-verified) or the owner-supplied Milvus sparse-vector page.

## The question

Where do the knowledge-side stores live — the AI-chat-transcript KB, code KB, and the coming
per-domain lanes (legal / code / timeline)? Owner's framing: SurrealDB "could be the first and
last stop for knowledge-based stuff"; evidence never lands there until end-of-process (that part
is settled — Topic 3 owns the consolidation space).

## The three candidates

| Criterion | A. Milvus as-is (incumbent) | B. Milvus + real sparse ("fix the sparse lane") | C. SurrealDB via custom retriever (challenger) |
|---|---|---|---|
| Hybrid search quality | True RRF fusion (`RRFRanker(k=60)`), but sparse half = **hashed TF-IDF approximation** (agno client) | True RRF over **real BGE-M3 sparse** — our text embedder already emits both lanes; Milvus 3.0 native `SPARSE_FLOAT_VECTOR` (GA) | **One-statement vector+graph+FTS/BM25** in SurrealQL — genuinely richer *shape* of query than either Milvus option |
| What we must build | Nothing | Custom insert/search path feeding sparse vectors (or upstream agno contribution); schema uses explicit dense/sparse fields (already what agno hybrid creates) | Custom `knowledge_retriever` (supported agno hook) + our own insert path; agno's Surreal vectordb is **vector-only** |
| Ownership / upgrade risk | None | Small — additive code alongside agno's Milvus class; worst case we pin behavior with tests | Moderate — we own the whole retrieval path; agno's Surreal integration is its **thinnest** (sync-only Db class, the D-030 stub history is the cautionary tale) |
| Per-domain isolation | Separate collections per domain/embedder (validated pattern) or **partition keys** within a collection | Same as A | Separate tables per domain; HNSW params per table (`efc/m/search_ef`); DISKANN for big lanes |
| Metadata filtering | Dict filters **push server-side** (verified); `FilterExpr`/keyword silently dropped | Same, plus real sparse improves keyword-ish recall | Full SurrealQL WHERE — strongest filtering expressiveness |
| ADR posture | ADR-0026/0027 locked (Milvus = platform-wide vector substrate) | Consistent with ADR-0027 | Requires a new ADR superseding 0027's KB scope |
| Ops | Already live (data-vector app), Attu UI, known etcd/WAL care | Same | Already live too (data-surreal app); one FEWER moving system if Milvus's KB role shrinks — but Milvus stays anyway (forensic collections, Semantica vector lane) |
| Synergy with Topic 3 (consolidation space) | Neutral — story layer in Surreal links out to Milvus hits | Neutral | **High** — story layer and KB in one engine; graph-relations between KB chunks and narrative nodes come free |
| Failure modes | Sparse-quality ceiling; two systems for KB+story | The custom path must stay dim/schema-compatible across agno upgrades | Recall/latency unproven at our scale; every retrieval bug is ours; SurrealDB vector maturity < Milvus's |

## What the research says bluntly

- **B is cheap and strictly improves A.** The sparse weakness is agno's client shortcut, not Milvus.
  BGE-M3's sparse output + native `SPARSE_FLOAT_VECTOR` is the designed use of the tech we already run.
- **C's real attraction is the one-statement multi-model query and Topic-3 synergy** — not raw vector
  performance. Its real cost is owning retrieval code on the platform's thinnest agno integration.
- These aren't mutually exclusive: **B now, C piloted on ONE domain** (e.g. the AI-chat-transcript KB,
  where graph-linking chat chunks to story nodes pays most) is a coherent path.

## Bake-off protocol (if wanted before deciding)

1. Corpus: ~200 real chunks from one domain (AI-chat transcripts, already parseable), 20 gold queries
   (owner-written or sampled), fixed embedder bge-m3 (dense+sparse).
2. Arms: A (agno Milvus hybrid as-is) · B (Milvus with real sparse via a ~100-line custom path) ·
   C (SurrealQL hybrid via custom retriever).
3. Metrics: recall@5 / MRR on the gold queries + p50 latency + LOC-owned per arm.
4. Effort: B ≈ half a day; C ≈ 1–2 days (retriever + table + insert path). Both branch-only, no deploy.

## Questions the interview should settle

1. Is Topic-3 synergy (story+KB in one engine) worth owning the retrieval path — or does the story
   layer simply *reference* KB hits across systems?
2. Bake-off first, or decide on the evidence above?
3. If B: fix in-repo custom path vs attempt an upstream agno PR?
4. If C pilot: which domain, and what's the promotion/rollback criterion?
