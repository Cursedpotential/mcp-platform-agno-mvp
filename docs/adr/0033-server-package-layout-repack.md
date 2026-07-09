# ADR-0033: `server/` package layout (Option A repack)

- Status: Accepted
- Date: 2026-07-09
- Deciders: owner + Lane A
- Supersedes-in-part: `docs/REPO_STRUCTURE.md` root layout (to be updated to match)
- Refs: `docs/planning/repo-restructure-spec.md` (§Tier 3, blast-radius map, runbook),
  `docs/DECISION_LOG.md` D-025, `docs/planning/restructure-report.html`

## Context

The repo drifted into **eight flat sibling Python packages at the root** (`app`, `agents`,
`db`, `evidence`, `gateway`, `tools`, `chatminer`, `evals`) whose boundaries are historical,
not architectural: `app` vs `agents` vs `db` are incidental splits, the behavioral-analysis
domain (`detection`, `patterns`, `court_language`, `milvus_forensic`, `semantica_wiring`) is
dumped inside the evidence spine, and `gateway`/`tools` are strays. The prior iteration
(`TheBigOne/01_MCP_Tool_Platform_Repo`) had the discipline this lacks: one backend boundary
(`server/`) with interface/domain separation inside it.

## Decision

Repack every backend Python package under a single **`server/`** boundary with
domain-separated sub-packages (Option A; owner-locked 2026-07-09):

```
server/
  api/        FastAPI entrypoint + HITL/knowledge/MCP routes      (was app/)
  core/       settings, db session, embedder, reranker            (was db/ + app/settings.py)
  agents/     factory, providers, instructions                    (was agents/)
  evidence/   THE SPINE only: custody, registry, normalize, store,
              workflows, cli, tools/, tool_finder/                 (tool_finder was gateway/)
  analysis/   detection, patterns, court_language, milvus_forensic,
              semantica_wiring                                     (extracted from evidence/)
  vendored/
    chatminer/  vendored parser core (import-only)                (was chatminer/)
ui/           CopilotKit shell (G1) — DEFERRED, not built yet
shared/       cross-boundary contracts — created only when ui/ needs them (DEFERRED)
```

- `tools/` (cross-domain `extract_text`) folds into `server/evidence/tools/`; the registry's
  second auto-discovery loop retargets accordingly.
- The move is **behavior-neutral** — code only; no logic, schema, or data changes (Lane B's
  freeze holds).

## Consequences

- Every backend import becomes `server.*`; ~200 sites rewritten (import-statement-scoped) and
  guarded by the 186-test suite + ruff + mypy. Path-depth constants (`patterns.py::_REPO`,
  `chatminer` sys.path hack, config-relative paths in `analysis/`) fixed in the same change.
- Deploy-coupled surfaces move in lockstep in ONE commit: uvicorn entrypoint
  (`app.main:app` → `server.api.main:app`) in Dockerfile + compose ×3, Dockerfile `COPY`,
  `pyproject` packages + mypy, DEPLOY RUNBOOK tar list. Proven with a local `podman build` of
  the exec image before merge (exec tier auto-deploys from `main`, D-011).
- `REPO_STRUCTURE.md` is updated to describe `server/` as the one backend boundary.

## Alternatives considered

- **Option B — 8→5 consolidation, no `server/` parent** (extract `analysis/`, dissolve
  `gateway/`, fold `tools/`, vendor `chatminer/`): ~40 import sites, captures domain
  separation but not the single-boundary win. Rejected — the owner wants the old design's
  one-boundary discipline.
- **Leave as-is / `src/` layout**: rejected (drift persists / cosmetic nesting with churn).
