# Lane 2 — Platform HTTP API Surface Inventory

> _Byline: lane-2 agent · Sonnet · 2026-08-24_

Evidence-only inventory. Every claim below is either a `file:line` citation into
this worktree (`E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform`,
branch `main`) or a live-probe result against `http://100.72.169.40:8000`
(GET-only, no mutating calls made). Where neither was available the item is
marked `UNKNOWN — not verified`.

All paths below are relative to `Agno-MCP-Platform/` unless stated otherwise.

---

## 0. How routes get onto the wire

`server/api/main.py`'s `_build_app()` builds a plain `FastAPI()` instance
(`server/api/main.py:368`), registers the custom routers listed in §1 directly
on it (`server/api/main.py:372-396`, **before** AgentOS wraps it —
`on_route_conflict="preserve_base_app"`, `server/api/main.py:453`), then hands
that app to `agno.os.AgentOS(base_app=app, ...)` (`server/api/main.py:424-463`),
which mounts its own native routers (agents/teams/workflows/knowledge/memory/
sessions/traces/etc.) and a `/mcp` JSON-RPC endpoint (`enable_mcp_server=True`,
`server/api/main.py:452`) onto the **same** app object and the **same** `:8000`
port. `agent_os.get_app()` (`server/api/main.py:464`) returns that single
merged ASGI app — this is what `uvicorn server.api.main:app` serves
(`server/api/main.py:504`, and `deploy/exec.yaml:52`, command line).

Consequence for auth (detail in §2): there is exactly **one** deployed process
and **one** listening port. Every route below — custom or agno-native — is
reachable at `http://100.72.169.40:8000<path>` (tailnet) or
`https://agentos.mitechconsult.com<path>` (public, currently 503 per prior
session notes — not re-verified here since only the tailnet host was in scope).

---

## 1. Custom routes registered in `server/api/`

These are the routes this codebase defines itself (as opposed to agno's
built-in routers, covered in §1b). Grouped by concern, each row cites the
`@app.<method>` / `@router.<method>` decorator line.

### Knowledge / ingest

| Method | Path | Auth | Purpose | Citation | Live probe |
|---|---|---|---|---|---|
| POST | `/v1/knowledge/reindex` | global gate (§2) | Run the framework-neutral folder-walk ingester into canonical PostgreSQL; returns `{indexedDocumentCount, status, store}` | `server/api/main.py:187` (`register_knowledge_routes`, called at `main.py:372`) | not probed (POST, mutating) |
| POST | `/v1/ingest` | global gate **+** route-local `_authorize()` re-check | Multipart upload → staged file → background `ingest_file()` task; returns 202 `{run_id, workflow, mode, status}` | `server/api/ingest_routes.py:114-159` | not probed (POST) |
| POST | `/v1/ingest/path` | global gate **+** route-local `_authorize()` | Ingest an already-staged path synchronously (up to the returned receipt); 201 | `server/api/ingest_routes.py:161-181` | not probed (POST) |
| GET | `/v1/knowledge/items` | global gate **+** route-local `_authorize()` | List canonical knowledge items (`matter_id`, `lane`, `limit` query params) | `server/api/ingest_routes.py:183-192` | **401** `{"detail":"Authorization header required"}` (unauthenticated GET) |
| GET | `/v1/knowledge/items/{artifact_id}` | global gate **+** route-local `_authorize()` | Fetch one canonical knowledge item; 404 if absent | `server/api/ingest_routes.py:194-202` | not probed individually; same gate confirmed via the list route above |

### Records / search (Data Explorer + native evidence search)

