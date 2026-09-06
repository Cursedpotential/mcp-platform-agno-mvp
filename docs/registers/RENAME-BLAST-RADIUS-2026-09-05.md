# Rename Blast-Radius Register — every surviving old name, all layers

> _Byline: Claude Code · Opus 5 · 2026-09-05_

**READ-ONLY inventory.** Nothing in this sweep was renamed, edited, moved, or deleted.
This register is the *blast radius*; `docs/NAMING.md` is the *intent* (old→new canon,
D-137..D-141). Where the two disagree, `docs/NAMING.md` rules the name and this file
rules the count.

**Snapshot:** repo HEAD `d7e8f81`, 216 modified / 4 renamed / 14 untracked files at
capture time. **Other agents were actively renaming inside `modules/engine`, `server`,
`deploy`, and `docs` while this ran** — two subagent readings of the same file
disagreed and were re-verified directly against the live tree (see §Verified
contradictions). Re-run the counts before acting on any number here.

**Owner's claim under test:** *"There's no way every single mention — every document,
file, script, folder, directory, docker compose, the URLs, the proxy, the Traefik tags,
Tailscale services — has been modified."*

**Verdict: the owner is right, with two exceptions in his favour.** The rename is
roughly one-third executed. What moved: the GitHub repo, the git remote, the Go module
path, some Go/deploy *filenames*. What did **not** move: every contract surface
(Postgres tables, n8n webhook paths, HTTP routes, TS types, env-var names, Temporal
queue), every piece of live infrastructure (34 Coolify apps, the `agno` docker network,
`/data/agno/`, `agentos-db`/`agentos-api`), and the local machine. The two layers the
owner named that are in fact **already clean** are **Traefik** (no router, service, or
Host rule carries an old product name) and **Tailscale services** (all five live
`svc:*` are component names, correct under the D-131/D-138 component rule).

---

## 0. Summary — hits and change class per layer

Change classes: **A** = repo file edit · **B** = live infra edit (Coolify / Traefik /
Tailscale / DNS / DB / docker) · **C** = external repo · **D** = local machine
(directories, shortcuts, scheduled tasks, memory stores) · **E** = keep (identifier
explicitly retained, or third-party).

| # | Layer | Files w/ hits | Total hits | A | B | C | D | E | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1a | `.github/**` | 1 | 4 | 2 | – | 1 | 1 | – | one path-keyed secrets filename |
| 1b | `.claude/**` | 35 | 6,946 | 3 | – | – | 2 | ~470 | almost all historical memory backups |
| 1c | `scripts/**` | 49 | 160 | ~25 | 8 | – | – | ~30 | `agentos-db`/`agentos-api`/`/data/agno` hardcoded |
| 1d | `sql/**` | 19 | 424 | ~30 | 25 live objects | – | – | ~365 | `agno_*` framework tables = E; `uiw_*` = A+B |
| 1e | `knowledge/**` | 4 | 597 | 0 | – | – | – | 597 | archived AI-chat transcripts — do not rewrite |
| 1f | `tests/**` | 49 | 262 | ~120 | – | – | – | ~110 | incl. the retired-name *negative* assertions |
| 1g | `deploy/**` | 63 | 505 | ~180 | ~120 | – | – | ~50 | the densest live-infra layer |
| 1h | `modules/**` | 165 | 1,976 | ~350 | ~40 | 5 repos | – | ~60 | contract surfaces all still old-named |
| 1i | `server/**` | 95 | 483 | ~20 | 8 | – | – | 54 + 61 vendored | 3 code spots carry the real weight |
| 1j | `docs/**` (excl. archive) | 425 | 5,464 | 5,464 | – | – | – | – | prose; 18 are infra-load-bearing |
| 1k | root files | 7 | ~60 | ~40 | – | 1 | – | ~18 | `pyproject.toml name = "platform-api"` |
| 1l | `evals/**` | 2 | 7 | 2 | – | – | – | 5 | |
| 2 | Live infrastructure | — | — | – | **~60** | – | – | – | 34 Coolify apps, 17 networks, DNS, PG |
| 3 | External repos | — | — | 8 | 1 | **6** | – | 4 | parent routers + 5 nested repos |
| 4 | Local machine | — | — | – | – | – | **11** | – | dir name, memory dir, collections |

**Totals (indicative, not exact — overlapping patterns):** ~16,900 raw matches across
~914 files. Class **A** ≈ 6,200 (mostly `docs/` prose). Class **B** ≈ 60 distinct live
identifiers. Class **C** = 6 external repos. Class **D** = 11 local artifacts.
Class **E** ≈ 1,700 (upstream `agno` library, `casebible-*`, archived transcripts).

---

## 1. Repo tree

### 1a. `.github/**`

| Identifier | Where | What it is | Would-be new name | Class | Blast / risk |
|---|---|---|---|---|---|
| `$HOME/.secrets/Agno-MCP-Platform.env` | `.github/workflows/validate.yml:158,159` | CI writes runtime secrets to a file **named after the directory** | `probata.env` | **A+D** | Renaming the dir orphans the secrets file; CI writes to the old name regardless. The file also exists locally at `~/.secrets/Agno-MCP-Platform.env` (7,160 bytes) — must move in lockstep |
| `Cursedpotential/sbv-forensic` | `.github/workflows/validate.yml:62,68` | submodule remote, in prose | keep (fork, D-131 rule 3) | **E** | — |
| `SUBMODULE_TOKEN` | `.github/workflows/validate.yml:67,75` | Actions repo secret | unchanged | **C** | Repo-scoped secret; survived the GitHub rename automatically (secrets are keyed to repo id, not name) |
| `INTEGRATION_SBV_*`, `SBV_*` (7 names) | `validate.yml:10,61-66,129-131,138-140,170-173` | CI secret + env names | keep | **E** | — |

**Clean:** no `mcp-platform-agno-mvp` anywhere in `.github/`. No `actions/checkout`
passes a `repository:` argument. `.github/copilot-instructions.md` has zero hits.
Only one workflow file exists.

### 1b. `.claude/**`

| Identifier | Where | What it is | Would-be new name | Class | Blast / risk |
|---|---|---|---|---|---|
| `guardian-naming-Agno-MCP-Platform-scripts.md` | `.claude/rules/` **filename** + `globs:` at `:3,:6` | auto-generated guardian rule; glob is `**/Agno-MCP-Platform/scripts/**` | `guardian-naming-probata-scripts.md` | **A+D** | **The rule silently stops matching** on a dir rename — no error, just no enforcement. A duplicate exists at `~/.claude/rules/` (class D) |
| `Agno-MCP-Platform` in permission strings | `.claude/settings.local.json` — 33 matching lines | Bash/Read allowlist entries with absolute paths + dead scratchpad session paths | n/a | **D** | Mostly already-dead session paths. `Read(//e/.../Agno-MCP-Platform/**)` grants stop matching after a rename → new permission prompts |
| `agentos-db` (+ Coolify container id `agentos-db-m4no8lart1mqjt67dyrbx3qf-004740442164`) | `.claude/settings.local.json:72,82` | container name inside allowed `ssh docker ps` commands | `probata-db` | **D** | Cosmetic |
| `mcp__agno-docs__*`, `mcp__claude_ai_agno__*` | `.claude/settings.json:14-17` | upstream Agno **docs** MCP tools | keep | **E** | Not our product name |
| `~/.claude/settings.local.json` | lines 47, 60, 65-72 | 12 matching lines; one hardcodes `...\Agno-MCP-Platform\.memsearch\memory` | n/a | **D** | |
| memory-store backups | `.claude/memories/*.json.bak-*` — 34 files, ~470 hits | historical JSON snapshots | do not rewrite | **E** | Live `project_memory.json` has only 2 hits |

**Answer to "path-keyed?":** yes, in exactly two functional places — the guardian rule
filename+glob, and `.github/workflows/validate.yml:158-159`. **No hook command is
keyed to an absolute path**: `.claude/settings.json` hooks are all relative
(`uv run python .claude/hooks/db_write_gate.py`) or `~/.claude/plugins/...`.

### 1c. `scripts/**`

| Identifier | Where (representative) | What it is | Would-be new name | Class | Blast / risk |
|---|---|---|---|---|---|
| `agentos-db` | `make_test_db.py:57-58`, `evidence_pipeline_report.py:174,496`, `backup_ovhdata_hot.sh:56,58`, `drain_context.py:19`, `ingest_context_chat.py:19`, `_wave1_validate_w15_isolation.py:83` (~12) | hardcoded compose-internal DB hostname | `probata-db` (NEEDS RULING R-3) | **A+B** | Several scripts **assert on the literal string as a sentinel** meaning "compose-internal, unreachable from desktop" — a rename silently disables those guards |
| `agentos-api` | `audit_dump.py:35,37`, `ingest_knowledge.py:8`, `surreal_inventory.py:3`, `generate_requirements.sh:28` (~10) | container name in `docker exec` / `docker ps --filter` | `probata-api` (NEEDS RULING R-3) | **A+B** | No Coolify app named `agentos-api` exists any more — these are already dead commands |
| `/data/agno/...` | `phase2_standup.sh:72-74`, `phase1b_coldcopy.sh:9,37-39`, `_matter_activation_preflight.py:199` (~10) | **live VPS filesystem root** | (NEEDS RULING R-2) | **B** | Renaming is a host migration with data movement, not a text edit |
| `SURREALDB_NS = "agno"` | `surreal_inventory.py:17` | SurrealDB namespace default | (NEEDS RULING R-9) | **A+B** | Namespace rename = data migration |
| `platform-api` / `platform_api` | `_matter_activation_preflight.py:199` + 5 (6/19) | service name + secret path `/run/secrets/platform-api-bearer` | (NEEDS RULING R-12) | **A+B** | |
| `Cursedpotential/probata` | `check_deploy_drift.py:63`, `phase2_standup.sh:37` | **already the NEW name** | — | done | Two naming generations coexist in `scripts/` |
| `casebible` (DB name, `casebible-catalog` skill, `casebible-coordination`) | `schema_report/build_reckoning.py:106-122`, `semantic_skill_cutover.py:26` | host DB + skill names | **KEEP** | **E** | `build_reckoning.py:122` already marks it *"owner ruling 2026-08-25: not this lane"* |
| `traceiq` (host DB name) | `schema_report/build_reckoning.py:106,114` | live PG database | **KEEP** (D-140) | **E** | |
| `agno` library / `agno_app` role | `verify_direct_providers.py`, `check_model.py`, `validate_0054_live.py` (~40) | upstream import + PG role | role = A; import = E | mixed | |

