# db/ — Progressive Disclosure Map

> Database layer: connections, knowledge engine, embeddings, rerankinging.

## Directory Map

```
db/
  __init__.py          <- Re-exports: create_knowledge, db_url, ensure_duckdb_r2_secret, get_agno_db.
  url.py               <- Database URL builder from env vars.
  session.py           <- Agno DB setup: SurrealDB (operational store), Weaviate (vectors, ADR-0040).
  embedder.py          <- NVIDIA NIM embedder (asymmetric query/passage).
  reranker.py          <- NVIDIA NIM reranker (native ranking API).
```

## Two Databases

| Database | Technology | Role |
|---|---|---|
| Operational store | **SurrealDB** (via `agno.db.surrealdb`) | Sessions, memory, metrics, eval, culture, traces, knowledge contents |
| Knowledge vectors | **Weaviate** (ADR-0040, owner-locked; cutover = HANDOFF-2026-07-27 Phase 1) | Embeddings for knowledge engine; Milvus SIDELINED (memsearch only, no new writers) |

> pgvector is in the PG image but is **no longer the knowledge store**.
> PostgreSQL holds the evidence + analysis schemas (relational).

## Embedders (ADR-0010; contract revised per ADR-0040/handoff)

- Text: `nvidia/nv-embed-v1` (4096-d, symmetric) — LIVE since 2026-07-19; documents, legal, transcripts. (Retired: `bge-m3` 1024-d — 500ing on NIM since 2026-07-04.)
- Code: `codestral-embed-2505` (1536-d) via OpenRouter — code artifacts.
- One collection per embedder; dimension fixed at collection creation (changing = re-embed).

## Reranker

- `NvidiaReranker` — calls `ai.api.nvidia.com/v1/retrieval/nvidia/reranking`.
- Model: `nvidia/rerank-qa-mistral-4b`.
- Fail-open: returns documents unranked on error.
