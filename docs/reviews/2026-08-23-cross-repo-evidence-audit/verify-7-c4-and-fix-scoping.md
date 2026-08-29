# Full-Review Phase 7 — C4 Verification + Fix Scoping

**Date:** 2026-08-23 | **Scope:** C4 (MMS multi-attachment), 6 scope items, 2 owner threads | **Status:** All findings VERIFIED against live code

---

## Task 1 — C4 Verdict (MMS Multi-Attachment)

**Claim:** "Multi-attachment MMS stores only the first part. Raw XML is retained and H2 covers the whole element, so it is recoverable — but the DB and all exports carry one attachment, unsignalled."

**Verdict:** **PARTIALLY CONFIRMED** — with important caveats.

### Evidence (vendored/sbv/internal/parser.go)

1. **Only first part persisted** — Lines 323-330 confirm explicit guard:
   ```go
   if msg.MediaType == "" { // Only store first media item
       data, err := base64.StdEncoding.DecodeString(part.Data)
       if err == nil {
           msg.MediaType = part.ContentType
           msg.MediaData = data
       }
   }
   ```
   Additional parts silently discarded in the loop.

2. **Discard is signalled: NOT** — No log, no counter, no rejection row, no field tracking discarded count. SILENT discard.

3. **Raw XML retained: REFUTED** — Lines 918-922 show:
   ```go
   // H2: hash the RAW <mms> element bytes (incl. base64 parts) BEFORE any conversion
   endOff := decoder.InputOffset()
   h2 := HashRecordH2(trimLeadingXMLSpace(cr.slice(startOff, endOff)))
   cr.discardBefore(endOff)  // DISCARDED after hashing
   ```
   Raw bytes are hashed for H2 custody, then **immediately discarded**. Only the hash is stored in the Message struct (`ContentHash` field, models.go:36). The raw MMS element bytes are NOT retained in the database or Message. If the original XML file exists separately as a backup, then yes it's recoverable from that. But in the parsed/normalized output, raw XML is NOT stored.

### Verdict: **CONFIRMED** — First attachment only, silent discard, H2 covers whole element **BUT raw XML not retained in DB**

---

## Task 2 — Revalidate Six Scope Items

| Item | Still Live? | Current Line(s) | Status | Notes |
|------|-------------|-----------------|--------|-------|
| 1. Behavioral MCL (j)/(k) inverted | **YES** | behavioral_patterns.json:59–66 | **CONFIRMED INVERTED** | (j)="Domestic Violence" desc (should be facilitate); (k)="Willingness to Facilitate" desc (should be DV) |
| 2. patterns.py validation | **YES** | patterns.py:41, 211–212 | **CONFIRMED** | Letter-only validation, never checks name/description |
| 3. sbv_sms.py docstring stale | **YES** | sbv_sms.py:15–19 | **CONFIRMED STALE** | Docstring says "alphabetical import order"; code uses `priority=100` at line 378; registry.py:87 sorts by priority DESC |
| 4. pyproject.toml docling/ocr | **YES** | pyproject.toml extras | **CONFIRMED** | docling in `document-ai` extra only; ocr extras separate. Code raises cleanly at runtime. No STUB marker (correct — not a stub). |
| 5. DEBT.md claims evals/cases.py empty | **REFUTED** | DEBT.md:119 is STALE | **OUTDATED** | evals/cases.py now has 146 lines with **8 Case entries** (lines 82–144), not empty tuple. |
| 6. FTS index on normalized_record | **YES (partial)** | schema_baseline.sql, inspect_routes.py:262 | **UNUSED INDEX** | GIN index created and syntactically correct. Query uses ILIKE (line 262), NOT FTS. Index built but never queried by Python. |

---

## Task 3 — Fix Scoping

### Fix 1: Behavioral patterns (j)/(k) swap

**Minimal change:**
- File: `server/analysis/config/behavioral_patterns.json`
- Lines 59–66: Swap `name` values between (j) and (k), preserve descriptions as-is

**Blast radius:** 
- Grep: `"mcl_factors": ["j", "k"]` → 12+ modules reference these factors (gaslighting, blame_shifting, minimization, threats_intimidation, isolation_tactics, financial_control, emotional_blackmail, parental_alienation, projection, darvo, power_asymmetry, love_bombing)
- Python: `server/analysis/patterns.py` consumes this JSON; no direct field dependencies (only letter validation)
- Tests: No test currently checks name correctness; would need integration test comparing factor letter to expected name

**Test needed:** Assert that `behavioral_patterns.json` factor (j).name == "Willingness to Facilitate Relationship" and (k).name == "Domestic Violence" (statute verification)

**Ordering constraint:** None; standalone config fix.

### Fix 2: patterns.py validation

**Minimal change:**
- File: `server/analysis/patterns.py`
- Line 211: Add validation loop after letter check to verify each letter's name/description matches expected statute binding

**Blast radius:**
- Validators called at: `validate_categories()` (line ~200+), invoked during pattern registration
- No direct callers; config-load only, no runtime queries

**Test needed:** Unit test `test_mcl_factors_match_statute()` that reads JSON and Python constants, verifies name/letter binding

**Ordering constraint:** Should follow Fix 1 (swap names first), then validate.

### Fix 3: sbv_sms.py docstring

