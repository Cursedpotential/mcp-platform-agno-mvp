# Verification of Prior Rulings — Review Findings

**Date of review:** 2026-08-23  
**Scope:** Agno-MCP-Platform (primary) + Legal-Workspace (Q6 only)  
**Status per each question below**

---

## Q1 — Migration 0026–0030 Cutover Decision

**RESOLVED with activation HELD**

- **Ruling:** DECISION_LOG D-066 (2026-08-18, Codex · GPT-5)
- **Verbatim:** "Evidence vectors leave Agno's JSON-metadata schema for a native, immutable Weaviate V1 collection… Migrations `0026`–`0029`, collection creation, production backfill, alias movement, reader rebinding, and deployment remain held. rel: **ADR-0059**, ADR-0040, D-042, D-065; runbook `docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md`." Status: "accepted design; **activation held**."
- **File:line:** `docs/DECISION_LOG.md:20`
- **Key sub-ruling (D-065, same date):** "accepted; owner ruling 2026-08-18; **activation still held**" — further narrows the horizon clock formula via ADR-0059.
- **Finding:** A cutover DECISION was made (D-066 ACCEPTED 2026-08-18); a **GO order / activation gate** has not yet been issued. The runbook exists and migrations are ROLLBACK-VALIDATED (ready to apply on signal). Migrations `sql/0026`–`sql/0030` all bear "HELD FOR OWNER / NOT APPLIED" banners and remain unapplied.

---

## Q2 — Matter MVP Decisions (P1–P5, R1–R6, A1–A4)

**PARTIALLY RESOLVED; Multiple Items PENDING OWNER RULING**

- **Document:** `docs/pending-review/plans/PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md`
- **Status (line 5):** "PENDING OWNER RULING — review packet only; not an ADR and not implementation authority"
- **ADR-0055 (D-060, 2026-08-15):** ACCEPTED; covers Matter/CourtCase identity boundary — answers the STRUCTURAL question ("one Matter, many CourtCases, preserve single-owner scope") but DOES NOT answer the 15 subsidiary P/R decisions in the pending doc.
- **File:line:** 
  - Pending doc: `docs/pending-review/plans/PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md:5` (PENDING status)
  - Ruling doc: `docs/adr/0055-matter-and-court-case-identity-boundary.md:5` (ACCEPTED 2026-08-15)
- **Finding:** The architectural boundary is DECIDED (ADR-0055). The 15 operational sub-decisions within that file (P1–P5 on People authority/review/roles/timeline/identity; R1–R6 on authentication/confidence/methods/redaction/release/custody) and A1–A4 (activation gates) remain marked "PENDING OWNER RULING" in their file. The template at line 159 of the pending doc shows what a ruling would look like but has not been filled with an owner answer.

---

## Q3 — SurrealDB: Retired or Live? And Its New Role

**RESOLVED: Retired from Operations → Revived as Analytical Projection**

- **Earlier ruling (retired):** ADR-0043 removed SurrealDB from the operational critical path (no date in this review, but predates August).
- **Current ruling (revived):** ADR-0056, Decision 2 (2026-08-15, owner approval, Codex · GPT-5)
  - **Verbatim:** "SurrealDB returns as a **governed, rebuildable analytical projection** and an experimental tri-temporal memory/runtime for one as-lived walk agent. It is not the Agno operational database and does not replace PostgreSQL."
  - **File:line:** `docs/adr/0056-surrealdb-governed-analytical-and-walk-memory-surface.md:29–30`
  - **Status:** "Accepted; Decision 10 superseded in part by ADR-0059" (2026-08-15, narrowed 2026-08-18)
- **Reinforcing decision:** DECISION_LOG D-061 (2026-08-15, Codex · GPT-5)
  - **Verbatim:** "SurrealDB returns as a governed analytical projection and experimental Spectron-compatible walk-memory runtime; PostgreSQL remains authority… This does not reactivate the parked legacy deployment or revive Agno's Surreal operational adapter. rel: **ADR-0056**, ADR-0043, ADR-0045."
  - **File:line:** `docs/DECISION_LOG.md:35` (Status: "accepted; design only 2026-08-15")
- **Finding:** The contradiction is resolved by the dates and scope: ADR-0043 correctly retired it from operational store; ADR-0056 (2026-08-15) revived it ONLY for analytical projection + walk-memory, NOT operations. Both rulings stand and are complementary, not conflicting.

---

## Q4 — Full-Text Search vs Substring on Records Browser

**DESIGNED (TBD Engine Implementation)**

- **Architectural ruling:** DECISION_LOG D-037 (2026-07-11, owner decision)
  - **Verbatim:** "**full-text search is the FIRST retrieval layer**; (b) chunking follows LATER... **Sequencing (both classes):** ingest = parse → custody hash → land (no vectors, no chunks) → full-text search available immediately **(PG tsvector / DuckDB FTS — engine TBD at build)**"
  - **File:line:** `docs/DECISION_LOG.md` (D-037 decision row) — large entry, lines ~89–95 in that table row
- **Architectural details (no specific retrieval design for records browser found):** ADR-0058 (2026-08-15, Codex · GPT-5) covers "Investigation search and behavioral-analysis modes" but focuses on scoped manifests and mode immutability, not the SQL/retrieval method.
  - **File:line:** `docs/adr/0058-investigation-search-and-behavioral-analysis-modes.md`
