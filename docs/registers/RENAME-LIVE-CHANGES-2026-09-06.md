# Rename — every LIVE change made outside git (register)

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Companion to `RENAME-BLAST-RADIUS-2026-09-05.md`
> and `docs/NAMING.md` (D-137..D-142). Written for the ingest session's reconciliation:
> reconcile against THIS list, not guesses. Updated as each live step lands._

Status legend: **DONE** (verified live) · **PENDING-OWNER** (classifier refused my write; owner runs it) ·
**NOT DONE** (deliberately left) · **AFTER PUSH** (sequenced behind the git push).

## 1. Git / GitHub

| Item | Old | New | Status |
|---|---|---|---|
| GitHub repository | `Cursedpotential/mcp-platform-agno-mvp` | `Cursedpotential/probata` (GitHub redirect from old name active) | DONE 2026-09-05 |
| Local `origin` remote | old URL | `https://github.com/Cursedpotential/probata.git` | DONE |
| Commits on `main`, local, **not yet pushed** at time of writing | — | `d7e8f81` (D-142 + swept pure renames), `34f8d8d` engine, `b50d828` server, `01dfaa2` docs, `48ff9f3` deploy/engine-contract/workbench/tests/gate | push is AFTER the Coolify repoint (§2), otherwise the next auto-build fails |

## 2. Coolify (control plane on IONOS) — PENDING-OWNER

The classifier refused the PATCH/env calls from this session; the exact commands are in the chat handoff
(scratchpad `coolify_rename.py`). Nothing below has landed yet as of 09:55 EDT; re-verify with `show`.

| App uuid | Field | Old | New |
|---|---|---|---|
| `d24bb9eoo47qtw9eq1xc6u64` | name | `universal-import-worker` | `proffer-worker` |
| 〃 | docker_compose_location | `/deploy/universal-import-worker.yaml` | `/deploy/proffer-worker.yaml` |
| 〃 | watch_paths | `modules/engine/**`, `deploy/docker/universal-import-worker/**`, `deploy/universal-import-worker.yaml` | `modules/engine/**`, `deploy/docker/proffer-worker/**`, `deploy/proffer-worker.yaml` |
| 〃 | env keys | `N8N_UNIVERSAL_IMPORT_BASE_URL/_AUTH_HEADER/_AUTH_VALUE`, `UIW_SOURCE_OBJECT_DIR`, `UIW_PARSER_BUNDLE_DIR`, `UIW_NORMALIZED_BUNDLE_DIR`, `UIW_INVENTORY_MANIFEST_DIR` | `N8N_PROFFER_BASE_URL/_AUTH_HEADER/_AUTH_VALUE`, `PROFFER_SOURCE_OBJECT_DIR`, `PROFFER_PARSER_BUNDLE_DIR`, `PROFFER_NORMALIZED_BUNDLE_DIR`, `PROFFER_INVENTORY_MANIFEST_DIR` (values copied verbatim) |
| `r1084s1lsm80fsv4ol9ocij0` | name | `universal-import-starter` | `proffer-starter` |
| 〃 | docker_compose_location | `/deploy/universal-import-starter.yaml` | `/deploy/proffer-starter.yaml` |
| 〃 | watch_paths | …`universal-import-starter`… | `modules/engine/**`, `deploy/docker/proffer-starter/**`, `deploy/proffer-starter.yaml` |
| 〃 | env keys | `N8N_UNIVERSAL_IMPORT_*` (3), `UNIVERSAL_IMPORT_UPLOAD_TOKEN`, `UNIVERSAL_IMPORT_UPLOAD_MAX_BYTES` | `N8N_PROFFER_*`, `PROFFER_UPLOAD_TOKEN`, `PROFFER_UPLOAD_MAX_BYTES` |
| `o11nxvzqwskxrqmtbvup7iet` (parser-activity-runtime) | git_repository only | old repo | `Cursedpotential/probata` (compose path unchanged; its bind mounts changed in git, see §3) |
| `xjbuo6drbwjfby75lalk8bk7` | name | `knowledge-workbench` | `workbench` (R-11) |
| 〃 | watch_paths | `workbench/**`, `deploy/workbench.yaml` (stale since the 2026-09-01 move) | `modules/workbench/**`, `deploy/workbench.yaml` |
| 〃 | env keys | `UIW_STARTER_URL`, `UIW_STARTER_TOKEN`, `UIW_UPLOAD_TOKEN` | `PROFFER_STARTER_URL`, `PROFFER_STARTER_TOKEN`, `PROFFER_UPLOAD_TOKEN` |
| all other 30 apps | git_repository | old repo (works via GitHub redirect) | `Cursedpotential/probata` — NOT DONE; cosmetic, redirect covers it |

Coolify renders env VALUES into the materialized compose at deploy — none of the above reaches a container
until each app is redeployed (§6).

## 3. Host directories — DONE 2026-09-06 13:48 UTC (running containers unaffected; bind mounts follow the inode)

| Host | Old absolute path | New absolute path |
|---|---|---|
| ovh-files (`100.91.190.107`, ubuntu) | `/data/agno/volumes/universal-import/` (source-objects, parser-bundles, normalized-bundles, inventory-manifests, parser-artifacts) | `/data/agno/volumes/proffer/` (same five subdirs, same uid 10001) |
| ovh-files | `/data/agno/secrets/uiw/{preview-cursor-key,service-token}` | `/data/agno/secrets/proffer/{preview-cursor-key,service-token}` |
| ovh-files | `/data/agno/secrets/n8n/universal-import-auth` | `/data/agno/secrets/n8n/proffer-auth` |
| ovh-app (`100.72.169.40`, debian) | `/data/agno/secrets/uiw/service-token` | `/data/agno/secrets/proffer/service-token` |
| ovh-app | `/data/agno/volumes/universal-import/` | did not exist on this host (nothing moved) |
| both | `/data/agno/` root, `/data/agno/secrets/{casebible-r2.json,platform/,tool-gateway/}` | **unchanged** (R-2: plumbing root, not a product name) |

