# Spec-Driven Development Process

**Status:** active guidance, updated for the wiki-first documentation model

---

## Core Principle

**No meaningful implementation work without a documented plan and traceable decision context.**

That does not require reviving legacy root `.planning/` paths. Current planning and architecture truth now live inside the repo and wiki.

## Current Documentation Hierarchy

Read and update these locations first:

| Location | Purpose |
|----------|---------|
| `CLAUDE.md` | project operating rules |
| `AGENTS.md` | repo-level architecture and agent guidance |
| `docs/.audit/2026-03-30-source-classification.md` | source hierarchy and conflict resolution |
| `docs/memory/MEMORY.md` | short bootstrap for current truth |
| `docs/plans/ROADMAP.md` | active sprint and backlog direction |
| `docs/wiki/architecture/ARCHITECTURE.md` | active architecture reference |
| `docs/wiki/architecture/TOOL_CATALOG.md` | current tool inventory/status |
| `docs/wiki/.plannotator/` | in-repo planning history, approved plans, annotations, and transcripts |
| `docs/wiki/archive/` | superseded and historical material |

## Required Process

### 1. Orient

Before changing code:

1. read the current roadmap and architecture docs
2. check source classification if planning sources conflict
3. verify current implementation in code
4. identify whether the work is `implemented`, `partial`, `planned`, or `historical`

### 2. Plan

Before substantial changes:

1. document the intended change in the relevant active doc, spec, audit note, or planning note
2. tie the change back to current MVP or architecture direction
3. call out risks to evidence handling, provenance, or storage correctness

### 3. Implement

During changes:

1. preserve first-touch evidence integrity
2. do not bypass coordinator/tool paths for evidence operations
3. keep source truth and downstream analysis clearly separated
4. prefer existing trusted tools and OSS before new custom code

### 4. Verify

After changes:

1. test the changed path
2. update the active doc(s) that now describe reality
3. archive superseded docs under `docs/wiki/archive/` instead of deleting context

## Evidence-Specific Non-Negotiables

1. DuckDB-first intake for evidence-bearing artifacts
2. hashing and stable linkage at first touch
3. provenance must survive storage and analysis
4. planned or placeholder features must not be documented as complete

## Historical Note

Older `.planning/*` references are historical only. User-root planning material that mattered has been moved into the worktree, primarily under:

- `docs/wiki/.plannotator/`
- `docs/wiki/archive/.planning/`
- `docs/wiki/archive/user-root/.planning/`

---

**Last Updated:** 2026-03-30