| Method | Path | Auth | Purpose | Citation | Live probe |
|---|---|---|---|---|---|
| GET | `/v1/records` | global gate | Paged `working.normalized_record` browser, resolved by `artifact_id` or `run_id` | `server/api/inspect_routes.py:249-347` | **401** (unauthenticated) |
| GET | `/v1/inspect/schemas` | global gate | Live PG table/column introspection (`evidence`,`working`,`analysis`,`reference`,`ops` schemas) + Weaviate collection introspection | `server/api/inspect_routes.py:590-597` | **401** (unauthenticated) |
| GET | `/v1/inspect/tables/{schema}/{table_name}` | global gate | Bounded PG row/field preview (max 25 rows) | `server/api/inspect_routes.py:599-601` | not probed individually; same gate |
| GET | `/v1/inspect/weaviate/{collection_name}` | global gate | Bounded Weaviate object/vector preview (max 10) | `server/api/inspect_routes.py:603-605` | not probed individually; same gate |
| POST | `/v1/verify/{sha256}` | global gate | Two-tier custody hash verification (H1 file hash; H2/H3 chain walk if `custody_tier='full'`) | `server/api/inspect_routes.py:664-752` | not probed (POST) |
| POST | `/v1/runs/{run_id}/parse-dryrun` | global gate | Run the parser candidate chain on an upload or an in-custody sha256 **without storing** | `server/api/inspect_routes.py:762-856` | not probed (POST) |
| PATCH | `/v1/records/{record_id}/meta` | global gate | Curate `title`/`labels`/`attrs_patch` on a normalized record (attrs-only merge; blocked on `acquired_third_party` rows, 409) | `server/api/inspect_routes.py:933-995` | not probed (PATCH) |
| POST | `/v1/third-party-conversations/{conversation_id}/approve` | global gate | Owner-resolves sender/participant entity IDs for an acquired third-party conversation; triggers knowledge reprojection | `server/api/inspect_routes.py:881-929` | not probed (POST) |
| POST | `/v1/flags` | global gate | Create a corroboration flag (`target_kind`∈{record,knowledge,run}) | `server/api/inspect_routes.py:1042-1077` | not probed (POST) |
| GET | `/v1/flags` | global gate | Paged/filtered flag list | `server/api/inspect_routes.py:1079-1116` | not probed individually; same gate |
| PATCH | `/v1/flags/{flag_id}` | global gate | Update flag status/notes/linked_artifacts | `server/api/inspect_routes.py:1118-1148` | not probed (PATCH) |
| POST | `/v1/evidence/search` | **walk-capability HMAC token** (not the global bearer alone — see §2) | Pass-bound agent evidence search; `case_id`/`horizon`/`disclosure_tiers` are server-resolved from an exact walk/step/checkpoint row, never caller-supplied | `server/api/native_evidence_search_routes.py:314-342` | not probed (POST); route exists only when `NATIVE_EVIDENCE_ENABLED` is true (`server/api/main.py:392-393`) |
| POST | `/v1/operator/evidence/search` | global gate **+** separate `EVIDENCE_OPERATOR_SECURITY_KEY` bearer | Owner-exploration evidence search; horizon capped at "now", tiers fixed to `(contemporaneous, discovered)` — never `hindsight` | `server/api/native_evidence_search_routes.py:344-374` | not probed (POST) |

`mode` on both search routes is `Literal["near_vector", "hybrid"]` only
(`server/api/native_evidence_search_routes.py:54,66`) — see §5 for the
full-text/fuzzy gap this implies.

### Evidence ops (custody / run ledger)

