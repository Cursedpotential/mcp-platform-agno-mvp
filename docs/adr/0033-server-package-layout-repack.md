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

## Amendment 2026-07-09: tools + registry promoted to `server/tools/`

This ADR originally landed the atomic-tools capability layer + registry *nested inside* the
evidence spine (`server/evidence/tools/`, `server/evidence/registry.py`) — see the "Decision"
layout above. That undersold the layer's actual shape: tools are **cross-domain**, consumed by
evidence, analysis, agents, workflows, and the CLI alike, not evidence-owned. D-026 promotes
them one level up to a top-level sibling of `evidence/`:

```
server/
  evidence/   THE SPINE only: custody, normalize, store, workflows, cli, tool_finder/
  tools/      CROSS-DOMAIN CAPABILITY LAYER: registry.py + atomic tool modules (was
              server/evidence/tools/ + server/evidence/registry.py)
```

`git mv server/evidence/tools server/tools` + `git mv server/evidence/registry.py
server/tools/registry.py`; import-statement-scoped rewrite of `server.evidence.tools` ->
`server.tools` and `server.evidence.registry` -> `server.tools.registry` across the repo
(same reuse of this ADR's rewrite approach); `server/evidence/__init__.py`'s PEP-562 `_LAZY`
dict re-points `registry`/`ToolRegistry` at `server.tools.registry` for back-compat. The
registry's two near-identical auto-discovery loops (one a leftover from the pre-repack
top-level `tools/` merge) collapsed into one loop, made package-name-agnostic (`__package__`
instead of a hardcoded dotted path — needed for the facade container below); intra-package
imports inside `server/tools/*.py` (of `registry`, `_common`, `_chatminer_adapter`, sibling
parser modules) converted from absolute to relative so the same source resolves under either
import root.

Also fixed, same change: `compose.yaml`/`compose.exec.yaml` still mounted
`./evidence:/opt/tools/evidence:ro` for the `docker/tools` platform-tools facade — a host path
that stopped existing the moment this ADR's Option A repack landed (it moved to
`server/evidence/`), so the facade silently served **zero** parser modules. Mount + facade
import path made consistent — but NOT with the narrowest `server/tools`-only mount first
tried: `server.tools.*` has real transitive deps outside itself
(`server.evidence.normalize` for the schema, `server.vendored.chatminer` for the parser core;
both lightweight, no sqlalchemy/agno at import time), so a `server/tools`-only mount left
`load_builtin_tools()` raising `ModuleNotFoundError: No module named 'server'` on the first
tool module that touches either dependency — confirmed by simulating the container's actual
(isolated, no editable install) import graph. Final fix mounts the **whole `server/` tree**:
`./server:/opt/tools/server:ro`, with `docker/tools/tools/facade.py` importing plain
`server.tools.registry` / `server.tools._sbv_client` — the same import path the main app uses,
no container-only alias needed. Verified: the isolated simulation loads all 23 tools. See
`docs/DECISION_LOG.md` D-026 and `docs/REPO_STRUCTURE.md`.
