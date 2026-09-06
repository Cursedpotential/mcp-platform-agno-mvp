# BUILD LANE N1 — n8n universal-import bridge: bind, activate, probe

> _Byline: Claude Code · Sonnet 5 · 2026-09-02._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

Scope: bind and activate the 7 n8n workflows that back the Go
`UniversalImportWorkflow`'s `select_parser_activity` / `execute_parser_activity`
Activities (plus the human preview start/decision/preview surface and the two
source-repair Activities), using credentials and endpoint values sourced live
from Coolify and the n8n instance. No code changed. No git commit made — the
orchestrator commits.

## TL;DR

- All **7** workflows (5 documented in the README + 2 undocumented
  source-repair workflows added 2026-08-29) were already imported from a
  2026-08-27 attempt. All 3 `httpHeaderAuth` credentials already existed and
  were already attached to the right nodes. I refreshed all 3 credential
  values from the **live** Coolify envs (never printed, never committed) so
  both sides are guaranteed to match, corrected the HTTP node URLs (the
  imported URLs pointed at a Coolify magic-FQDN that does not route — see
  below), and **activated all 7**.
- **Live-probed every webhook** (synthetic payloads, no real import started —
  confirmed via n8n's own execution log, not assumed). Result, by hop:
  - n8n **inbound** webhook trigger + `N8N_UNIVERSAL_IMPORT_WEBHOOK` auth:
    **working** on all 7 (proven for `start` via a deliberately-incomplete
    payload that reached n8n's own validation Code node; proven for the rest
    because their HTTP Request node fired at all).
  - n8n → **universal-import-starter** (`start`/`decision`/`preview`):
    **network-reachable**, but the starter's own `authorizedTailnetPeer`
    check (source-IP allowlist, not the `httpHeaderAuth` credential) rejects
    n8n's calls with a real `401 reference import starter authorization
    required`. This is a **new, previously-undiscovered blocker** — see
    §3.
  - n8n → **parser-activity-runtime** (`select`/`execute`/`assess-repair`/
    `resolve-repair`): **`ECONNREFUSED`** at every address I could construct
    (the Coolify-assigned FQDN, and both `:8090` and `:8092` on the tailnet
    IP). This is the task's named blocking symptom, and it is **still
    blocked** — see §4. It is a network/deploy problem on the
    parser-activity-runtime side, not an n8n binding problem.
- One process note: while extracting secret values from `~/.secrets/n8n-ovh2.env`
  and a Coolify `envs` dump, two redaction regexes silently failed (character
  classes missing digits; one key without TOKEN/AUTH/KEY/SECRET in its name)
  and printed real values into this transcript — never into a git-tracked
  file. Per this repo's own written policy that is not a rotation-triggering
  incident, but is disclosed here for the record. All secret handling after
  that point used name/length-only reporting and value-blind scripts.

## 1. Workflow inventory (`deploy/docker/n8n/workflows/universal-import/`)

| File | n8n workflow name | Webhook path | Calls | In README? |
|---|---|---|---|---|
| `wf-select-parser-activity.json` | Universal Import - select_parser_activity | `universal-import/select-parser-activity` (POST) | `parser-activity-runtime` `/activities/select_parser_activity` | yes |
| `wf-execute-parser-activity.json` | Universal Import - execute_parser_activity | `universal-import/execute-parser-activity` (POST) | `parser-activity-runtime` `/activities/execute_parser_activity` | yes |
| `wf-start-import.json` | Universal Import - start | `universal-import/start` (POST) | `universal-import-starter` `POST /reference-import/start` | yes |
| `wf-preview-decision.json` | Universal Import - decision | `universal-import/decision` (POST) | `universal-import-starter` `POST /reference-import/{workflow_id}/decision` | yes |
| `wf-preview-status.json` | Universal Import - preview | `universal-import/preview` (GET, `?workflow_id=`) | `universal-import-starter` `GET /reference-import/{workflow_id}/preview` | yes |
| `wf-assess-source-repair-activity.json` | Universal Import - assess_source_repair_activity | `universal-import/assess-source-repair-activity` (POST) | `parser-activity-runtime` `/activities/assess_source_repair_activity` | **no** (added 2026-08-29) |
| `wf-resolve-source-repair-activity.json` | Universal Import - resolve_source_repair_activity | `universal-import/resolve-source-repair-activity` (POST) | `parser-activity-runtime` `/activities/resolve_source_repair_activity` | **no** (added 2026-08-29) |

**Important discrepancy found, not a binding problem but worth recording:**
the Go engine's `AssessSourceRepair` / `ResolveSourceRepair` Activities
(`modules/engine/activities/repair.go`, registered in
`modules/engine/activities/register.go:123-124`) call a `RepairToolClient`
that runs `repair.detect` / `repair.preview` / `repair.write-derived` /
`repair.pdf-derived` **platform-tools capabilities directly** — never n8n,
never the two `assess_source_repair_activity` / `resolve_source_repair_activity`
HTTP handlers on `parser-activity-runtime`
(`modules/engine/runtimeapi/repair_activities.go`). Those runtime HTTP
handlers and the two n8n workflows that call them exist and are now
active/bound, but **nothing in the production worker calls them**. They are
either a forward-looking alternate integration or dead surface — flagging
for an owner decision, not treating either workflow as load-bearing today.

## 2. Endpoint values used, and how each was confirmed

| Target | Value used | Confirmed against |
|---|---|---|
| `universal-import-starter` | `http://100.91.190.107:8091` | `deploy/universal-import-starter.yaml` (`REFERENCE_STARTER_ADDR: 100.91.190.107:8091`, `network_mode: host`) + Coolify app detail (`ports_mappings: "8091:8091"`, `ports_exposes: 8091`) |
| `parser-activity-runtime` | `http://100.91.190.107:8092` (best available; **still unreachable**, see §4) | Coolify app detail's **live** `ports_mappings: "8092:8090"` — NOT the `deploy/parser-activity-runtime.yaml` default of `${BIND_IP:-127.0.0.1}:8090:8090`. Coolify bumped the published host port to 8092, almost certainly to avoid a collision, the same pattern already documented in this repo's memory for `coolify-proxy` owning 8080 |

**Worker-side contract, verified byte-for-byte against the live n8n paths**
(the task's named #1 failure mode):

- `modules/engine/uiwworker/config.go` requires `N8N_UNIVERSAL_IMPORT_BASE_URL`
  and trims a trailing `/`. Live Coolify value on both
  `universal-import-worker` and `universal-import-starter`:
  `http://n8n-ddjgrmys36d9n8xwcwj0mml2:5678/webhook` (internal Coolify
  service DNS name for the n8n container, port 5678, `/webhook` prefix).
- `modules/engine/temporal/n8n_client.go`'s `stageRoutes()` builds
  `c.baseURL + "/" + route.path`, where `route.path` is the literal string
  `"universal-import/select-parser-activity"` / `"universal-import/execute-parser-activity"`
  — **exactly** the Webhook trigger node's `path` parameter in the two n8n
  JSON exports. Full worker-constructed URL:
  `http://n8n-ddjgrmys36d9n8xwcwj0mml2:5678/webhook/universal-import/select-parser-activity`.
  Match confirmed.
- **Not verified, flagged as an open risk**: `universal-import-worker` and
  `universal-import-starter` both run with `network_mode: host`
  (`deploy/universal-import-worker.yaml`, `deploy/universal-import-starter.yaml`).
  Host-network containers do not get Docker's embedded DNS resolver, so
  whether `n8n-ddjgrmys36d9n8xwcwj0mml2` (a Docker bridge-network service
  name) actually resolves from a host-network container on the same box is
  unproven from this session — I have no shell on that host and could not
  test it. This is the reverse direction of the blocker in §4 (worker → n8n,
  not n8n → runtime) and was out of this task's probe scope, but it is the
  same class of problem and should be checked before declaring the pipeline
  end-to-end live.

## 3. Credentials

All 3 `httpHeaderAuth` credentials already existed in n8n from the 2026-08-27
attempt and were already attached to the correct nodes. I refreshed all 3
values via `PATCH /credentials/{id}` from the **live** Coolify env values
(worker/starter envs for the webhook credential, parser-activity-runtime env
for the runtime credential) so both sides are provably in sync — no value was
retyped or invented, and no value was printed to logs, files, or this
transcript after the initial redaction-bug exposure noted above.

| Credential | n8n id | Used by | Header | Source of value |
|---|---|---|---|---|
| `N8N_UNIVERSAL_IMPORT_WEBHOOK` | `Dld9smudiIlCuMv7` | all 7 Webhook trigger nodes (inbound) | `Authorization` (name confirmed live, not secret) | `N8N_UNIVERSAL_IMPORT_AUTH_HEADER`/`_VALUE` on `universal-import-worker` **and** `universal-import-starter` — both apps show identical lengths (13 / 71), consistent with each other |
| `REFERENCE_IMPORT_STARTER` | `b8Ue9L1WkaNosGtB` | `start`/`decision`/`preview` HTTP nodes (outbound to starter) | `Authorization: Bearer <REFERENCE_STARTER_TOKEN>` | `REFERENCE_STARTER_TOKEN` on `universal-import-starter` (len 64) — **see finding below: this value is not actually checked by the starter** |
| `PLATFORM_IMPORT_RUNTIME` | `sIcLLMkpZTG07DB0` | select/execute/assess-repair/resolve-repair HTTP nodes (outbound to runtime) | `Authorization: Bearer <PARSER_ACTIVITY_TOKEN>` | `PARSER_ACTIVITY_TOKEN` on `parser-activity-runtime` (len 64), confirmed against `modules/engine/cmd/parser-activity-runtime/main.go:47` and `modules/engine/runtimeapi/parser_activities.go:65` (`validBearerToken(request.Header.Get("Authorization"), ...)`) |

**Finding: `REFERENCE_STARTER_TOKEN` is dead configuration.** The starter's
route auth (`modules/engine/temporal/httpapi.go:53-59`, `withAuth`) does not
check any header at all — it calls `authorizedTailnetPeer(r)`
(`httpapi.go:190-196`), which parses `r.RemoteAddr` and accepts the request
only if the **observed TCP peer IP** is in `100.64.0.0/10` (Tailscale's CGNAT
range: `ip[0]==100 && 64<=ip[1]<=127`). `REFERENCE_STARTER_TOKEN` is set in
Coolify (len 64) but is not read anywhere in `modules/engine` — confirmed via
a full-repo grep with zero matches outside the env table in this README. The
`REFERENCE_IMPORT_STARTER` credential's value is therefore cosmetically
correct but functionally irrelevant; whatever governs `start`/`decision`/
`preview` reachability is n8n's outbound source IP, not this credential.

## 4. Live probe results (2026-09-02, ~19:00–19:25 UTC)

Every probe used a synthetic, obviously-fake `request_id`/refs/`workflow_id`
and was verified via `GET /executions/{id}?includeData=true` on the n8n
instance itself (not inferred from the webhook's own HTTP status, since a
failed n8n execution still returns `200` with an empty body to the caller —
see the "empty 200 body" note below). **No real import was started**: the
`start` probe used a deliberately-incomplete payload that n8n's own
`Validate + Shape Start Request` Code node rejected before it ever reached
the starter's HTTP node (execution 27, confirmed from `runData` — only the
`Webhook` and `Code` nodes ran); `decision`/`preview` targeted a
nonexistent `workflow_id`, so even a fully-authorized call could not have
signaled a real run.

| Workflow | Webhook → n8n webhook trigger + inbound auth | Next hop | Result |
|---|---|---|---|
| `select_parser_activity` | reached (HTTP node fired) | → `parser-activity-runtime` | **`ECONNREFUSED`** at `100.91.190.107:8092` (also confirmed at `:8090`, also `404` at the Coolify FQDN — see §4a) |
| `execute_parser_activity` | reached | → `parser-activity-runtime` | **`ECONNREFUSED`** at `100.91.190.107:8092` |
| `assess_source_repair_activity` | reached | → `parser-activity-runtime` | **`ECONNREFUSED`** at `100.91.190.107:8092` |
| `resolve_source_repair_activity` | reached | → `parser-activity-runtime` | **`ECONNREFUSED`** at `100.91.190.107:8092` |
| `start` | reached, own validation node fired correctly | (not reached — probe intentionally stopped here) | n8n-side contract confirmed working; starter hop not directly exercised (see reasoning below) |
| `decision` | reached | → `universal-import-starter` | **`401`**, JSON body `{"error":"reference import starter authorization required"}` — real response from `authorizedTailnetPeer` rejecting n8n's source IP |
| `preview` | reached | → `universal-import-starter` | **`401`**, same `authorized ... required` body |

Reasoning for not directly probing `start`'s starter hop: `decision` and
`preview` share the exact same starter binary, the exact same
`withAuth`/`authorizedTailnetPeer` gate, and the exact same network path
(`100.91.190.107:8091`) as `start`. Both got a real, business-level `401`
from that gate — strong evidence the same would happen for `start`, without
actually invoking `WorkflowStarter.Start` and creating a real Temporal run,
which the task explicitly ruled out.

**Why the webhook itself always returns `200` with an empty body on
failure**: these workflows have no error branch (by design, per the
README — "no `retryOnFail`... anywhere in this directory"), and n8n's
webhook trigger apparently still emits `200`/empty rather than `500` when
the workflow execution errors past the trigger node on this instance/version
combination. The **only** reliable signal is the execution log
(`GET /executions?workflowId=...` then `GET /executions/{id}?includeData=true`),
which is what every result above is drawn from — not the webhook's own HTTP
status, which would have falsely read as "success" for all 7 endpoints if
taken at face value. Recorded here because it is a trap for any future
"live" verification against this instance.

### 4a. `parser-activity-runtime` reachability — full evidence trail

1. Coolify app detail for `parser-activity-runtime`
   (`o11nxvzqwskxrqmtbvup7iet`): `fqdn: http://o11nxvzqwskxrqmtbvup7iet.100.91.190.107.sslip.io`,
   `ports_exposes: 8090`, **`ports_mappings: "8092:8090"`**. Coolify reports
   `status: running:healthy`.
2. Direct probe of the Coolify FQDN from this session (no tailnet route, but
   the FQDN is public DNS + a public Traefik listener): **every path 404s**,
   including the app's own `/healthz` (`modules/engine/runtimeapi/router.go:40-47`,
   definitely registered in the current source) — `404 page not found`,
   which is Go's stock `http.NotFoundHandler` text. Since `/healthz` is
   unconditionally registered on this exact mux, a 404 there — even though
   Coolify's own (in-container) health probe reports "healthy" — means the
   **external FQDN route does not reach this container's mux at all**, not
   that the binary is missing the route.
