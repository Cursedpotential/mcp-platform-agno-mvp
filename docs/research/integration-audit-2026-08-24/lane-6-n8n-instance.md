# Lane 6 — Live n8n Instance Audit (D-068 substrate)

> _Byline: lane-6 agent · Sonnet · 2026-08-24_

Evidence-only inventory. READ-ONLY tools used throughout (`docker inspect`, `docker exec` network
probes, n8n MCP `search_*`/`list_*`/`get_*` read tools). No workflow, agent, or credential was
created, published, executed, or mutated. Every claim below is either a direct tool/command result
(quoted or cited) or explicitly marked `UNKNOWN — not verified`.

---

## 1. Version + edition

**Command:** `ssh root@100.91.190.107 'docker ps -a --format ... | grep -i n8n'` then
`docker inspect n8n-ddjgrmys36d9n8xwcwj0mml2`

- Container name: `n8n-ddjgrmys36d9n8xwcwj0mml2` (Coolify-managed; `coolify.resourceName=casebible-n8n`,
  `coolify.projectName=case-bible`, `coolify.version=4.1.2`)
- Image: `docker.n8n.io/n8nio/n8n:2.36.6`
- Confirmed twice: `Config.Image` = `...:2.36.6` AND OCI label `org.opencontainers.image.version=2.36.6`
- Image build date (label `com.docker.dhi.created`): 2026-07-31
- Node.js runtime: `24.18.1-r0` (Alpine 3.24 base, `dhi/node` distroless-ish image)
- Companion containers on the same host (from `docker ps`): `sandbox-runner-1-ddjgrmys36d9n8xwcwj0mml2`
  and `sandbox-api-ddjgrmys36d9n8xwcwj0mml2` (both `ghcr.io/n8n-io/n8n-sandbox-service-*`, both
  `Up 6 hours`/`healthy`), plus `sandbox-certs-...` (Exited (0), one-shot init container).

**Verdict vs. the two version lines in the task:**
- **First-class Agents require ≥2.32.3** → **2.36.6 > 2.32.3. We are ON the correct side of this
  line.** Independently corroborated: `N8N_ENABLED_MODULES=instance-ai,agents` is set in the
  container env, `search_agents` returned `{"ok":true,"data":[],"count":0}` (module responds, zero
  agents exist yet), and `get_agent_builder_reference` returned the full Agent JSON config schema
  successfully (would 4xx/feature-gate if the module were absent).
- **n8n 3.0 lands ~Oct 2026 with breaking removals** → **2.36.6 is BEFORE 3.0.** No breaking-removal
  exposure from that release yet; this is a live version, not a pinned/stale one (image built
  2026-07-31, less than a month old at audit time).

## 2. Deployment mode

**Command:** same `docker inspect`, `.Config.Env` and `.HostConfig`/`.Mounts` sections.

