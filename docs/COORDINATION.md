# COORDINATION — multi-chat war room for Agno-MCP-Platform

> _Byline: Claude Code · Fable 5 · 2026-07-08 (TODO/Ledger update: Claude Opus 4.8 · 2026-07-10)_
> **Purpose:** two (or more) Claude chats work this repo concurrently. This file is the
> shared ledger: who owns what, what's in flight, what's frozen, and handoffs. **Append,
> don't rewrite history** — add timestamped entries under your lane; strike (~~…~~) items
> you complete. Commit this file with your changes so the other lane sees it on pull.

## Lanes & ownership (as of 2026-07-08)

### LANE A — "Restructure" (this file created by Lane A)
**Scope:** repo structure + seed reconciliation. Branch: `restructure/option-a`.
- Tier 0/1 hygiene + planning consolidation (in flight)
- Seed reconciliation: read-only dump of live ontology → committed seed catches up
  (live drifted: behavior_category 153→164, detection_pattern 512→527); promote applied
  0005/0006 into `sql/`; retire the parallel P2.1 tables (`analysis_module`,
  `pattern_phrase`, `mcl_factor_ref`, `contradiction_rule` — never applied live)
- Tier 3 Option A code repack: `server/{api,core,agents,evidence,analysis,vendored}` —
  **moves every Python package; imports rewritten** (~200 sites)
