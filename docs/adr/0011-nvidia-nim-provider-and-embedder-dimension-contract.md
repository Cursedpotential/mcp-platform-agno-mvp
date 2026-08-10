# ADR-0011: NVIDIA NIM is the MVP provider; embedder dimension contract = text 2048-d / code 4096-d
- Status: Accepted (the dimension-contract *shape* remains in force). **Text-model choice
  amended 2026-08-09**: the live text embedder is `nvidia/nv-embed-v1` (4096-d, symmetric;
  LIVE since 2026-07-19 per the `server/core/session.py` contract), superseding the
  `llama-nemotron-embed-vl-1b-v2` (2048-d) pick below.
- Date: 2026-06-07
- _Amended byline: Claude Code · Fable 5 · 2026-08-09_
- Supersedes: the embedder/provider specifics of ADR-0003 (VECTOR(1536) ↔ text-embedding-3-small),
  ADR-0008 open decision D7, and ADR-0010's text-embedder choice (nv-embedqa-e5-v5). The *shapes*
  those ADRs lock (provider-agnostic factory, one-collection-per-embedder, raw docs = source of truth)
  remain in force.

## Context
Three conflicting embedder specs accumulated across the docs and code:
- ADR-0003 / ADR-0008: OpenAI `text-embedding-3-small`, **1536-d**, OpenAI key required.
- ADR-0010 / `app/settings.py` EMBEDDER_IDS: NVIDIA `nv-embedqa-e5-v5` (text) + `nv-embedcode-7b-v1` (code).
- `db/session.py` (newest, "verified against NIM API 2026-06-07"): NVIDIA
  `llama-nemotron-embed-vl-1b-v2` (**2048-d**, multimodal text+image) for text + `nv-embedcode-7b-v1`
  (**4096-d**) for code.

The embedder output dimension is the contract for the pgvector `VECTOR(N)` column written in Phase 2
SQL. A wrong dimension is not a config tweak — it forces re-embedding the entire corpus. D7 (which
provider agents actually run on) was still formally open, even though `settings.py` already put NVIDIA
NIM first in the selection order.

## Decision
**NVIDIA NIM is the active provider for the MVP** — chat (Nemotron / Kimi on NIM), embeddings, and
rerank all ride NVIDIA's OpenAI-compatible endpoint. One provider, one API key (`NVIDIA_API_KEY`), no
OpenAI key required. The provider-agnostic factory (ADR-0008) stays; NVIDIA is simply first in order.

**Embedder dimension contract (pinned, per `db/session.py`):**
| Collection | Model | Dim |
|---|---|---|
| text (docs, legal/forensic text, transcripts, notes) | `nvidia/llama-nemotron-embed-vl-1b-v2` | **2048** |
| code (codebase, ChatMiner code blocks) | `nvidia/nv-embedcode-7b-v1` | **4096** |

`db/session.py` is the source of truth for embedder IDs and dimensions. Both dims are overridable via
env (`NVIDIA_EMBED_TEXT_DIM`, `NVIDIA_EMBED_CODE_DIM`) but the **2048** default is verified; the **4096**
code dim must be confirmed live before the first code-collection ingest.

## Consequences
- Phase 2 SQL: any explicit pgvector column for the text collection is `VECTOR(2048)`, code is
  `VECTOR(4096)`. (Agno's PgVector usually creates the column from the embedder dim — do not hardcode a
  conflicting dimension.)
- NIM retrieval embedders require `input_type` (`query` vs `passage`) and `modality=["text"]`; if Agno's
  `OpenAIEmbedder` can't pass `extra_body`, subclass it or default to `passage` (noted in `db/session.py`).
- `app/settings.py` EMBEDDER_IDS must be reconciled to the nemotron text model (was `nv-embedqa-e5-v5`).
- Switching either embedder later = re-ingest originals into a new table, swap atomically (ADR-0010).
- D7 is **closed**. The EXECUTION_PLAN open-decisions table is updated to reflect NVIDIA + the dim contract.

## Alternatives considered
- OpenAI `text-embedding-3-small` 1536-d (ADR-0003/0008) — rejected: adds a second provider + key for no
  MVP benefit when NIM already serves chat + embed + rerank.
- `nv-embedqa-e5-v5` text embedder (ADR-0010) — rejected in favor of `llama-nemotron-embed-vl-1b-v2`
  (multimodal headroom for future image evidence; dim verified live).