### 1d. `sql/**`

**Live schemas** (verified against PG `platform` on `100.91.190.107`): `ai`, `analysis`,
`archive`, `canon`, `context`, `duckdb`, `evidence`, `ext`, `ops`, `public`, `raw`,
`reference`, `registry`, `timeline`, `working`.

> ⚠ **Correction to the brief and to `docs/NAMING.md` §6:** there is **no `casebible` PG
> schema** in this database. `casebible` is (a) a separate **host database**, (b) four
> `ai.casebible_*` **tables**, and (c) a Weaviate/Semantica **namespace**. The KEEP
> intent stands; the wording should be corrected.

| Identifier | Where | What it is | Would-be new name | Class | Blast / risk |
|---|---|---|---|---|---|
| `ai.agno_*` — **16 live tables** (`agno_approvals`, `agno_traces`, `agno_spans`, `agno_learnings`, `agno_components`, `agno_component_links`, `agno_component_configs`, `agno_schedules`, `agno_schedule_runs`, `agno_service_accounts`, `agno_memories`, `agno_metrics`, `agno_sessions`, `agno_schema_versions`, `agno_eval_runs`, `agno_knowledge`) + ~85 `idx_agno_*` | `sql/bootstrap/schema_baseline_20260830.sql:121`, `sql/0002_schema.sql:18` (~365) | **created and owned by the `agno` library** | **KEEP** | **E** | Renaming breaks the framework. Only removable by removing agno itself |
| `context.uiw_*` — **9 live tables** (`uiw_preview_{attachment,binding,decision,event,message,participant,receipt,snapshot}`, `uiw_source_context_revision`) + triggers `forbid_uiw_preview_mutation`, `guard_uiw_source_context_revision`, `guard_uiw_preview_event_sequence`, `assert_uiw_preview_snapshot_complete`, view `v_uiw_scope_owner`, FKs `uiw_source_context_*_fk` | `sql/bootstrap/schema_baseline_20260830.sql:1800-1890`, `sql/0050`, `0053` (256 hits) | live tables in schema `context` | `proffer_*` (D-140) | **A+B** | **Highest-risk single item.** Live tables with data + append-only guard triggers. Requires a migration, not a rename; every Go `postgres/uiw_*.go` call site moves with it |
| migration **filenames** `0050_uiw_…`, `0051_uiw_…`, `0053_uiw_…`, `0066_uiw_…`, `0067_uiw_…` | `sql/` | already-applied migrations | leave | **E** | Never rename an applied migration file |
| `agno_app` | `sql/0029_pass_grants.sql:19`, `0033:45`, `0034:89` (15) | **live PG role** (confirmed in `pg_roles`) | `probata_app` (NEEDS RULING R-8) | **A+B** | `GRANT` statements must be re-issued; a rename mid-flight breaks running connections |
| `platform_api`, `platform_admin`, `platform_runtime`, `platform_worker`, `platform_reader` | `sql/0056:248-254`, `0062:53-54` | live PG roles | (NEEDS RULING R-8) | **A+B** | |
| `ai.casebible_*` — 4 tables | `sql/bootstrap/schema_baseline.sql:3216-3282` | evidence-content tables | **KEEP** (D-138/D-141) | **E** | |
| `acquisition_source = 'sbv'` | `sql/0010:30,180`, `0008:208`, `schema_baseline.sql:5024` | **a stored data value**, not an identifier | keep | **E** | Renaming would need a data migration of existing rows |
| `universal-import-worker`, `UniversalImportWorkflow` | `sql/0066:1`, `0036:1939,2,117` | names in comments | `proffer-worker`, `ProfferWorkflow` | **A** | |

### 1e. `knowledge/**` — 4 files, 597 hits, **class E**

| File | Hits | Note |
|---|---|---|
| `knowledge/platform/conversations/perplexity-framework-selection-agno-vs-haystack.txt` | 241 | **The only place `mcp-platform-agno-mvp` appears in the whole repo tree** (lines 2002-2365, 13×) |
| `knowledge/platform/docs/agno-mcp-platform-mvp-handoff-guide-v8.1.md` | 108 | **Filename itself carries the old name** |
| `knowledge/platform/conversations/perplexity-platform-followup-links.txt` | 109 | |
| `knowledge/platform/docs/v2-verification-and-repo-insights.md` | 18 | |

These are **verbatim archived AI-chat transcripts and historical handoffs**. Rewriting
them would falsify the record. Recommend: leave content untouched; the one open
question is whether the *filename* `agno-mcp-platform-mvp-handoff-guide-v8.1.md` is
renamed (a filename is not a quotation) — see R-18.

### 1f. `tests/**`

| Identifier | Where | What it is | Class | Blast / risk |
|---|---|---|---|---|
| **Retired-name negative assertions** | `test_platform_api_deploy_contract.py:49`, `test_workbench_platform_api_deploy_contract.py:34-35` — `for retired_surface in ("agentos-api","agentos-mcp","AgentOS","enable_mcp_server","agentos.mitechconsult.com")` | tests that **prove the old names are absent** | **E** | ⚠ **A naive global find-and-replace inverts these tests.** They are the rename's own regression net. Read before touching |
| `platform-api` / `platform_api` (~75) | `test_platform_api_deploy_contract.py`, `test_matter_activation_preflight.py`, `test_platform_api_host.py`, `test_workbench_platform_api_deploy_contract.py`, `test_opencode_ops_platform_cutover.py`, `test_ingest_staging_deploy_contract.py` | deploy-contract assertions on service name + URL `http://platform-api:8000/v1/runs` | **A** | Must change in lockstep with `deploy/exec.yaml` |
| `AGENTOS_TAILNET_AUTH_{TRUSTED_PROXY_CIDRS,BYPASS_ENABLED,ALLOWED_CIDRS}` | `test_tailnet_auth.py`, `test_platform_api_host.py` (8) | **live env var names** | **A+B** | Env-name change requires a Coolify redeploy per app (env values render at deploy) |
| `AGENTOS_API_TOKEN`, `AGENTOS_API_URL` | `test_matter_activation_preflight.py` (3) | env var names | **A+B** | |
| `agentos-db` | `test_db_id_middleware.py:19` — `DEFAULT = "agentos-db"` | registry-id fixture | **A** | Pairs with `server/core/session.py:70` |
| `universal-import` / `universal_import` (~35) | `test_universal_import_deploy_contract.py` (21), `test_uiw_repair_workflow_contract.py`, `test_sbv_demotion.py`, `test_n8n_parser_activity_workflows.py` | compose service name + host volume paths `/data/agno/volumes/universal-import/{parser-bundles,parser-artifacts,source-objects}` | **A+B** | |
| `uiw` (~12) | `test_universal_import_deploy_contract.py:96` (`/data/uiw/source-objects`), plus **test filenames** `test_0051_uiw_repair_activity_store.py`, `test_0048_context_fingerprint_uiw_repair.py` | mount paths + filenames | **A** | |
| `knowledge-workbench` (6) | `test_authentik_deploy_contract.py:133-161`, `test_workbench_platform_api_deploy_contract.py:15` | `manifest["services"]["knowledge-workbench"]` | **A+B** | |
| `agno` external network | `test_authentik_deploy_contract.py:171` — `compose["networks"]["agno"]["external"] is True` | **asserts the live docker network name** | **A+B** | |
| `casebible` (8) | `test_universal_import_deploy_contract.py:129-139`, `test_semantica_wiring.py:73` | `CASEBIBLE_R2_CONFIG_PATH`, namespace `"casebible"` | **E** | |

### 1g. `deploy/**` — 33 compose files, the densest live-infra layer

**Service names carrying an old name**

| Service | File:line | Would-be new name | Class |
|---|---|---|---|
| `agentos-db` | `compose.yaml:11`, `data-pg.yaml:27` | (NEEDS RULING R-3) | **A+B** |
| `agentos-api` | `compose.yaml:40` | (NEEDS RULING R-3) | **A+B** |
| `platform-api` | `exec.yaml:67` | (NEEDS RULING R-12) | **A+B** |
| `knowledge-workbench` | `workbench.yaml:42` | `workbench` (NEEDS RULING R-11) | **A+B** |
| `unified-operator-surface` | `unified-operator-surface.yaml:5` | retire (R-13) | **A+B** |
| `universal-import-starter` | **`proffer-starter.yaml:16`** | `proffer-starter` | **A+B** |
| `universal-import-worker` | **`proffer-worker.yaml:40`** | `proffer-worker` | **A+B** |
| `graphiti-mcp`, `graphiti-case-{mcp,hostfix,portkeyfix}`, `graphiti-{hostfix,portkeyfix}` | `compose.yaml:240`, `data-graphiti.yaml:45,107,154`, `data-graphiti-case.yaml:56,86,99` | retire (R-14) | **A+B** |
| `phase1-surreal-runner`, `data-surreal-phase1-t0-r1` | `compose.surreal-phase1.yaml:7,48` | retire (R-14) | **A+B** |

**`container_name:` values** — 40 total; old-named: `agentos-db` (`compose.yaml:18`,
`data-pg.yaml:32`), `agentos-api` (`compose.yaml:44`), `platform-api` (`exec.yaml:71`),
`knowledge-workbench` (`workbench.yaml:47`), `graphiti-mcp` ×2 (`compose.yaml:242`,
`data-graphiti.yaml:48`), `graphiti-case-*` ×3 (`data-graphiti-case.yaml:59,88,101`).

**Image names** (⭐ rename-critical, all locally built)

