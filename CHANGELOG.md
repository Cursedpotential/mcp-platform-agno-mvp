# Changelog

All notable changes to probata (formerly Agno-MCP-Platform) are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
decisions behind changes live in [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md).

The project has no release tags yet (the `v0.x-forensic` tags belong to the vendored
SBV fork, not the platform), so history below is a dated chronicle rather than versioned
releases. Sections are newest-first. `[Unreleased]` lists work committed to branches but
not yet merged to `main`.

> _Backfilled from git history 2026-07-10 (commits `ebcdc62`…`b169afb`)._

## [Unreleased]

_Nothing pending — all branch work below merged to `main` 2026-07-11._

## 2026-07-11

### Added
- **Forensic guard — no fabricated timestamps**:
  `tests/test_no_fabricated_timestamps.py` AST-scans all parser/extractor modules and fails on
  any wall-clock call (`datetime.now/utcnow/today`, `date.today`, `time.time`), plus a behavioral
  check that `imessage._parse_ts` returns `None` (never `now()`) on unparseable input. Encodes the
  parser-inventory finding that TS-lineage parsers fabricate event times while the Python lane
  preserves the raw value.
- **SBV Phase 5a — native Go automation endpoints** (under `vendored/sbv/`): headless `POST /api/automation/extract`, `GET /api/automation/status/:id`,
  `GET /api/automation/export/:id`, `GET /api/automation/backups`. Custody ordering preserved
  (H1 → parse/H2/H3 → record, before normalization); source files opened read-only and never
  deleted. Source merged; the deployed image stays on the `0.2.3-forensic` pin until the locked
  subtree → fork CI → tag-bump ship sequence runs.

### Changed
- **Documentation sync (autonomous arc)** — CHANGELOG backfilled from full git history;
  ADR-0035 flipped to Accepted & Implemented (+ as-built Outcome) and ADR index reconciled
  (+0033); root `AGENTS.md` rewritten to the real `server/*` layout with 5 nested `AGENTS.md`
  drill-downs (progressive disclosure); `CLAUDE.md` fixed from inert text to a real
  `@AGENTS.md` import; COORDINATION/DECISION_LOG/REPO_STRUCTURE/PROJECT_CANON/CONVENTIONS/
  BUILD_PLAN/DEBT/DOC_DEBT reconciled to post-restructure reality incl. roadmap/status
  refresh (Phase A parser core-swap verified DONE; Qdrant→Milvus correction).

### Fixed
- `custody.reconcile_sbv_import` actor default updated to the module's real path
  (`server.tools.parsers.messaging.sbv_sms`) — verified consequence-free against live PG
  (`evidence.custody_event` held 0 rows).

## 2026-07-10

### Changed
- **ADR-0035 — tools/ sub-namespacing + record-contract home** (`8240205`, `8d65cb1`, `a299cf0`).
  `server/tools/` reorganized by capability into `parsers/{messaging,ai_chat,generic}/`,
  `extractors/`, and `gateway/` (`tool_finder` moved out of `server/evidence/`). `NormalizedRecord`
  /`RecordType`/`DisclosureTier` promoted to a new import-light `server/contracts/records.py`
  (`server/evidence/normalize.py` is now a deprecated re-export shim). Tool auto-discovery switched
  to recursive `pkgutil.walk_packages`. Behavior-neutral: 23 tool IDs unchanged, no CF
  re-registration, facade import graph verified sqlalchemy-free. Gated (ruff/mypy/pytest 208).

### Added
- `/sbv/hashes` facade route proxying SBV custody hashes (H1 file hash + H3 chain hash) for
  ContextForge federation (`abceff7`).
- Planning deliverables: `docs/planning/parser-iterations-inventory.md` (exhaustive cross-repo
  parser variant catalog), `docs/planning/agno-chunking-strategy.md` (hybrid semantic+fixed
  chunking research vs. agno 2.6.13), and `docs/planning/ui-vision/constellation-mockup.html`
  (front-end vision mockup) (`b169afb`).

## 2026-07-09