| Setting | Value | Source |
|---|---|---|
| `EXECUTIONS_MODE` | **Not set in container env** → n8n defaults to `regular` (single-process, non-queue). No `QUEUE_BULL_REDIS_*` vars present either, consistent with regular mode. | env list (absence confirmed by full scan of all 40 `Env` entries) |
| `N8N_RESTRICT_FILE_ACCESS_TO` | **Not set** → no file-access restriction configured at the n8n-app level | env list |
| `N8N_COMMUNITY_PACKAGES_ENABLED` | `true` | env |
| `N8N_MCP_ACCESS_ENABLED` | `true` | env |
| `N8N_MCP_MANAGED_BY_ENV` | `true` | env |
| DB backend | **PostgreSQL** — `DB_TYPE=postgresdb`, host `fgz1n7useplhk0t91uk7k1aw` (internal service DNS, not sqlite), port `5432`, database `n8n`, user `n8n` | env |
| DB password | present, redacted — key `DB_POSTGRESDB_PASSWORD`, ~50 chars | env (value not reproduced here) |
| Webhook URL config | `N8N_WEBHOOK_URL=https://n8n.mitechconsult.com/`, `N8N_HOST=n8n.mitechconsult.com`, `N8N_PROTOCOL=https`, `N8N_EDITOR_BASE_URL=https://n8n.mitechconsult.com/`, `N8N_PROXY_HOPS=1`, `N8N_SECURE_COOKIE=true` | env |
| Instance-AI / Agents module | `N8N_ENABLED_MODULES=instance-ai,agents`; `N8N_INSTANCE_AI_MODEL=openai/nvidia/nemotron-3-super-120b-a12b`; `N8N_INSTANCE_AI_MODEL_URL=https://integrate.api.nvidia.com/v1`; `N8N_INSTANCE_AI_MODEL_API_KEY` present (redacted, key name `nvapi-...`, ~66 chars) | env |
| Sandbox (used by Agent custom-tool code execution) | `N8N_INSTANCE_AI_SANDBOX_ENABLED=true`, `N8N_INSTANCE_AI_SANDBOX_PROVIDER=n8n-sandbox`, `N8N_INSTANCE_AI_SANDBOX_IMAGE=ghcr.io/n8n-io/n8n-sandbox-service-sandbox:latest`, `N8N_SANDBOX_SERVICE_URL=http://sandbox-api:8080`; backed by the two live `sandbox-*` containers seen in `docker ps` | env + docker ps |
| Timezone | `GENERIC_TIMEZONE=America/Detroit` | env |
| Bind mounts / volumes | **One volume only**: named Docker volume `ddjgrmys36d9n8xwcwj0mml2_n8n-data` → `/home/node/.n8n` (`rw`). **No host bind mounts** (no `/srv/ingest`, no `/data`, nothing under `/data/coolify/...` mapped into the container). `.Mounts` array has exactly one entry, type `volume`, not `bind`. | `docker inspect` `.Mounts` / `.HostConfig.Binds` |
| Networks | Attached to two docker networks: `coolify` (172.18.0.5) and the Coolify per-service network `ddjgrmys36d9n8xwcwj0mml2` (172.19.0.2, DNS alias `n8n`) | `docker inspect` `.NetworkSettings.Networks` |
| Port publish | `100.91.190.107:5678 -> 5678/tcp` (host-bound to the tailnet IP, not `0.0.0.0`) | `docker inspect` `.HostConfig.PortBindings` |

**Note (out of scope for this READ-ONLY audit, flagged for the record only):** the data volume is a
named Docker volume, not a bind mount. The owner's global preference (memory: "Docker mapped-volumes
preference — always bind-mounts, never named volumes") is not met here. Not fixed; not asked to fix.

## 3. Existing content

**Commands:** `search_workflows` (limit 200), `search_agents` (limit 100), `list_credentials`
(limit 200), `list_workflow_tags`, `search_projects`, `search_folders`.

- **Workflows:** `search_workflows` → `{"data":[],"count":0}`. **Zero workflows exist.**
- **Agents (first-class):** `search_agents` → `{"ok":true,"data":[],"count":0}`. **Zero agents
  exist**, but the call succeeded (not a 404/feature-gate error), confirming the Agents module is
  live and queryable.
- **Credentials** (name + type only, no secret values requested or returned):
  1. `NVIDIA NIM` — type `nvidiaApi`, id `8rIx3JdfHxiCigW8`, home project = personal
     (`MATTHEW SALEM <matt.salem85@gmail.com>`)
  2. `Weaviate (ovh2 :8081)` — type `weaviateApi`, id `GqrgbHVa6M7gI4f8`, same personal project
  - `list_credentials` `count: 2`. No other credentials exist on the instance.
- **Folders:** `search_folders` (personal project) → `{"data":[],"count":0}`. No folders.
- **Projects:** `search_projects` → one project only: personal project for
  `MATTHEW SALEM <matt.salem85@gmail.com>` (id `TVeMXcVuQeUOr8jM`). `teamProjectsEnabled: false` —
  team/shared projects are not licensed on this instance.