| Image | File:line | Class |
|---|---|---|
| ⭐ `agno-postgres:18-duckdb` | `compose.yaml:17`, `data-pg.yaml:31` — **also live in Coolify** as `ghcr.io/cursedpotential/agno-postgres:18-duckdb` (db `casebible-pg18`) and `@sha256:b1f6f82b…` (db `horizon-swift-scratch-pg`) | **A+B+C** |
| ⭐ `${IMAGE_NAME:-agentos}:${IMAGE_TAG:-latest}` | `compose.yaml:45` | **A** |
| ⭐ `agno-platform-tools:latest` | `compose.yaml:124`, `platform-tools.yaml:41` | **A** |
| ⭐ `agno-sandbox:latest` | `compose.yaml:143`, `sandbox.yaml:29` | **A** |
| ⭐ `agno-gateway:latest` | `compose.yaml:182`, `gateway.yaml:71` | **A** |
| ⭐ `agno-llm-probe:latest`, `agno-llm-probe-ui:latest` | `llm-probe.yaml:27`, `llm-probe-ui.yaml:20` | **A** |
| ⭐ `agno-knowledge-workbench:latest` | `workbench.yaml:46` | **A** |
| ⭐ `platform-unified-operator-surface:latest` | `unified-operator-surface.yaml:9` | **A** |
| ⭐ `${UNIVERSAL_IMPORT_STARTER_IMAGE:-platform-universal-import-starter:latest}` | `proffer-starter.yaml:20` | **A** |
| ⭐ `${UNIVERSAL_IMPORT_WORKER_IMAGE:-platform-universal-import-worker:latest}` | `proffer-worker.yaml:44` | **A** |
| `ghcr.io/cursedpotential/graphiti-mcp:0.29.3` | `data-graphiti-case.yaml:57` | **C** |

> 🚨 **LIVE BUILD BREAKAGE — verified 2026-09-05 by direct `ls`.**
> `deploy/proffer-starter.yaml:19` → `dockerfile: deploy/docker/universal-import-starter/Dockerfile`
> and `deploy/proffer-worker.yaml:43` → `dockerfile: deploy/docker/universal-import-worker/Dockerfile`,
> but only `deploy/docker/proffer-starter/` and `deploy/docker/proffer-worker/` exist —
> `deploy/docker/universal-import-*` is **gone**. Both Coolify apps
> (`universal-import-starter` `r1084s1lsm80fsv4ol9ocij0`, `universal-import-worker`
> `d24bb9eoo47qtw9eq1xc6u64`) **will fail their next build.** Half-executed rename;
> not caused by this read-only sweep.

**Traefik — the layer that is already CLEAN of product names**

| Kind | Name | File:line | Class |
|---|---|---|---|
| router | `authentik` | `authentik.yaml:108-113` | E |
| router | `authentik-workbench-outpost` | `authentik.yaml:116-121` | E |
| router / service | `contextforge` | `contextforge.yaml:91-96` | E |
| router / service | `workbench` | `workbench.yaml:152-158` | E (component name) |
| middleware | `workbench-authentik` | `workbench.yaml:159-161` | E |
| middleware (file provider) | `hsts` | `docker/coolify-proxy/dynamic/hsts.yaml:45` | E |
| router / service | `neo4j` — **commented out** | `data-neo4j.yaml:72-77` | E |

`Host(...)` rules — **4 live, none carrying a product name**:
`auth.int.mitechconsult.com` (`authentik.yaml:108`),
`workbench.int.mitechconsult.com` (`authentik.yaml:116`, `workbench.yaml:152`),
`mcp.mitechconsult.com` (`contextforge.yaml:91`). No `HostSNI`. Certresolver:
`letsencrypt` only. **Zero `sslip.io` in `deploy/**`** (sslip.io hostnames are
Coolify-generated, not in the repo). `traefik.docker.network=agno` at
`authentik.yaml:107` is the one Traefik label that carries an old name.

**Networks**

| Network | Declarations | Class | Risk |
|---|---|---|---|
| **`agno`** (`external: true`) | **17 files**: `authentik:141`, `compose.data-surreal:83`, `contextforge:99`, `data-graphiti:165`, `data-neo4j:84`, `data-pg:58`, `data-vector:182`, `exec:195`, `infisical:85`, `librechat-mongo:40`, `librechat:76`, `llm-probe-ui:37`, `llm-probe:57`, `nocodb:33`, `platform-tools:75`, `temporal/compose.temporal:96`, `workbench:166` | **A+B** | **The single widest-blast identifier.** A local bridge shared by every app; renaming = create new network, re-attach 17 apps, redeploy each. Asserted in `tests/test_authentik_deploy_contract.py:171` |
| `agentos` (project-local) | `compose.yaml:280`, 8 attachments | **A** | Local to one compose file |
| `graphiti`, `graphiti-case`, `phase1-surreal-t0-r1` | `data-graphiti:164`, `data-graphiti-case:109`, `compose.surreal-phase1:72` | **A+B** | Retirement candidates (R-14) |
| `coolify` (`external: true`) | `parser-activity-runtime.yaml:48` | E | |

**Volumes — `/data/agno/` host root, ~60 bind mounts across 20 compose files**

Representative: `authentik.yaml:60-83`, `compose.data-surreal.yaml:65`,
`compose.surreal-phase1.yaml:27`, `contextforge.yaml:76`,
`data-graphiti{,-case}.yaml:87-158`, `data-neo4j.yaml:63`, `data-pg.yaml:38-42`,
`data-vector.yaml:88,120`, `data-weaviate{,-native-v1}.yaml:43,24`,
`desktop.yaml:36-37`, `gateway.yaml:98`, `librechat{,-mongo}.yaml:29-69`,
`nocodb.yaml:23`, `parser-activity-runtime.yaml:37-38`, `platform-tools.yaml:48,54`,
`proffer-starter.yaml:41-45`, `proffer-worker.yaml:66-76`, `sandbox.yaml:35`,
`tool-gateway.yaml:80-85`, `workbench.yaml:123-132`. **Class B** — a rename is a
host-side data migration on two VPS boxes, not a text edit.

Nested old-named paths inside it — `/data/agno/volumes/universal-import/{source-objects,
parser-bundles,normalized-bundles,inventory-manifests}` and container-side `/data/uiw/*`
— appear in **three apps** (`proffer-starter`, `proffer-worker`,
`parser-activity-runtime`) plus `workbench.yaml:132`. ⚠ They **must move in lockstep**
or the `file://` locators fail closed (`proffer-worker.yaml:25-29`).

**Environment variable NAMES carrying an old name** (values shown only where non-secret)

| Var NAME | File:line | Non-secret value | Class |
|---|---|---|---|
| `AGENTOS_URL` | `compose.yaml:64` | `http://127.0.0.1:8000` | **A+B** |
| `AGNO_DEBUG` | `compose.yaml:62`, `exec.yaml:116` | `"True"` | **A** |
| `OS_SECURITY_KEY` | `compose.yaml:72` — **comment only** | — | **B** (R-6) |
| `SURREALDB_NS` | `exec.yaml:148` | **`agno`** | **A+B** |
| `DB_HOST` | `compose.yaml:65` | **`agentos-db`** | **A+B** |
| `PLATFORM_API_URL` | `workbench.yaml:64` | **`http://platform-api:8000`** | **A+B** |
| `PLATFORM_API_BEARER_SECRET_FILE` | `workbench.yaml:68` | `/run/secrets/platform-api-bearer` | **A+B** |
| `PLATFORM_TOOLS_BASE_URL` | `proffer-worker.yaml:63`, `tool-gateway.yaml:55` | required | **A** |
| `PLATFORM_DATABASE_URL{,_FILE}` | `parser-activity-runtime.yaml:26`, `proffer-*.yaml:27,50` | | **A** |
| `N8N_UNIVERSAL_IMPORT_{BASE_URL,AUTH_HEADER,AUTH_VALUE_FILE}` | `proffer-starter.yaml:35-37`, `proffer-worker.yaml:54-56` | secret file `/run/secrets/n8n-universal-import-auth` | **A+B** |
| `UNIVERSAL_IMPORT_UPLOAD_MAX_BYTES` | `proffer-starter.yaml:34` | | **A** |
| `UNIVERSAL_IMPORT_{STARTER,WORKER}_IMAGE` | `proffer-starter.yaml:20`, `proffer-worker.yaml:44` | | **A** |
| `UIW_{PREVIEW_CURSOR_KEY_FILE,SERVICE_TOKEN_FILE}` | `proffer-starter.yaml:38-39`, `workbench.yaml:73` | `/run/secrets/uiw-*` | **A+B** |
| `UIW_STARTER_URL` | `workbench.yaml:70` | `http://100.91.190.107:8091` | **A+B** |
| `TEMPORAL_TASK_QUEUE` | `proffer-starter.yaml:30`, `proffer-worker.yaml:53` | **`universal-import-v1`** | **A+B** |
| `CASEBIBLE_R2_CONFIG_PATH` | `tool-gateway.yaml:78`, `proffer-worker.yaml:64` | | **E** |

**Non-secret DB identifier values:** `POSTGRES_USER`/`DB_USER` default `ai`;
`POSTGRES_DB`/`DB_DATABASE` default **`platform`** (`compose.yaml:29-31,67-69`,
`data-pg.yaml:44-46`, `exec.yaml:128-130`) — **the PG database name is already clean**;
`agno`/`agentos` survive only as the *host alias*, the *role* `agno_app`, and the
*SurrealDB namespace*.

**Ports (downtime relevance):** `agentos-db` `5432:5432` and `agentos-api` `8000:8000`
bind `0.0.0.0` in `compose.yaml:21,51`; everything else binds `${BIND_IP}`.
`temporal/compose.temporal.yaml:66,86` hardcodes `100.91.190.107:7233/:8233`.
Collisions already present: `8090` is published by both `platform-tools` and
`parser-activity-runtime`; `4000` is published but dead in two files (LiteLLM retired,
ADR-0042). `network_mode: host` on `proffer-starter.yaml:25`, `proffer-worker.yaml:48`,
`tool-gateway.yaml:44`.

