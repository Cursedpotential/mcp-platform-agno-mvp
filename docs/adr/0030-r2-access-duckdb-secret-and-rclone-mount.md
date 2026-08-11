# ADR-0030: Agno R2 access = pg_duckdb account-wide S3 secret (SQL) + rclone bucket mount (files); creds in Coolify
- Status: **Accepted (2026-06-23)** — extends ADR-0007 (R2 landing zone) and ADR-0013 (pg_duckdb).
  **AMENDED 2026-08-10 (owner ruling, emphatic; ADR-0050 §6): rclone is FILE TRANSPORT ONLY —
  it moves/mounts bytes, it does not own "ingestion." The bulk-data INGESTION POINT is
  pg_duckdb** (`read_parquet`/`read_csv`/`read_json` → `staging.*` tables → normalize →
  custody). This ADR's phrase ~~"file-level ingestion → rclone"~~ should be read as
  "file-level *access/transport* → rclone"; the ingestion role assignment is corrected here
  rather than rewritten below (provenance).
- Date: 2026-06-23
- _Amended byline: Claude Code · Fable 5 · 2026-08-10_
- _Byline: Claude Code · Opus 4.8 · 2026-06-23_
- _Handoff 2026-06-25: drafted by the CaseBible ingestion workstream; ownership/maintenance transferred to the platform workstream (owner of this repo). File stays in place; revise as you see fit._

## Context
Agno needs to read R2 (the CaseBible buckets) two different ways: **SQL/forensic queries** over object
data, and **file-level ingestion** that reads bytes from a path. The deployed `exec-tier` container had
all `R2_*` env vars **empty** (length-1) — Coolify never received real values — so `ensure_duckdb_r2_secret()`
returned False, no S3 secret existed, and agents could reach **neither** path. This presented as the
ingestion agent "timing out" and forensic R2 queries failing.

## Decision
Two complementary access mechanisms, by purpose:
1. **SQL / forensic reads → a pg_duckdb account-wide S3 secret.** At AgentOS startup
   `ensure_duckdb_r2_secret()` reads `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_ACCOUNT_ID` and runs
   `duckdb.create_simple_secret(type:='S3', …, endpoint:='{account}.r2.cloudflarestorage.com')` on the Agno
   Postgres. The secret is **account-wide** — one secret covers every bucket (`nexus`, `casebible-sorted`, …).
2. **File-level ingestion → an rclone docker-volume bucket mount.** The bucket is mounted into the
   container via the rclone volume plugin (`-d rclone:latest --opt remote=r2:<bucket> --opt vfs-cache-mode=writes`),
   read by the evidence/knowledge file path. Used by the dedicated CaseBible resource (ADR-0029).

R2 credentials are staged in **Coolify env** (build + runtime) so deploys re-bake them. The **sandbox**
container stays **R2-isolated by design** (no secret, no mount) — untrusted code must not reach R2.

## Consequences
- `forensic-data-agent` can query R2 objects through DuckDB; ingestion reads files from the mount. Both
  verified this session (R2 read of `casebible-sorted` via pg_duckdb secret; rclone mount listing + ingest).
- The DuckDB secret lives in Postgres, so it **survives container restarts**; only a DB volume reset
  (`down -v`) drops it, after which startup re-creates it from env. Obligation: keep `R2_*` populated in
  Coolify env or a rebuild bakes empties again (the original failure mode).
- One account-wide secret means any bucket is reachable — bucket scoping is by agent intent/path, not by
  credential.

## Alternatives considered
- **FUSE/rclone mount only** — insufficient for the SQL/forensic path (DuckDB reads `s3://` via the secret).
- **Per-bucket secrets** — unnecessary; the account-wide secret already covers all buckets.
- **Bake creds into the image only (build-arg)** — fragile; runtime env + the PG-resident secret are more
  robust and the secret outlives the container.
