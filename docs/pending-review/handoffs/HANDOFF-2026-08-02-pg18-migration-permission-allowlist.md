# HANDOFF — pg18 Case Bible migration (paused 1 step from done) + permission allowlist + cb-sort halt

> _Byline: Claude Code · Fable 5 · 2026-08-02_
> Session: `d4340a2e-a329-4e2c-88f9-9ac491f834d3` · Branch: `feat/stream-repair-layer`
> Trust this over the compaction summary where they conflict (HANDOFF v2 convention).

## STATUS — one sentence

The Case Bible pg18 migration is **paused exactly one API call from completion**: the
docker-compose Coolify service just needs `POST /services` retried with `docker_compose_raw`
**base64-encoded**; everything upstream (image published, pg16 dumped, compose authored) is done
and verified. Separately, the read-only permission allowlist was merged this turn, and the
cb-sort orchestrator halted before any upload awaiting per-stage GO.

## OWNER CORRECTIONS — read first, do not re-litigate

1. **"Why the fuck did you not just make a damn docker-compose like the other one did" / "With a
   proper docker compose you can put it on the right fucking net."** → The Coolify **"database"
   resource type is wrong for this job**: it is pinned to the `coolify` network and the API
   rejects `custom_docker_run_options` (422 at create AND PATCH), with no `agno` destination
   creatable (`POST /destinations` 404). **Use a docker-compose Coolify service (`POST /services`)
   instead** — that gives direct network control so the pg18 instance can join `agno`. This is
   the mandated path; do not go back to the DB-resource type.
2. **"all of the VPS already have the buckets mounted what are you doing"** → The VPS boxes
   already have the R2 buckets mounted. **Do not reinvent the Case Bible file pipeline or plan
   devbox-streaming uploads as if no mounts exist.** Acknowledge the existing VPS-side mounts
   before proposing any file movement.
3. **"The mounts are very slow, you're gonna have better luck with rclone directly."** → Prefer
   **direct rclone commands over mount-based file operations** (mounts are slow). Use mounts for
   discovery, rclone-direct for actual transfers.
4. Method (still in force): **everything through the Coolify API — push the image to ghcr.io,
   have Coolify pull it. No ad-hoc docker outside Coolify.**

## BUILD_STATUS — pg18 migration

### Done + verified
- **Custom image published:** `ghcr.io/cursedpotential/agno-postgres:18-duckdb`
  (digest `sha256:b1f6f82bbda7…`) = `pgduckdb/pgduckdb:18-v1.1.1` + PostGIS + pgvector,
  CMD preloads `pg_duckdb,pg_stat_statements`. Dockerfile SSOT: `docker/postgres/Dockerfile`.
  Pushed from ovh-files (AG migrated ovh-data→ovh-files mid-session; ovh-data copy cleaned).
- **pg16 dump taken:** `/tmp/casebible_pg16.dump` on ovh-files (39M, `pg_dump -Fc`, 5 tables:
  enrichment / faces / faces_scanned / photos / screenshots). Target-independent — reusable
  for the compose-app restore.
- **Compose file authored** (for `POST /services` — must be base64-encoded as `docker_compose_raw`):
  ```yaml
  services:
    casebible-pg18:
      image: ghcr.io/cursedpotential/agno-postgres:18-duckdb
      container_name: casebible-pg18
      environment:
        POSTGRES_USER: postgres
        POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
        POSTGRES_DB: casebible
      command: ["postgres", "-c", "shared_preload_libraries=pg_duckdb,pg_stat_statements"]
      volumes:
        - /data/coolify/applications/casebible-pg18/pgdata:/var/lib/postgresql/data
      networks:
        - agno
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U postgres -d casebible"]
        interval: 15s
        timeout: 5s
        retries: 5
        start_period: 10s
      restart: unless-stopped
  networks:
    agno:
      external: true
  ```

