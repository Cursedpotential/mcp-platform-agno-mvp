# ADR-0010: Per-task embeddings = one vector collection per embedder; raw docs are the source of truth
- Status: Accepted (the one-collection-per-embedder pattern remains in force). **Model names
  amended 2026-08-09**: the live text embedder is `nvidia/nv-embed-v1` (4096-d, symmetric;
  LIVE since 2026-07-19 per the `server/core/session.py` contract, re-verified 2026-08-08) —
  not the embedqa model named below.
- Date: 2026-06-01
- _Amended byline: Claude Code · Fable 5 · 2026-08-09_

## Context
Embedding vectors from different models are not interchangeable: models output **different
dimensions** AND occupy **different vector spaces**, so cross-model similarity is meaningless. A pgvector
column is fixed at `VECTOR(N)` with an index built for that one space. Therefore changing the embedder
for a corpus requires **re-embedding the entire corpus** into a new table. We want per-task embedders
(code vs text) without mixing incompatible vectors.

## Decision
**One vector collection per embedder**, never mixed:
- `knowledge_text` → ~~`nvidia/nv-embedqa-e5-v5`~~ **`nvidia/nv-embed-v1`** (amended 2026-08-09;
  the asymmetric embedqa pick was never shipped live — inapplicable for this client path because
  it cannot send per-call `input_type`, NOT because such models are banned) — documents,
  legal/forensic text, chat transcripts.
- `knowledge_code` → `nvidia/nv-embedcode-7b-v1` — code artifacts (codebase, ChatMiner code blocks).

Each table is internally consistent (single model, single dimension, single index). Agents query the
collection matching their task; the two are never cross-queried. **Raw source documents are the source
of truth** (kept in Agno `contents_db` + Cloudflare R2); vectors are disposable derivatives. Switching
an embedder = re-ingest the originals into a new table (build alongside, swap atomically) — compute/time
cost, never data loss. The primary text embedder is treated as a **pinned contract** (ADR-0003 dimension
contract) — not swapped casually.

## Consequences
- Embedder is configured per `Knowledge` instance (`table_name` + `embedder`); a small embedder factory
  selects by task ("text" | "code").
- pgvector column dimension per table must equal that model's output dim (confirmed live, not assumed).
- NVIDIA retrieval embedders require an `input_type` (`query` vs `passage`); the embedder integration
  must send it (custom embedder if Agno's OpenAIEmbedder can't).
- Re-embedding tooling (re-ingest from contents_db/R2) is part of the Knowledge phase.

## Alternatives considered
- One mixed table / casual model swaps — rejected: incompatible vectors, silent retrieval corruption.
- Single pinned embedder for everything — viable but weaker code retrieval; rejected in favor of the
  text+code split (owner decision).