**Minimal change:**
- File: `server/tools/parsers/messaging/sbv_sms.py`
- Lines 15–19: Rewrite to explain priority-based resolution, cite `priority=100` at line 378, cite `registry.py:87` sort

**Blast radius:**
- Docstring only; no code impact
- Related: `server/tools/registry.py` resolve logic is correct and unchanged

**Test needed:** None (doc only); linter check to ensure docstring doesn't contradict code intent

**Ordering constraint:** None; pure documentation.

### Fix 4: pyproject.toml docling (no fix needed)

**Status:** WORKING AS DESIGNED — docling is optional, code raises cleanly with actionable error. No fix required. If anything, document in AGENTS.md or a run-guide that `document-ai` extra is required for Docling extraction.

### Fix 5: DEBT.md evals/cases.py claim

**Minimal change:**
- File: `docs/DEBT.md`
- Line 119: Replace stale quote `"CASES: tuple[Case, ...] = ()"` with accurate description: "8 eval cases for classification/sentiment/comparison (lines 82–144)"

**Blast radius:**
- Documentation only; no code impact
- Related: If DEBT.md is part of audit checklists, readers may have relied on stale info

**Test needed:** None (doc correction); keep DEBT.md in audit checklist to catch future drift

**Ordering constraint:** None; standalone documentation correction.

### Fix 6: FTS index on normalized_record (unused)

**Minimal change (2 options):**
- **Option A (enable FTS):** Rewrite `server/api/inspect_routes.py:262` to use `@@` operator and `to_tsvector()` instead of ILIKE for full-text search against the GIN index
- **Option B (remove unused):** Drop `idx_normrec_fts` from `sql/bootstrap/schema_baseline.sql` if FTS is not planned

**Blast radius (Option A):**
- Query at line 262 used for: `GET /v1/records?q=<query>`
- Callers: Workbench evidence browser, any client using the records API
- Performance: FTS would improve large-scale searches; ILIKE is a substring match

**Blast radius (Option B):**
- Index creation: One line in baseline schema (no cost to remove)
- Performance: ILIKE would continue; no change to query behavior

**Test needed (Option A):** Integration test: `test_records_fts_search()` verifying FTS query finds records by keyword and ranks by relevance

**Ordering constraint:** Option B is safe now; Option A requires testing against real data.

**Recommendation:** Option B (remove unused index) is reversible and safe. If full-text search is desired, that should be a separate feature request with test coverage.

---

## Task 4 — Contradiction Check on Two Owner Threads

### Thread 1: HANDOFFS.md Fix (R14 Addendum + Moved Links)

**Status:** **FIXED**

1. **R14 addendum not surfaced in index:** 
   - FIXED (2026-08-18). Line 26 in `docs/HANDOFFS.md` now includes strikethrough: `~~Core live gates pass / full set partial~~ — **superseded 2026-08-18, see below**`
   - Linked to full ADR-0059 supersession context at line 44–51

2. **Two broken links:**
   - FIXED. Both now point to correct `awaiting-verification/plans/` path:
     - `awaiting-verification/plans/GOALS-2026-08-15-surreal-investigation-memory.md`
     - `awaiting-verification/plans/SURREAL-INVESTIGATION-BLUEPRINT-2026-08-15.md`

**Verification:** Both fixes confirmed live in HANDOFFS.md as of 2026-08-23.

### Thread 2: Matter-MVP P1/P2 Decision Packet

**Status:** **STILL PENDING / UNANSWERED**

- **Location:** `docs/awaiting-verification/plans/PENDING-OWNER-DECISIONS-MATTER-MVP-2026-08-15.md`
- **State:** Line 5 still reads "STATUS: PENDING OWNER RULING — review packet only; not an ADR"
- **Decisions outstanding:** P1–P5 (people authority, review meaning, role cardinality, court-event scope, identity dedup), R1–R6 (auth/release, confidence, methods, redaction, who-may-release, custody coupling), A1–A4 (activation approvals)
- **Line 159:** "Recommended compact ruling" template has NOT been filled with owner decisions
- **No ruling found:** Searched all `docs/*.md` and `OWNER-REVIEW-2026-08-18*.md` — no P1/P2/P3 rulings recorded

**Specific open question:** P2 — "Review meaning for an operator-created person — usable immediately at `safe_for_legal_use=false`, or does creation imply approval?" (PENDING-OWNER-DECISIONS line 27–35)

**Action:** This packet remains blocked until owner records decision answers per the recommended-ruling format at line 159.

---

## Summary Table — Fix Priority & Risk

| Fix | Risk | Complexity | Blocker | Recommend |
|-----|------|-----------|---------|-----------|
| 1. MCL (j)/(k) swap | LOW | S | None | **YES** (statute accuracy) |
| 2. patterns.py validation | LOW | S | Fix 1 first | **YES** (prevents future drift) |
| 3. sbv_sms.py docstring | NONE | S | None | **YES** (doc accuracy) |
| 4. docling optional | NONE | — | None | **SKIP** (working as designed) |
| 5. DEBT.md evals claim | NONE | S | None | **YES** (doc accuracy) |
| 6. FTS index unused | MEDIUM | J | None | **MAYBE** (remove or implement, needs owner call) |

**No fix touches held migrations (0026–0030) or the unanswered Matter-MVP packet.**

---

_Byline: Claude Code · Haiku 4.5 · 2026-08-23_
