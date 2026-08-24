# Investigation: 16 Pending Deletions in Legal-Workspace

**Date:** 2026-08-23  
**Investigator:** Claude Code · Haiku 4.5  
**Status:** SAFE (with caveats)

---

## Verdict

**SAFE — Copies exist elsewhere. No content loss on commit.**

However, this is a **partial/incomplete move operation** that violates the user's standing rule: "never delete — move to a stale/archive directory instead." The files exist in backups (`Legal-desktop/`), but the deletion is not paired with an explicit move to a `_stale/` directory in the Legal-Workspace repo itself.

---

## Findings

### 1. Git History: No Prior Deletion Pattern

**Query:** `git log --diff-filter=D --name-only -20 -- docs/planning/original-context/`

**Result:** No commits show prior deletions in this area. This is a **one-off event**, not part of a history of pruning.

---

### 2. Files Still Exist Elsewhere (Confirmed Backups)

All 15 deleted planning files exist in `Legal-desktop/` (a sibling directory tree):

**Sources and skills files** (4 files):
- `Legal-desktop/Sources and skills/Casememory — M0–M3 Scaffold.md` ✓
- `Legal-desktop/Sources and skills/FM16frontmatter.md` ✓
- `Legal-desktop/Sources and skills/M1casestagejurisdictiontriage.md` ✓
- `Legal-desktop/Sources and skills/M2standardsthatdecideyourcase.md` ✓

**Artifacts (3) files** (11 files):
- `Legal-desktop/artifacts (3)/Agno Platform — Interface & Integration Analysis.md` ✓
- `Legal-desktop/artifacts (3)/Bloomberg + Legal Terminal Feature Catalog.md` ✓
- `Legal-desktop/artifacts (3)/HANDOFF — Category 1–7 (7 files)` ✓
- `Legal-desktop/artifacts (3)/Legal OS — Feature Decision Matrix.md` ✓
- `Legal-desktop/artifacts (3)/Legal Terminal & Legal MCP — Deep Analysis (Part 1).md` ✓

**Result:** **All 15 files are backed up in `Legal-desktop/`.** Content is not lost.

---

### 3. Current State: Partial Move Operation In-Flight

The 16 deletions represent an **incomplete move**, not a true deletion:

- **Subdirectories deleted:** `Sources and skills/` and `artifacts (3)/` are gone.
- **Files relocated:** The files now appear as **untracked** at the root of `docs/planning/original-context/`:
  - `docs/planning/original-context/Agno Platform — Interface & Integration Analysis.md` (untracked)
  - `docs/planning/original-context/HANDOFF — Category 1–7 (7 files)` (untracked)
  - etc.
- **Subdirectory structure removed:** No `Sources and skills/` or `artifacts (3)/` subdirectories remain.

**Interpretation:** The files were **manually moved up one level** (from subdirectories to root), but the deletions were not paired with a proper `_stale/` backup as the user's rule requires.

---

### 4. No Authorization in Documentation

**Searched:**
- `docs/URGENT-TODO.md` — No mention of deleting planning/original-context files.
- `docs/HANDOFF-2026-08-19-*.md` — No mention.
- `docs/COMPACT-SUMMARY-2026-08-*.md` — One relevant line found (see below).

**Found reference in COMPACT-SUMMARY-2026-08-18.md:**
```
git rm -r --cached docs/planning/original-context/` was blocked by case-bible hook 
for hard-delete. Fixed by using `git rm --cached --ignore-unmatch` on individual files.
```

This refers to **removing files from the git index** (staging area), not deleting them from disk. There is no explicit authorization to delete the planning source material itself.

---

### 5. `web/package-lock.json` — Known Issue (URGENT-TODO B6)

**Status:** UNSAFE BUILD REPRODUCIBILITY (but documented).

**URGENT-TODO.md — Item B6 (exact quote):**
```
| B6 | `web/package-lock.json` deleted, not regenerated | `deploy/Dockerfile.web` 
uses `npm install` (not `npm ci`), so builds succeed but are **not reproducible** 
— dependency drift between builds is silent. | **OPEN.** |
```

**Dockerfile.web confirmation:**
```dockerfile
5:RUN npm install          ← Uses npm install, not npm ci
```

**Impact:**
- `npm install` allows dependency resolution flexibility; it can pick different (compatible) versions between builds.
- `npm ci` (CI install) reads `package-lock.json` and installs exact versions — reproducible builds.
- **Without `package-lock.json`, every build can drift silently.**

**This deletion is a **known defect**, not an authorization.** It must be regenerated before any production deploy.

---

## At-Risk Files (Content Would Be Lost Without `Legal-desktop/` Backup)

If all copies in `Legal-desktop/` were also deleted, the following would be lost:

1. `Casememory — M0–M3 Scaffold.md`
2. `FM16frontmatter.md`
3. `M1casestagejurisdictiontriage.md`
4. `M2standardsthatdecideyourcase.md`
5. `Agno Platform — Interface & Integration Analysis.md`
6. `Bloomberg + Legal Terminal Feature Catalog.md`
7. `HANDOFF — Category 1: Persistence & Settings.md`
8. `HANDOFF — Category 2: Command Bar & UI Shell.md`
9. `HANDOFF — Category 3: Chat & AI Agent Orchestration.md`
10. `HANDOFF — Category 4: Research Tools.md`
11. `HANDOFF — Category 5: Contract & Document Analysis.md`
12. `HANDOFF — Category 6: Privilege, Privacy & LLM Routing.md`
13. `HANDOFF — Category 7: Workflow & Automation Engine.md`
14. `Legal OS — Feature Decision Matrix.md`
15. `Legal Terminal & Legal MCP — Deep Analysis (Part 1).md`
16. `web/package-lock.json`

---

## Rule Violation Assessment

**User's standing rule (from memory):**  
> "HARD RULE — never delete — move to a stale/archive directory instead."

**Status:** **Violated.** The deletions are:
1. Not paired with a move to `Legal-Workspace/_stale/`.
2. Left untracked in the working directory instead of being quarantined.
3. Not documented in any authorization ledger.

The fact that backups exist in `Legal-desktop/` prevents data loss, but the **process** does not comply with the user's "always move, never delete" discipline.

---

## Recommendation

**Before committing:**

1. **Restore the move operation properly:**
   - Move the untracked files from `docs/planning/original-context/` root to `Legal-Workspace/_stale/original-context-relocated-2026-08-23/`.
   - Or move them back to their original subdirectories and properly authorize their removal.

2. **Regenerate `web/package-lock.json`:**
   - Run `npm install --package-lock-only` in the `web/` directory.
   - Commit the lockfile to ensure reproducible builds.

3. **Document the decision:**
   - Add a line to `docs/URGENT-TODO.md` or `docs/HANDOFF-*.md` explaining why `original-context/` subdirectories were consolidated (if that was intentional) and where the canonical copies live.

---

**Byline: Claude Code · Haiku 4.5 · 2026-08-23**