**Tailscale in `deploy/`:** `svc:tool-gateway` (`tool-gateway.yaml:69`),
`svc:workbench` (`tailscale/workbench-serve.hujson:5-17`, `tool-gateway.yaml:64`),
tag `tag:docker` (`tool-gateway.yaml:70`), tsnet state at
`/data/agno/volumes/tool-gateway/tsnet`. **No `*.ts.net` literal and no bare
`TS_AUTHKEY` in `deploy/`.**

### 1h. `modules/**`

**Already renamed (verified):** Go module path is
**`github.com/Cursedpotential/probata/engine`** (`modules/engine/go.mod:1`). Packages
`modules/engine/proffer/` and `modules/engine/profferworker/` exist. Binary
`cmd/proffer-worker/`. **No `uiw/`, `uiwworker/`, or `universal-import*/` directory
remains.**

**Not renamed — the contract surfaces**

| Identifier | Where | What it is | Would-be new name | Class | Blast / risk |
|---|---|---|---|---|---|
| n8n webhook paths `universal-import/{select-parser-activity,execute-parser-activity,chunk-preview}` | `engine/temporal/n8n_client.go:37,42`; `flowbinding.go:63`; tests `n8n_client_test.go:100,224`, `integration_test.go:97,101`, `flowbinding_test.go:77,117,203` | **live HTTP contract with n8n** | `proffer/...` | **A+B** | Renaming requires editing the **live n8n workflows on `n8n.mitechconsult.com`** in the same change or ingest breaks. The n8n workflow dir in-repo is already renamed to `deploy/docker/n8n/workflows/proffer/` |
| `context.uiw_*` table names in Go | `engine/postgres/uiw_schema_probe.go:42-53,100,194-215`; `uiw_preview_store.go:206-754` (~40 sites); `source_context_store.go:57-126`; `source_lifecycle_repository.go:84` | SQL identifiers in Go | `proffer_*` | **A+B** | Moves with the SQL migration (§1d) |
| Go **filenames** `postgres/uiw_preview_store{,_test}.go`, `postgres/uiw_schema_probe.go`, `runtimeapi/uiw_preview{,_test}.go` | `modules/engine/` | 5 stale filenames | `proffer_*` | **A** | Cosmetic |
| `/run/secrets/n8n-universal-import-auth` | `temporal/config.go:53`; `profferworker/config.go:106` | secret mount path | | **A+B** | Must match `deploy/*.yaml` and the host file under `/data/agno/secrets/n8n/` |
| Env `N8N_UNIVERSAL_IMPORT_*`, `PLATFORM_TOOLS_BASE_URL`, `PLATFORM_DATABASE_URL_FILE`, `PLATFORM_DEV_AUTH_BYPASS`, `PLATFORM_0050_TEST_DSN`, `CASEBIBLE_R2_CONFIG_PATH` | `engine/temporal/config.go`, `profferworker/config.go`, `runtimeapi`, `cmd/tool-gateway/main.go:174,200` | env var names | | **A+B** | Coolify renders env values at deploy — a name change needs a redeploy per app |
| HTTP routes `/api/uiw/{upload,sources,source-inspection,source-contexts,start}` | `workbench/web/src/lib/api-client.ts:593,627,631,659,667` | **live browser↔API contract** | `/api/proffer/*` | **A** | Front end + `workbench/api` router must change atomically |
| TS types `UIWDecisionResponse` … `UIWSourceContextReceipt` (14) | `workbench/web/src/lib/api-client.ts:82-94` | type names | `Proffer*` | **A** | |
| `package.json` `name: "knowledge-workbench-web"` | `workbench/web/package.json:2` | npm package name | (NEEDS RULING R-11) | **A** | |
| `package.json` `name: "unified-operator-surface"` | `workbench/design-mockups/unified-operator-surface/package.json:2` | mockup package | retire (R-13) | **A** | |
| FastAPI/OpenAPI title `"Knowledge Workbench API"` | `workbench/api/main.py:55` | **public API title** | (NEEDS RULING R-11) | **A** | Visible in `/docs` |
| MCP clientInfo `"knowledge-workbench"` | `workbench/api/repo/mcp_client.py:124` | MCP client identity | | **A+B** | Server-side logs/ACLs may key on it |
| `uiw_starter_url`, `uiw_service_token_file` settings; `UIW_STARTER_URL` in `workbench/api/.env` | `workbench/api/config/settings.py:39,41` | settings + **a real on-disk `.env`** | | **A+B** | ⚠ `modules/workbench/api/.env` is a live env file, not an example — confirm it is gitignored before any rename touches it |
| Workbench api/web stale **filenames** `app/runtime/uiw.py`, `app/service/uiw{,_streams}.py`, `app/types/uiw.py`, `tests/test_uiw_*.py`, `web/src/components/sbv/uiw-preview-client.tsx`, `web/smoke/uiw-repair-gate.contract.test.mjs` | | | | **A** | |
| `http://platform-api:8000` | `workbench/api/tests/test_promote_ai_chat_fence.py:102-251` (8) | docker-DNS service name in tests | | **A** | |
| `agno==2.8.7` + 7 `agno.*` imports | `workbench/api/requirements.txt:15`; `api/app/service/model_providers.py:14-20` | upstream library | keep | **E** | |
| `svc:workbench`, `svc:tool-gateway`, `tag:docker` | `engine/cmd/tool-gateway/main.go:211-216,282-287`; `workbench/api/app/runtime/auth.py:76` | tsnet service identities | keep (component names) | **E** | See R-10 |
| `https://workbench.tilapia-skilift.ts.net` | `workbench/web/README.md:82` | **only `*.ts.net` literal in `modules/`** | keep | **E** | |
| `casebible-sorted` / `casebible-raw` | `engine/runtimeapi/source_ref.go:17-65`; `profferworker/worker.go:133` | R2 bucket names | **KEEP** | **E** | |
| `modules/engine/decode/` | — | **does not exist yet** | D-131 target | — | SBV enters via 3 parallel paths: submodule `modules/forks/sbv`, `replace` in `go.mod:18`, and a committed `vendor/` snapshot (what Docker actually builds) |
| `modules/vendored/` | — | **empty leftover directory** | remove | **A** | Post-2026-09-01 restructure residue |

**Zero occurrences** of `agno`/`agentos`/`platform-api`/`knowledge-workbench` in
`modules/engine/**` Go source (excl. `vendor/`).

### 1i. `server/**`

| Identifier | Where | What it is | Would-be new name | Class | Blast / risk |
|---|---|---|---|---|---|
| `DB_ID = "agentos-db"` | **`server/core/session.py:70`** | **live agno registry key** | (NEEDS RULING R-3) | **A+B** | ⚠ Not cosmetic — `server/api/db_id_middleware.py` injects it as a query default into **every** agno route. Changing it is a live registry-key change |
| `db_id: agentos-db` ×7 | `server/api/config.yaml:72,80,86,92,98,104,110` | same key, in config | | **A+B** | Must move with the above |
| `SURREALDB_NS` default `"agno"` | `server/core/session.py:97` | SurrealDB namespace | (NEEDS RULING R-9) | **A+B** | Namespace rename = data migration |
| `id="agentos-surreal-legacy"` | `server/core/session.py:357` | legacy SurrealDb registry id | | **A** | |
| `server/ingest/**` (4 modules: `__init__`, `chunking`, `query`, `service`) | | the lane being renamed to `proffer` | `server/proffer/` | **A** | **Blast radius is small:** 9 external import sites in 4 production files (`server/api/ingest_routes.py:22,179,186`, `server/api/main.py:138`, `scripts/ingest_knowledge.py:71`) + 6 test files. Contained |
| `agentos-api` / `agentos-mcp` in runnable snippets | `server/agents/ingestion.py:3` (`docker exec agentos-api …`), `server/core/knowledge_handle.py:4,26`, `server/agents/tools/gateway_tools.py:35-36`, `server/analysis/semantica_wiring.py:106` | container names in comments/docstrings | | **A** | Already-dead commands (no such Coolify app) |
| `server/api/mcp_main.py` | `:6,7,9,12,38,39,40` | **retired-but-retained module**, densest `agentos-*` cluster | **delete, not rename** | **A** | Its own docstring says the `agentos-mcp` service block was removed. Separate decision |
| `server/temporal/knowledge_harness/agno_harness.py` | filename | names the retired framework | | **A** | |
| `namespace: "casebible"` | `server/analysis/semantica_wiring.py:91` | Weaviate/Semantica namespace | **KEEP** | **E** | |
| `agno` library imports — **54 lines / 25 files** | `agents/factory.py` (7), `core/settings.py` (8), `core/session.py` (5), `agents/providers.py` (3), `core/reranker.py` (3), + 20 files | upstream `agno` | keep | **E** | Only removable by removing the dependency |
| `server/vendored/**` | 61 lines / 21 files | chatminer + semantica, third-party | keep | **E** | |

**Already clean:** FastAPI title is `"Platform API"` (`server/api/main.py:202`) — no
`AgentOS`. `DB_DATABASE` default is `platform` (`server/core/url.py:91`). **No
`CORSMiddleware`, no `allow_origins`, no `agentos.mitechconsult.com`, no `os.agno.com`
in any `server/**` code path** (only comments). **`OS_SECURITY_KEY` appears nowhere in
`server/**`** — it is docs-only; the bearer boundary was re-homed.

**Hardcoded hosts:** `https://n8n.mitechconsult.com` (`server/temporal/n8n_activities.py:55`,
live default); `100.91.190.107` (`server/api/runtime_support.py:97`,
`server/analysis/semantica_wiring.py:54-55`, `graphiti_case_client.py:32`);
`ws://100.119.96.29:8000/rpc` (`server/core/session.py:94` — **stale, ovh-data**).

**Vector/graph names — all clean:** live Weaviate classes are `Platform_context`,
`Platform_knowledge`, `Platform_code_knowledge`, `Personal_history_knowledge`,
`Legal_knowledge`, `Evidence_knowledge`, `Relationship_timeline_knowledge`,
`EvidenceChunkV1`. Neo4j db `evidence`, user `platform_projector`. No old product name.