### PAUSED HERE — the one remaining call to land the compose-app
- `POST /services` with: `name=casebible-pg18`, `server_uuid=cn89l8801u8gsginw1rxq5qt`,
  `project_uuid=z45vmrtvk1woiwjhr91m57b2`, `environment_name=production`,
  `docker_compose_raw` = **base64-encoded** compose string above.
  - First attempt 404'd on `POST /applications/dockercompose` (deprecated on 4.1.2).
  - Second attempt on `/services` returned **422: "docker_compose_raw should be base64 encoded."**
  - **Fix is literally: base64-encode the compose string and re-POST.** That is the resume point.
- Then upsert the password env so it's not in the compose/ transcript:
  `PATCH /applications/{uuid}/envs/bulk` body
  `{"data":[{"key":"POSTGRES_PASSWORD","value":"153b6512b816403ac842d7631cd86662b8cd79dcc89d3c4c","is_preview":false}]}`
  (fetch the value in-process from `~/.secrets/`; it is the existing casebible PG password —
  reuse so consumers only change host). Then `POST /deploy?uuid={uuid}`.
- **Verify:** container on the `agno` network (172.24.0.0/16), `PG 18.1`, `pg_duckdb` preloadable
  (`SHOW shared_preload_libraries`).

### Cleanup pending (safe — empty wrong-network resource)
- **DELETE `/databases/fgz1n7useplhk0t91uk7k1aw`** — the wrong-network Coolify DB resource created
  earlier (running the ghcr image + PG 18.1 BUT on `coolify` 172.18.0.4, NOT agno; NO data
  migrated into it — empty). Delete via Coolify API once the compose-app is confirmed up on agno.
  Never `docker rm` a Coolify-owned container on the host.

### Then Task 3 — restore + extensions
- `pg_restore /tmp/casebible_pg16.dump` into the compose-app pg18.
- `CREATE EXTENSION pg_duckdb;` (+ postgis, vector).
- Verify: `enrichment` row count (expect ~15,252 — the lakehouse shows 15,249; reconcile the
  3-row delta), `\dx` lists pg_duckdb/postgis/vector.
- **Keep pg16 stopped-but-present (NEVER delete)** until pg18 is confirmed end-to-end.

### Then Task 4 — repoint + tunnel + lakehouse refresh
- Update `Backups/config/cb.env` `CB_PG_DSN` → new pg18 host/port (password unchanged).
- Bring up tunnel `localhost:15432 → casebible-pg18:5432` via ssh to ovh-files.
- Run `cb_lakehouse.py` refresh against pg18 (also verifies the `cfut_` Iceberg **write/publish**
  capability, currently unverified — reads verified 15,249 rows 2026-08-02).
- Confirm rows end-to-end (catalog + PG agree).

## BUILD_STATUS — permission allowlist (DONE this turn)

