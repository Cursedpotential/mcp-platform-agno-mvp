# SBV Option B — Fork-from-Source Plan

> _Byline: Claude Code · Fable 5 (plan by Sonnet sub-agent) · 2026-07-09_
> Status: DRAFT for owner sign-off. Companion to `docs/planning/sbv-mcp-integration-plan.md`,
> `docs/planning/gui-integration-spec.md` (SBV = G2 embed), ADR-0016/0017/0023.
> Private fork already created: **`Cursedpotential/sbv-forensic`** (mirror of `lowcarbdev/sbv`, MIT).

## Phase 0 — Discovery findings (verified against source)

- **`lowcarbdev/sbv`** = public, MIT, "Web viewer for SMS Backup & Restore XML files." Active
  (last push 2026-07-03). Latest tag **v0.1.11** — matches the `git-0.1.11` string in our
  `_sbv_client.py`, so `ghcr.io/lowcarbdev/sbv:stable` we run today is current, not stale.
- **Language = Go 1.25 backend + React/Vite frontend** (GitHub's "JavaScript" label just counts
  frontend LOC). Echo v4, `mattn/go-sqlite3` (CGO), `strukturag/libheif-go` for HEIC.
  Full upstream snapshot already in-repo at `extracted-code/sbv/sbv-upstream-main.zip` (2026-06-10).
- **Structure**: `main.go` (route table), `internal/*` (auth, handlers, parser, database, models,
  autoimport, settings, middleware, cors, heic build-tag pair, utils), `frontend/` (React+Vite,
  **no `base` path** → root-relative assets), 3-stage `Dockerfile` (node build → `golang:1.25-alpine`
  CGO build `-tags "fts5 heic"` → `alpine:3` runtime), `.github/workflows/docker-build.yml` (buildx,
  amd64+arm64, pushes ghcr).
- **Storage**: multi-user, **one SQLite DB per user** (`GetUserDB`). `messages` table has a UNIQUE
  index for idempotent re-import but **NO content-hash column today**. Separate `sbv.db` for
  auth (bcrypt, hex session tokens, 30-day, `SameSite=Lax`).
- **Current API** (authoritative, from `main.go`):
  - Public: `POST /api/auth/{register,login,logout}`, `GET /api/health`, `GET /api/version`
  - Protected: `GET/PUT /api/settings`; `GET /api/auth/me`, `POST /api/auth/change-password`;
    `POST /api/upload` (multipart XML, async → poll `/api/progress`); `GET /api/conversations`,
    `/api/messages`, `/api/activity`, `/api/calls`, `/api/daterange`, `/api/progress`,
    `/api/media`, `/api/media-items`, `/api/search`, `/api/analytics`; SPA fallback.
  - CLI: `-reset-password`, `-list-users`, `-journal`. Auto-import: watches `<data>/<uuid>/ingest/` every 60s.
  - **No `/api/export`, no headless extract, no hash/custody fields, no DB-target selector** — all
    four owner asks are genuinely additive, not "already there."
