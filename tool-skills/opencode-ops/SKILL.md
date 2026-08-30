---
name: opencode-ops
description: Operate the platform's headless OpenCode server, framework-neutral Platform API run ledger, and ContextForge federated tool catalog via the `oc` CLI. Use for OpenCode sessions, provider/model checks, platform run submission or inspection, ContextForge MCP calls, and explicit checks of currently unavailable generic semantic search.
---

# opencode-ops — `oc` CLI

> _Byline: Claude Code · Sonnet · 2026-07-20 (agno 2.8 MCP door migration :8001->:8000 + bearer, 2026-07-23)_
> _Cutover true-up: Codex · GPT-5.6-Sol · 2026-08-29._

## Canon role

OpenCode (headless server, `http://100.72.169.40:4096` on the tailnet) is the platform's **builder /
ops copilot** — it consumes the same MCP tools and gateway models as everything else and can edit
code, run shells, etc. It is **not a canonical writer or durable workflow owner**. Temporal owns
durable platform execution; ContextForge publishes tools; Portkey routes model calls. Reach for
`oc run` when you want OpenCode itself to act. Generic AgentOS agents, teams, workflows, and MCP
surfaces are retired and must never be called from this skill.

## Endpoint map

| Lane | URL (env override) | Auth |
|---|---|---|
| OpenCode headless server | `http://100.72.169.40:4096` (`OC_SERVER`) | none currently (tailnet-only) |
| Platform API (REST) | `http://100.72.169.40:8000` (`PLATFORM_API_URL`) | Runtime file `PLATFORM_API_BEARER_SECRET_FILE` (default `/run/secrets/platform-api-bearer`) |
| ContextForge MCP (federated catalog) | `http://100.72.169.40:4444/mcp` (`OC_CONTEXTFORGE_MCP_URL`) | Bearer `CF_MCP_CLIENT_TOKEN`, parsed from `~/.secrets/contextforge.env` |
| Graphiti memory | — | use the sibling **`grc`** CLI (graphiti-client skill) — do not duplicate |

Secrets are read from their files at call time and never printed. The Platform API bearer has no
environment-secret fallback; change only its non-secret file path when the mount location changes.

## Verbs

| Command | Does |
|---|---|
| `oc doctor` | PASS/FAIL table for OpenCode, the private Platform API, and ContextForge MCP |
| `oc providers` | list OpenCode providers, connected vs known (API keys redacted — see gotcha below) |
| `oc models [--provider ID] [--connected-only] [--limit N]` | model list per provider |
| `oc sessions [list\|get <id>] [--limit N]` | OpenCode sessions |
| `oc run "<prompt>" [--model provider/model] [--session <id>] [--directory PATH] [--timeout N]` | create/reuse a session, send a prompt, print the final text (synchronous — the server blocks until done or errors, so no separate poll loop is needed) |
| `oc runs [list\|get <run_id>\|start <file> --workflow chat-transcript\|sms-xml --domain X]` | Platform API run ledger (`/v1/runs`); start sends the source as multipart bytes |
| `oc tools [list\|call contextforge:<tool> --args '<json>']` | MCP tools/list + tools/call through ContextForge only |
| `oc ksearch "<query>" [--limit N]` | Fails closed: no generic framework-neutral semantic-search contract exists yet |

Every verb accepts `--json` (raw output) and `--timeout SECONDS`.

## Integration recipes

**(a) Drive an ingestion run and watch it**
```
oc runs start transcript.txt --workflow chat-transcript --domain custody
oc runs get <run_id>          # poll; or `oc runs list` to find it
```
The Platform API bearer is reread for every operation, so runtime rotation requires no redeploy.

**(b) Call a published tool through ContextForge**
```
oc tools list --server contextforge
oc tools call contextforge:<exact-listed-tool-name> --args '{"key":"value"}'
```

Do not replace a failed `oc ksearch` with direct evidence search: that endpoint requires a distinct
operator credential and horizon/case semantics that this CLI does not own.

**(d) Memory stack** — three separate lanes, don't cross them:
- Graphiti episodes/facts/entities → `grc search "..."` / `grc add "..." "..."` (graphiti-client skill).
- Platform semantic search → use the Workbench's evidence-only native search until a broader neutral contract exists.
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
3. **Generic semantic search is intentionally unavailable.** `oc ksearch` fails closed and performs
   no network request until a framework-neutral search contract is implemented.
4. **AgentOS historical notes in `references/known-issues.md` are explicitly retired.** They remain
   only as incident history and are not operational instructions.