### 1j. `docs/**` — counts only

| Subdirectory | Files w/ match | Matches |
|---|---|---|
| `docs/planning` | 119 | 1,450 |
| `docs/awaiting-verification` | 59 | 999 |
| `docs/reviews` | 102 | 826 |
| `docs` (root files) | 40 | 554 |
| `docs/adr` | 47 | 221 |
| `docs/research` | 7 | 150 |
| `docs/plans` | 18 | 47 |
| `docs/schema` | 4 | 38 |
| `docs/CLAIMED_COMPLETE_LIKELY_LIES` | 6 | 27 |
| `docs/schemas` | 3 | 25 |
| `docs/design` | 2 | 23 |
| `docs/runbooks` | 2 | 13 |
| `docs/wiki` | 10 | 11 |
| `docs/blueprint` | 2 | 6 |
| `docs/registers` | 1 | 3 |
| `docs/reference` | 2 | 2 |
| `docs/reports`, `docs/recovered` | 1 each | 1 each |
| `docs/agent-memory`, `docs/visualizations` | 0 | 0 |
| **`docs/archive`** | **0** | **0** (one `README.md`, six empty subdirs) |
| **Total excl. archive** | **426** | **4,397** |

**Infra-load-bearing doc hits** (a doc asserting an identifier live infra depends on):

| # | file:line | Identifier asserted | Class |
|---|---|---|---|
| 1 | `docs/planning/architecture-directives/dns-and-domains.md:33` | `api.int.mitechconsult.com` A → `100.72.169.40` = agentos-api | B |
| 2 | `docs/planning/architecture-directives/dns-and-domains.md:16` | Cloudflare zone id for `mitechconsult.com` | B |
| 3 | `docs/planning/architecture-directives/dns-and-domains.md:34-40` | `chat.` `mcp.` `tools.` `desktop.` `gw.` `neo4j.` `milvus.` `.int.mitechconsult.com` → tailnet IPs | B |
| 4 | `docs/INFRASTRUCTURE.md:49` | Coolify server names **`ovh1-agno`**, `ovh2-worker` + server/SSH-key UUIDs | B |
| 5 | `docs/INFRASTRUCTURE.md:63` | subdomain plan lists `agno.` under `mitechconsult.com` | B |
| 6 | `docs/INFRASTRUCTURE.md:89`; `INFRASTRUCTURE.template.md:23-24,40,51,58,91` | secrets path `<repo>/Agno-MCP-Platform/.env`; "Agno box" | A+D |
| 7 | `docs/CHANGE-ORDER.md:662` | `~/.secrets/Agno-MCP-Platform.env` | D |
| 8 | `docs/CHANGE-ORDER.md:741` | live container `agentos-api-…-194330527059` | B |
| 9 | `docs/COORDINATION.md:98,275,311-312` | `id="agentos-db"`; `agentos-api :8000/health`; `agentos-api`/`agentos-mcp` service blocks | B |
| 10 | `docs/plans/WAVE1-W1.5-pre-mortem-2026-08-14.md:133-134,236` | `agentos-api` at `100.72.169.40:8000`; `/config` gated by **`OS_SECURITY_KEY`** | B |
| 11 | `docs/adr/0035-…:168` | `agentos-api :8000/health`; `agentos.mitechconsult.com/` returns 503 | B |
| 12 | `docs/planning/facade-collapse-plan.md:534,697,738` | **Traefik rule `agentos.mitechconsult.com` + `PathPrefix(/mcp)`, `mcp-auth`** | B |
| 13 | `docs/HANDOFF-2026-08-29-derived-document-ingest-wiring.md:754,106` | `SBV_BASE_URL=http://platform-tools:8085`; repo id `Agno-MCP-Platform` @ commit | A |
| 14 | `docs/create-new-agent.md:153,193,200-201,211`; `docs/extend-agent.md:18,84,103,126` | runnable `docker compose restart/logs/inspect/exec agentos-api`; `https://os.agno.com` | A |
| 15 | `docs/PROJECT_CANON.md:227` | `os.agno.com` via `agentos-control.cmd` (Desktop shortcut name) | D |
| 16 | `docs/registers/SETTLED.md:26` | Milvus `100.91.190.107:19530`, collection `agent_session_memory_nemotron3` | E |
| 17 | `docs/runbooks/N8N-PIPELINE-GOLIVE-RUNBOOK.md:73` | runnable `cd E:/…/Agno-MCP-Platform` | D |
| 18 | `docs/CONVENTIONS.md:132` | provenance literal `vendored: Agno-MCP-Platform-alpha/chatminer/…` — `:11` already marks it deliberately unchanged | E |

### 1k. Root files

| Identifier | Where | What it is | Would-be new name | Class |
|---|---|---|---|---|
| **`name = "platform-api"`** | `pyproject.toml:4` | **distribution / package name**; import package `platform_api`; produces `platform_api.egg-info/` | (NEEDS RULING R-12) | **A** |
| `modules/Legal-Workspace`, `modules/traceIQ` | `pyproject.toml:125,135,199` | ruff/mypy `exclude` + pytest `norecursedirs` | keep | **E** |
| `agno==2.8.7`, mypy override `"agno.*"` | `pyproject.toml:15,20,22,90,93,109,147`; `requirements.txt:3` | pinned upstream dep | keep | **E** |
| `AGENTOS_URL` | `example.env:62` (commented), `.env:31` | env var NAME | (NEEDS RULING R-5) | **A+B** |
| `DB_HOST=agentos-db` | `.env` | env value | (NEEDS RULING R-3) | **A+B** |
| `url = https://github.com/Cursedpotential/sbv-forensic` | `.gitmodules:3` | submodule remote | keep (fork) | **E** |
| `agno-docs` MCP server + `https://docs.agno.com/mcp` | `.mcp.json:3,5` | upstream docs server | keep | **E** |
| `agno-mcp-platform` / `Agno-MCP-Platform` prose | `README.md:11`, `CHANGELOG.md:3` | product name | already annotated `(renamed D-138)` in README | **A** |
| `agentos-api`, `agentos-db`, `agentos-mcp` prose | `AGENTS.md:324,328,332,333`; `CHANGELOG.md:98,102` | container/DB names | | **A** |
| `UIW` prose | `AGENTS.md:23,158,205`; `AGENT_MEMORY.md:23` | already annotated → `proffer` (D-140) | | **A** |

**Absent at root:** no `Makefile`, no `compose.yaml`, no `docker-compose.yml`.
`Dockerfile` exists with **zero** matches.

### 1l. `evals/**`

`evals/__main__.py:13,71` — prose "Connect your AgentOS at os.agno.com" (**A**);
`evals/cases.py:24,27` — **our own** function `server.core.get_agno_db` (**A**);
4 `agno.*` library imports (**E**).

---

## 2. Live infrastructure — probed read-only 2026-09-05, nothing changed

### 2a. Coolify — 34 applications, 3 services, 4 databases

Credentials read from `~/.secrets/coolify-ionos-api.env` with a tolerant regex (never
sourced). `COOLIFY_API` base + `COOLIFY_API_TOKEN` (length 50) — **values not printed.**

> 🚨 **33 of 34 applications still declare `git_repository: Cursedpotential/mcp-platform-agno-mvp`.**
> The GitHub repo *has* been renamed (verified: `gh api repos/Cursedpotential/mcp-platform-agno-mvp`
> → `Cursedpotential/probata`), so builds keep working **only via GitHub's rename
> redirect**. Every one of these 33 records is stale. The single exception is
> `legal-workspace`, which points at `Cursedpotential/Legal-Workspace`.

| App name | UUID | compose location | Status | Class |
|---|---|---|---|---|
| `knowledge-workbench` | `xjbuo6drbwjfby75lalk8bk7` | `/deploy/workbench.yaml` | running:healthy | **B** (R-11) |
| `universal-import-starter` | `r1084s1lsm80fsv4ol9ocij0` | `/deploy/universal-import-starter.yaml` ⚠ **file no longer exists** | running:healthy | **B** |
| `universal-import-worker` | `d24bb9eoo47qtw9eq1xc6u64` | `/deploy/universal-import-worker.yaml` ⚠ **file no longer exists** | running:unknown | **B** |
| `legal-workspace` | `gvghzivfmctev8dloetfssnj` | `/compose.yaml` (repo `Cursedpotential/Legal-Workspace`) | running:unknown | **B+C** |
| `exec-platform-tools` | `e1mshujml6bv8ldtoe8n7je0` | `/deploy/platform-tools.yaml` | running:healthy | **B** |
| `exec-tier` | `rz41wqhpjfh1rj796ixvjhfs` | `/deploy/exec.yaml` (service `platform-api`) | running:unknown | **B** |
| `data-pg-files` | `w10gg3an43jvry4y79n6sxi1` | `/deploy/data-pg.yaml` (service `agentos-db`) | running:healthy | **B** |
| `data-surreal-phase1-t0-r1` | `hastprr4a99tvpdi4c2k8i36` | `/deploy/compose.surreal-phase1.yaml` | running:healthy | **B** (R-14) |
| `data-graphiti-case` | `wi3vzgd4hekbddvqj8nkn33j` | `/deploy/data-graphiti-case.yaml` | running:unknown | **B** (R-14) |
| `data-graphiti-files` | `wvkwd9kq47a70del6nrnbgcb` | `/deploy/data-graphiti.yaml` | running:unknown | **B** (R-14) |
| `tool-gateway` | `ws67wgw1qxdgxo956p2k1jvi` | `/deploy/tool-gateway.yaml` | running:unknown | E (component) |
| `parser-activity-runtime` | `o11nxvzqwskxrqmtbvup7iet` | `/deploy/parser-activity-runtime.yaml` | running:healthy | E |
| `temporal-stack` | `llv5zt8phx1xf4devwqugk3y` | `/deploy/temporal/compose.temporal.yaml` | running:unknown | E |
| `temporal-worker` | `e4dkqfshveu77zhryllsb345` | `/docker-compose.yaml` (build_pack `dockerfile`) | running:unknown | E |
| `exec-contextforge` · `exec-desktop` · `exec-gateway` · `exec-sandbox` | `k272znxpa4gh6drmolut723w` · `t130q2xn4r1tux3huee9gal1` · `f29166r47gro6fjiq4d8ya92` · `mn2autapl223gmgcpjqy7def` | `/deploy/{contextforge,desktop,gateway,sandbox}.yaml` | mixed | E |
| `data-neo4j` · `data-vector` · `data-weaviate-files` · `data-weaviate-native-v1` | `ksbq02zynhdt63b8b9ba5cpv` · `d725i1io2o1dwlfjdz09lo87` · `o97r85b7nagwjuncs4oo07hs` · `v43tfq25o7i561n4lnc124p2` | `/deploy/data-*.yaml` | running | E |
| `coolify-mcp` · `infisical` · `portkey` · `llm-probe` · `llm-probe-ui` | | `/deploy/*.yaml` | running:healthy | E |
| `librechat` · `librechat-app` · `librechat-mongo` · `librechat-mongo-app` · `nocodb` · `nocodb-app` · `clone-of-nocodb-…` | 7 apps on branches `infra/librechat`, `infra/nocodb` | | 5 of 7 `exited:unhealthy` | E (dead) |