- **Embed readiness (#4)**: no `X-Frame-Options`/CSP anywhere → framing allowed by default. BUT
  hardcoded CORS allow-list (`localhost:5173/5175/3000/8085`) and root-relative frontend assets
  will break under a `/x/sbv/` path prefix — scoped fix in Phase 5b. `gui-integration-spec.md`
  already lists `/x/sbv/` as the intended same-origin reverse-proxy mount.
- **Custody schema ALREADY fits (#1)**: `server/evidence/custody.py` + `0005_forensic_reconciliation.sql`
  define H1/H2/H3 (`evidence.evidence_hash.level`; H1/H2 need `source_id`/`file_node_id`, H3 is the
  chain level with `member_hash_ids[]`), plus append-only hash-chained `evidence.custody_event` and
  per-unit `evidence.file_node` (`node_kind='message_unit'`). So H2 per-message lands in `file_node`;
  writing custody is largely **existing Python** — SBV Go just needs to *compute* the hashes.

## Phase 1 — Fork + subtree

- **DONE**: private fork `Cursedpotential/sbv-forensic` created by mirror (new private repo +
  `git push --mirror` — because `gh repo fork` makes a PUBLIC fork GitHub won't privatize).
  Full history, all tags, `main` + dependabot branches present.
- **Next**: add `upstream` remote (`lowcarbdev/sbv`) to the fork for future `git merge upstream/main`.
- **Vendor** at top-level `vendored/sbv/` (NOT `server/vendored/` — ADR-0033 scopes that to
  import-only Python): `git subtree add --prefix=vendored/sbv <fork> main --squash`. First real
  subtree in this repo (chatminer was a squash-import, not subtree).
- **Update discipline**: keep custom features in NEW files (`internal/custody.go`,
  `internal/automation_handlers.go`, `internal/export.go`) wired into `main.go` with minimal edits
  to existing files, so `git subtree pull --squash` rarely conflicts. Record last-pulled upstream
  tag in `vendored/sbv/UPSTREAM.md`.

## Phase 2 — Docker build-from-source
Replace `FROM ghcr.io/lowcarbdev/sbv:stable AS sbv` with SBV's own build stages (node frontend →
`golang:1.25-alpine` CGO `-tags "fts5 heic"` → `alpine:3` runtime), reproducing upstream's own
Dockerfile shape so the existing musl-loader-copy trick (`/lib/ld-musl-x86_64.so.1`, `/usr/lib →
/opt/sbv-libs`, `LD_LIBRARY_PATH`) is unchanged. **Build-context note**: `vendored/sbv/` is at repo
root, outside the current `./docker/tools` build context → bump `platform-tools` build `context:` to
repo root `.` (recommended; future `ui/`/embeds want that anyway).

## Phase 3 — Hashing (#1), onto the existing H1/H2/H3 schema
- **H1** (file): `internal/parser.go: SaveUploadedFile()` — sha256 whole upload before parse; surface
  in `UploadResponse`/`/api/progress`.
- **H2** (per-record): `internal/database.go: InsertMessage()` — sha256 canonical tuple (address,
  date, type, body/content); add `content_hash` column; return in message/call/activity payloads.
- **H3** (chain): end of `ParseSMSBackupStreaming()` — running/Merkle digest over ordered H2s per
  import batch (new `imports` table: file_hash, record_count, chain_hash, imported_at).
- New `internal/custody.go` with `HashFileH1`/`HashRecordH2`/`ChainH3` using the SAME canonicalization
  as `server/evidence/custody.py` (`h1-rawbytes-v1`) so SBV's Go H1 and our Python H1 are byte-identical.
- New `GET /api/hashes/{importID}`.

## Phase 4 — Evidence handling / custody + DB-target (#2, #6)
- **SBV side gets NO DB credentials** — keeps the trust boundary (agents/tools never hold write creds;
  `custody.py` read-only-engine posture). SBV exposes hashes + export; **our** `sbv_sms.py` remains the
  only writer into `evidence.*`.
- **Python side (extend existing)**: (1) consume SBV's H1/H2 as a **cross-check** against
  `ingest_artifact()`'s independent H1 — mismatch → `integrity_violation` custody_event (two
  independent hash computations = strongest court-defensibility). (2) emit H2/H3 rows + `custody_event`s
  for SBV records via a thin extension of the existing `ingest_artifact()` pattern.
- **#6 "DB target selection"**: assumed FUNCTIONAL — `sbv_sms.py` already returns `NormalizedRecord`s
  consumed by `store.py`/`workflows.py` which write PG `evidence`/`analysis`. Milvus/Surreal/Neo4j are
  **workflow steps** (embed/entity-extract after normalize), resolved like every other capability-step
  (ADR-0017) — NOT taught to SBV. **⚠ OWNER DECISION**: literal (SBV itself writes to Milvus/Neo4j —
  needs DB creds in the SBV container, bigger attack surface) vs functional (default). 

## Phase 5 — Automation API + UI embed + agent-drivability + export (#3,#4,#5,#7)
- **5a Automation endpoints (#3,#5)**: new Go `POST /api/automation/extract`, `GET
  /automation/status/{id}`, `/automation/export/{id}`, `/automation/backups`. **Highest effort** — but
  the facade proxy (`_sbv_client.py` upload+wait+all_activity) + registry `@register` + ContextForge
  REST-wrap (ADR-0023; `scripts/register_sbv_contextforge.sh`, currently dry-run) already deliver ~90%
  of "agent-drivable, MCP-callable." **⚠ OWNER DECISION**: build 5a or defer (facade already covers it)?
- **5b UI embed (#4)**: `vite.config.js` add env-driven `base` (`/x/sbv/`); make CORS allow-list
  env-configurable; rely on the reverse proxy to strip `/x/sbv/` (no Go route changes). Don't add
  security headers that would break framing. **⚠ OWNER DECISION**: reverse proxy = Caddy or Traefik?
- **5c Best-format export (#7)**: KEEP the NormalizedRecord mapping in Python (`sbv_sms.py` `_map_message`/
  `_map_call` already do it, live/tested) rather than duplicating in Go — avoids schema drift. Recommended.

## Risks
- Build reproducibility: subtree = manual merge risk vs a digest-pinned upstream image; keep the fork's
  own CI (`docker-build.yml`) for verified builds.
- musl/CGO/libheif build must track upstream base images (`golang:1.25-alpine`/`alpine:3`).
- `_sbv_client.py` must stay in lockstep with our own Go changes (treat `internal/models.go` as truth).
- Subtree conflicts concentrate in `main.go`/`handlers.go`/`database.go` — mitigate with new-files convention.
- CGO/libheif multi-arch build adds real CI minutes.

## Open questions (owner)
1. Fork destination — personal `Cursedpotential` (used) vs a dedicated private org (`admin:org` available)?
2. Fork name — `sbv-forensic` (used) vs `sbv`?
3. DB-target scope (#6) — literal (SBV holds DB creds) vs functional (default; SBV never holds creds)?
4. Phase 5a native Go automation endpoints — build, or defer (facade proxy already ~90%)?
5. Reverse-proxy tech for `/x/sbv/` — Caddy vs existing Traefik labels?