- Contract rewrite (`docs/REPO_STRUCTURE.md`) + final HTML report with diagrams
- **Lane A does NOT touch:** ingestion/detection LOGIC, table schema design, live DB
  writes (read-only dumps only), `analytics/` (untracked, not Lane A's)

### LANE B — "Ingestion/table redesign" (the other chat)
**Scope (per owner):** table structure + question/ingestion workflow redesign — the
"solid brainstorm". Data in live PG stays frozen meanwhile.
- Owns: future schema of `analysis.*` ontology/finding tables, ingestion flow redesign,
  detection/analysis rework
- Untracked `analytics/visit-locations/` presumed Lane B / owner-local — Lane A won't touch
- **Requested of Lane B:** log your in-flight items below; avoid committing to `main`
  while Lane A's repack PR is open (or coordinate here first); after the repack merges,
  note that **import paths change** (`evidence.*` → `server.evidence.*` etc.)

### LANE C — "Infra/gateway" (Coolify + ContextForge + Portkey chat)
**Scope:** VPS/Coolify ops, ContextForge, Portkey/LiteLLM, MCP wiring, tailnet. Does NOT
touch repo structure, schema design, or ingestion logic. Repo footprint is minimal and
listed here so Lane A can carry it through the repack:
- **exec-tier Coolify app now deploys from `main`** (was `hotfix/agent-ui-lockfile`,
  repointed 2026-07-08 per owner). ⚠️ Any merge to main auto-redeploys the exec tier on
  ovh-app (gateway/CF/agentos/sandbox/desktop/agent-ui). When the Lane-A repack merges,
  expect that redeploy — and note `docker/` Dockerfiles COPY configs at build time
  (gateway bakes `docker/gateway/litellm-config.yaml`), so keep `docker/` paths stable or
  flag here.
- Lane C commits on main: `6ad0c25` (agent-ui Dockerfile pnpm9/OOM fix ported from the
  hotfix branch — main was unbuildable without it). On `hotfix/agent-ui-lockfile`:
  `740675b` (embed-text → nv-embed-v1). **Stray commit `6bcfddc` on
  `claude/ingestion-offline-work-hu8eud`** (Lane B's branch?) — same embed fix, landed
  there by accident mid-rebase; content harmless (touches only
  `docker/gateway/litellm-config.yaml`); drop or keep at Lane B's discretion.
- embed-text MUST stay `nvidia/nv-embed-v1` (4096-d): the graphiti Neo4j graph is
  embedded at 4096-d; any dim change breaks vector search (bit us twice).
- In flight: exec-tier redeploy-from-main verification (background watcher);
  Portkey routing configs pending an owner planning session.

## FROZEN (owner mandate, 2026-07-08)
- Live PG data: unchanged until the Lane-B brainstorm lands
- Ingestion + detection logic: as-is (structure moves it; behavior identical)

## Hazards / heads-up board
- **2026-07-08 (A):** repack will move every top-level Python package under `server/`.
  If Lane B edits `.py` files on main between now and the repack merge, say so HERE —
  Lane A will rebase and carry the edits through the move.
- **2026-07-08 (A):** live ontology drift (+11 categories, +15 patterns beyond committed
  0006) — being captured into the committed seed by Lane A, **content-faithful, no
  redesign** (redesign is Lane B's).
- **2026-07-08 (A):** sealed-lexicon rows: committed seeds keep `[REDACTED:]` placeholders
  ONLY; real values never enter git (0006 court-safety rule).

## TODO / carried tasks
- [ ] **Milvus real-sparse lane (D-031)** — replace agno's hashed-TF-IDF sparse with genuine
  dense+sparse hybrid (BM25 server function or real BGE-M3 sparse); build WITH the KB-ingest
  work after Topic 4 decides collection/partition shape. Owner-decided 2026-07-11; must not slip.
- [x] ~~**CHANGELOG backfill**~~ — done on branch `docs/changelog-backfill`, folded into
  `docs/autonomous-doc-sync` (`9fd032c`); `CHANGELOG.md` now carries the full backfilled history
  (`ac14385`) plus a corrected `[Unreleased]` section.
- [ ] **Cloudflare global API key rotation** (owner-only; leaked in old repos, redacted 2026-07-04).
- [ ] **Lane C:** confirm n8n isn't deployed from the old `deploy/n8n/` path (now `docker/n8n/`).
- [x] ~~**SBV Phase 5a — native Go automation endpoints**~~ — BUILT, not shipped: `POST
  /api/automation/extract` + `status`/`export`/`backups` implemented in the SBV fork on branch
  `worktree-agent-abe280ccbefefe136` (`813f3b2`), custody ordering preserved (H1 → parse/H2/H3 →
  record). Not yet pushed through the locked subtree → fork → CI → tag-bump sequence, so it isn't
  live — see `docs/planning/sbv-fork-plan.md` §5a before shipping.
- [ ] **SBV Phase 5b — `/x/sbv/` UI embed** (DEFERRED to the G2/VPS window): Vite `base` env, CORS
  allow-list env-configurable, reverse-proxy prefix-strip. Reverse-proxy tech (Caddy vs Traefik) = open. §5b.
- [x] ~~**SBV — run the ContextForge registration**~~ — DONE 2026-07-10: all 14 facade tools
  (`docker/tools/tools/facade.py`) registered directly as ContextForge REST tools in a 5th virtual
  server `platform_tools`, alongside the existing `agno`/`coolify`/`graphiti`/`exa` servers. (This
  superseded running `scripts/register_sbv_contextforge.sh` as originally planned — see the
  FACADE COLLAPSE entry below for why the facade-REST-wrap path won instead of an MCP repoint.)
- [ ] **restore-heic — FIND A BETTER SOLUTION** (owner: wants HEIC functional someday, DOWN THE ROAD,
  not urgent). Today the SBV fork image (`v0.2.3-forensic`) has the `heic` tag DROPPED because pinned
  `strukturag/libheif-go@20250130` no longer compiles vs current Alpine libheif (CGO enum drift). HEIC
  attachment BYTES are still ingested + custody-hashed; only in-app HEIC transcode/display is off.
  Owner wants a ROBUST long-term fix, not a brittle version pin. Options to explore (best→worth-trying):
  - (a) **Decouple HEIC from SBV's build entirely** — transcode HEIC→JPEG via a separate path (ffmpeg
    is already in the platform-tools image; or a standalone `heif-convert`/libheif CLI, or a small
    media-conversion tool/app) so SBV never needs the fragile CGO libheif binding. Cleanest, most durable.
  - (b) bump `strukturag/libheif-go` to a version matching current Alpine libheif (may break SBV's
    `heic_enabled.go` if the binding API changed — test).
  - (c) pin a compatible libheif + libheif-go PAIR in `vendored/sbv/Dockerfile` (brittle; ties us to
    an old Alpine).
  Whichever: re-add `-tags "fts5 heic"` (or route HEIC around it), rebuild the fork image, bump the tag
  in `docker/tools/Dockerfile`. NOTE: this also relates to the broader media pipeline (HEIC/3GP/AMR/etc.
  from iPhone MMS = real forensic evidence), so a general media-conversion capability may be the right
  home rather than SBV-internal HEIC.
- [x] **FACADE COLLAPSE — Batches B/C now MOOT, the facade STAYS** (corrected 2026-07-10). Batch A
  (add the G4 gateway + SBV toolkit as agno `@tool`s) was built, merged, and deployed (`bec5596`).
  This item's original premise — that `enable_mcp_server` re-exports granular `@tool` functions
  over `agentos-mcp`, so ContextForge could be repointed there (Batch B) and the facade removed
  (Batch C) — was **DISPROVEN 2026-07-10**: verified from agno source (`agno/os/app.py:588-595`),
  AgentOS's MCP surface only ever exposes ~19 AgentOS *operations*, never the parser/SBV `@tool`s.
  The facade therefore stays as the only granular-tool MCP surface; all 14 facade tools were
  instead registered directly in ContextForge as REST tools (see the "SBV — run the ContextForge
  registration" entry above). Full corrected plan + superseded banner:
  `docs/planning/facade-collapse-plan.md`.
- [x] ~~**SEMANTICA MOVE**~~ — done on `restructure/semantica-vendor` (branch, not merged); see Ledger
  entry below. Landed as a **`git mv` relocate**, not a subtree add (see rationale in the entry) —
  correcting this line item's original "subtree" wording.

## SBV build path (LOCKED 2026-07-09) — do NOT rebuild SBV from source in the exec tier
The SBV app is built by **GitHub Actions in the fork** `Cursedpotential/sbv-forensic` (workflow
`docker-build.yml`, publishes `ghcr.io/cursedpotential/sbv-forensic:<tag>`), because the 4CPU/8GB exec
box can't/shouldn't compile Go+CGO+node. `docker/tools/Dockerfile` LIFTS the binary via
`FROM ghcr.io/cursedpotential/sbv-forensic:<tag> AS sbv`. To ship SBV source changes: edit
`vendored/sbv/**` → `git subtree split --prefix=vendored/sbv` → force-push to fork `main` + a `v*.*.*`
tag → CI builds → bump the tag in `docker/tools/Dockerfile`. Image name MUST be lowercase (hardcoded
`cursedpotential/sbv-forensic` in the workflow — `${{ github.repository }}`'s capital C breaks the push).

## Ledger (append below; newest on top)
- **2026-07-10 — DOCUMENTATION SYNC (branch `docs/autonomous-doc-sync`):** AGENTS.md
  progressive-disclosure reconfiguration after ADR-0033/0035 left the root `AGENTS.md`
  describing the pre-repack flat-package layout and promising per-directory `README.md`
  files that never existed. Rewrote root `AGENTS.md` as a concise map (`server/*` layout,
  `## Commands` table, closest-file-wins pointer) and added 5 nested `AGENTS.md` drill-downs:
  `server/AGENTS.md` (dependency direction), `server/tools/AGENTS.md` (registry + "how to add
  a parser"), `server/evidence/AGENTS.md`, `server/agents/AGENTS.md`, `server/contracts/AGENTS.md`
  (facade-safety rule). Reconciled `docs/COORDINATION.md` (this entry + the TODO closures above),
  `docs/DECISION_LOG.md`, `docs/adr/README.md` (added the missing ADR-0033 index row), and
  `docs/REPO_STRUCTURE.md` (ADR-0035 tree: `contracts/`, sub-namespaced `tools/`, `gateway/`).
  Fixed a stale comment in `docker/tools/Dockerfile` (said `server.evidence.registry`, real import
  is `server.tools.registry`). Doc-only; gates re-run to confirm no regression.
- **2026-07-10 — ADR-0035 EXECUTED, MERGED, DEPLOYED:** tools sub-namespacing
  (`parsers/{messaging,ai_chat,generic}/`, `extractors/`), G4 gateway extraction
  (`server/evidence/tool_finder/` → `server/tools/gateway/`), and the record contract's new home
  (Option A, `server/contracts/records.py`; `server/evidence/normalize.py` now a deprecated
  re-export shim). Merged to `main` (`8240205`), deployed to the exec tier, verified healthy
  (facade `/health` 23 tools, `agentos-api :8000/health` 200, `agentos-mcp` up). Behavior-neutral:
  23 tool IDs unchanged, no ContextForge re-registration needed. Gates green: ruff/mypy/pytest 208.
  Full as-built record: `docs/adr/0035-tools-subnamespacing-and-record-contract-home.md` (Outcome
  section).
- **2026-07-09 — FORENSIC GUARD: no fabricated timestamps (branch
  `test/forensic-no-fabricated-timestamps`):** `tests/test_no_fabricated_timestamps.py` AST-scans
  every parser/extractor module and fails on any wall-clock call (`datetime.now/utcnow/today`,
  `date.today`, `time.time`), plus a behavioral check that `imessage._parse_ts` returns `None`
  (never `now()`) on unparseable input. Encodes the parser-inventory finding that TS-lineage
  parsers fabricate event times while the Python lane preserves the raw value. Not yet merged.
- **2026-07-09 (A) — FACADE COLLAPSE BATCH A (branch, not merged):** built Batch A of
  `docs/planning/facade-collapse-plan.md` on `feature/facade-collapse-batch-a` (off `main`) —
  the additive half of the FACADE COLLAPSE TODO (line ~98). **Does NOT close that TODO**;
  only Batch A of 3 (Batch B repoints ContextForge, Batch C removes the facade — both still
  gated on live deploy verification per the plan §6). New `server/agents/tools/` package:
  `gateway_tools.py` (5 agno `@tool` wrappers over the G4 progressive-disclosure meta-ops,
  `server/evidence/tool_finder/toolfinder.py` — `get_tool_categories`, `search_tools`,
  `describe_tool`, `execute_tool`, `get_ref`) and `sbv_tools.py` (11 agno `@tool` wrappers
  over `SBVClient`, `server/tools/_sbv_client.py` — mirrors the old facade's `/sbv/*` proxy
  surface, PLUS `sbv_hashes` which exposes the H1/H3 forensic custody hashes that
  `SBVClient.hashes()` already had but the facade never routed — the custody chain is the
  whole point of the SBV fork). Both wired into `source_tools` in
  `server/agents/providers.py:169` (one import + one list-splice, same append pattern already
  used for Graphiti), so every agent built off `PlatformContext` — and therefore
  `agentos-mcp`'s MCP surface — picks them up with zero other file changes.
  **Error convention (OQ-8) resolved:** neither module catches/re-shapes exceptions into an
  `{"error": ...}` dict. Both let exceptions propagate (`KeyError`/`ValueError` from the
  registry/toolfinder layer, `SBVError` from `SBVClient`) — this matches the convention
  already dominant one layer down (`server/tools/*.py`, `server/evidence/tool_finder/`, which
  raise and document raising), and agno's own `Function.execute()` already catches any
  exception raised inside a `@tool` entrypoint and reports a structured
  `status="failure"` result to the calling agent — so re-catching here would only throw that
  signal away. The codebase's other `@tool` (`apply_db_modification`, `factory.py`) uses a
  string-prefixed `"ERROR: ..."` return instead, but that's a different tool shape (a
  HITL-approval-gated write reporting a tri-state OK/REJECTED/ERROR outcome), not a precedent
  for these read-only, dict/list-returning tools.
  `compose.exec.yaml` (`agentos-api` + `agentos-mcp` env blocks) and `compose.yaml`
  (`agentos-api` only — no `agentos-mcp` service exists in the local/dev compose) both get
  `SBV_BASE_URL` (defaults to `http://platform-tools:8085`, the docker-network hostname —
  `_sbv_client.py`'s own default of `localhost:8085` is wrong from inside these containers),
  `SBV_SERVICE_USER`, `SBV_SERVICE_PASS`. On the exec tier `SBV_SERVICE_PASS` is a **hard**
  `${SBV_SERVICE_PASS:?...}` per the plan (unset = container won't start, checked BEFORE
  merging); on local/dev it's a soft `${SBV_SERVICE_PASS:-}` default (matches every other
  local-compose secret, none of which are hard-required there) — a judgment call, not
  explicitly specified by the plan for the local file.
  Tests: `tests/test_gateway_tools.py` (9 tests) + `tests/test_sbv_tools.py` (11 tests, incl.
  a CSV/JSON shape-parity regression test for the ported `sbv_export` synthesis logic —
  the one piece of real business logic moving, not just re-plumbing) — mock `SBVClient`
  entirely, no live SBV dependency. Gates on the branch: `ruff format`/`ruff check` clean,
  `mypy` clean (112 files), `pytest` 208 passed (191 baseline + 17 new — up, not down).
  **Deploy-only, cannot be verified from the repo:** whether `agentos-mcp`'s MCP `tools/list`
  actually surfaces these 16 tools over the wire once this merges (FastMCP standalone-app
  extraction is an integration property unit tests don't exercise — plan §1.4/§6 Batch-A
  post-deploy gate) — do not proceed to Batch B/C until that's confirmed. Facade
  (`docker/tools/tools/facade.py`) untouched this batch, exactly as scoped. Branch NOT
  merged — pushed to origin for a watched-deploy review before Batch B/C proceed.
- **2026-07-09 (A) — SEMANTICA VENDOR MOVE (branch, not merged):** ADR-0033 amendment
  ("2026-07-09b") on `restructure/semantica-vendor` (off `main`): relocated
  `docs/wiki/tools/semantica/` (12MB, 615 tracked files) to `server/vendored/semantica/` via
  `git mv` — **NOT** a `git subtree add`. Rationale: our vendored copy is a modified snapshot
  (`pyproject` says `0.3.0-alpha`, `__init__.py` says `0.2.7`, no `README.md` despite
  `pyproject` declaring one) that diverges from upstream HEAD; the discoverable upstream URL
  (`github.com/Hawksight-AI/semantica` in `mkdocs.yml`/`FUNDING.yml`) could not be reliably
  confirmed as canonical (a WebFetch resolved a *different* org, `semantica-agi/semantica` —
  unverified, possible org-rename or fetch noise); `server/analysis/semantica_wiring.py`
  hard-codes config-key names that an upstream version bump could silently rename; and the
  chatminer precedent (same vendored/ class) was itself a plain relocate, no subtree/remote.
  A future live-upstream adoption is a **separate, deliberate upgrade** (verify the real
  remote first) — appendix commands left in the ADR amendment, not run here.
  Symlinked `docs/semantica` → `../server/vendored/semantica/docs` and
  `docs/semantica-benchmarks` → `../server/vendored/semantica/benchmarks`, git-tracked as real
  mode-`120000` symlink blobs (via `git update-index --cacheinfo 120000`, since this dev
  sandbox has `core.symlinks=false` and no Developer-Mode/admin symlink privilege — the
  working tree here shows plain text placeholder files, but the git objects are correct and
  Linux checkouts/CI/containers will resolve them as functional symlinks).
  `server/vendored/` excluded from ruff+mypy (`pyproject.toml`, closing a latent gap where
  chatminer was previously unexcluded too) and added to pytest `norecursedirs` — semantica's
  test suite pulls heavy ML deps (torch/spacy/transformers, present even in its "safe
  default" install) that aren't in our env, so it stays **opt-in only**
  (`uv pip install -e "server/vendored/semantica[dev]"` then
  `uv run pytest server/vendored/semantica/tests`), never in the default run. Nothing in-tree
  imports semantica yet — behavior-neutral. Gates: see commit message for the exact numbers
  from this run. Branch NOT merged — pushed to origin for review only.
- **2026-07-09 (A) — TOOLS LAYER PROMOTED (branch, not merged):** D-026 / ADR-0033 amendment on
  `restructure/tools-layer` (off `main`, post-repack): moved the atomic-tools capability layer +
  registry OUT of the evidence spine to a top-level `server/tools/` (cross-domain — evidence,
  analysis, agents, workflows, and the CLI all consume it). `git mv server/evidence/tools
  server/tools`; `git mv server/evidence/registry.py server/tools/registry.py`; registry
  auto-discovery made package-name-agnostic + intra-package imports relativized. Also fixed a
  LIVE mount regression: `compose.yaml`/`compose.exec.yaml` still mounted
  `./evidence:/opt/tools/evidence:ro` for the `docker/tools` platform-tools facade — that host
  dir stopped existing the moment the D-025 repack landed, so the facade was serving **zero**
  parser modules. Now mounts the WHOLE `server/` tree (`./server:/opt/tools/server:ro`, not just
  `server/tools/` — `server.tools.*` transitively needs `server.evidence.normalize` +
  `server.vendored.chatminer`, both lightweight), with `docker/tools/tools/facade.py` importing
  plain `server.tools.registry`/`server.tools._sbv_client`, same as the main app. Verified via an
  isolated-Python simulation of the container's real import graph (not the repo venv, which has
  `server` editable-installed and would mask the bug) — loads all 23 tools.
  **⚠ ALL LANES: import paths changed AGAIN** — `server.evidence.tools.*` → `server.tools.*`,
  `server.evidence.registry` → `server.tools.registry`; rebase before further `.py` work. Gates
  GREEN: ruff clean, mypy clean, **pytest 186**. Branch NOT merged (merge auto-deploys exec
  tier, D-011) — pushed to origin for review only.
- **2026-07-09 (A) — REPACK EXECUTED (branch, not merged):** ADR-0033 `server/` repack done on
  `restructure/option-a`. Every backend package now under `server/{api,core,agents,evidence,
  analysis,vendored/chatminer}`; imports are `server.*`. 152 files, 240 import rewrites; fixed
  path-depth (`patterns.py::_REPO`, chatminer sys.path), string-module refs (registry loops,
  `evidence/__init__` lazy map, test monkeypatches), config split (analysis configs →
  `server/analysis/config/`), entrypoint (`server.api.main:app` in Dockerfile+compose×3),
  pyproject packages+mypy. Gates GREEN: ruff, mypy (106), pytest (186). **⚠ ALL LANES: import
  paths changed — rebase onto this before further `.py` work.** `podman build` proof + merge
  DEFERRED (owner configs podman later; merge auto-deploys exec tier → needs the watched window).
  Reproducible via `scripts/repack_to_server_layout.py`.
- **2026-07-09 (A):** owner decided the open questions (while driving). DONE on
  `restructure/option-a`: `visualizations/`→`docs/visualizations/`; `configs/`→`docker/milvus/`;
  `deploy/n8n/`→`docker/n8n/` (compose mounts Milvus configs from absolute VPS host paths, so
  these are DEPLOY-NEUTRAL — no re-up needed; scp comment repointed). **Lane C: confirm n8n
  isn't deployed from the old `deploy/n8n/` path.** DECISIONS: repack = Option A (full `server/`)
  LOCKED; UI/G1 DEFERRED (repack proceeds in its own coordinated window, not racing the shell);
  `shared/` deferred. Repack still NOT executed — pending the keyboard-present window. Branch not
  merged (merge = exec-tier auto-deploy; owner is driving).
- **2026-07-09 (A→C):** the old untracked `.planning/build/` = **live architecture directives**
  (owner: "most of that was good directives"), now committed at
  `docs/planning/architecture-directives/` (+ `INDEX.md` mapping each doc to a lane). These are
  YOUR infra directives (ContextForge/SurrealDB/DNS/Traefik/topology) — reconcile against what's
  now live (CF v1.0.4, Portkey, coolify-mcp), capture deltas as ADRs. Not archive, not stale.
- **2026-07-08 late (C):** coolify-write MCP deployed as HTTP service. NEW Lane-C files on
  `main`: `compose.coolify-mcp.yaml` + `docker/coolify-mcp/` (server.py/requirements/Dockerfile
  — patched repo copy of the local stdio skill; keep paths stable through the repack, same as
  `docker/gateway`). Commits `82cd8c8` + `c6e3e66` (Host-check fix). New Coolify app
  `coolify-mcp` (uuid `oyzznioap03u34xz125l90oq`, ovh-app, tailnet-only 100.72.169.40:8765,
  token via app envs — never in git). CF gateway `coolify-write`
  (`fe0789de7cdb47cc9bec10eb7a0ddfc0`, transport STREAMABLEHTTP — CF defaults to SSE and hangs
  on streamable-http servers without the explicit field). `coolify` virtual server
  (`d8a45fe53fa4415cadfb3982d9026d43`) re-pointed 10 read tools → 14 coolify-write tools
  (read names mirrored, so callers keep working); verified end-to-end (initialize/tools-list/
  list-projects with real data). Old read-only `coolify` gateway
  (`5a2c512b6e0e43bfa62471a9461ad83f` → 100.98.98.38:8000/mcp) left registered but now
  REDUNDANT (doors policy). ⚠️ Reminder: any push to `main` auto-redeploys exec-tier AND
  the webhooked coolify-mcp/portkey/data-* apps.
- **2026-07-08 (A):** SEED RECONCILIATION RESOLVED — no action needed: live (164/527) ==
  exact `0007` prefix of Lane B's committed migration chain (0006+0007+0008);
  `evidence/patterns.py` chain validator OK; corpus fully homed (0 missing); only the 4
  contradiction rules remain unhomed (pending owner table decision). My earlier "drift"
  read compared live against 0006 alone — wrong baseline, withdrawn. Full gates green
  (186 tests) + live smoke ALL-PASS (PG ontology/source/detection-dry-run, Milvus,
  wiring). Added `scripts/dump_live_ontology.py` (read-only → gitignored `live-dumps/`).
  NEXT: Tier 3 Option A repack — built and gated ON BRANCH `restructure/option-a`,
  **NOT merged** (Lane C: main auto-deploys the exec tier; merge needs owner + Lane C go,
  Docker paths move in lockstep in the same commit).
- **2026-07-08 (C):** CF v1.0.4 live + federation verified (41 tools / 4 gateways); graphiti
  hostfix sidecar (`0f2cd16`); graphiti CF virtual server + Claude Code rewire (restart
  pending); Portkey 1.15.2 live on ovh-app:8787; exec-tier repointed hotfix→main + agent-ui
  Dockerfile fix ported (`6ad0c25`); redeploy-from-main verification in flight.
- **2026-07-08 ~AM (A):** Tier 0/1 done on `restructure/option-a` (dead venvs deleted,
  recall fragments → `../_stale/repo-recall-fragments-2026-07-08/`, goals/.planning/plans
  consolidated into `docs/planning/`). Next: seed reconciliation (read-only vs live), then
  Tier 3 repack. Final deliverable: illustrated HTML report in `docs/planning/`.