| Method | Path | Auth | Purpose | Citation | Live probe |
|---|---|---|---|---|---|
| POST | `/v1/evidence/import` | global gate | Multipart upload → `run_chat_transcript` workflow (custody→parse→normalize→store→knowledge); `domain`∈{platform,legal,personal_history,context,evidence} | `server/api/evidence_routes.py:63-98` | not probed (POST) |
| POST | `/v1/runs` | global gate | Start a `chat-transcript` or `sms-xml` run in the background; 202 `{run_id, workflow, mode}` | `server/api/run_routes.py:453-516` | not probed (POST) |
| GET | `/v1/runs` | global gate | List recent runs + per-stage status (`status`, `limit` query params) | `server/api/run_routes.py:518-526` | **401** (unauthenticated) |
| GET | `/v1/runs/{run_id}` | global gate | Full run detail (row + ordered stages) | `server/api/run_routes.py:528-536` | not probed individually; same gate |
| GET | `/v1/runs/{run_id}/report` | global gate | Versioned report: every stage/disposition/reason/review action | `server/api/run_routes.py:538-546` | not probed (GET, path-param) |
| POST | `/v1/runs/{run_id}/review-actions` | global gate | Record a human decision (`acknowledge`\|`approve`\|`override`) on a run/stage | `server/api/run_routes.py:548-564` | not probed (POST) |
| POST | `/v1/runs/{run_id}/continue` | global gate | Release a `mode="supervised"` gate; 409 if not paused | `server/api/run_routes.py:566-584` | not probed (POST) |
| POST | `/v1/runs/{run_id}/abort` | global gate | Abort a paused/running run at the next stage boundary; 409 if terminal | `server/api/run_routes.py:586-614` | not probed (POST) |
| POST | `/v1/runs/{run_id}/retry` | global gate | Re-run a terminal-failed run, or (optional body `{"from_stage":"knowledge"}`) re-run only the knowledge stage over already-stored records | `server/api/run_routes.py:616-796` | not probed (POST) |
| GET | `/v1/health/deps` | global gate | Parallel pg + Weaviate connectivity check, 3s timeout each (the `milvus` key is a deprecated alias of the same Weaviate check) | `server/api/run_routes.py:431-451` | **401** (unauthenticated) |
| POST | `/v1/repairs/execute` | global gate **only** (no separate credential; requires in-body `approved: true`) | Authenticated operator-only execution door for approval-gated repair tools (`tool_id` must match `^repair\.`) | `server/api/repair_routes.py:20,33-47` | not probed (POST) |

### Entities

| Method | Path | Auth | Purpose | Citation | Live probe |
|---|---|---|---|---|---|
| GET | `/v1/entities` | global gate | Search canonical entities (`q`, `limit`); excludes merged rows | `server/api/entity_routes.py:114-116` | **401** (unauthenticated) |
| POST | `/v1/entities` | global gate | Create a canonical entity (`display_name`, `entity_type`); 409 on normalized-name collision | `server/api/entity_routes.py:118-122` | not probed (POST) |

### Case management (Matters / Evidence Items)

| Method | Path | Auth | Purpose | Citation | Live probe |
|---|---|---|---|---|---|
| GET | `/v1/matters` | global gate | Paged matter list | `server/api/case_management_routes.py:55-60` | **401** (unauthenticated) |
| POST | `/v1/matters` | global gate | Create a matter | `server/api/case_management_routes.py:62-69` | not probed (POST) |
| GET | `/v1/matters/{matter_id}` | global gate | Matter detail | `server/api/case_management_routes.py:71-73` | not probed individually; same gate |
| POST | `/v1/matters/{matter_id}/court-cases` | global gate | Create a court case under a matter | `server/api/case_management_routes.py:75-82` | not probed (POST) |
| POST | `/v1/matters/{matter_id}/knowledge/resolve` | global gate | Resolve a knowledge-source reference into provenance | `server/api/case_management_routes.py:84-93` | not probed (POST) |
| POST | `/v1/matters/{matter_id}/evidence-items` | global gate | **Promote** a resolved knowledge source into a matter's evidence item | `server/api/case_management_routes.py:95-104` | not probed (POST) |
| GET | `/v1/matters/{matter_id}/evidence-items/{evidence_item_id}` | global gate | Evidence item detail | `server/api/case_management_routes.py:106-115` | not probed individually; same gate |
| GET | `/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/court-readiness` | global gate | Court-readiness assessment for one evidence item | `server/api/case_management_routes.py:117-126` | not probed individually; same gate |
| POST | `/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews` | global gate | Record a review of an evidence item | `server/api/case_management_routes.py:128-138` | not probed (POST) |
| GET | `/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/reviews` | global gate | List reviews for an evidence item | `server/api/case_management_routes.py:140-149` | not probed individually; same gate |
| GET | `/v1/matters/{matter_id}/evidence-items` | global gate | Paged evidence-item list, filterable by `review_status` | `server/api/case_management_routes.py:151-169` | not probed individually; same gate |
| GET | `/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/source-content` | global gate | Original source content for an evidence item | `server/api/case_management_routes.py:171-180` | not probed individually; same gate |
| GET | `/v1/matters/{matter_id}/evidence-items/{evidence_item_id}/conversation-context` | global gate | Surrounding conversation context (`before`/`after` message counts) | `server/api/case_management_routes.py:182-200` | not probed individually; same gate |