- **Tags:** `list_workflow_tags` → `{"data":[],"count":0,"totalCount":0}`. No tags.

**Conclusion: this instance is greenfield.** Nothing built yet — no workflows, no agents, no
folders, no tags. Only infrastructure-level credentials (NVIDIA NIM, Weaviate) are pre-staged.

## 4. First-class Agents availability

- `get_agent_builder_reference` **works** — returned the full guide text and the complete
  `AgentJsonConfig` JSON Schema (name/model/credential/instructions required; tools, skills, tasks,
  memory, subAgents, providerTools, mcpServers, vectorStores, personalisation, config all supported
  per-schema). This confirms the Agent Builder API surface is live and functional on this instance,
  not just enabled-but-broken.
- `search_agents` **works** (see §3) — zero agents currently.
- **Model providers / connect services:** `list_n8n_connect_services` → `{"available":false}`.
  n8n Connect (managed/no-setup credentials for supported node+credential combos) is **not
  available** on this instance — UNKNOWN whether that's a licensing gate or a config gate; not
  investigated further (out of scope for read-only tool set available). This means any Agent model
  credential must be a manually-created credential (as the 2 existing ones are), not a
  connect-managed one.
- The instance-level default Agent model is pre-wired via env vars (§2): NVIDIA NIM-hosted
  `nvidia/nemotron-3-super-120b-a12b` via the OpenAI-compatible endpoint
  `https://integrate.api.nvidia.com/v1`. This is the "Instance AI" default model, separate from
  per-Agent model selection which an Agent config can override with its own `model`/`credential`.

## 5. Node availability (via `get_node_types` / `search_nodes`, ground truth, not guesses)

| Node | Present? | Type ID | Notes |
|---|---|---|---|
| Weaviate Vector Store | **Present** | `@n8n/n8n-nodes-langchain.vectorStoreWeaviate` v1.3 | modes: load / insert / retrieve / retrieve-as-tool / update |
| MultiQuery Retriever | **Present** | `@n8n/n8n-nodes-langchain.retrieverMultiQuery` v1 | |
| MCP Server Trigger | **Present** | `@n8n/n8n-nodes-langchain.mcpTrigger` v2.1 | trigger node, exposes n8n tools as an MCP server endpoint |
| MCP Client | **Present** | `@n8n/n8n-nodes-langchain.mcpClient` v1.1 (standalone) and `mcpClientTool` v1.4 (as Agent tool) | |
| Local File Trigger | **Present** | `n8n-nodes-base.localFileTrigger` v1 | Confirmed via direct `get_node_types` lookup (returned full TS type def: file/folder watch, chokidar options). Note: this node did **not** surface in fuzzy `search_nodes` text search under 2 different query phrasings — direct type lookup is the authoritative check here. |
| Extract From File | **Present** | `n8n-nodes-base.extractFromFile` v1.1 | operations: csv, html, ics, json, ods, pdf, rtf, text, xml, xls, xlsx, binaryToProperty |
| Code node — JS | **Present** | `n8n-nodes-base.code` v2 | |
| Code node — Python | **Present** | same node, same v2 | Node description literally: "Run custom JavaScript or Python code". Sandbox has no network access (fetch/axios/http all fail) per the node's own builder hint — this is a general n8n Code-node constraint, not specific to this instance. |
| Date & Time | **Present** | `n8n-nodes-base.dateTime` v2 | operations: addToDate, extractDate, formatDate, getCurrentDate, getTimeBetweenDates, roundDate, subtractFromDate |
| Compare Datasets | **Present** | `n8n-nodes-base.compareDatasets` v2.3 | |
| Execute Command | **Present** | `n8n-nodes-base.executeCommand` v1 | Confirmed via direct `get_node_types` lookup (returned TS type def: `command` string param, `executeOnce` bool). Same fuzzy-search gap as Local File Trigger — 3 different search phrasings ("executeCommand", "shell command", "run command terminal") did NOT surface it; direct type lookup is authoritative and it IS registered. **Enabled/disabled status:** no `NODES_EXCLUDE` / node-blocklist env var was found anywhere in the container's 40 `Env` entries, so nothing at the container-config level blocks it. Whether it's reachable from an Agent-as-tool context vs. only workflow context was not separately tested (no workflow/agent was created — out of scope for read-only audit). |