Container-side paths changed in git: `/data/uiw/*` → `/data/proffer/*`; `/run/secrets/uiw-*` → `/run/secrets/proffer-*`;
`/run/secrets/n8n-universal-import-auth` → `/run/secrets/n8n-proffer-auth`.

## 4. Temporal — AFTER PUSH

| Item | Old | New | Note |
|---|---|---|---|
| Task queue | `universal-import-v1` | `proffer-v1` | compose defaults changed in git; BUT Coolify sets `TEMPORAL_TASK_QUEUE` explicitly on both apps and the value is 19 chars = `universal-import-v1`, which overrides the default. PENDING-OWNER: set `TEMPORAL_TASK_QUEUE=proffer-v1` on `d24bb9eoo47qtw9eq1xc6u64` and `r1084s1lsm80fsv4ol9ocij0` in Coolify before redeploy, or the new worker/starter keep polling the old queue |
| Workflow type | `UniversalImportWorkflow` | `ProfferWorkflow` | in-flight runs are rehearsals (D-142); they are orphaned, not drained — terminate them in Temporal UI after the new worker is up |
| Old worker drained? | — | no | D-142: nothing live to preserve |

## 5. n8n — PENDING-OWNER (MCP access is not enabled on the seven workflows, so this session cannot edit them)

| Live workflow (id) | Old webhook path | New path | Rename name to |
|---|---|---|---|
| Universal Import - start (`7HDcx0GPDELB56J0`) | `universal-import/start` | `proffer/start` | Proffer - start |
| Universal Import - preview (`nobMh2uO8eIBuH2p`) | `universal-import/preview` | `proffer/preview` | Proffer - preview |
| Universal Import - decision (`abOE3dzoZo3yw26x`) | `universal-import/decision` | `proffer/decision` | Proffer - decision |
| Universal Import - select_parser_activity (`fvKS2gcsRUdEKUun`) | `universal-import/select-parser-activity` | `proffer/select-parser-activity` | Proffer - select_parser_activity |
| Universal Import - execute_parser_activity (`YQoFBykpZoDrU0n6`) | `universal-import/execute-parser-activity` | `proffer/execute-parser-activity` | Proffer - execute_parser_activity |
| Universal Import - assess_source_repair_activity (`6TMn03Jq8WSxt9iY`) | `universal-import/assess-source-repair-activity` | `proffer/assess-source-repair-activity` | Proffer - assess_source_repair_activity |
| Universal Import - resolve_source_repair_activity (`cu7y91jsOVfBBWJC`) | `universal-import/resolve-source-repair-activity` | `proffer/resolve-source-repair-activity` | Proffer - resolve_source_repair_activity |

The checked-in definitions under `deploy/docker/n8n/workflows/proffer/*.json` already carry the new paths. The
`headerAuth` credential named `N8N_UNIVERSAL_IMPORT_WEBHOOK` is a credential NAME inside n8n — unchanged.
Sequencing: change the live paths at the same time as the worker/starter redeploy; until both sides match,
parser select/execute calls 404.

## 6. Redeploys — AFTER PUSH (in this order)

1. `proffer-worker` and `proffer-starter` together (queue + workflow type + env names + mounts all change at once).
2. `parser-activity-runtime` (new bind-mount paths).
3. `workbench` (new env names, `/api/proffer` routes).
Proof: worker log shows polling `proffer-v1`; starter `/healthz` 200 on `100.91.190.107:8091`; Temporal UI lists
pollers on `proffer-v1`; a Workbench preview call reaches `/api/proffer/...`.

## 7. R2 dev fixtures — NOT DONE (flagged)

Code now expects `r2://nexus/proffer/test-fixtures/…` (`runtimeapi.devFixturePrefix`, dev-bypass only). The
objects sit at `nexus/uiw/test-fixtures/`. Server-side copy required (`rclone copy` within the bucket, dry-run
first per the transfer rule); old prefix stays until the copy is verified. Not done in this pass.

## 8. Deliberately left on the old name

| Identifier | Why |
|---|---|
| PG tables `uiw_preview_*`, `uiw_source_context_revision`; migration filenames `0066_uiw_*`, `0067_uiw_*` | `sql/` is immutable applied history; a rename migration belongs to the golden-clone lane (D-142 §3) |
| docker network `agno`, `/data/agno/` host root, PG roles `agno_app`/`platform_*`, `SURREALDB_NS=agno`, `agentos-*` compose services, `OS_SECURITY_KEY` | need owner rulings R-1..R-9 (blast-radius register) |
| `agentos.mitechconsult.com` DNS (live, 503) | R-4: retire, not rename — owner action in Cloudflare |
| `ghcr.io/cursedpotential/agno-postgres` image | R-17: two live DBs pull it by digest; republish-then-deprecate, separate change |
| `svc:workbench`, `svc:tool-gateway`, `platform-api` | component names, correct under the rule |
| SBV's own "universal import" API term in `sbv_sms.py` / `_sbv_client.py` | donor vocabulary, not our lane |
| Case Bible identifiers (`casebible-*` buckets, `casebible` database/table prefix, `cb-*` commands) | D-141 KEEP |
| sibling repos `Legal-Workspace` → advocatio, `traceIQ` → vestigia (GitHub names) | directory renames are the last step of this pass; GitHub repo renames need their own decision |
| Checkout directory `Agno-MCP-Platform` → `probata` + memory dir + parent gitlink + memsearch collection | last step, ends the session; see chat |