**No Coolify app is named `agentos-api`, `agentos-db`, or `agentos-mcp`** — those
service names survive only in `deploy/compose.yaml` (which no Coolify app points at)
and in docs/scripts. **No application fqdn uses `mitechconsult.com`** — every one is a
Coolify-generated `<uuid>.<tailnet-ip>.sslip.io` (`100.72.169.40` or `100.91.190.107`).

Services: `casebible-n8n` (`ddjgrmys36d9n8xwcwj0mml2`, **E**), `casebible-pg18`
(`l5lqi1c9z729w9li5oicrqm4`, exited, **E**),
`horizon-swift-scratch-pg-service-v2-20260816` (`yrhzg9ksyr8sjko1yg44qvgc`).

Databases: **`uiw-pg18-rehearsal-20260830`** (`c145wqnhagyhs7hcgkc4gp3e`,
running:healthy — **class B, old name in a live DB resource name**);
`casebible-pg18` (`fgz1n7useplhk0t91uk7k1aw`, image
**`ghcr.io/cursedpotential/agno-postgres:18-duckdb`** — **class B+C**);
`casebible-db` (`rmj36da884vt5nzueh28mlng`, `postgres:16`);
`horizon-swift-scratch-pg-20260816` (`v5sxg7kpiwxwrk6moooweogz`, exited, image
`ghcr.io/cursedpotential/agno-postgres@sha256:b1f6f82b…`).

### 2b. Traefik — **CLEAN**

Every router, service, middleware and `Host()` rule is listed in §1g. **None carries a
product name.** The only Traefik-adjacent old name is the label
`traefik.docker.network=agno` (`deploy/authentik.yaml:107`), which names the docker
network, not a Traefik object. One certresolver: `letsencrypt`.

### 2c. Tailscale — **CLEAN**

Live tailnet read via `tailscale status --json` and `tailscale service list`:

| Item | Value | Class |
|---|---|---|
| MagicDNS suffix | `tilapia-skilift.ts.net` | E |
| Nodes | `ion-control` `100.98.98.38` · `ovh-app` `100.72.169.40` · `ovh-data` `100.119.96.29` · `ovh-files` `100.91.190.107` · `tool-gateway-node` `100.126.220.36` · `cursed-ws-1` (this desktop) — all `tag:docker` except phones | E |
| **VIP Services (live)** | `svc:llm-probe` `100.112.203.206` · `svc:llm-probe-ui` `100.75.17.185` · `svc:n8n` `100.70.243.34` · `svc:tool-gateway` `100.110.251.133` · `svc:workbench` `100.105.91.39` (display name "Workbench") — all `tcp:443` http | **E** |
| ACL tag | `tag:docker` only | E |

**All five service names are component names**, correct under the D-131/D-138 component
rule. Nothing here needs renaming. Note the Coolify **server** name `ovh1-agno`
(`docs/INFRASTRUCTURE.md:49`) is a Coolify label, not a Tailscale one.

### 2d. DNS — public hostnames

| Hostname | Live check 2026-09-05 | Class |
|---|---|---|
| **`agentos.mitechconsult.com`** | resolves `40.160.5.19`; **HTTPS returns 503** (edge up, no backend) | **B** — a live DNS record for a service that no longer exists |
| `n8n.mitechconsult.com` | **HTTP 200** | E |
| `*.int.mitechconsult.com` (`workbench.` `auth.` `api.` `mcp.` `tools.` `gw.` `neo4j.` `milvus.`) | **do not resolve publicly** — split-horizon / tailnet-only | E |
| `mcp.` `coolify.` `chat.` `api.` `attu.` `milvus.` `llm.` `platform.` `windmill.` `.mitechconsult.com` | referenced in repo; not individually probed | B |
| `<uuid>.100.72.169.40.sslip.io` / `<uuid>.100.91.190.107.sslip.io` | Coolify-generated per app; **no product name — a repo rename does not touch them** | E |

DNS risk if `agentos.mitechconsult.com` is renamed: Cloudflare TTL, plus a **Traefik
certificate re-issue** for the new host (`letsencrypt` resolver), plus the rule at
`docs/planning/facade-collapse-plan.md:534`.

### 2e. PostgreSQL — live, `100.91.190.107:5432`, database `platform`

| Object kind | Values | Old-name carriers |
|---|---|---|
| **Databases** | `archive`, **`casebible`**, `infisical`, **`platform`**, `platform_baseline_test`, `platform_preburn_20260830`, `postgres`, `temporal`, `temporal_visibility`, **`traceiq`** | `casebible` = **E** (KEEP); `traceiq` = **E** (KEEP, D-140). **The main DB is `platform` — already clean** |
| **Schemas** | `ai`, `analysis`, `archive`, `canon`, `context`, `duckdb`, `evidence`, `ext`, `ops`, `public`, `raw`, `reference`, `registry`, `timeline`, `working` | **none carries an old name.** No `casebible` schema exists (see §1d correction) |
| **Roles** (28) | **`agno_app`**, `ai`, `analysis_writer`, `context_*` (7), `evidence_reader`, `horizon_reviewer`, `infisical`, `infisical_dbadmin`, `matt`, `pass_reader`, `pass_refresher`, **`platform_admin`**, **`platform_api`**, **`platform_app`**, **`platform_migrator`**, **`platform_reader`**, **`platform_runtime`**, **`platform_worker`**, `projection_refresher`, `temporal`, `timeline_*` (3) | `agno_app` = **A+B** (R-8); `platform_*` = **A+B** (R-8) |
| **Old-named tables** (25 live) | `ai.agno_*` ×16 → **E** (framework-owned) · `context.uiw_*` ×9 → **A+B** (D-140 → `proffer_*`) | |

`DB_HOST=agentos-db` is a **compose-internal alias only** — the real host is the
tailnet IP. Renaming the alias is a compose + env change, not a DNS change.

### 2f. Vector stores

| Store | Names | Class |
|---|---|---|
| **Weaviate** (`100.91.190.107:8081`) | `Platform_context`, `Platform_knowledge`, `Platform_code_knowledge`, `Personal_history_knowledge`, `Legal_knowledge`, `Evidence_knowledge`, `Relationship_timeline_knowledge`, `EvidenceChunkV1` | **E** — no class name carries an old product name |
| **Milvus** (`100.91.190.107:19530`) — memsearch only, service **UP** | 21 collections incl. `agent_session_memory_nemotron3` (memsearch backend, **E**), **`ms_agno_mcp_platform_9e350219_nemotron3_d2048`** and **`ms_agno_mcp_platform_9e350219`** (stale), `ms_legal_workspace_14d8fdc4`, `ms_casebible_21972a18`, `ms_the_platform_workspace_dee8325a`, `ms_ai_workspace_7325ff0b`, `ms_mitech_consult_site_4bd6000a`, plus per-worktree collections | **D** — see §4 |

> ⚠ **The memsearch collection name is derived from the checkout DIRECTORY name.**
> `ms_agno_mcp_platform_9e350219_nemotron3_d2048` (recorded in
> `<repo>/.memsearch/.collection`). Renaming the directory `Agno-MCP-Platform` →
> `probata` **re-keys memsearch to a new, empty collection** — the project's entire
> session-memory index silently goes dark until re-indexed, exactly the failure mode of
> the 2026-09-03 embedder incident. Plan the re-index in the same change.

---

## 3. External repos

| Repo | Current name | New product name | Repo renamed? | Referenced from | Class |
|---|---|---|---|---|---|
| **this repo** | `Cursedpotential/probata` | **Indicia Probata** / `probata` | ✅ **DONE** — `gh api repos/Cursedpotential/mcp-platform-agno-mvp` → `Cursedpotential/probata`; local `origin` already `https://github.com/Cursedpotential/probata.git`; `go.mod:1` = `github.com/Cursedpotential/probata/engine` | 33 stale Coolify records; `Projects/REPOSITORY_BOUNDARIES.md:38` | **C** done / **B** stale |
| `Cursedpotential/Legal-Workspace` | unchanged | **advocatio** | ❌ not renamed (D-138: "not renamed yet") | `modules/Legal-Workspace/` (nested, gitignored); `pyproject.toml:125,135,199`; Coolify app `legal-workspace`; `REPOSITORY_BOUNDARIES.md:39` | **E** for now |
| `Cursedpotential/TraceIQ` | unchanged | **vestigia** | ❌ explicitly **NOT** renamed (D-140, `NAMING.md` §6) | `modules/traceIQ/` (nested); `pyproject.toml:125,135,199`; PG database `traceiq`; `REPOSITORY_BOUNDARIES.md:41`; `traceiq-rebuild` at `:43` | **E** |
| `Cursedpotential/sbv-forensic` | unchanged | n/a — **fork**, keeps upstream name (D-131 rule 3) | ❌ correctly not renamed | `.gitmodules:3`; `.github/workflows/validate.yml:62`; remotes `sbv-fork`/`sbv-upstream`; `go.mod:11,18` (`github.com/lowcarbdev/sbv` + `replace ../forks/sbv`); vendored snapshot at `modules/engine/vendor/`; image `ghcr.io/lowcarbdev/sbv` at `server/tools/_sbv_client.py:4` | **E** |
| `Cursedpotential/milvus-coolify` | unchanged | n/a | ❌ | `REPOSITORY_BOUNDARIES.md:40`; parent routers | **E** |
| `Cursedpotential/mitech-consult-site` | unchanged | n/a | ❌ | `REPOSITORY_BOUNDARIES.md:42` | **E** |
| `Cursedpotential/ai-workspace` | parent workspace | n/a | ❌ | `git -C E:/AI_Workspace remote -v` | **E** |

