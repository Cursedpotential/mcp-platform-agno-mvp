# opencode-ops — known issues / API-shape notes

> _Byline: Claude Code · Sonnet · 2026-07-20_ — all verified live against the tailnet deployment
> on 2026-07-20. Re-verify before assuming these are still true if it's been a while.

## 1. Provider endpoints leak API keys in plaintext

**FIX WIRED 2026-07-21, DEPLOY PENDING** (console/c2.5-copilot branch): `opencode serve` speaks
HTTP Basic natively via `OPENCODE_SERVER_USERNAME`/`OPENCODE_SERVER_PASSWORD` -- compose.gateway.yaml
now sets both (`OPENCODE_SERVER_PASSWORD: ${OPENCODE_SERVER_PASSWORD:?set}`, a hard required-env
gate so the app can't deploy without the owner setting a real password in Coolify). `oc.py` now
sends `Authorization: Basic ...` on every OC_SERVER call via `_opencode_auth_headers()`, built from
new `OC_SERVER_USERNAME`/`OC_SERVER_PASSWORD` env vars (empty password = no header, i.e. today's
still-unauthenticated behavior is unchanged until the gateway app is actually redeployed with the
password set -- that's an owner/deploy action, not done by this branch). The workbench's own
copilot backend (`workbench/api/app/repo/opencode_client.py`) does the same thing independently via
`OPENCODE_USERNAME`/`OPENCODE_PASSWORD`. Once deployed: re-verify this section's live claim (bare
curl without credentials should 401) and delete this note.

`GET /provider` and `GET /config/providers` on the OpenCode server (`:4096`) both return a `"key"`
field for every provider connected via an env-sourced credential — verified live with real
NVIDIA_API_KEY / OPENROUTER_API_KEY / GROQ_API_KEY values coming back over an **unauthenticated**
tailnet HTTP endpoint. `oc.py`'s `_redact_providers()` strips this to `<redacted len=N>` before any
print or `--json` output. **Never** curl these endpoints directly and paste the output anywhere —
route through `oc providers`/`oc models` instead. Flagged for the parent: this is a real exposure
(low blast radius since it's tailnet-only, but still a live secret in an HTTP response body).

## 2. `oc run` / `POST /session/{id}/message` currently 500s

**Directory-cause FIX WIRED 2026-07-21, DEPLOY PENDING** (console/c2.5-copilot branch): the ENOENT/
`SystemPrompt.environment` flavor of this 500 (distinct from the `ContextOverflowError` flavor above)
is caused by `?directory=` naming a path that doesn't exist *inside the opencode container* --
verified by inspecting the error, not by a clean repro in this branch's work (that was on the
workbench side, not this CLI). Fix: compose.gateway.yaml now bind-mounts
`/data/agno/volumes/gateway-workdirs:/workspace` into the gateway container (HOST-PREP: mkdir +
chown 1000:1000 on the host, once, before redeploy). `oc.py`'s `cmd_run` now honors a new
`OC_WORKSPACE` env var: when set (e.g. `OC_WORKSPACE=/workspace/oc`) and `--directory` isn't passed
explicitly, it defaults to `<OC_WORKSPACE>/<timestamp>-<pid>` instead of the shared default scope --
a directory that will actually exist once the bind mount above lands. Unset `OC_WORKSPACE` (today's
default) keeps the exact old behavior (shared scope unless `--directory` is passed by hand), so this
is non-breaking pending deploy. The workbench's Ops Copilot backend takes a DIFFERENT approach for
its own sessions (one single shared `/workspace/copilot` directory for every copilot session,
isolation via opencode's own session model rather than per-session directories -- see
`workbench/api/app/repo/opencode_client.py` module docstring for why) -- `oc run`'s per-invocation
slug and the copilot backend's single shared directory are two independent, deliberately different
choices for two different call patterns; don't conflate them.

Once the gateway app is redeployed with the bind mount, re-verify this section's 500 repro and
delete/trim this note + the ENOENT flavor above if confirmed fixed.

First attempt (fresh session, `groq/llama-3.1-8b-instant`, default `/` directory):
```
ContextOverflowError: "Session too large to compact - context exceeds model limit even after
stripping media"
```
Oddity: this was the *first* message on a brand-new session, yet the response's `info.parentID`
pointed at a pre-existing message — the default project scope (`projectID: "global"`, directory
`/`) is shared across every session created against that directory, and evidently already carries
enough accumulated history (from real coding work OpenCode does against this box) to blow a small
model's context on the very first turn.

Retried with an isolated `--directory` (`/tmp/oc-cli-probe`, then `/tmp/oc-cli-smoke*`) — new
session, still failed, but with a different, generic fault both times:
```
HTTP 500 {"name":"UnknownError","data":{"message":"Unexpected server error. Check server logs for
details.","ref":"err_..."}}
```
Reproduced across two different connected providers (`groq/llama-3.1-8b-instant`,
`nvidia/z-ai/glm-5.2`) and two different isolated directories — rules out a single-provider or
context-overflow explanation for the *second* failure mode. This is a server-side fault on the
OpenCode headless deployment itself, not a client/CLI bug.

Checked and ruled out: the task brief's hinted cause ("provider config still pointing at retired
LiteLLM") — `GET /provider` shows all 5 connected providers (`nvidia`, `ollama-cloud`, `opencode`,
`openrouter`, `groq`) pointing straight at their real public API base URLs
(`integrate.api.nvidia.com`, `ollama.com`, `opencode.ai/zen`, `openrouter.ai`, groq's default), none
route through a LiteLLM gateway. Worth checking the opencode container's own logs on ovh-app next
(`ref: err_...` IDs are logged server-side per the error body).

`oc run` documents this cleanly (`FAIL: HTTP 500: {...}` + session/model echoed) rather than hanging
or crashing — that's the acceptance bar the CLI was built to hit, not a claim that prompting works.

## 3. `/v1/runs` (spine run ledger) is not deployed yet

`GET /v1/runs` on agentos-api (`:8000`) 404s. `GET /info` reports `workflow_count: 0` — no
workflows are registered on this AgentOS build (`agno_version: 2.6.13`, `agent_count: 6`,
`team_count: 3`). The live API surface (from `/openapi.json`, 75 paths) nests runs per resource
type instead:
- `/agents/{agent_id}/runs` (`GET`, `POST`), `/agents/{agent_id}/runs/{run_id}` (`GET`)
- `/workflows/{workflow_id}/runs`, `/workflows/{workflow_id}/runs/{run_id}`
- `/teams/{team_id}/runs`, `/teams/{team_id}/runs/{run_id}`

`oc runs` targets the unified `/v1/runs` contract as specced (the platform's own stated intent for
a cross-type run ledger) and 404s with a clear, non-crashing message pointing at the current
per-type shape. When the spine ledger ships, `oc runs` should start working with zero code changes
(same URL, same bearer). If it ships under a different path, update `AGENTOS_URL`-relative paths in
`cmd_runs()` in `oc.py`.

Also note: `/v1/evidence/import` and `/v1/knowledge/reindex` DO exist today under the `/v1/` prefix
— so `/v1/` isn't wholesale unbuilt, just the runs ledger specifically.

## 4. `/agents` and `/teams` list return 500

`GET /agents` and `GET /teams` on agentos-api both return `Internal Server Error` (plain text, not
JSON) even though `GET /info` reports non-zero `agent_count`/`team_count`. `GET /health` and
`GET /info` work fine (200). Workaround: enumerate via the MCP tool `agentos:get_sessions` (lists
sessions which reference agent/team ids) or `agentos:run_agent`/`run_team` directly if the id is
already known from other context (e.g. Coolify env, AGENTOS docs).

## 5. ContextForge `/mcp` gateway is stateless; agentos MCP is session-scoped

Verified live: a bare `tools/list` POST against `http://100.72.169.40:4444/mcp` with **no prior
`initialize` call at all** returns 200 with the full 69-tool catalog — no `Mcp-Session-Id` header
is issued or required. `http://100.72.169.40:8000/mcp` (agentos-api's mounted MCP surface) **does**
issue a session id on `initialize` and expects it echoed back on subsequent calls. `oc.py`'s
`McpClient` handles both: it always calls `initialize()` once per client instance, captures a
session id if one comes back, and only sends the `Mcp-Session-Id` header when it has one.

(Historical note: this same session-scoped behavior was previously observed against the standalone
`agentos-mcp` service on `:8001`, retired 2026-07-23 once agno 2.8.0 fixed the mounted-`/mcp` bug
that service worked around — `:8000/mcp` now exhibits the identical session-id contract.)

ContextForge's federated tool names are the catalog's own registered names verbatim (e.g.
`agno-platform-run-agent`, `coolify-write-list-projects`, `graphiti-get-status`) — **not** a fixed
`<server>-` prefix derived from the `oc tools call <server>:<tool>` server selector. The `server`
argument only picks which endpoint to hit (`agentos` → direct `:8000/mcp` with native
underscore-style names like `run_agent`; `contextforge` → `:4444/mcp` with the catalog's own
hyphenated names like `agno-platform-run-agent`). Always `oc tools list --server X` first to get the
exact literal name before `oc tools call X:<name>`.

## 6. OpenCode server API surface (162 paths from `/doc`, condensed)

Full OpenAPI 3.1 spec at `GET /doc`. Two parallel path families exist in the same doc — top-level
(`/session`, `/provider`, `/config`, `/agent`, `/event`, ...) and an `/api/*`-prefixed mirror
(`/api/session`, `/api/provider`, ...). `oc` uses the top-level family throughout (verified working
live); the `/api/*` family appears to be a compat/proxy mirror and wasn't separately exercised.

Endpoints `oc` does not yet wrap but may be worth adding later: `/find`, `/find/file`,
`/find/symbol` (code search inside whatever the server has open), `/file`, `/file/content`,
`/file/status`, `/vcs/*` (git status/diff), `/pty/*` (remote shell), `/tui/*` (drive the actual TUI
if one's attached). These map to the `mcp__opencode__*` MCP tool tiers already registered in this
Claude Code session (see its "Tier 1/2/3" guide) — that MCP server is a *different* integration path
(local dev-tool MCP against a project-scoped OpenCode instance) from the platform's shared headless
server this skill targets; don't conflate the two.