All case-management routes delegate to `server/case_management/service.py`
(imported at `server/api/case_management_routes.py:18`); domain errors are
translated to HTTP status via `_translate()` (`case_management_routes.py:45-49`).

### Registration wiring (for cross-reference)

`server/api/main.py:374-396` imports and calls, in this order:
`register_evidence_routes`, `register_entity_routes`,
`register_case_management_routes`, `register_inspect_routes`,
`register_ingest_routes`, `register_native_evidence_search_routes`
(conditional), `register_run_routes`, `register_inspect_routes` (again, see
below), `app.include_router(repair_router)`. `register_knowledge_routes` is
called separately at `main.py:372`, before the evidence-module imports.

Note: `register_inspect_routes` is invoked once, at `main.py:390`
(`register_inspect_routes(app, _knowledge_handle, native_projector)`) — the
call order in the source text is
knowledge→evidence→run→inspect→ingest→(native-evidence)→entity→case-management→repairs;
listed here exactly as it appears so a future reader isn't misled by my
grouping above, which is by concern, not by source order.

---

## 1b. Native AgentOS (agno-framework) routes — not defined in `server/api/`, but reachable on the same port

These are **not** this codebase's code — they come from the pinned `agno==2.8.x`
package's `agno/os/routers/*` and are mounted onto the same FastAPI app by
`AgentOS(...)` (`server/api/main.py:424-463`). Listed because they are part of
"what n8n could call today" on `:8000`; only representative/aggregate detail is
given (full per-route enumeration is agno's own surface, not this repo's).

| Concern | Representative paths | Source (agno package, this venv) |
|---|---|---|
| Unauthenticated meta | `GET /`, `GET /health`, `GET /info`, `GET /docs`, `GET /redoc`, `GET /openapi.json` | `.venv/Lib/site-packages/agno/os/routers/home.py:12`, `routers/health.py:13`; exclusion list at `agno/os/app.py:1441-1451` |
| Agents | `POST /agents/{agent_id}/runs`, `GET /agents`, `GET /agents/{agent_id}`, `GET /agents/{agent_id}/sessions`, etc. | `.venv/.../agno/os/routers/agents/router.py` (auth wired at line 541) |
| Teams | `POST /teams/{team_id}/runs`, `GET /teams`, etc. | `.venv/.../agno/os/routers/teams/router.py` (auth wired at line 528) |
| Workflows | `GET /workflows`, `POST /workflows/{workflow_id}/runs`, etc. — includes the `chat-transcript` and `sms-xml` factories this repo registers (`server/api/workflow_registry.py:184-201`, wired at `server/api/main.py:448-450`) | `.venv/.../agno/os/routers/workflows/router.py` (auth wired at line 979) |
| Knowledge | `GET/POST /knowledge*` (per-base; `knowledge_id`∈{legal_knowledge, personal_history_knowledge, platform_context, platform_knowledge} per `server/api/main.py:95-102`) | `.venv/.../agno/os/routers/knowledge/knowledge.py` (auth wired at line 56) |
| Memory / Sessions / Traces / Metrics | `GET /memories`, `GET /sessions`, `GET /traces`, `GET /metrics` | `.venv/.../agno/os/routers/{memory,session,traces,metrics}/*.py` |
| Schedules / Approvals / Service accounts | `POST /schedules`, `GET/POST /approvals`, `POST /service-accounts` | `.venv/.../agno/os/routers/{schedules,approvals,service_accounts}/router.py` |
| Config / Registry / Database / Components / Evals / Learnings | `GET /config`, `GET /registry`, `GET /database*`, `GET/POST /components*`, `.../evals*`, `.../learnings*` | `.venv/.../agno/os/routers/{database,registry,components,evals,learnings}/*.py` |
| MCP | `/mcp` (JSON-RPC, StreamableHTTP) | mounted via `enable_mcp_server=True`, `server/api/main.py:452`; see §4 |

