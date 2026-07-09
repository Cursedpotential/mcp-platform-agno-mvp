# Repo Restructure — Drift Audit & Tiered Fix

> _Byline: Claude Code · Fable 5 · 2026-07-08_
> Status: **DRAFT for owner annotation** (Plannotator: `/plannotator-annotate docs/planning/repo-restructure-spec.md`
> or `./scripts/annotate-plans.sh docs/planning/repo-restructure-spec.md`).
> Companion: `docs/REPO_STRUCTURE.md` (the contract this restores), `docs/HANDOFFS.md` Track G,
> `gui-integration-spec.md`. Owner complaint (2026-07-08): root is "messy and unstructured,
> doesn't match the original design or the unified-platform goal."

## 0. Thesis

`docs/REPO_STRUCTURE.md` is a good contract — the root just drifted from it. The fix is
mostly **enforcement + a small contract amendment**, not a redesign. Everything below is
`git mv`/delete/gitignore; no Python imports change in Tiers 0–1.

## 1. Drift inventory (audited 2026-07-08)

### 1a. Untracked cruft (~580 MB)
| Item | What | Verdict |
|---|---|---|
| `.venv.broken-20260626/` (229 MB) | dead venv | DELETE (regenerable artifact) |
| `.venv.stale-20260705/` (348 MB) | dead venv | DELETE (regenerable artifact) |
| `.mypy_cache/ .pytest_cache/ .ruff_cache/ .osgrep/` | tool caches | keep (regenerated); ensure gitignored |
| `agent_platform.egg-info/` | build artifact | delete + add `*.egg-info/` to .gitignore |
| `.memsearch/ .remember/` | recall-lane fragments from subdir-opened sessions | MERGE up into the workspace-root lanes (`../.memsearch/`, `../.remember/`), then remove in-repo copies. Same disease as the auto-memory fragmentation fixed 2026-07-08 |

### 1b. Planning scatter (4 homes → 1)
| Item | Contents | Verdict |
|---|---|---|
| `docs/planning/` | the real planning home (specs, forensic-db trees, backlog) | **CANONICAL — everything consolidates here** |
| `plans/` | EMPTY (contract sanctioned it; nothing uses it) | remove; contract drops it |
| `goals/` | 2 stale goal-runner dirs (June 19: agno-mvp-boot-ingest, evidence-platform-buildout) | `git mv` → `docs/planning/goals-archive/` |
| `.planning/` (untracked) | `build/`, README | fold anything current into `docs/planning/`; rest → `../_stale/` per never-delete rule |

