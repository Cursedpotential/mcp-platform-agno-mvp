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

## 4. Open questions (annotate these)
- Q1 `visualizations/` — keep at root or move under `docs/`/future `ui/public/`?
- Q2 `.planning/build/` — anything in there still live, or all `_stale/`?
- Q3 Tier-1 deploy gate — do items 6–7 now and coordinate the VPS re-up, or defer them to the next VPS window (G2/G3) and do only 4–5 now?
- Q4 Are the two dead venvs safe to hard-delete (they're regenerable artifacts), or move to `../_stale/` per the never-delete rule?

## 5. Non-goals
- No `src/` layout migration (import churn across every module for aesthetics — not worth it).
- No moving `chatminer/`/`tools/` (working packages, contract amends around them).
- No parallel-stack anything (contract §"one active build" stands).
