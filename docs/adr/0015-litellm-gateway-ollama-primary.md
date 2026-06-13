# ADR-0015: LiteLLM gateway; Ollama Cloud is the primary LLM, NVIDIA NIM = embed/rerank/backup
- Status: Accepted
- Date: 2026-06-11
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