**Parent workspace routers** (all outside this repo — commit separately from
`E:/AI_Workspace` with an explicit path allowlist):

| File | Matching lines | What must change | Class |
|---|---|---|---|
| `E:\AI_Workspace\Projects\REPOSITORY_BOUNDARIES.md` | **18** | `:38` canonical origin `https://github.com/Cursedpotential/mcp-platform-agno-mvp` → `.../probata`; the gitlink path row | **C** |
| `E:\AI_Workspace\Projects\AGENTS.md` | 4 | "Evidence Platform" rows naming `the-platform-workspace/Agno-MCP-Platform/` | **C** |
| `E:\AI_Workspace\Projects\AGENT_MEMORY.md` | 3 | same | **C** |
| `E:\AI_Workspace\Projects\the-platform-workspace\AGENTS.md` | 3 | Active-products table row | **C** |
| `E:\AI_Workspace\Projects\the-platform-workspace\AGENT_MEMORY.md` | 4 | vertical-load-order rows | **C** |
| `E:\AI_Workspace\AGENT_MEMORY.md` | 2 | `Projects/the-platform-workspace/Agno-MCP-Platform/` path | **C** |
| `E:\AI_Workspace\AGENTS.md`, and all three `CLAUDE.md` files | 0 | — | — |

---

## 4. Local machine

