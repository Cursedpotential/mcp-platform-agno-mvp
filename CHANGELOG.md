# Changelog

All notable changes to Agno-MCP-Platform are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
decisions behind changes live in [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md).

> **TODO (backfill):** this log was started 2026-07-09. Entries before that date are
> not yet reconstructed from git history — backfill from tags/PRs when there's time.
> Going forward, add an entry per merge under `[Unreleased]`, then cut a dated section
> on release.

## [Unreleased]

### Changed (branch `restructure/option-a`, not yet merged)
- Repo structure: `visualizations/` → `docs/visualizations/`; `configs/` → `docker/milvus/`;
  `deploy/n8n/` → `docker/n8n/` (deploy-neutral — Milvus configs mount from absolute VPS paths).
- Planning consolidation: `goals/`, `.planning/`, `plans/` → `docs/planning/`; the old
  `.planning/build/` set surfaced as `docs/planning/architecture-directives/` (live directives).

### Added
- `docs/COORDINATION.md` — multi-chat (Lane A/B/C) war-room ledger.
- `docs/DECISION_LOG.md` — running design/decision log.
- `docs/planning/repo-restructure-spec.md` + `docs/planning/restructure-report.html` — the
  restructure plan, blast-radius map, `server/` repack runbook, and illustrated report.
- `scripts/dump_live_ontology.py` — read-only live ontology dump (→ gitignored `live-dumps/`).

### Removed
- Dead virtualenvs (`.venv.broken-*`, `.venv.stale-*`, ~577 MB) and stray `*.egg-info`.

### Verified (no change, recorded)
- Seed/ontology reconciliation: live == `0007` prefix of the committed migration chain
  (186 tests green, live smoke 5/5).

### Pending (decided, not executed)
- Full `server/` repack (Option A) — runbook queued for a coordinated window (auto-deploy gate).