### Added
- **SBV forensic fork, Phases 1–4** — H1/H2/H3 custody hashing (raw-file, raw-element, and
  left-fold chain), hashing performed before normalization; vendored under `vendored/sbv/`
  (`826b4e6`, `c4c5c06`). Platform-tools now lifts the CI-built ghcr fork image rather than
  building from source (`c1bf2f8`).
- **Facade-collapse Batch A** — G4 tool-gateway meta-ops and the SBV toolkit exposed as agno
  `@tool`s (including `sbv_hashes`) wired into every agent (`bec5596`, `5058f63`).
- **Semantica vendored** into `server/vendored/semantica/` via relocate + symlinks (ADR-0033
  amendment) (`a496a52`, `91637b1`).
- Planning docs: facade-collapse execution plan (`63fcf17`), SBV Option-B fork plan + deferred
  TODOs (`483b524`); `docs/DECISION_LOG.md` and this `CHANGELOG.md` started (`35f9f33`, `8228dc1`).

### Changed
- **ADR-0033 `server/` repack** executed — every backend package repacked under
  `server/{api,core,agents,evidence,analysis,vendored}`; imports are now `server.*` (`e2086c2`,
  merged via PR #16 `0f701ef`). Tools + registry promoted out of `evidence/` to `server/tools/`
  (D-026) (`9bba295`, `6c410dc`).
- Repo hygiene moves: `visualizations/` → `docs/visualizations/`, `configs/` → `docker/milvus/`,
  `deploy/n8n/` → `docker/n8n/` (`09dabf0`); `.planning/build/` reframed as live
  `docs/planning/architecture-directives/` (`28e2dcb`).

### Fixed
- SBV CI: hardcode lowercase ghcr image name (`github.repository` capital-C broke push) (`7e1ad8b`).
- SBV build: drop `heic` tag (upstream libheif-go/libheif CGO drift) — HEIC bytes still ingested +
  hashed, only in-app transcode disabled (`a10c32f`).
- Retarget `test_sbv_custody` imports to `server.tools` post-move (`1956eb7`).

## 2026-07-08

### Fixed
- **agentos-mcp restored on main** — ported the entire service, `app/mcp_main.py`,
  `enable_mcp_server=True`, and `fastmcp` install from the hotfix branch (main lacked them after the
  exec tier repointed hotfix→main) (`44a55f7`, `d8f572f`, `98bec29`). `FASTMCP_HOST=0.0.0.0` fixes
  the 421 Host-allowlist bug (`d750b93`).
- agentos-api: install `pymilvus` explicitly (uv pip sync skipped its transitive deps) (`e0bccde`).
- Ported hotfix-only fixes main was missing: agent-ui pnpm9/no-frozen-lockfile/OOM Dockerfile
  guard (`6ad0c25`), ContextForge public-MCP Traefik labels (`d815e91`), coolify-mcp DNS-rebinding
  Host check disabled for tailnet bind (`c6e3e66`).
- Gateway: restore `embed-text` to `nv-embed-v1` (4096-d symmetric) — drift to 2048-d asymmetric
  had broken Graphiti Neo4j vector search (`9d48c8e`).

### Added
- coolify-write MCP deployed as an HTTP service behind ContextForge (`82cd8c8`); Lane C coordination
  ledger (`cff1cb6`).
- Restructure spec (drift audit + tiered fix + blast-radius map + illustrated report) and the
  multi-chat war-room doc; Tier 0/1 hygiene + planning consolidation (`c7e4aac`, `7bb8d49`,
  `9ca9dbf`, `f490bac`). Read-only live-ontology dump tool (`c0b21ad`).

## 2026-07-07

### Added
- ContextForge upgraded 0.8.0 → v1.0.4 (CSRF env + forced password-change gate handled) (`a617b23`).
- Portkey OSS gateway compose — LLM door, phase 1 (`9b93e1b`).

### Fixed
- Portkey healthcheck probes `/` (`/v1/health` 400s without a provider header) (`789ebe3`).
- Graphiti nginx host-fix sidecar rewrites Host to `localhost:8071` (upstream 421) (`0f2cd16`).

## 2026-07-05

### Changed
- **Data tier split** — bundled `compose.data.yaml` split into 4 independent Coolify apps
  (data-pg/neo4j/graphiti/surreal) (`d3a2207`, `902c2ed`; PRs #13/#14). All joined to a shared
  external `agno` docker network for cross-app DNS (`3038688`, `e8111b0`). Milvus
  `stop_grace_period: 60s` added to prevent etcd WAL corruption (`3307d75`).

## 2026-07-04

### Added
- Ontology seed reconciliation — live DB becomes canonical via the migration chain (`67cf27e`).
- Coercive-control classification rubric + court-safe language tooling (#11) (`6b454b7`); Nova/AWS
  coercive-control rubric as a supplementary mining source (#12) (`c4f147b`).
- Visit-locations analytics (Evidence.dev) + interactive 2023 cluster map + full-record
  transparency views (`21262cc`, `28e2102`, `dc6c241`).

### Changed
- Home parser work + forensic-db reconciliation merged (#9) (`b7739e0`, `3644d2b`).

### Fixed
- Gateway: symmetric embeddings + schema-capable Graphiti LLM (ADR-0015 amendment) (`bdde030`).

## 2026-07-01

### Added
- **Evidence-spine P1** — forensic parsers, SBV integration, PG custom types, chatminer pipeline
  (`7cb7653`); transcript-marker, messaging-CSV, iMessage, and Facebook parsers (#6) (`2b6f52e`).

## 2026-06-30

### Added
- Reconciled forensic-db schema + live migrations 0005/0006 + behavioral ontology (`86a31d0`).

## 2026-06-27

### Changed
- Split Milvus + Attu out of the bundled data-tier; fix SurrealDB healthcheck (`18c42d2`).

### Added
- Test coverage for forensic message tools + remaining chat parsers (#5) (`4851e6f`).

## 2026-06-25 – 2026-06-26

### Added
- Forensic message parsers + SBV→MCP + general OCR pass; pin ContextForge 0.8.0 (`702c300`).
- First-party test suite wired into CI, plus parser/registry/store/artifact unit tests
  (`39d2d81`, `6cad5c8`, `b36917f`, and follow-ups).

### Changed
- Drop the PG Multicorn FDW federation hub (ADR-0032) (`2f02bfa`); SBV/messaging parsers +
  agent-layer rewrite + federation ADRs (`c3ef1e8`).

### Fixed
- mypy passes across real and optional deps (stub ignores for OCR/HTML/ML libs); PR-review fixes for
  source-hint misrouting and a test-helper off-by-one (`889d632`, `534127e`, `324117d`, `ab50b2a`,
  `94bb0f4`).

### Docs
- Document required `R2_ACCOUNT_ID` in `example.env` (ADR-0030) (`f72e66c`).

## 2026-06-14

### Added
- PG federation hub + rich domain types (Multicorn FDW layer) (`bb08045`); SurrealDB as the Agno
  operational store + staged Milvus configs (`700eefe`); self-hosted agent-ui chat surface
  (`99fd637`).

### Changed
- Rewire deploy composes for the OVH-3 data-tier topology (`71d1f62`).

## 2026-06-13

### Added
- **Initial platform snapshot** — SSOT docs, ChatMiner vendoring, schema-crux scaffolding, agent
  handoffs (`ebcdc62`).
- Architecture decisions ADR-0023 – ADR-0027: universal API+MCP exposure principle + SurrealDB store
  layer (`cec863b`, `6fb5ff5`); self-hosted Milvus as the shared semantic store, off EU Zilliz
  (ADR-0026) (`ae1aec0`); Milvus as the platform-wide vector/ANN substrate incl. the Knowledge
  engine (ADR-0027), repointing Agno Knowledge pgvector → Milvus (`5778dd9`, `e360b35`).
- Split the deploy compose into data + exec tiers for Coolify (`7d26592`).

### Fixed
- Move the platform-tools host port off 8080 (Coolify/Traefik collision) (`6a6abef`).
