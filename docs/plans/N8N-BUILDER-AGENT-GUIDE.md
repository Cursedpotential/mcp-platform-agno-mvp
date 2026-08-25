# n8n Builder-Agent Guide (owner-supplied methodology)

> _Byline: owner-authored process, recorded verbatim-in-substance by Claude Code · Fable 5 · 2026-08-24_
> Governs how n8n workflows/agents get built under the D-068 architecture: reuse existing
> template shapes, never write from scratch; two mandatory human checkpoints.

## Pipeline

| Stage | Goal | Type |
|---|---|---|
| 1. Decompose | Break goal into shape categories + contracts | Agent (autonomous) |
| 1.5 HITL Interview A | Confirm/adjust shape list and priorities before searching | Human checkpoint (mandatory) |
| 2. Discover | Search n8n/GitHub/npm for candidate templates per shape | Agent (autonomous) |
| 2.5 HITL Interview B | Review ranked candidates, pick winners or reject/redirect | Human checkpoint (mandatory) |
| 3. Extract | Pull JSON/config for chosen candidates | Agent (autonomous) |
| 4. Compose | Splice into one workflow JSON — unique node IDs, rewired connections, validated | Agent (autonomous) |

Output contract: the final importable workflow JSON **plus a source-attribution table**
(shape → chosen candidate → URL).

## Tool mapping in THIS environment

| Guide tool | Actual tool here |
|---|---|
| human_interview | AskUserQuestion (structured options, blocks until answered) |
| web_search / searxng_search | WebSearch + n8n template gallery + n8n-docs MCP |
| github_code_search | `gh api` / `gh search code` |
| npm_registry_search | registry.npmjs.org queries via fetch |
| http_fetch | WebFetch / curl |
| code_execution | Bash/python locally; import via n8n API only after Compose validates |

## Standing constraints every build inherits (D-068 + rulings)

- Custody path (ingest → hash → store) is NEVER n8n-side: the ingestion shape's contract is
  "hand raw file to the platform door, receive record IDs back."
- n8n is read-only against evidence Weaviate collections; epoch-numeric timestamps required
  for range filters.
- Temporal-awareness mandate: chunks/prompts carry timestamps; every retrieval carries a window.
- Idempotency: trigger-derived workflow/run IDs come from object keys (at-least-once polling).
- Model calls ride the Portkey gateway (THE model gateway) unless the owner rules otherwise
  per-build.
- First real build target (owner, 2026-08-24): SMS + AI-chat conversation workflow — ingest →
  semantic chunk → classify/tag/summarize per chunk → cheap-LLM round-robin → cost logging.