### 1c. Orphan tracked dirs (contract never named them)
| Item | Reality | Verdict |
|---|---|---|
| `configs/` | Milvus `embedEtcd.yaml` + `user.yaml` (mounted by `compose.data-vector.yaml`) | `git mv` → `docker/milvus/` + update compose mount paths **same commit**. ⚠ VPS coordination: OVH-3 bind-mounts these paths — sync + `docker compose up -d` on the data host must follow, or next redeploy breaks |
| `deploy/n8n/` | n8n compose + README | `git mv` → `docker/n8n/`; drop empty `deploy/` (same VPS caveat if n8n is live) |
| `tests/` | the real pytest suite (182 tests) | KEEP at root; **amend contract** to name it |
| `chatminer/` | vendored parser core (10 parsers + segmenters), imported by `evidence/tools/_chatminer_adapter` | KEEP at root (it's an importable package; moving = churn for zero gain); **amend contract** as "vendored packages live at root, one dir per vendor" |
| `tools/` | cross-domain platform tools (`extract_text`), auto-discovered by registry | KEEP (deliberate design: cross-domain ≠ evidence-domain); **amend contract** |
| `gateway/` | my G4 build (content-store + tool-finder FastAPI) — **diverges from the owner's locked G4 spec** (`evidence/tools/tool_finder/`, SQLite ref store, execute-through-CF) | Tier 2: adapt to the locked spec during Track G G4; `gateway/` dissolves into `evidence/tools/tool_finder/` |
| `compose.data.yaml / compose.data-vector.yaml / compose.exec.yaml` | multi-VPS topology split (deliberate, post-contract) | KEEP; **amend contract** (contract still says "one compose.yaml with profiles" — stale) |
| `visualizations/` | visit-locations map (PR #7) | KEEP; amend contract (or move under `docs/`? — **owner call**) |
| `.github/` | CI | KEEP; amend contract |

### 1d. Root file sprawl (minor)
`requirements.txt` is generated (`scripts/generate_requirements.sh`) — fine. `uv.lock` +
`pyproject.toml` — fine. `example.env`, `.mcp.json`, `.gitattributes` — fine. No action.

## 2. The unified-platform target shape (post-Track-G)

```
Agno-MCP-Platform/
  app/           AgentOS API (FastAPI entrypoint)
  ui/            ← G1: CopilotKit/Next.js shell (LOCKED: in-repo)
  agents/        agent/team constructors
  evidence/      THE SPINE (custody→parse→normalize→store) + tools/ + tool_finder/ (G4)
  chatminer/     vendored parser core (import-only)
  tools/         cross-domain atomic tools
  db/            connections, embedder, reranker
  sql/           numbered migrations (incl. promoted 0005/0006 after seed reconciliation)
  docker/        one dir per service image (+ milvus/, n8n/ after Tier 1)
  compose*.yaml  the 4-file multi-host topology (contract-amended)
  evals/  tests/  scripts/  knowledge/  visualizations/
  docs/          canon + 5 authoritative docs + adr/ + planning/ (THE one planning home) + wiki/
```

## 3. Execution tiers

### Tier 0 — hygiene (no tracked files; ~580 MB reclaimed)
1. Delete `.venv.broken-20260626/`, `.venv.stale-20260705/`, `agent_platform.egg-info/`.
2. `.gitignore` += `*.egg-info/`, `.osgrep/` (verify caches covered).
3. Merge `.memsearch/` + `.remember/` fragments into the workspace-root lanes; remove in-repo copies.

### Tier 1 — consolidation (one commit, `git mv` only + compose path edits)
4. `git mv goals docs/planning/goals-archive`
5. Fold `.planning/` → `docs/planning/` (current) / `../_stale/` (dead); `git rm -r plans` if tracked-empty.
6. `git mv configs docker/milvus` + fix mounts in `compose.data-vector.yaml`.
7. `git mv deploy/n8n docker/n8n`; remove `deploy/`.
8. ⚠ **Deploy gate:** items 6–7 change paths the data-tier VPS bind-mounts. Do NOT sync to the VPS without re-upping the affected services in the same window.

### Tier 2 — contract + structure (folds into the existing queue)
9. Amend `docs/REPO_STRUCTURE.md`: add tests/, chatminer/, tools/, visualizations/, .github/, the compose split, `ui/` (G1), `evidence/tools/tool_finder/` (G4); drop `plans/`. One rev, same commit as an ADR note.
10. `gateway/` → locked G4 spec (`evidence/tools/tool_finder/` + SQLite ref store + execute-through-CF) — **inside Track G G4**, not a standalone move; tests move with it.
11. Seed reconciliation (already queued): promote applied 0005/0006 into `sql/`, retire P2.1 tables.

### Tier 3 — CODE REPACK (rev 2, owner escalation 2026-07-08)

> Owner: the complaint isn't just docs/planning scatter — "the overall Agno project
> structure" lacks the discipline of the previous iteration. Audit of that iteration
> (`dev-resources/Archives/TheBigOne/01_MCP_Tool_Platform_Repo`) confirms what it did right:

**The old design's virtues** (client/server/shared top split):
- **ONE backend boundary** — everything server-side lives under `server/`, not N sibling packages
- **Interface/domain separation inside it** — `server/api/` (routers) vs `server/core/` (types,
  routing) vs `server/mcp/<domain>/` — 22 domain dirs (analysis, forensics, storage,
  orchestration, observability, auth, hitl, prompts, stats, …), one concern each
- **Co-located tests** (`server/tests/`), schemas in one place (`drizzle/`), `shared/` types

**The current repo's failure mode:** 8 sibling Python packages at root (`app`, `agents`,
`db`, `evidence`, `gateway`, `tools`, `chatminer`, `evals`) with no expressed hierarchy —
`app` vs `agents` vs `db` boundaries are historical, not architectural; analysis-domain code
(`detection`, `patterns`, `court_language`, `milvus_forensic`, `semantica_wiring`) is dumped
inside `evidence/` (the spine) rather than owning a package; `gateway`/`tools` are strays.

**Target shape — Option A (full repack, mirrors the old design; RECOMMENDED):**
```
Agno-MCP-Platform/
  server/                       ONE Python backend package
    api/                        FastAPI entrypoint + HITL/knowledge routes   (was app/)
    core/                       settings, db session, embedder, reranker    (was db/ + app/settings.py)
    agents/                     factory, providers, instructions             (was agents/)
    evidence/                   THE SPINE only: custody, registry, normalize,
                                store, workflows, cli, tools/, tool_finder/  (G4 lands here)
    analysis/                   the BEHAVIORAL/ANALYSIS domain: detection,
                                patterns, court_language, milvus_forensic,
                                semantica_wiring                              (extracted from evidence/)
    vendored/
      chatminer/                vendored parser core (import-only)           (was chatminer/)
  ui/                           G1 CopilotKit shell (LOCKED in-repo)
  shared/                       cross-boundary contracts if/when needed (JSON schemas, court_safe map?)
  sql/  docker/  compose*.yaml  evals/  tests/  scripts/  knowledge/  docs/  visualizations/
```
- `tools/` (cross-domain `extract_text`) → `server/evidence/tools/` or `server/analysis/` per
  capability — registry auto-discovery updated accordingly.
- Imports become `server.evidence.…` etc. — mechanical rewrite, ~200+ sites, fully guarded by
  the 186-test suite + ruff + mypy.

**Blast-radius map (audited 2026-07-08 — the exact touch-list for the repack RUNBOOK):**
| Surface | Sites | Change |
|---|---|---|
| `uvicorn app.main:app` entrypoint | `Dockerfile:32`, `app/main.py:178`, `compose.yaml:39`, `compose.exec.yaml:39` | → `server.api.main:app` — **must move in the SAME commit** (Lane C: exec-tier auto-deploys from main; a lagging entrypoint = failed redeploy) |
| Registry auto-discovery **string** module paths | `evidence/registry.py:127` (`f"evidence.tools.{mod.name}"`), `:136` (`f"tools.{mod.name}"`) | → `server.evidence.tools.*`; the cross-domain `tools/` merges into `server/evidence/tools/` or `server/analysis/`, so the second loop's target changes too |
| Lazy PEP-562 export | `evidence/__init__.py:45` (`importlib.import_module`) | path-relative, moves with the package — verify |
| `chatminer` sys.path hack | `chatminer/cli/main.py:46` (`parent.parent.parent`) | depth changes under `server/vendored/chatminer/` → `parent.parent.parent.parent` (or drop the hack, rely on package install) |
| Dockerfile `COPY` source paths | `Dockerfile`, `docker/*/Dockerfile` | every `COPY app/ … / COPY evidence/ …` → `COPY server/ …`; **keep `docker/` config paths stable** (gateway bakes `docker/gateway/litellm-config.yaml` — do NOT move those) |
| `pyproject.toml` packages + mypy paths | `[tool.setuptools]`/`[tool.hatch]` package globs, `[tool.mypy]` | repoint to `server/*` |
| DEPLOY RUNBOOK tar list | `docs/HANDOFFS.md` runbook, `scripts/*` | `tar czf … chatminer evidence …` → `server` |
| Test imports | `tests/*.py` (`from evidence…`, `from gateway…`) | rewrite; tests stay at root `tests/` |
| `agents/`, `db/`, `app/settings.py` internal cross-imports | ~40 sites | rewrite to `server.*` |

**Execution note (why NOT a long-lived branch):** every day this sits as a branch, Lane B's
`.py` edits and Lane C's `docker/` edits diverge from it → escalating rebase pain. So the repack
is a **single-window RUNBOOK** (below), run when B's schema brainstorm has landed and C can
watch the redeploy — not an open PR held for a week.

**Repack RUNBOOK (one sitting, ~1–2h, all-or-nothing):**
1. Announce in `docs/COORDINATION.md`; ask B+C to pause commits for the window.
2. `git mv` packages into `server/{api,core,agents,evidence,analysis,vendored/chatminer}` + merge `tools/` per capability.
3. Global import rewrite (scripted: `evidence.→server.evidence.`, `app.→server.api.`, `agents.→server.agents.`, `db.→server.core.`, `tools.→server.evidence.tools.`, `chatminer→server.vendored.chatminer`), then hand-fix the registry string-path loops + chatminer sys.path depth.
4. Update entrypoint (4 files), Dockerfiles' COPY, pyproject packages+mypy, HANDOFFS tar list.
5. Gates: `ruff format/check`, `mypy`, `uv run python -m pytest` (186), `uv run python -m evidence…→server.…` smoke, and a **`docker build`** of the exec image locally to prove the redeploy won't fail.
6. One commit, PR, owner+C review, merge in a watched window; C confirms exec-tier redeploy green.
- **Blast radius (why this is one atomic PR, done in a quiet window):** pyproject packages +
  mypy paths, Dockerfiles' COPY paths, `uvicorn server.api.main:app`, compose mounts,
  tools-facade image bake list, DEPLOY RUNBOOK tar list, scripts. VPS needs a full re-sync +
  image rebuild after merge (images rebuild on deploy anyway).
- **Sequencing:** do this BEFORE G1 (`ui/` lands into the clean shape) and AFTER the seed
  reconciliation (so migrations move once). One PR, all gates green, no behavior change.

**Option B (lighter, if A feels too invasive):** keep top-level packages but consolidate
8 → 5: extract `analysis/` out of `evidence/`, dissolve `gateway/` into the G4 home, fold
`tools/` into `evidence/tools/`, move `chatminer/` under `vendored/`. No `server/` parent,
~40 import sites instead of ~200. Captures the domain-separation virtue, not the
one-boundary virtue.

## 4a. Already decided & DONE — do NOT annotate (recorded so nothing gets re-litigated)
> These were open at draft; Lane A acted on them the same session. Listed here only so the
> trail is honest — you should not have to make a call on any of them.
- **Q2 `.planning/build/`** → these are **live architecture DIRECTIVES** (owner: "most of that
  was good directives"), not dead notes. Moved to `docs/planning/architecture-directives/`
  (June-14 ContextForge/SurrealDB/DNS/topology set) with an `INDEX.md` mapping each to its lane;
  reconcile against live infra, don't discard. NOT `_stale`.
- **Q4 dead venvs** → hard-deleted (`.venv.broken-20260626`, `.venv.stale-20260705`, ~577 MB;
  regenerable via `uv sync`, NOT source, so the never-delete rule doesn't apply). Recall-lane
  fragments (`.memsearch/.remember`) went to `../_stale/` instead (those aren't regenerable).

## 4b. DECIDED 2026-07-09 (owner, via questions while driving)
- **Q1 `visualizations/`** → **DONE:** moved to `docs/visualizations/`.
- **Q3 VPS-path moves** → **DONE (branch), deploy-neutral:** `configs/`→`docker/milvus/`,
  `deploy/n8n/`→`docker/n8n/`. Finding: compose mounts Milvus configs from ABSOLUTE VPS host
  paths (`/data/agno/config/milvus/…`), not the repo — the repo copy is only the scp SOURCE, so
  **no re-up is actually required** (scp comment repointed in `compose.data.yaml`). ⚠ Lane C:
  confirm nothing deploys n8n directly from the old `deploy/n8n/` path.
- **Q5 Repack scope** → **Option A LOCKED** (full `server/` repack).
- **Q6 Repack timing** → **repack proceeds; UI/G1 DEFERRED.** Do the repack in its coordinated
  window (after Lane-B brainstorm, Lane-C watching the redeploy); do NOT rush `ui/`. So the
  repack no longer sequences "before G1" — G1 is decoupled and deferred.
- **Q7 `shared/`** → **wait** (create only when `ui/` needs shared types; consistent with
  deferring UI).

> Repack (Q5/Q6) stays a RUNBOOK, still NOT executed here — it moves ~200 import sites + the
> uvicorn entrypoint + Dockerfile COPY, and merging auto-deploys the exec tier, so it needs the
> keyboard-present coordinated window (§Tier 3 RUNBOOK), not a drive-by branch push.

## 5. Non-goals
- No `src/`-layout-for-its-own-sake — Tier 3 Option A is a DOMAIN repack, not cosmetic nesting.
- No parallel-stack anything (contract §"one active build" stands).
- No renaming the repo or the deployed images.
- Old-design pieces we deliberately do NOT copy: its tRPC data layer (dead), `.manus/` platform
  coupling, MySQL/drizzle schema home (ours is `sql/`), and its 22-dir granularity on day one —
  domains earn a dir when they have >1 module.
