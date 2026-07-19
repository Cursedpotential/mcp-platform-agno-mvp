# Graphiti failure modes — incident history + doctor diagnosis map

> _Byline: Claude Code · Sonnet · 2026-07-19_

Graphiti has failed silently twice before `grc doctor` existed — both times nothing watched for
it, and it was only noticed on manual inspection weeks later. This doc exists so any session can
go from symptom → fix without re-deriving the incident history.

## Incident 1 — 2026-07-04: empty graph since deployment

Three compounding faults, all fixed same day:

1. `NVIDIA_API_KEY` was empty in the Coolify exec-tier app on OVH-1 → the LiteLLM `embed-text`
   route had no credentials → every memory search returned HTTP 500. Fixed: key restored via
   Coolify API, gateway container recreated.
2. Graphiti's LLM was `glm-5.1` via Ollama Cloud, which **cannot emit schema-conformant structured
   output** → every `add_memory` episode ever submitted failed entity extraction silently → the
   Neo4j graph had been empty since deployment despite episodes appearing "queued". Fixed:
   switched to `nemotron` (NVIDIA NIM guided JSON, verified schema-conformant).
3. The embedder `llama-nemotron-embed-vl` (2048-d) is **asymmetric** and the gateway forced
   `input_type=passage` on all calls including queries, collapsing retrieval margin from 0.33 to
   0.09 (measured). Fixed: switched to `nvidia/nv-embed-v1` (4096-d, symmetric, margin 0.29), graph
   cleared and re-recorded at 4096-d with owner approval.

**Rule born from this:** never use glm for schema-constrained output; never use an asymmetric
embedder without per-call `input_type` control.

## Incident 2 — ~2026-07-08 to 2026-07-19: embed-text 403 stall

`embed-text` returned 403 starting ~2026-07-08 → search dead, every queued episode since then
stuck (including at least one corral/merge episode). Root cause and exact fix window not
separately documented here — folded into the 2026-07-19 Portkey changeover, which moved Graphiti's
LLM+embedder routing off LiteLLM onto Portkey (stable as of 2026-07-19, verified via
`grc doctor` search roundtrip + `grc add`/`grc search` self-test roundtrip).

**Rule born from this:** nothing was watching for a stuck embedder — `grc doctor`'s search
roundtrip + episode-freshness check exist specifically to make this class of failure loud instead
of silent.

## `doctor` check → diagnosis map

| Check | FAIL meaning | Likely fix |
|---|---|---|
| `direct init` | tailnet sidecar (nginx hostfix on ovh-data, `100.119.96.29:8071`) unreachable or down | check the sidecar container; check Tailscale connectivity from this box |
| `cf init` | ContextForge vserver route broken, or `CF_MCP_CLIENT_TOKEN` missing/stale in `~/.secrets/contextforge.env` | re-check the token; check ContextForge's virtual server config for the graphiti route |
| `status` | Graphiti itself reports not-ok, or Neo4j connection broken | check Graphiti container logs; check Neo4j reachability from Graphiti's network |
| `tools/list` | 0 tools, or call errored | server likely up but MCP layer broken — check Graphiti's FastMCP wiring |
| `search roundtrip` (embedder probe) | error containing `403` | embed-text route/NIM key issue on the exec-tier gateway (litellm) — the exact class of incident 2 |
| ″ | error containing `500` | check Graphiti/Neo4j logs directly; embedder or LLM route down |
| ″ | error containing `421` | sidecar/nginx hostfix down on ovh-data (Host header mismatch) |
| `episode freshness` | newest episode in `platform` group is >72h old | **the silent-stall signature** — episodes are being queued but not landing, or nothing has been written in 3 days. Cross-check with `grc episodes` and recent session activity; if episodes ARE being added but freshness still fails, re-run `doctor`'s search roundtrip — a stuck embedder queues episodes that never finish extraction. |

## Tool wire-name reference (direct vs CF)

Direct sidecar uses native names; ContextForge prefixes `graphiti-` and hyphenates:

| Direct (native) | ContextForge (`--via cf`) |
|---|---|
| `add_memory` | `graphiti-add-memory` |
| `search_nodes` | `graphiti-search-nodes` |
| `search_memory_facts` | `graphiti-search-memory-facts` |
| `delete_entity_edge` | `graphiti-delete-entity-edge` |
| `delete_episode` | `graphiti-delete-episode` |
| `get_entity_edge` | `graphiti-get-entity-edge` |
| `get_episodes` | `graphiti-get-episodes` |
| `clear_graph` | `graphiti-clear-graph` — **NEVER call this** |
| `get_status` | `graphiti-get-status` |

`grc`'s `McpClient(tool_prefix=...)` handles this translation automatically — `grc raw` takes the
native (direct) name regardless of `--via`.

## Tool argument reference (verified live 2026-07-19 against server v1.26.0)

| Tool | Required | Optional (default) |
|---|---|---|
| `add_memory` | `name`, `episode_body` | `group_id` (null→server default), `source` ("text"), `source_description` (""), `uuid` (null) |
| `search_nodes` | `query` | `group_ids` (null), `max_nodes` (10), `entity_types` (null) |
| `search_memory_facts` | `query` | `group_ids` (null), `max_facts` (10), `center_node_uuid` (null) |
| `get_episodes` | — | `group_ids` (null), `max_episodes` (10) — **not `group_id`/`last_n`** |
| `get_entity_edge` / `delete_entity_edge` / `delete_episode` | `uuid` | — |
| `clear_graph` | — | `group_ids` (null) |
| `get_status` | — | — |

`get_episodes` results are **not** ordered by `created_at` — sort client-side if recency matters.