- **Evidence of FTS intent:** Forensic DB architecture docs reference `gin(to_tsvector())` indexes on evidence tables, but no binding decision on `working.normalized_record` specifically.
- **Finding:** D-037 DECIDED that full-text search is the first retrieval layer (not vector-primary), but deferred the ENGINE choice (tsvector vs DuckDB FTS vs other) to build time. No explicit ruling found on ILIKE vs FTS for the records browser on `working.normalized_record`. Code inspection shows ILIKE used in `inspect_routes.py` for `normalized_record.content` but this is not a cited design decision.

---

## Q5 — Custody: Mandatory at Capture vs Best-Effort

**RESOLVED: Custody Primary, Fallback Explicit & Flagged**

- **Owner mandate:** DECISION_LOG D-055 (2026-08-12, Claude Code · Kimi K3) embedded citation
  - **Verbatim (from `server/evidence/workflows.py:702–707`):** "NO SILENT SUBSTITUTION (owner mandate 2026-07-02): if the PRIMARY tool fails, the workflow STOPS by default and says exactly what failed. Passing `allow_fallback=True` permits the substitution loop to continue autonomously, but the run and every stored record are flagged as an ALTERNATE-PARSER parse with the primary's failure recorded — a backup parse must never be indistinguishable from the primary."
  - **File:line:** `server/evidence/workflows.py:702–707` (mandate dated 2026-07-02, cited in DECISION_LOG D-055)
- **Implementation context:** `SBV_CUSTODY_ENABLED` env var gates custody reconciliation in `sbv_sms.py`; when absent, custody is skipped but ingest proceeds (best-effort). When present, custody H1/H2/H3 reconciliation is mandatory per `_reconcile_custody()`.
- **Related:** D-054 (2026-08-12) states "**Extraction runs REGARDLESS of custody-approval**" — custody approval gates visibility, not extraction.
- **File:line:** `docs/DECISION_LOG.md:48–50` (D-054–D-056 cluster)
- **Finding:** Custody is PRIMARY (must be attempted); fallback is permitted ONLY if explicitly flagged and logged. The system defaults to STOP if primary fails; this is the "NO SILENT SUBSTITUTION" mandate. Custody reconciliation itself is OPT-IN via environment flag, not mandatory at startup.

---

## Q6 — 16 Pending Deletions in Legal-Workspace

**NO RULING FOUND (Deletions Remain Uncommitted)**

- **Items:** 15 files in `docs/planning/original-context/` + `web/package-lock.json`
- **Status per Legal-Workspace URGENT-TODO.md:**
  - **B6** (line 31): "`web/package-lock.json` deleted, not regenerated" — marked **OPEN**. Impact: "Dockerfile.web uses `npm install` (not `npm ci`), so builds succeed but are **not reproducible**."
  - No entry for the 15 `original-context/` files.
- **Context:** COMPACT-SUMMARY-2026-08-21.md (lines 20–21, 23) notes that many deletions were a flattening of `original-context/artifacts/` into `original-context/` (structure reorganization), and `Legal-Workspace/git` operations were blocked by a case-bible hard-delete hook, but **no owner authorization** was cited for the deletions themselves.
- **Hard rule (global):** From CLAUDE.md — "NEVER delete — move to stale" (memory file `never-delete-move-to-stale.md`).
- **File:line:** 
  - URGENT-TODO: `Legal-Workspace/docs/URGENT-TODO.md:31` (B6, OPEN)
  - Compaction summary: `Legal-Workspace/docs/COMPACT-SUMMARY-2026-08-21.md:20–21`
- **Finding:** NO EXPLICIT RULING FOUND. The `web/package-lock.json` deletion is logged as an open defect (B6). The 15 `original-context/` files show no authorization; they appear to be an uncommitted state (per COMPACT-SUMMARY line: "~10 modified source files + many deleted `docs/planning/original-context/` files"). Per the global hard rule "NEVER delete — move to stale," these should be recovered to a `_stale/` directory, not deleted.

---

## Summary by Resolution Status

| # | Question | Status | Date | Authority |
|---|----------|--------|------|-----------|
| Q1 | Migration 0026–0030 cutover | **RESOLVED** (activation HELD, ready to apply) | 2026-08-18 | D-066, ADR-0059 |
| Q2 | Matter MVP P1–P5, R1–R6, A1–A4 | **PENDING** (ADR-0055 covers structure, not sub-decisions) | 2026-08-15 (partial) | ADR-0055 (structure only); pending-review doc still "PENDING OWNER RULING" |
| Q3 | SurrealDB: retired or live? | **RESOLVED** (retired from ops, revived as analytical projection) | 2026-08-15 | ADR-0056 D.2, D-061 |
| Q4 | Full-text vs substring search | **DESIGNED** (full-text decided; engine TBD) | 2026-07-11 | D-037; ADR-0058 (modes only) |
| Q5 | Custody: mandatory or best-effort? | **RESOLVED** (primary mandatory, fallback flagged) | 2026-07-02 (mandate); 2026-08-12 (log) | Owner mandate in workflows.py:702; D-054/D-055 |
| Q6 | 16 pending deletions in Legal-Workspace | **NO RULING FOUND** (uncomitted state; violates "never delete" rule) | — | None; URGENT-TODO B6 is OPEN |

---

## Byline

> _Verification: Claude Code · Haiku 4.5 · 2026-08-23_  
> _Findings written to `.full-review/verify-8-existing-rulings.md`_
