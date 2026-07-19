---
name: graphiti-client
description: Write and read Graphiti knowledge-graph memory (episodes, facts, entity nodes) via the `grc` CLI — MCP streamable-HTTP JSON-RPC spoken directly, no session-registered graphiti MCP required. Use when the user says graphiti, remember to graph, knowledge graph memory, episode, memory facts, record this durably, or graph stale/is the graph broken.
---

# graphiti-client — `grc` CLI

> _Byline: Claude Code · Sonnet · 2026-07-19_

Graphiti (Neo4j-backed knowledge-graph memory) is normally reached through the `graphiti` MCP
server registered in `.claude.json`. That only works when the MCP is actually connected to the
session. `grc` talks the same MCP streamable-HTTP JSON-RPC protocol directly over HTTP
(`initialize` → `notifications/initialized` → `tools/call`, session-id header, SSE-framed
responses) so **any session, hook, or plugin can write/read episodes with zero MCP dependency** —
run it as a plain CLI via Bash.

## When to use

- Any durable fact, decision, correction, or "X is now Y" worth recording across sessions —
  **write an episode with `grc add`** (see write-discipline below).
- Recalling prior context before a non-trivial task — **`grc search "<terms>"`** for facts,
  `--nodes` for entities.
- Checking whether Graphiti itself is healthy (embedder/LLM path, stale graph) — **`grc doctor`**.
- Wiring a plugin (case-bible, etc.) to auto-write episodes on tool use / session end — see
  `scripts/hook-template/` for the design (template only; not installed anywhere yet).

## Location

- Live: `C:\Users\matts\.claude\skills\graphiti-client\scripts\grc.py` (+ `grc.cmd` / `grc` wrappers)
- Repo mirror: `E:\AI_Workspace\Projects\the-platform-workspace\Agno-MCP-Platform\tool-skills\graphiti-client\`
- stdlib-only Python (urllib, json, argparse) — no venv/pip install needed. Run with the
  uv-managed `python` on PATH.

## Commands

| Command | Does |
|---|---|
| `grc status` | one-line server + Neo4j health |
| `grc doctor` | full diagnosis: direct init, CF fallback init, status, tools/list count, search roundtrip (embedder probe), episode-freshness (stale-graph alarm, >72h flagged) — PASS/FAIL table, exit code 0/1 |
| `grc search "<query>" [--nodes] [--group G] [--max N]` | facts (default) or entity nodes (`--nodes`) |
| `grc add "<name>" "<body>" [--group G] [--source text\|json\|message] [--desc "..."]` | queue an episode (async — see below) |
| `grc episodes [--last N] [--group G]` | most-recent-N episodes, sorted client-side (see gotcha below) |
| `grc raw <tool> '<json-args>'` | escape hatch — call any tool the server exposes with raw JSON args |

Global flags go **after** the subcommand: `grc search "q" --via cf --json`.
- `--via direct` (default) — tailnet sidecar `http://100.119.96.29:8071/mcp`
- `--via cf` — ContextForge vserver fallback, bearer token from
  `~/.secrets/contextforge.env` (`CF_MCP_CLIENT_TOKEN`); never printed, only length shown.
- `--json` — raw JSON output instead of the formatted table/list.

Default `group_id` is `platform` unless `--group` is passed or `GRAPHITI_GROUP_ID` env var is set.

## Write discipline (owner rule)

- **One focused episode per durable fact.** Not a running journal — a decision, a correction, an
  infra state change, an "X is now Y".
- **Skip chit-chat and transient state.** If it won't matter next week, don't write it.
- Give `add` a short descriptive **name** (shows up in `grc episodes` and search hit context) and
  put the actual content in **body** — plain prose is fine, Graphiti extracts entities/facts from it.
- `--source text` (default) for prose; `json` for a JSON-string payload; `message` for
  conversation-style content. See `add_memory`'s docstring (`grc raw tools/list '{}'` or read
  `references/failure-modes.md`) for exact shapes.
- **Ingestion is async.** `add` returns immediately ("queued"); the episode is searchable roughly
  30s–3min later once entity/fact extraction finishes. Don't loop-poll tightly — a few checks
  30–60s apart is plenty.

## Known gotchas (verified live 2026-07-19, cost real debugging time — don't re-derive)

1. **`structuredContent` sometimes double-wraps.** For `get_episodes` and `add_memory`,
   `structuredContent` is `{"result": {...actual payload...}}` (matches their outputSchema's
   SuccessResponse/ErrorResponse union) while the plain-text `content[0].text` block has the
   payload unwrapped. `grc` prefers the text block for this reason — don't switch back to
   preferring `structuredContent` without re-checking every tool's shape.
2. **`get_episodes` real params are `group_ids` (array) + `max_episodes`** — NOT `group_id`/`last_n`
   as a literal reading of the tool's docstring implies. Also: **results are not returned in
   `created_at` order.** `grc episodes`/`grc doctor` over-fetch (floor 50) and sort+slice
   client-side; don't trust `episodes[0]` as "the newest" from a raw call.
3. **ContextForge (`--via cf`) renames every tool**: `graphiti-` prefix + hyphens instead of
   underscores (`get_status` → `graphiti-get-status`). `grc`'s `McpClient` has a `tool_prefix`
   translation layer for this — direct sidecar tool names stay native.
4. **Never call `clear_graph`.** It's in the tool list; `grc raw clear_graph` would work
   mechanically but is off-limits per owner rule — there's no CLI shortcut for it on purpose.

## Failure modes / doctor diagnosis

See `references/failure-modes.md` for the incident history (embedder 403/500, glm JSON-schema
failure, 421 host) and what `doctor`'s LIKELY FIX hints point to.

## Do / Don't

**Do:**
- Run `grc doctor` first in any session where Graphiti health is in question — it's cheap and
  catches the two failure classes that have silently killed the graph before (2026-07-04, 2026-07-08).
- Prefer `--via direct` (fewer hops); fall back to `--via cf` only if direct is unreachable.
- Use `grc search` before `grc add` on a topic you're unsure has been recorded — avoid duplicate
  episodes for the same fact.

**Don't:**
- Don't hardcode the CF bearer token anywhere — it's read from `~/.secrets/contextforge.env` at
  call time and never printed.
- Don't treat `grc add`'s return as proof of ingestion — it only confirms the episode was queued.
- Don't wire hooks into any plugin without owner sign-off — `scripts/hook-template/` is a design
  reference only, not an installed hook.