3. n8n → `http://100.91.190.107:8092/activities/select_parser_activity`:
   `ECONNREFUSED` ("service refused the connection — perhaps it is
   offline"), confirmed via n8n execution detail, `httpCode: ECONNREFUSED`.
4. n8n → `http://100.91.190.107:8090/activities/select_parser_activity`
   (the compose file's stated default, tested as a fallback): also
   `ECONNREFUSED`.
5. `parser-activity-runtime`'s Coolify env list has **no `BIND_IP`**
   variable set at the application level. `deploy/parser-activity-runtime.yaml`
   binds `"${BIND_IP:-127.0.0.1}:8090:8090"` — with no override, the
   container's published port is almost certainly bound to `127.0.0.1` on
   the host, which is consistent with every external-address probe above
   refusing the connection cleanly (a loopback-only bind, not a firewall
   drop, which usually times out rather than refusing).

**Conclusion: this is a genuine, unresolved blocker, not an n8n
binding/credential/URL problem.** `parser-activity-runtime` is not reachable
from n8n by any address constructible from current Coolify/deploy-yaml data:
not its own Coolify FQDN (Traefik route broken/absent), not `:8090`
(compose default, refused), not `:8092` (Coolify's actual published port,
also refused). The most likely fix is adding an explicit `BIND_IP` (matching
`universal-import-starter`'s pattern, i.e. `100.91.190.107`) to the
`parser-activity-runtime` Coolify app's environment and redeploying — but
that is an infrastructure/Coolify change outside this task's scope (n8n
workflow binding), and was not made.

## 5. What was bound (state as of this write)

All 7 workflows: **imported, credentials attached, URLs corrected,
activated.**

| Workflow | id | active |
|---|---|---|
| Universal Import - start | `7HDcx0GPDELB56J0` | true |
| Universal Import - decision | `abOE3dzoZo3yw26x` | true |
| Universal Import - select_parser_activity | `fvKS2gcsRUdEKUun` | true |
| Universal Import - preview | `nobMh2uO8eIBuH2p` | true |
| Universal Import - execute_parser_activity | `YQoFBykpZoDrU0n6` | true |
| Universal Import - assess_source_repair_activity | `6TMn03Jq8WSxt9iY` (newly imported) | true |
| Universal Import - resolve_source_repair_activity | `cu7y91jsOVfBBWJC` (newly imported) | true |

## 6. Remaining blockers (do not treat the pipeline as live)

1. **`parser-activity-runtime` is unreachable from n8n** (§4a). This directly
   reproduces the task's named symptom — `select_parser_activity` and
   `execute_parser_activity` cannot complete, so `UniversalImportWorkflow`
   still stalls at parser selection. Needs an infra fix (most likely
   `BIND_IP` on the Coolify app, or a working Traefik route for its FQDN)
   and a re-probe after.
2. **`universal-import-starter`'s tailnet-peer-IP authorization rejects
   n8n's calls** (§3, §4). `start`/`decision`/`preview` are reachable but
   not authorized. Either n8n's egress needs to present a `100.64.0.0/10`
   source IP to the starter (e.g. routing n8n's outbound calls to this
   specific host via the tailnet interface), or `authorizedTailnetPeer` needs
   a second accepted identity for n8n specifically. This is a design
   decision for the owner, not something I changed unilaterally.
3. **Worker → n8n direction unverified** (§2): whether
   `n8n-ddjgrmys36d9n8xwcwj0mml2:5678` actually resolves from the
   host-networked `universal-import-worker`/`universal-import-starter`
   containers was not tested (no shell access to that host in this
   session).
4. **`wf-assess-source-repair-activity.json` / `wf-resolve-source-repair-activity.json`
   are orphaned** (§1): bound and active, but the Go worker's repair
   Activities never call them. Either wire them in or note them as
   intentionally dormant — owner call.
5. `REFERENCE_STARTER_TOKEN` (§3) is dead config on the Coolify side; either
   remove it or wire it into `authorizedTailnetPeer` as an additional
   accepted credential — owner call, not changed here.

## 7. Process note on secret handling

Two redaction-regex bugs in this session printed real secret values into
this transcript (never into a git-tracked file):

- A `sed -E 's/^([A-Z_]+)\s*=.*/.../'` pattern against `~/.secrets/n8n-ovh2.env`
  used a character class missing digits, so `N8N_ENCRYPTION_KEY`,
  `N8N_MCP_SERVER_TOKEN`, and `N8N_API_KEY` (all containing `N8N` with the
  digit `8`) were not matched and printed in full.
- A Coolify `envs` dump redaction heuristic keyed on the substrings
  `TOKEN`/`AUTH`/`PASSWORD`/`KEY`/`SECRET` in the variable name missed
  `PLATFORM_DATABASE_URL`, which contains a live Postgres password, and
  printed it in full (three times, once per app queried).

Per this repository's own written policy (`CLAUDE.md`, amended 2026-08-12:
"transcript exposure is acceptable — GIT-TRACKED FILES are the only hard
line"), this is not treated as a rotation-triggering incident since nothing
reached a tracked file. All secret handling for the remainder of the session
used name/length-only reporting and value-blind Python (values read into
memory and used directly in HTTP calls or n8n credential payloads, never
echoed to stdout).

## 8. VERIFY LANE N3 — post-fix re-probe (2026-09-02, ~19:58–20:01 UTC)

> _Byline: Claude Code · Sonnet 5 · 2026-09-02._

Scope: re-probe all 7 webhooks after two claimed fixes (parser-activity-runtime
`BIND_IP` set, publishing on `100.91.190.107:8090`; starter's `withAuth` now
honors `PLATFORM_DEV_AUTH_BYPASS`), root-cause any remaining failures with
container-log evidence, and verify the reverse direction (worker →
n8n). No code changed, no workflow changed, no git commit. No real import was
started — `start` was deliberately probed with an incomplete payload exactly
as in §4, and `select`/`execute`/`assess`/`resolve` used synthetic
`probe://synthetic/...` refs that satisfy each workflow's own field-shape
validation but cannot resolve to real evidence.

**Method correction vs the original §4 probe:** the n8n-mcp tool's
`search_workflow_executions`/`get_workflow_execution` could not be used —
all 7 workflows report `"availableInMCP": false`, and the tool refuses with
`"Workflow is not available in MCP"`. Re-verified against n8n's own REST API
(`GET /executions`, `GET /executions/{id}?includeData=true`, key length 289,
from `~/.secrets/n8n-ovh2.env`) instead, which is what every result below is
drawn from — again never the webhook's own HTTP status (still `200`/empty on
every one of the 7 probes, confirming the §4 finding that this endpoint
lies about failure).

**Process note, same class of issue as §7:** the first execution-detail fetch
(`GET /executions/38?includeData=true`) returned the inbound webhook node's
captured request headers verbatim, which includes the real
`N8N_UNIVERSAL_IMPORT_WEBHOOK` bearer value — it printed to this transcript
and to a scratchpad file once before the redaction wrapper below was added.
The scratchpad file is outside this repository and was never git-tracked;
per this repo's amended secret-handling policy that is not a
rotation-triggering incident. Every fetch after that point ran through a
wrapper that redacts any `authorization`/`auth`/`bearer` key before printing
or saving.

### 8.1 Per-workflow results

| Workflow | Reached backend? | Downstream status / error (from n8n execution detail, not the webhook's own 200) |
|---|---|---|
| `select_parser_activity` | **No.** n8n admitted the request, validated it, and fired the outbound HTTP node — but the node itself failed. | `ECONNREFUSED`: *"The service refused the connection – perhaps it is offline"*, at `http://100.91.190.107:8092/activities/select_parser_activity` |
| `execute_parser_activity` | **No**, same shape | `ECONNREFUSED` at `http://100.91.190.107:8092/activities/execute_parser_activity` |
| `assess_source_repair_activity` | **No**, same shape | `ECONNREFUSED` at `http://100.91.190.107:8092/activities/assess_source_repair_activity` |
| `resolve_source_repair_activity` | **No**, same shape | `ECONNREFUSED` at `http://100.91.190.107:8092/activities/resolve_source_repair_activity` |
| `start` | Not exercised past n8n's own validation (deliberate — starting a real Temporal run was out of scope) | n8n's `Validate + Shape Start Request` Code node rejected the intentionally-incomplete probe body, as designed. No HTTP node ran. Starter hop not directly invoked; see `decision`/`preview` below for the same gate, now proven passable. |
| `decision` | **Yes.** Reached `universal-import-starter`, past `authorizedTailnetPeer`. | Real business-level Temporal error, not a 401: `"temporal: signal preview decision: workflow not found for ID: nonexistent-probe-n3verify-268d255ee2f3"` |
| `preview` | **Yes.** Reached `universal-import-starter`, past `authorizedTailnetPeer`. | Real business-level Temporal error, not a 401: `"temporal: query preview state: workflow not found for ID: nonexistent-probe-n3verify-05395263f0ef"` |

**Corroborating evidence — `universal-import-starter` container log**
(`docker logs`, timestamps UTC, on `ovh-files` 100.91.190.107):

```
2026/09/02 20:00:56 WARN UIW starter HTTP auth: PLATFORM_DEV_AUTH_BYPASS admitted a non-tailnet peer (D-125, D-127) -- remove this flag before go-live flag=PLATFORM_DEV_AUTH_BYPASS remote_addr=172.18.0.5:47128 method=POST path=/reference-import/nonexistent-probe-n3verify-268d255ee2f3/decision
2026/09/02 20:00:57 WARN UIW starter HTTP auth: PLATFORM_DEV_AUTH_BYPASS admitted a non-tailnet peer (D-125, D-127) -- remove this flag before go-live flag=PLATFORM_DEV_AUTH_BYPASS remote_addr=172.18.0.5:47138 method=GET path=/reference-import/nonexistent-probe-n3verify-05395263f0ef/preview
```

Timestamps and `nonexistent-probe-*` ids match the `decision`/`preview`
executions exactly (n8n execution 50 started `20:00:56.703Z`, execution 51
started `20:00:57.119Z`). `remote_addr=172.18.0.5` is n8n's container IP on
the shared `coolify` bridge network — a genuinely non-tailnet peer, so the
warning firing is direct proof the bypass is what admitted these calls, not
a real tailnet-peer match. No corresponding log line exists for `/start` in
this window — its absence is itself confirmation that `start`'s probe never
reached the starter, consistent with the n8n-side execution trace (no HTTP
node ran). **§3/§6-item-2 blocker is resolved**: `decision`/`preview`/(by
the same-gate argument) `start` are now authorized.

### 8.2 Root cause of the still-failing 4 (§4a is now the WRONG diagnosis)

§4a concluded `parser-activity-runtime` itself was unreachable
(loopback-only bind, no working route). That is **no longer true** — it was
fixed exactly as the task described. Live evidence, this session:

- `docker ps` on `ovh-files`: `parser-activity-runtime-o11nxvzqwskxrqmtbvup7iet-...` →
  `100.91.190.107:8090->8090/tcp`.
- `ss -ltnp` on the host: `LISTEN 100.91.190.107:8090` owned by `docker-proxy`.
- `curl http://100.91.190.107:8090/healthz` → `200 {"status":"ok"}`, both
  from this desktop session (itself tailnet-attached) and from `ovh-files`
  itself.
- `GET /applications/{uuid}` for `parser-activity-runtime` via the Coolify
  API still reports `ports_mappings: "8092:8090"` — **this field is stale
  relative to the live container** and was the source of the wrong port
  used when §2 picked `100.91.190.107:8092` as "confirmed against ... the
  live `ports_mappings`". It was not live; `docker ps`/`ss` on the host is
  ground truth, the Coolify API field is not.

**The actual, current root cause: the 4 parser-facing n8n HTTP Request nodes
still point at port `8092`, which nothing listens on** (`ss -ltnp` shows no
socket on 8092; `curl` to `:8092/healthz` returns `000`, i.e. refused, not a
timeout). Confirmed by reading the live node config via the n8n REST API
(`GET /workflows/{id}`), not the repo's exported JSON:

| Workflow | Live HTTP node URL (n8n API, 2026-09-02) |
|---|---|
| `select_parser_activity` | `http://100.91.190.107:8092/activities/select_parser_activity` |
| `execute_parser_activity` | `http://100.91.190.107:8092/activities/execute_parser_activity` |
| `assess_source_repair_activity` | `http://100.91.190.107:8092/activities/assess_source_repair_activity` |
| `resolve_source_repair_activity` | `http://100.91.190.107:8092/activities/resolve_source_repair_activity` |

**This is now purely an n8n workflow configuration problem, not an
infrastructure/network problem.** The infra fix (§6 item 1) landed and
works; the n8n side was bound against the wrong port before that fix shipped
and was never re-pointed at the corrected `:8090`. Fix (not applied in this
verify-only lane): update these 4 HTTP Request nodes' `url` field from
`:8092` to `:8090` and re-probe — no credential, auth, or network change
needed, `authorizedTailnetPeer`/bearer auth on the runtime side is untouched
by this.

### 8.3 Reverse direction — worker → n8n

**Verdict: still blocked, but the true address is now known and it is
same-host, not cross-tailnet.**

1. `modules/engine/uiwworker` reads `N8N_UNIVERSAL_IMPORT_BASE_URL`. Live
   Coolify value on `universal-import-worker` (confirmed via the Coolify API,
   `GET /applications/{uuid}/envs`): still
   `http://n8n-ddjgrmys36d9n8xwcwj0mml2:5678/webhook` — unchanged since §2.
2. **Correction to the task's own premise**: n8n does not run on
   `ion-control` (100.98.98.38). Its Coolify service (`casebible-n8n`,
   `ddjgrmys36d9n8xwcwj0mml2`) is deployed to server `100.91.190.107` —
   `ovh-files`, the **same host** as `universal-import-worker`,
   `universal-import-starter`, and `parser-activity-runtime` (confirmed via
   `GET /services/{uuid}` on the Coolify API, and independently via
   `docker ps` on `ovh-files` itself, which lists
   `n8n-ddjgrmys36d9n8xwcwj0mml2` running there). `100.98.98.38` is the
   **Coolify control-plane** host (where its API/UI lives, `ion-control`);
   the app it manages is deployed onto `ovh-files`. Worth fixing in memory/
   docs wherever "n8n runs on ion-control" is asserted, so this doesn't
   recur.
3. **DNS test, from inside the worker container** (`docker exec`, host
   network mode, no curl/wget in this image — used bash's `/dev/tcp` as the
   equivalent per the task's fallback intent):
   `getent hosts n8n-ddjgrmys36d9n8xwcwj0mml2` → exit 2, not found; a raw
   `/dev/tcp/n8n-ddjgrmys36d9n8xwcwj0mml2/5678` connect attempt →
   `Temporary failure in name resolution`. This reproduces exactly the
   failure mode the task predicted: a Coolify-internal Docker
   bridge-network service name (`n8n-ddjgrmys36d9n8xwcwj0mml2`, valid only
   on the `coolify`/service-specific bridge networks) does not resolve from
   a **host-network** container (confirmed `NetworkMode: host` via
   `docker inspect`), which uses the host's own resolver
   (`/etc/resolv.conf` → `127.0.0.53`, systemd-resolved) and has no view of
   Docker's embedded DNS for that name.
4. **The real reachable address, tested from the same worker container**:
   n8n's container publishes port 5678 directly on the host,
   `100.91.190.107:5678->5678/tcp` (confirmed via `docker ps`/`docker
   inspect` on `ovh-files`). A raw TCP connect from inside the worker
   container — `cat < /dev/null > /dev/tcp/100.91.190.107/5678` — returned
   **`CONNECT_OK`**.

**Conclusion**: the worker cannot reach n8n today because
`N8N_UNIVERSAL_IMPORT_BASE_URL` names a Docker-internal hostname that is
invisible to its host-network container — not because of any cross-host
tailnet problem (there isn't one; everything in this pipeline is
co-located on `ovh-files`). Fix (not applied in this verify-only lane):
set `N8N_UNIVERSAL_IMPORT_BASE_URL=http://100.91.190.107:5678/webhook` on
both `universal-import-worker` and `universal-import-starter`, then
redeploy both.

### 8.4 Is the bridge connected in both directions? No — precise remaining state

| Hop | State |
|---|---|
| n8n inbound webhook trigger + auth (all 7) | **Working.** Confirmed via execution detail on every probe. |
| n8n → `universal-import-starter` (`decision`/`preview`, and by the same-gate argument `start`) | **Working.** `PLATFORM_DEV_AUTH_BYPASS` admits n8n's non-tailnet egress; proven via a real Temporal business error past the gate, and via the starter's own log line correlated by timestamp + probe id. |
| n8n → `parser-activity-runtime` (`select`/`execute`/`assess`/`resolve`) | **Still blocked** — but the blocker moved. The runtime itself is now reachable (network fix confirmed working, §8.2). The 4 n8n HTTP nodes are configured against the old, wrong, non-listening port `8092` instead of the live `8090`. This is an n8n workflow edit, not an infra change — smallest possible remaining fix. |
| worker → n8n (`N8N_UNIVERSAL_IMPORT_BASE_URL`) | **Still blocked.** Configured Docker-internal hostname does not resolve from the host-networked worker/starter containers. n8n is co-located on `ovh-files` (100.91.190.107:5678, confirmed reachable by raw TCP from the worker container) — not on `ion-control` as previously assumed. Needs an env-var fix + redeploy on both `universal-import-worker` and `universal-import-starter`. |

**Bottom line: not fully connected in both directions yet.** Two small,
well-evidenced, disjoint fixes remain, neither infra-mysterious this time:

1. Repoint the 4 parser-facing n8n HTTP Request node URLs from `:8092` to
   `:8090`.
2. Repoint `N8N_UNIVERSAL_IMPORT_BASE_URL` (worker + starter) from
   `http://n8n-ddjgrmys36d9n8xwcwj0mml2:5678/webhook` to
   `http://100.91.190.107:5678/webhook`, then redeploy both apps.

Both are configuration-only (no code change), both have a concrete, already-
verified target value, and both should get one more live re-probe after
applying — the same synthetic-payload/execution-detail method used in §4 and
here, never the webhook's own HTTP status.


## §9 — Post-fix state (2026-09-02 ~16:10 ET, orchestrator)

Both blockers from §8 are fixed and live:

1. **n8n parser-node URLs repointed `:8092` → `:8090`** on all four
   parser-facing workflows (select_parser, execute_parser,
   assess_source_repair, resolve_source_repair) via the n8n REST API. The
   `:8092` value came from Coolify's stale `ports_mappings` field, not from the
   live container. All 7 Universal Import workflows confirmed `active=True`
   after the edit.
2. **`N8N_UNIVERSAL_IMPORT_BASE_URL` repointed** on universal-import-worker and
   universal-import-starter from the Coolify-internal container name
   `http://n8n-ddjgrmys36d9n8xwcwj0mml2:5678/webhook` (which does not resolve
   from a host-network container) to `http://100.91.190.107:5678/webhook`.
   Both apps redeployed. NOTE: Coolify keeps a separate `is_preview` duplicate
   of each env var; a naive read of the env list shows the stale preview value
   and looks like the PATCH failed — filter `is_preview=false`.

Ground-truth verification of the parser backend, from the desktop over tailnet:

```
GET  http://100.91.190.107:8090/healthz                        -> 200
POST http://100.91.190.107:8090/activities/select_parser_activity
     -> 401 {"error":"parser Activity authorization required"}
```

A 401 from the service's own handler proves the socket is live and the process
is answering — the ECONNREFUSED class of failure is gone. (401 is correct here:
the probe deliberately carried no PARSER_ACTIVITY_TOKEN.)

Starter direction was already proven in §8: `decision` and `preview` reached
real Temporal business errors ("workflow not found for ID: ...") and the
starter logged the matching per-request line
`PLATFORM_DEV_AUTH_BYPASS admitted a non-tailnet peer ... path=/reference-import/.../decision`.

**Not yet proven end to end:** a webhook probe through n8n whose HTTP node
actually fires — the synthetic payloads used so far are rejected by each
workflow's envelope Code node before the HTTP request is made, so "no
ECONNREFUSED" is necessary but not sufficient evidence. That proof belongs to
the rehearsal, where a real well-formed run exercises the node for real.
