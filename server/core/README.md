# db/ — Progressive Disclosure Map

> Database layer: connections, knowledge engine, embeddings, rerankinging.

## Directory Map

```
db/
  __init__.py          <- Re-exports: create_knowledge, db_url, ensure_duckdb_r2_secret, get_agno_db.
  url.py               <- Database URL builder from env vars.
  session.py           <- Agno DB setup: SurrealDB (operational store), Milvus (vectors).
  embedder.py          <- NVIDIA NIM embedder (asymmetric query/passage).
  reranker.py          <- NVIDIA NIM reranker (native ranking API).
```

## Two Databases

| Database | Technology | Role |
|---|---|---|
| Operational store | **SurrealDB** (via `agno.db.surrealdb`) | Sessions, memory, metrics, eval, culture, traces, knowledge contents |
| Knowledge vectors | **Milvus** (via `agno.vectordb.milvus`) | Embeddings for knowledge engine (ADR-0026/27) |

> pgvector is in the PG image but is **no longer the knowledge store**.
> PostgreSQL holds the evidence + analysis schemas (relational).

## Embedders (ADR-0010)

- Text: `bge-m3` (1024-d) via OpenRouter — documents, legal, transcripts.
- Code: `codestral-embed-2505` (1536-d) via OpenRouter — code artifacts.
- One Milvus collection per embedder.

## Reranker

- `NvidiaReranker` — calls `ai.api.nvidia.com/v1/retrieval/nvidia/reranking`.
- Model: `nvidia/rerank-qa-mistral-4b`.
- Fail-open: returns documents unranked on error.