Live-probed subset: `GET /` → **200**; `GET /health` → **200**; `GET /info` →
**200**; `GET /openapi.json` → **200**; `GET /config` → **401**; `GET /agents`
→ **401**; `GET /workflows` → **401**; `GET /mcp` → **401**.

---

## 2. Auth mechanics

Two independent layers exist; most routes carry only the first.

**Layer 1 — global `AuthMiddleware` (the "OS_SECURITY_KEY gate").**
`AgentOS.get_app()` calls `_add_auth_middleware(fastapi_app, security_key=...)`
(`.venv/Lib/site-packages/agno/os/app.py:1240`) whenever
`auth_configured = bool(self.authorization or jwt_env_configured or security_key)`
is true (`agno/os/app.py:1235`). This repo sets `authorization=False`
(`server/api/main.py:457`) and configures no JWT env vars, so the sole trigger
is `security_key = self.settings.os_security_key` (`agno/os/app.py:1212`),
which `pydantic_settings.BaseSettings` populates from the environment variable
`OS_SECURITY_KEY` (field `os_security_key`,
`.venv/Lib/site-packages/agno/os/settings.py:21`). `deploy/exec.yaml:145-146`
documents this in a deploy comment ("Authentication is enforced by AgentOS's
OS_SECURITY_KEY bearer middleware"), and the credential is Coolify-managed
(not present anywhere in `deploy/exec.yaml`'s `environment:` block — it is
injected by the platform, consistent with the other `?:`-required secrets in
that file such as `WALK_PASS_SIGNING_KEY` and
`EVIDENCE_OPERATOR_SECURITY_KEY`).

Because `fastapi_app` at the point this middleware is installed **is the
base_app** (`agno/os/app.py:1003-1004`: `if self.base_app: fastapi_app =
self.base_app`), `add_middleware` wraps the **entire** ASGI app — this
authentication layer covers every custom route in §1 exactly the same as
agno's own routers in §1b, even though none of the `server/api/*.py` route
functions declare an explicit `Depends(...)`. The only exemptions are
`excluded_route_paths`: `/`, `/health`, `/info`, `/docs`, `/redoc`,
`/openapi.json`, `/docs/oauth2-redirect` (`agno/os/app.py:1441-1451`), plus any
`authenticates_own_requests` interface prefixes (none configured here) and any
`mcp_auth`-derived OAuth paths (no `mcp_auth` provider is configured in
`server/api/main.py`, so `/mcp` itself is **not** exempt — confirmed live,
§1b). This was verified live: unauthenticated GET to `/v1/entities`,
`/v1/matters`, `/v1/runs`, `/v1/records`, `/v1/inspect/schemas`,
`/v1/health/deps`, `/v1/knowledge/items`, `/agents`, `/workflows`, `/config`,
and `/mcp` all returned **401** `{"detail":"Authorization header required"}`
(the exact body from `GET /v1/entities`); `/`, `/health`, `/info`, and
`/openapi.json` returned **200** unauthenticated.

**Layer 2 — per-route additional credentials, on top of Layer 1:**
- `server/api/ingest_routes.py:28-40` (`_authorize()`) re-checks a
  `Authorization: Bearer <OS_SECURITY_KEY>` header inside the handler itself
  for `POST /v1/ingest`, `POST /v1/ingest/path`, `GET /v1/knowledge/items`,
  `GET /v1/knowledge/items/{artifact_id}` — reads the **same**
  `OS_SECURITY_KEY` env var directly (`getenv("OS_SECURITY_KEY", "")`,
  line 29), so this is redundant with Layer 1 for this deployment, not a
  distinct credential.
- `server/api/native_evidence_search_routes.py:78-89`
  (`_authenticate_bearer`) checks a **separate** env-configured bearer
  (`EVIDENCE_OPERATOR_SECURITY_KEY`) for `POST /v1/operator/evidence/search`
  (call site `native_evidence_search_routes.py:346`) — a genuinely distinct
  credential from `OS_SECURITY_KEY`.
- `server/api/native_evidence_search_routes.py:92-109`
  (`_authenticate_walk_capability`) validates an **HMAC-signed, single-use**
  capability token bound to one exact
  `(walk_run_id, walk_step_id, checkpoint_id)` triple, minted by
  `issue_walk_search_capability()` (`server/evidence/search_capability.py:16-24`,
  signed with `WALK_PASS_SIGNING_KEY`) for `POST /v1/evidence/search`
  (call site `native_evidence_search_routes.py:316`). This is not a bearer
  token a caller can obtain independently — it must be issued server-side for
  an exact ledger transition, so an external orchestrator cannot call this
  route without first driving a walk/checkpoint sequence through the platform.
- `server/api/repair_routes.py` adds **no** additional credential beyond
  Layer 1 — it relies on the global gate plus an in-body `approved: true`
  boolean (`repair_routes.py:29,36-37`) and a `tool_id` pattern restriction to
  `^repair\.` (`repair_routes.py:27`). The module docstring's claim that this
  route "is protected by AgentOS's normal security-key middleware"
  (`repair_routes.py:5-7`) is accurate per the Layer-1 trace above.

**Not an auth mechanism:** `server/api/db_id_middleware.py` installs a
`@app.middleware("http")` that defaults a missing `db_id` query parameter on
routes whose endpoint signature declares one (`db_id_middleware.py:118-166`).
It exists to route around agno's multi-db 400 gate
(`db_id_middleware.py:1-46`), not to authenticate or authorize anything —
called out here only so it isn't mistaken for a security control. It also
explicitly excludes `/knowledge*` paths (`db_id_middleware.py:153-154`)
because those routes resolve via `knowledge_id`, not `db_id` — a caller
targeting a specific named knowledge base (legal / personal_history / context
/ platform) must pass `knowledge_id` explicitly.

---

## 3. Live validation (GET-only probes, `http://100.72.169.40:8000`)

| Path | HTTP status | Note |
|---|---|---|
| `GET /` | 200 | `{"name":"AgentOS API","id":"mcp-forensic-platform","version":"1.0.0"}` |
| `GET /health` | 200 | excluded from auth |
| `GET /info` | 200 | excluded from auth |
| `GET /openapi.json` | 200 | excluded from auth |
| `GET /config` | 401 | agno-native, Layer-1 gated |
| `GET /agents` | 401 | agno-native, Layer-1 gated |
| `GET /workflows` | 401 | agno-native, Layer-1 gated |
| `GET /mcp` | 401 | mounted MCP endpoint, Layer-1 gated (not exempted — no `mcp_auth` provider configured) |
| `GET /v1/entities` | 401 | body: `{"detail":"Authorization header required"}` |
| `GET /v1/matters` | 401 | |
| `GET /v1/knowledge/items` | 401 | |
| `GET /v1/runs` | 401 | |
| `GET /v1/records` | 401 | |
| `GET /v1/health/deps` | 401 | |
| `GET /v1/inspect/schemas` | 401 | |

No route in this probe set returned a 5xx or timed out — the deployed process
is up and the auth gate behaves as the code predicts. Credentials were never
sought or used, per task instructions; every 401 above is the finding, not an
obstacle worked around.

---

## 4. MCP surface

- **One live MCP endpoint:** `/mcp`, mounted onto the same `:8000` process by
  `enable_mcp_server=True` (`server/api/main.py:452`). Transport is agno's
  FastMCP `StreamableHTTP` (JSON-RPC over HTTP) — documented in the retired
  standalone-extraction module `server/api/mcp_main.py:1-42`, whose docstring
  states the mount now works natively as of agno 2.8.0 (previously the
  mounted sub-app's task group didn't survive mounting, requiring a
  standalone `:8001` workaround). `server/api/mcp_main.py` itself is dead code
  (kept per never-delete convention, `mcp_main.py:1-17`) — not imported by
  anything live.
- **No standalone `agentos-mcp` service exists.** `deploy/exec.yaml` documents
  its retirement inline (`deploy/exec.yaml:129-138`): "agentos-mcp RETIRED
  2026-07-23 ... all MCP traffic now goes to agentos-api's mounted /mcp on
  :8000." No `agentos-mcp` service block remains in the file.
- **Tool list:** not enumerated anywhere in `server/api/` — agno's
  `enable_mcp_server` auto-derives the exposed MCP tools from whatever agents
  (`agents=solo_agents`), teams (`teams=teams`), and workflows
  (`workflows=list[...](registered_workflows(...))`) are passed to
  `AgentOS(...)` (`server/api/main.py:428-450`). No custom MCP tool
  registration file exists under `server/api/`. `UNKNOWN — not verified`
  precisely which tool names the mounted server publishes (would require an
  authenticated JSON-RPC `tools/list` call, out of scope for a GET-only probe).
- **A second, MCP-**adjacent** but undeployed surface:**
  `server/tools/gateway/api.py` builds its own standalone `FastAPI()`
  (`build_app()`, `server/tools/gateway/api.py:21-74`) exposing `GET /health`,
  `GET /categories`, `GET /tools`, `GET /tools/{tool_id}`,
  `POST /tools/{tool_id}/execute`, `GET /refs/{sha}` — its module docstring
  states the intent explicitly: "ContextForge REST-wraps these five routes
  into MCP tools" (`server/tools/gateway/api.py:1-3`). However `build_app()`
  is only invoked by `server/tools/gateway/__main__.py` (a standalone dev
  server, default port 8098, `getenv("GATEWAY_PORT","8098")`,
  `server/tools/gateway/__main__.py:1-14`) and by `tests/test_gateway.py`.
  Searched `server/api/main.py` and every file in `server/api/` for an
  import of `server.tools.gateway.api` or a call to `build_app()`: none
  found. Searched every `deploy/*.yaml` for `tools.gateway`/`gateway.api`:
  none found. **This tool-catalog HTTP surface is code-complete but has no
  live deployment path today.**

---

## 5. Capabilities with NO HTTP surface today

- **Full-text and fuzzy search modes.** Both native-evidence search request
  schemas constrain their `mode` field to `Literal["near_vector", "hybrid"]`
  (`server/api/native_evidence_search_routes.py:54` and `:66`), and
  `server/evidence/retrieval.py:native_evidence_search()`
  (`retrieval.py:62-97`) only branches on those same two values (passes
  `query=None` unless `mode=="hybrid"`, `retrieval.py:96`). Searched
  `server/evidence/`, `server/core/` for a fuzzy-matching implementation
  (pattern `fuzzy`): zero matches anywhere in those directories. There is no
  HTTP-reachable full-text-only or fuzzy-only search mode on this platform —
  only vector-nearest-neighbor and a vector+something-called-"hybrid" mode,
  neither of which is documented in this repo as literal BM25/trigram fuzzy
  matching. (This directly informs the owner requirement recorded elsewhere
  in `docs/reviews/` that search must offer full-text, fuzzy, semantic, and
  hybrid modes — semantic and one flavor of hybrid exist; full-text and fuzzy
  do not have a dedicated HTTP-exposed mode.)
- **Semantica.** All Semantica code lives under `server/analysis/` —
  `semantica_candidates.py`, `semantica_contracts.py`, `semantica_wiring.py`,
  `semantica_worker.py` — plus the vendored engine at
  `server/vendored/semantica/`. Searched every file in `server/api/*.py` for
  the string `semantica`: zero matches. No route imports, calls, or exposes
  anything from `server/analysis/semantica_*`. Semantica is entirely
  code/worker-only; nothing in it is reachable over HTTP.
- **The generic tool-execution gateway** (`server/tools/gateway/toolfinder.py`
  and its dedicated `api.py` app) — see §4. The only live HTTP door into
  `execute_tool()` is the narrow, `^repair\.`-scoped, approval-gated
  `POST /v1/repairs/execute` (`server/api/repair_routes.py`). Arbitrary tool
  discovery (`GET /tools`) and arbitrary tool execution
  (`POST /tools/{tool_id}/execute`) have no live path.
- **Evidence promotion (knowledge → evidence) is NOT a gap** — confirmed
  present at `POST /v1/matters/{matter_id}/evidence-items`
  (`server/api/case_management_routes.py:95-104`, calling
  `service.promote_evidence`). Listed here only to close the loop, since
  "promotion" was named explicitly in the task's example gap list.
- **Workflow execution has two parallel live doors**, not a gap but worth
  flagging for an integrator picking one: the platform-owned run-ledger
  surface (`POST /v1/runs`, §1) and agno-native
  `POST /workflows/{workflow_id}/runs` (§1b, backed by the same
  `chat-transcript`/`sms-xml` `WorkflowFactory` objects,
  `server/api/workflow_registry.py:184-201`). They are not interchangeable:
  only the `/v1/runs` surface writes to this repo's own `ops.workflow_run`
  ledger with the C2 supervised-gate/retry/abort semantics documented in
  `server/api/run_routes.py:1-55`; `workflow_registry.py`'s factories create
  their own ledger row via `_ledgered()` (`workflow_registry.py:122-157`) as
  a best-effort mirror, but a caller wanting the full retry/from_stage
  semantics of §1 should use `/v1/runs`, not the native workflow router.

---

## Summary (8 lines)

1. One deployed process (`agentos-api`, `:8000`, `deploy/exec.yaml`) serves everything: this repo's custom `/v1/*` routes and agno's native `/agents`,`/teams`,`/workflows`,`/knowledge*`,`/mcp`, etc., merged onto one FastAPI app.
2. n8n can call, today, unauthenticated only: `GET /`, `/health`, `/info`, `/openapi.json`/`/docs`/`/redoc` (all confirmed 200 live).
3. Everything else needs `Authorization: Bearer $OS_SECURITY_KEY` — confirmed live via 401s on `/v1/entities`, `/v1/matters`, `/v1/runs`, `/v1/records`, `/v1/inspect/schemas`, `/v1/health/deps`, `/agents`, `/workflows`, `/config`, `/mcp`.
4. With that bearer, n8n gets full read/write access to: ingest (`/v1/ingest*`), the run ledger (`/v1/runs*`, C2 gates/retry), records/inspect/verify (`/v1/records`,`/v1/inspect/*`,`/v1/verify/*`), entities (`/v1/entities`), matters/evidence-items incl. promotion (`/v1/matters/*`), corroboration flags (`/v1/flags*`), and agno-native agents/teams/workflows/knowledge/memory/sessions/traces.
5. Two evidence-search routes exist with a stricter, *second* credential each: `/v1/operator/evidence/search` needs `EVIDENCE_OPERATOR_SECURITY_KEY`; `/v1/evidence/search` needs a server-minted HMAC walk-capability token an external caller cannot self-issue.
6. `/mcp` is live (JSON-RPC/StreamableHTTP, same bearer, confirmed 401 unauth) but its exposed tool list was not enumerated (would need an authenticated `tools/list` call).
7. Missing from the live surface: full-text/fuzzy search modes (only `near_vector`/`hybrid` exist), Semantica (code-only, zero HTTP references), and the generic tool-execution gateway (`server/tools/gateway/api.py` exists but is never mounted or deployed — only its `^repair.*`-scoped subset is live via `/v1/repairs/execute`).
8. Evidence promotion and workflow execution are NOT gaps — both are live, the latter via two parallel doors (`/v1/runs` for full C2 ledger semantics, native `/workflows/{id}/runs` as a lighter-weight mirror).