**Gap called out explicitly:** the `search_nodes` fuzzy search tool undersells node availability —
it missed 2 of 10 requested nodes that direct `get_node_types` lookups confirmed ARE present. Any
later build phase should verify node presence via `get_node_types` on the exact type ID, not rely
solely on `search_nodes` text matching, when a node doesn't show up in search results.

## 6. Reachability for the architecture

**Method:** `docker exec` into the running n8n container, using tools already present inside it
(`wget`, `nc` — both confirmed present via `which wget nc curl`; no `curl` binary in the image).
All probes are read-only (HTTP GET / TCP connect-and-close, no payload sent).

| Target | Result | Evidence |
|---|---|---|
| (a) Platform API `100.72.169.40:8000` | **REACHABLE** | `docker exec ... wget -qO- http://100.72.169.40:8000/` → `{"name":"AgentOS API","id":"mcp-forensic-platform","version":"1.0.0"}` (HTTP 200, full JSON body returned) |
| (b) Temporal `100.91.190.107:7233` | **REACHABLE** | `docker exec ... nc -zv -w5 100.91.190.107 7233` → `100.91.190.107 (100.91.190.107:7233) open` |
| (c) Weaviate `100.91.190.107:8081` | **REACHABLE** | `docker exec ... wget -S -O /dev/null http://100.91.190.107:8081/v1/.well-known/ready` → `HTTP/1.1 200 OK`, `Content-Length: 0` |

All three architecture-critical dependencies are network-reachable from inside the n8n container
right now, over plain TCP/HTTP, with no additional routing/firewall changes observed as necessary.
(Not tested: authenticated calls to any of the three — these were unauthenticated
connectivity/readiness probes only, per the read-only/no-mutation constraint.)

---

## 8-line summary

1. **Version:** n8n `2.36.6` (image built 2026-07-31) — past the `≥2.32.3` Agents threshold, before the `3.0` breaking-changes line. Both green.
2. **Mode:** Postgres-backed (`DB_TYPE=postgresdb`), `EXECUTIONS_MODE` unset → regular (non-queue), no file-access restriction set, community packages enabled, only one Docker **named volume** mounted (no host bind mounts).
3. **Existing content:** Fully greenfield — 0 workflows, 0 agents, 0 folders, 0 tags; only 2 credentials pre-staged (NVIDIA NIM, Weaviate ovh2:8081), 1 personal project (no team projects licensed).
4. **First-class Agents:** Module live and functional (`get_agent_builder_reference` + `search_agents` both respond correctly); instance default model is NVIDIA NIM `nemotron-3-super-120b-a12b`; n8n Connect (managed credentials) is unavailable on this instance.
5. **Node gaps:** None found among the 10 requested — Weaviate Vector Store, MultiQuery Retriever, MCP Server Trigger, MCP Client, Local File Trigger, Extract From File, Code (JS+Python), Date & Time, Compare Datasets, and Execute Command are all present, though 2 of them only surfaced via direct type lookup, not fuzzy search.
6. **Reachability:** Platform API (8000), Temporal (7233), and Weaviate (8081) are all confirmed network-reachable from inside the n8n container via read-only probes.
7. **Sandbox stack:** A separate live sandbox-runner + sandbox-api container pair backs Agent custom-tool code execution (`N8N_INSTANCE_AI_SANDBOX_ENABLED=true`).
8. **Bottom line:** the substrate is ready — current version, Agents feature live, all three downstream dependencies reachable, zero pre-existing content to work around or conflict with.
