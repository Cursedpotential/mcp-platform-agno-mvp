---
name: opencode-ops
description: Operate the platform's headless OpenCode server plus its surrounding control plane (agentos-api, agentos-mcp, ContextForge federated tool catalog) via the `oc` CLI. Use when the user says opencode, headless agent, oc run, drive opencode, ops copilot, run workflow from cli, platform runs, tool catalog call, or wants to create/drive an OpenCode session, check provider/model config, call an agentos or ContextForge MCP tool, kick off or watch a platform run, or search platform knowledge from the command line.
---

# opencode-ops — `oc` CLI

> _Byline: Claude Code · Sonnet · 2026-07-20_

## Canon role

OpenCode (headless server, `http://100.72.169.40:4096` on the tailnet) is the platform's **builder /
ops copilot** — it consumes the same MCP tools and gateway models as everything else and can edit
code, run shells, etc. It is **not a new writer or domain brain**: AgentOS agents/teams/workflows
stay the domain intelligence (forensic ingestion, analysis, evidence). Reach for `oc run` when you
want OpenCode itself to do or explain something; reach for `oc tools call agentos:run_agent` when
you want one of the platform's own agents to act.

## Endpoint map

| Lane | URL (env override) | Auth |
|---|---|---|
| OpenCode headless server | `http://100.72.169.40:4096` (`OC_SERVER`) | none currently (tailnet-only) |
| agentos-api (REST) | `http://100.72.169.40:8000` (`OC_AGENTOS_URL`) | Bearer `OS_SECURITY_KEY`, parsed from `C:\Users\matts\.secrets\infra-access.md` |
| agentos MCP (JSON-RPC, mounted on agentos-api) | `http://100.72.169.40:8000/mcp` (`OC_AGENTOS_MCP_URL`) | none — standalone `agentos-mcp` service on :8001 retired 2026-07-23, agno 2.8.0 fixed the mounted-`/mcp` bug it worked around |
| ContextForge MCP (federated catalog) | `http://100.72.169.40:4444/mcp` (`OC_CONTEXTFORGE_MCP_URL`) | Bearer `CF_MCP_CLIENT_TOKEN`, parsed from `~/.secrets/contextforge.env` |
| Graphiti memory | — | use the sibling **`grc`** CLI (graphiti-client skill) — do not duplicate |

Secrets are read from the files above at call time and never printed — `oc doctor` shows only
`present (len=N)` / `MISSING`. Override with `OC_OS_SECURITY_KEY` / `OC_CF_MCP_CLIENT_TOKEN` env
vars if the files move.

## Verbs

| Command | Does |
|---|---|
| `oc doctor` | PASS/FAIL table across all 4 endpoints (opencode root+providers, agentos-api health+bearer route, agentos-mcp, contextforge-mcp) |
| `oc providers` | list OpenCode providers, connected vs known (API keys redacted — see gotcha below) |
| `oc models [--provider ID] [--connected-only] [--limit N]` | model list per provider |
| `oc sessions [list\|get <id>] [--limit N]` | OpenCode sessions |
| `oc run "<prompt>" [--model provider/model] [--session <id>] [--directory PATH] [--timeout N]` | create/reuse a session, send a prompt, print the final text (synchronous — the server blocks until done or errors, so no separate poll loop is needed) |
| `oc runs [list\|get <run_id>\|start <file> --workflow chat-transcript\|sms-xml --domain X]` | agentos-api spine run ledger (`/v1/runs`) — **see gotcha: not deployed on the current build**, 404s cleanly |
| `oc tools [list\|call <server>:<tool> --args '<json>']` | MCP tools/list + tools/call against `agentos` or `contextforge` |
| `oc ksearch "<query>" [--limit N]` | `POST /knowledge/search` on agentos-api |

Every verb accepts `--json` (raw output) and `--timeout SECONDS`.

## Integration recipes

**(a) Drive an ingestion run and watch it**
```
oc runs start transcript.txt --workflow chat-transcript --domain custody
oc runs get <run_id>          # poll; or `oc runs list` to find it
```
As of 2026-07-20 this 404s cleanly — see "runs API not deployed yet" in
`references/known-issues.md`. Once the spine ledger lands, this pair is the intended loop.

**(b) Call a platform agent directly (bypass OpenCode)**
```
oc tools list --server agentos
oc tools call agentos:run_agent --args '{"agent_id":"ingestion-orchestrator","message":"..."}'
```

**(c) Knowledge search then feed context into a prompt**
```
oc ksearch "platform canon" --json
oc run "Given this context: <paste hits>, summarize the doc contract" --model groq/llama-3.1-8b-instant
```

**(d) Memory stack** — three separate lanes, don't cross them:
- Graphiti episodes/facts/entities → `grc search "..."` / `grc add "..." "..."` (graphiti-client skill).
- Platform knowledge (Milvus-backed) → `oc ksearch "..."`.
- Claude Code's own auto-memory (`MEMORY.md`) → internal to this tool, not reachable via `oc`.

## Known issues (read before debugging "it doesn't work")

See `references/known-issues.md` for full detail; headline items:
1. **`/provider` and `/config/providers` leak live API keys in plaintext** (NVIDIA/OpenRouter/Groq/etc,
   unauthenticated tailnet endpoint). `oc` redacts the `key` field before printing/`--json`-ing —
   never bypass that with a raw `curl` against these endpoints without the same care.
2. **`oc run` currently 500s** ("UnknownError — Unexpected server error") on this OpenCode build,
   reproduced across two different providers (groq, nvidia) and two isolated `--directory` values —
   this is a server-side fault, not a client bug. LiteLLM-retired routing was checked and ruled out
   (all 5 connected providers point straight at their real public APIs, not a gateway). Worth a
   server-log check on ovh-app's opencode container.
3. **`/v1/runs` (list/get/start) is not deployed** on the live AgentOS build (`workflow_count: 0`).
   The real live shape nests runs per resource type instead: `/agents/{id}/runs`,
   `/workflows/{id}/runs`, `/teams/{id}/runs`. `oc runs` targets the spec'd unified `/v1/runs`
   contract per the platform's own convention and 404s cleanly until that ships.
4. **`/agents` and `/teams` (list) 500** on agentos-api even though `/info` reports `agent_count: 6,
   team_count: 3` — use `oc tools call agentos:get_sessions`/MCP routes as a workaround if you need
   agent enumeration today.