| # | Identifier | Where | What it is | Would-be new name | Class | Blast / risk |
|---|---|---|---|---|---|---|
| 1 | `Agno-MCP-Platform` | `E:\AI_Workspace\Projects\the-platform-workspace\Agno-MCP-Platform\` | **the checkout directory name** | `probata` | **D** | The root cause of items 2-8. `NAMING.md` §3 says the folder rename is *not* executed by the naming sweep. See R-16 |
| 2 | parent gitlink | `git -C E:\AI_Workspace ls-files -s Projects/the-platform-workspace/Agno-MCP-Platform` → `160000 ddd258dc…` | raw gitlink at the old path | | **C+D** | Renaming the dir requires a parent-repo commit moving the gitlink path — a separate parent-repo decision per `REPOSITORY_BOUNDARIES.md` |
| 3 | `C:\Users\matts\.claude\projects\E--AI-Workspace-Projects-the-platform-workspace-Agno-MCP-Platform\` | **4,041 files / 2,865 `.jsonl` / 1.6 GB** | **path-keyed Claude session + memory store**, incl. `memory/MEMORY.md` | new path key | **D** | ⚠ **A dir rename orphans 1.6 GB of session history and the canonical MEMORY.md.** Claude Code keys this directory by cwd; the new key gets an empty store. Must be moved deliberately. Three sibling worktree-keyed dirs exist too |
| 4 | `<repo>/.memsearch/.collection` = `ms_agno_mcp_platform_9e350219_nemotron3_d2048` | plus live Milvus collections `ms_agno_mcp_platform_9e350219{,_nemotron3_d2048}` | **memsearch index key derived from the dir name** | `ms_probata_<hash>` | **D+B** | Rename ⇒ new empty collection ⇒ **memsearch silently returns nothing.** Re-index in the same change and live-validate |
| 5 | `C:\Users\matts\.claude\rules\guardian-naming-Agno-MCP-Platform-scripts.md` | + the repo copy at `.claude/rules/` | guardian rule filename + `globs:` | | **D+A** | Rule stops matching silently |
| 6 | `C:\Users\matts\.claude\settings.local.json` | 12 matching lines (47, 60, 65-72) | permission allowlist with absolute repo paths + `.memsearch\memory` path | | **D** | Lost grants ⇒ new permission prompts |
| 7 | `<repo>/.claude/settings.local.json` | 33 matching lines | same, project-scoped | | **D** | |
| 8 | `~/.secrets/Agno-MCP-Platform.env` | 7,160 bytes, written by CI at `validate.yml:158` | **secrets file named after the directory** | `probata.env` | **D** | Must move in lockstep with the CI change |
| 9 | `C:\Users\matts\bin\agentos-control.cmd` + `agentos-tunnel-keeper.cmd` | both dated 2026-07-22 | launchers that SSH-tunnel `7777`/`8000` → `100.72.169.40:8000` and open `https://os.agno.com` | | **D** | ⚠ **Both are already dead** — no Coolify app serves `:8000` on ovh-app any more. Retire rather than rename |
| 10 | Desktop shortcut "AgentOS Control Plane" | **NOT PRESENT** — `C:\Users\matts\Desktop` has no matching entry | referenced by `docs/PROJECT_CANON.md:227` | | — | **Doc drift: the shortcut described in canon does not exist** |
| 11 | Scheduled task `AgentOSTunnel` | **NOT PRESENT** — verified via `Get-ScheduledTask`; the only non-Microsoft tasks are `RcloneR2Mounts`, PowerToys, OneDrive, SoftLanding | referenced in `agentos-tunnel-keeper.cmd` comments | | — | **Doc drift: the task the .cmd claims to run under was never created or was removed** |
| 12 | `~/.claude/skills/**` — 7 files | `graphiti-client/SKILL.md`, `llm-probe/SKILL.md`, `opencode-ops/{SKILL.md,scripts/oc.py,references/known-issues.md}`, `sessions/19252.json`, `sequential-react-ship-MUST_USE.html` | skills referencing `agentos-api`/old names | | **D** | `opencode-ops` drives the platform control plane — check it does not still call `agentos-api` |
| 13 | `~/.agents/skills/**` — 7 files | `graphiti-client/SKILL.md`, `env-inventory/{SKILL.md,*.ps1}`, `mineru/*`, `sequential-react-ship-MUST_USE.html` | same | | **D** | |
| 14 | `~/.memsearch/config.toml` | `collection = "agent_session_memory_nemotron3"` | global memsearch backend | **KEEP** | **E** | Not project-keyed; unaffected by a dir rename |
| 15 | `<repo>/.remember/` | `now.md`, `recent.md`, `archive.md`, `logs/` | in-repo memory; travels with the dir | | **E** | Path-relative, survives a rename |
| 16 | `<repo>/.cocoindex_code/{settings.yml, cocoindex.db, target_sqlite.db}` | **no old-name match in `settings.yml`**; `~/.cocoindex_code/global_settings.yml` also clean | `ccc` semantic index | | **E** | Index is path-relative; a rename likely triggers a re-index but nothing is name-keyed |
| 17 | Worktrees | `E:\AI_Workspace\.claude\worktrees\` — **empty**. Repo worktrees: main + `.claude/worktrees/affectionate-carson-fccaa9` (detached `f954467`) | | | **D** | One live worktree under the repo; it moves with the dir. Four stale worktree-keyed Claude memory dirs exist |

---

## 5. Needs an owner ruling

Identifiers where D-137..D-141 does **not** determine the new name. Each has a
recommendation and the live-change risk.

| # | Identifier | Where it lives | Recommended target | Risk of changing it live |
|---|---|---|---|---|
| **R-1** | **the `agno` docker network** (`external: true`, 17 compose files) | `deploy/**` ×17; `traefik.docker.network=agno`; asserted in `tests/test_authentik_deploy_contract.py:171` | **`probata`** — or **keep**: it is an infrastructure network, not a product surface | **Highest blast radius of any single rename.** Create the new network, re-attach 17 apps, redeploy each; any app missed loses service-name DNS to its peers. Recommend **keep** and revisit only during a planned data-tier maintenance window |
| **R-2** | **`/data/agno/` host root** (~60 bind mounts, 2 VPS boxes) | `deploy/**`, `scripts/**`, `tests/**` | **`/data/probata/`** — or **keep** | Host-side data migration: stop every app, `mv` on both boxes, edit ~60 mounts, redeploy all. Any mismatch = containers start with empty volumes and **silently lose state**. Recommend **keep**; it is invisible to users |
| **R-3** | **`agentos-db` / `agentos-api`** (service + container names, `DB_HOST`, `DB_ID`) | `deploy/compose.yaml:11,18,40,44,65`, `data-pg.yaml:27,32`; `server/core/session.py:70`; `server/api/config.yaml` ×7; ~22 scripts/tests | **`probata-db` / `probata-api`** | `DB_ID` is a **live agno registry key** injected into every agno route by `db_id_middleware.py` — not cosmetic. `DB_HOST` is a compose-internal alias (safe). No Coolify app carries these names, so the *deploy* risk is low; the *registry* risk is real. Change `DB_ID` in one deliberate step with a route smoke test |
| **R-4** | **`agentos.mitechconsult.com`** | DNS (live, `40.160.5.19`, returns **503**); Traefik rule in `docs/planning/facade-collapse-plan.md:534`; `tests/*deploy_contract.py:49` asserts its **absence** | **Retire the DNS record** rather than rename it — the service behind it no longer exists in Coolify | Cloudflare TTL + Let's Encrypt cert re-issue if a replacement host is introduced. Retiring is near-zero risk; confirm nothing external bookmarks it |
| **R-5** | **`AGENTOS_*` env var names** (`AGENTOS_URL`, `AGENTOS_TAILNET_AUTH_{TRUSTED_PROXY_CIDRS,BYPASS_ENABLED,ALLOWED_CIDRS}`, `AGENTOS_API_{TOKEN,URL}`) | `deploy/compose.yaml:64`; `.env:31`; `example.env:62`; `tests/test_tailnet_auth.py`, `test_matter_activation_preflight.py` | **`PROBATA_*`** — or **`PLATFORM_*`** to match the existing majority prefix | **Coolify renders env values into the materialized compose at deploy** — a name change does NOT reach running containers until a redeploy of every consuming app. Rename reader + writer + Coolify var in one change, then redeploy |
| **R-6** | **`OS_SECURITY_KEY`** | docs only (`WAVE1-W1.5-pre-mortem:236`, `adr/0035:168`); a warning comment at `deploy/compose.yaml:72`; **zero occurrences in `server/**`** | **Retire the name** — the bearer boundary was already re-homed | Near-zero: it is no longer read by code. Confirm no Coolify app still sets it before removing the docs references |
| **R-7** | **PG database name** | live DB is **`platform`** (`server/core/url.py:91`, `deploy/*.yaml`) | **No change needed** — it never carried the old name | n/a. What *does* need a ruling is the **role** `agno_app` (R-8) |
| **R-8** | **PG roles `agno_app` and `platform_*`** (`platform_admin`, `platform_api`, `platform_app`, `platform_migrator`, `platform_reader`, `platform_runtime`, `platform_worker`) | live `pg_roles`; `sql/0029:19`, `0033:45`, `0034:89`, `0056:248-254`, `0062:53-54` | `agno_app` → **`probata_app`**; leave `platform_*` (generic, not a product name) | `ALTER ROLE … RENAME` invalidates the role's password and **breaks live connections using it**. Do it in a maintenance window with a coordinated app redeploy |
| **R-9** | **`SURREALDB_NS = "agno"`** | `server/core/session.py:97`; `deploy/exec.yaml:148`; `scripts/surreal_inventory.py:17` | **`probata`** — or `indagatio` if the namespace follows the analysis engine (D-139) | A SurrealDB namespace rename is a **data migration**, not a config change. The legacy Surreal instance is parked (D-073/D-080) so risk is currently low — but decide the *target* before `indagatio` splits out, or it will be migrated twice |
| **R-10** | **`svc:workbench`** (Tailscale VIP Service, live, `100.105.91.39`) | `deploy/tailscale/workbench-serve.hujson:5-17`; `engine/cmd/tool-gateway/main.go:213`; `workbench/api/app/runtime/auth.py:76` | **KEEP** — `workbench` is a component name, correct under D-131/D-138 | If renamed anyway: a Tailscale Service rename is a **new identity** — new VIP address, ACL grants re-issued, MagicDNS name changes, every client URL breaks, and the Serve config must be re-advertised. Strongly recommend keep. Same for `svc:tool-gateway` |
| **R-11** | **`knowledge-workbench`** (Coolify app `xjbuo6drbwjfby75lalk8bk7`, compose service + container name, image `agno-knowledge-workbench`, npm `knowledge-workbench-web`, FastAPI title "Knowledge Workbench API", MCP clientInfo) | `deploy/workbench.yaml:42,46,47`; `modules/workbench/web/package.json:2`; `api/main.py:55`; `api/repo/mcp_client.py:124`; `tests/test_authentik_deploy_contract.py:133-161` | **`workbench`** (component rule — drop the `knowledge-` prefix and the `agno-` image prefix) | Coolify app rename is a UI/API field change (low risk). The **Traefik router/service are already named `workbench`**, so no cert or Host change. Container rename = one redeploy. npm name + API title are cosmetic |
| **R-12** | **`platform-api`** (pyproject dist name, compose service `exec.yaml:67`, container name, `PLATFORM_API_URL=http://platform-api:8000`, secret `/run/secrets/platform-api-bearer`, PG role, ~75 test assertions) | `pyproject.toml:4`; `deploy/exec.yaml:67,71`; `workbench.yaml:64,68`; `tests/*` | **KEEP** — `platform-api` is a functional component name, not a product name; or **`probata-api`** if R-3 renames the API | If renamed: docker service-name DNS breaks for `workbench` until both redeploy together; the secret file path must move on the host; ~75 test assertions change |
| **R-13** | **`unified-operator-surface`** (compose service, image, npm package) | `deploy/unified-operator-surface.yaml`; `modules/workbench/design-mockups/unified-operator-surface/`; `docs/design/0061-unified-operator-surface/` | **Retire** — D-138 lists it as an open retirement item; it is a design mockup | No live Coolify app of that name was found. Retiring is low risk; confirm nothing depends on host port `8020` |
| **R-14** | **`graphiti*` and `phase1-surreal*` compose files/apps** (9 services, 3 live Coolify apps) | `deploy/{compose,data-graphiti,data-graphiti-case,compose.surreal-phase1}.yaml`; apps `data-graphiti-case`, `data-graphiti-files`, `data-surreal-phase1-t0-r1` | **Retire** — D-070 retired Graphiti; D-138 lists these as an open item | All three apps are `running`. Stopping them frees ovh-files resources; confirm no consumer first (`server/analysis/graphiti_case_client.py:32` still has a live default URL) |
| **R-15** | **Temporal task queue `universal-import-v1`** | `deploy/proffer-starter.yaml:30`, `proffer-worker.yaml:53` — **verified live default** | **`proffer-v1`** (D-140 already rules this name; `NAMING.md` §2 states it) | ⚠ A task-queue rename is a **cutover, not an edit**: workflows in flight on the old queue are orphaned. Drain the queue, redeploy starter + worker together. This one is *ruled* — listed here because the execution has a real failure mode |
| **R-16** | **the checkout directory name `Agno-MCP-Platform`** | filesystem; parent gitlink; 1.6 GB Claude memory dir; memsearch collection; guardian rule; `~/.secrets/*.env`; permission allowlists | **`probata`** | ⚠ **Do not rename the directory casually.** It re-keys the Claude session store (1.6 GB orphaned), re-keys memsearch to an empty collection, breaks a guardian rule silently, orphans a secrets file, and needs a parent-repo gitlink commit. `NAMING.md` §3 already defers this. Sequence it as its own change with the memory + memsearch moves in the same step |
| **R-17** | **`agno-*` locally-built image names** (`agno-postgres`, `agno-platform-tools`, `agno-sandbox`, `agno-gateway`, `agno-llm-probe{,-ui}`, `agno-knowledge-workbench`) — one is published as `ghcr.io/cursedpotential/agno-postgres` and consumed **by two live Coolify databases** | `deploy/**`; Coolify DBs `casebible-pg18`, `horizon-swift-scratch-pg` | **`probata-*`** | Local image names are free to rename. **`ghcr.io/cursedpotential/agno-postgres` is not** — two live databases pull it (one by digest). Publish under the new name, repoint, verify, then deprecate the old tag. Never delete the old package while a digest-pinned DB references it |
| **R-18** | **The `knowledge/` archived-transcript filename** `agno-mcp-platform-mvp-handoff-guide-v8.1.md` | `knowledge/platform/docs/` | **Rename the file, never the contents** | Zero infra risk. The question is purely whether a historical artifact's *filename* is part of the record |

---

## 6. Verified contradictions and drift found during this sweep

1. **Task queue.** Two subagents disagreed. Re-read directly: `deploy/proffer-starter.yaml:30`
   and `proffer-worker.yaml:53` both read
   `TEMPORAL_TASK_QUEUE: ${TEMPORAL_TASK_QUEUE:-universal-import-v1}`.
   The string `proffer-v1` (ruled in D-140 / `NAMING.md` §2) **does not exist anywhere
   in the repo.**
2. **Broken build path.** Verified by `ls`: `deploy/proffer-{starter,worker}.yaml` point at
   `deploy/docker/universal-import-{starter,worker}/Dockerfile`, which no longer exist —
   only `deploy/docker/proffer-{starter,worker}/` do. **Two live Coolify apps will fail
   their next build.**
3. **Coolify staleness.** 33 of 34 apps still record the pre-rename GitHub repo; builds
   survive only on GitHub's rename redirect.
4. **`NAMING.md` §6 inaccuracy.** It reserves "the `casebible` PostgreSQL **schema**".
   No such schema exists — `casebible` is a *database*, an `ai.casebible_*` table prefix,
   and a Weaviate namespace. The KEEP intent stands; the wording should be corrected.
5. **Canon drift.** `docs/PROJECT_CANON.md:227` describes a Desktop shortcut "AgentOS
   Control Plane" and `agentos-tunnel-keeper.cmd` describes a scheduled task
   `AgentOSTunnel`. **Neither exists** (verified). Both launchers point at a service
   Coolify no longer runs.
6. **`agentos.mitechconsult.com` is live DNS with no backend** — resolves, returns 503.

---

## 7. Method and limits

- Case-insensitive ripgrep per top-level directory (repo-wide grep times out on this
  tree), excluding `.venv`, `node_modules`, `vendor`, `.git`, `**/__pycache__`,
  `docs/archive`, `*.lock`.
- Live probes, **all read-only**: Coolify REST `GET /applications|/services|/databases`;
  PostgreSQL `pg_database` / `pg_namespace` / `pg_roles` / `information_schema.tables`;
  Weaviate `GET /v1/schema`; Milvus `POST /v2/vectordb/collections/list`;
  `tailscale status --json` + `tailscale service list`; `nslookup` + `curl`;
  `gh api repos/...`; `git remote -v`; `Get-ScheduledTask`.
- Secrets were parsed with a tolerant `^\s*([A-Za-z_]+)\s*=\s*(.+?)\s*$` regex, never
  sourced. **No secret value appears in this register** — only names and lengths.
- **Counts are a snapshot.** Other agents were renaming in `modules/engine`, `server`,
  `deploy`, and `docs` during the sweep; two subagent readings of the same file already
  disagreed. Re-run before acting.
- Not covered: the interiors of the five nested gitignored repos (`modules/forks/sbv`,
  `modules/forks/timesketch`, `modules/custom`, `modules/Legal-Workspace`,
  `modules/traceIQ`) — each is its own commit root and needs its own sweep.
