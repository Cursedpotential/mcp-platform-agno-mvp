# ADR-0015: LiteLLM gateway; Ollama Cloud is the primary LLM, NVIDIA NIM = embed/rerank/backup
- Status: Accepted — **SUPERSEDED by ADR-0042** (2026-07-29; Portkey = the model gateway;
  LiteLLM retired, teardown pending per `adr/README.md`). Kept for history; do not wire
  anything new to LiteLLM.
- Date: 2026-06-11

> _Byline: Claude Code · Kimi K3 (drift-fix) · 2026-08-12 — header marked superseded by ADR-0042._
- Amended: 2026-07-04 — see "Amendment" below (embed-text model swap; Graphiti LLM exception)
- Supersedes: the "NVIDIA NIM is the active provider" runtime choice in ADR-0011 (the
  embedder dimension contract and one-provider-for-embeddings parts of 0011 remain in force).
  Closes ADR-0008 D7 definitively.

## Context
NVIDIA NIM rate-limited the owner for the first time during real use. The provider-agnostic
factory (ADR-0008) already put a preference order in `app/settings.py`, but agents, n8n, and
Graphiti each reached providers differently, and a single rate-limited provider could stall
everything. We need one swap point and a primary that isn't NVIDIA.

## Decision
Run a **LiteLLM proxy in the `gateway` container** as the single OpenAI-compatible endpoint
(`:4000`) over every provider we hold keys for. **Ollama Cloud `glm-5.1` is the PRIMARY LLM.**
**NVIDIA NIM is relegated to embeddings + rerank + LLM backup only.** `app/settings.py` stays
Ollama-first so agents auto-select glm-5.1; Graphiti and other services point at the gateway.
Gateway models: glm-5.1 (primary), nemotron (backup), kimi-k2.6, embed-text (NIM, with
`input_type` injected), groq-llama, openrouter-deepseek, gemini-pro.

## Consequences
- One place to add/swap providers; the NVIDIA→Ollama pivot took minutes, not a per-agent edit.
- agno's `Ollama` model class needs the `ollama` pip package (added to requirements).
- Embeddings still ride NIM (asymmetric query/passage — ADR-0021); rerank still NIM (custom client).
- Gateway holds provider keys via env from `.env`; `LITELLM_MASTER_KEY` fronts it.

## Alternatives considered
- Per-agent provider config — rejected: no single swap point; a rate-limit stalls the fleet.
- Keep NVIDIA primary — rejected: it rate-limited; Ollama Cloud glm-5.1 is the owner's choice.

## Amendment (2026-07-04)
> _Byline: Claude Code · Fable 5 · 2026-07-04_
- **`embed-text` → `nvidia/nv-embed-v1` (4096-d, SYMMETRIC).** The asymmetric
  llama-nemotron-embed-vl required per-call `input_type`; the gateway's blanket
  `input_type: passage` collapsed retrieval margin 0.33→0.09 (measured), and Graphiti
  cannot split query/passage per call. The `extra_body` injection is removed. Changing
  the embed model again requires re-embedding the graph (mixed dims hard-error).
  bge-m3 (owner-preferred symmetric, 1024-d) was 500ing server-side on NIM 2026-07-04;
  candidates when revisiting: NIM bge-m3, or CF Workers AI bge-m3 (~$0/mo at our volume).
- **Graphiti's LLM = `nemotron`, an exception to glm-5.1-primary.** glm-5.1 cannot emit
  schema-conformant structured output (fails Graphiti's entity extraction on every try;
  the knowledge graph had been silently empty since deployment). glm-5.1 remains primary
  for agents/chat. Do not use glm-5.1 for any JSON-schema-constrained workload.
- kimi-k2.6 verified working via chat completions (an earlier 404 was specific to the
  /v1/responses structured-output path).