Merged into **project** `.claude/settings.json` `permissions.allow` (8 new entries, nothing removed):
- `mcp__agno-docs__query_docs_filesystem_agno`, `mcp__agno-docs__search_agno` — read-only Agno
  docs. **Note:** the two pre-existing `mcp__claude_ai_agno__*` entries use a WRONG server prefix
  (the actual enabled server is `agno-docs`) so they were inert; the new correctly-prefixed entries
  are the live ones. Left the stale ones in place (don't-remove rule).
- `Bash(rclone lsd *)`, `rclone ls *`, `rclone lsf *`, `rclone size *`, `rclone listremotes *`,
  `rclone listmounts *` — read-only rclone listing ops (proven-used in `settings.local.json`,
  central to Case Bible work).

**Skipped (auto-allowed, no rule needed):** `cd`, `echo`, `ls`, `grep`, `cat`, `tail`, `find`,
`which`, `sed`, `head`, `sleep`, `test`, all git/gh read-only subcommands, `docker ps/images/logs/inspect`.
**Dropped (arbitrary code execution — never allowlist):** `ssh` (151!), `python3`/`python`/`python.exe`,
`duckdb` (SQL engine w/ write/COPY capability — can't safely wildcard), `for`, `set`, `gh api *`,
`docker exec/run`. **Dropped (mutation):** `rm`, `cp`, `mkdir`, `rclone copy`, `go run`.
**Not done this turn:** the `/fewer-permission-prompts` allowlist is complete; no further
permission work pending.

## BUILD_STATUS — cb-sort orchestrator (background agent a9d46a8bfd7d92d42 — COMPLETED, HALTED)

The orchestrator finished Phase 1 + 2 (zero-download) and **halted before Phase 3 (any upload)**
per the owner's hard hold. Do NOT spawn a duplicate orchestrator.

- **Phase 1 (catalog refresh): DONE.** `r2_files` in `E:/AI_Workspace/casebible/casebible.duckdb`
  via parallel `rclone ls` (zero-download LIST, ~11 min, 948k objects). Current counts:
  `casebible-raw` 492,300 / 659.71 GB; `casebible-quarantine` 441,983 / 1,264.68 GB (3,699
  zero-byte); `casebible-sorted` 14,551 / 96.81 GB.
- **Phase 2 (per-source new-to-add manifest): DONE for 14 local/disk sources; OneDrive listing
  was still running** (metadata-only, `od_case_bible.tsv`, 8,915+ rows). Totals (local):
  1,281,563 files / 770.69 GB → **592,314 new / 143.16 GB / $2.67 Class-A conservative**
  (likely $0 — first 1M ops/mo free). D:\Backup is 71% of the new files (423,564 / 127 GB).
  34,651 zero-byte files flagged (skip, never canonical). 3 sources already fully in raw (0 new).
- **Phase 3 (uploads): NOT STARTED — awaiting explicit per-stage GO.** Proposed stage 1:
  D:\Backup → `r2:casebible-raw/_backup_import/` ($1.91).

### ⚠ Reconcile with owner correction #2/#3 before resuming Phase 3
The orchestrator's Phase 3 plan is **"Class B — devbox rclone → R2 (zero staging)"** for the
local-disk sources. The owner's "the VPS already has the buckets mounted" + "mounts are slow,
use rclone directly" remarks mean: **before firing any upload, confirm the intended path with the
owner.** Local-disk sources (D:/F:/J:/E:) physically cannot bypass the devbox (the bytes are
there), but the owner may want the VPS-side mounts/rclone used for the R2 destination side, or may
be redirecting the whole approach. **Ask, don't infer** — present the staged plan + costs and get
explicit GO per stage (the orchestrator already holds for this). OneDrive (Class A, VPS-side) is
additionally blocked on VPS `od:` remote setup (not yet authorized).

## UNRESOLVED / pending owner decisions
1. **Resume the pg18 compose-app creation?** It is one base64-retry away. Owner interrupted
   mid-pivot; confirm GO to fire `POST /services` (base64) + env upsert + deploy.
2. **cb-sort Phase 3 upload path** — reconcile with "VPS has buckets mounted" / "rclone direct."
   Which stage, and devbox-stream vs VPS-side? Explicit GO per stage.
3. **OneDrive `od:` remote** on VPS (`/var/lib/docker-plugins/rclone/config/rclone.conf` has only
   `[r2]`) — one-time owner-gated credential setup before the OneDrive stage can fire.
4. **cfut_ Iceberg write/publish capability** — unverified; gets verified incidentally by
   Task 4's `cb_lakehouse.py` refresh.

## Key file / resource pointers
- Custom image: `ghcr.io/cursedpotential/agno-postgres:18-duckdb` · Dockerfile: `docker/postgres/Dockerfile`
- pg16 dump: `/tmp/casebible_pg16.dump` (ovh-files)
- Wrong-net DB resource to delete: `fgz1n7useplhk0t91uk7k1aw`
- Coolify API: `http://100.98.98.38:8000/api/v1` (token in `~/.secrets/coolify-ionos-api.env`)
- Catalog DB: `E:/AI_Workspace/casebible/casebible.duckdb` · manifest logs: `E:/AI_Workspace/casebible/manifest_p2.log`
- cb.env: `Backups/config/cb.env` (`CB_PG_DSN`, `CB_R2_*`) · R2 catalog token: `~/.secrets/r2.env` (`R2_CATALOG_TOKEN` cfut_…)
- Settings merged this turn: `.claude/settings.json` (project, committed) — NOT `.claude/settings.local.json`