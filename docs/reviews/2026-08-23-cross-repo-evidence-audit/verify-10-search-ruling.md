# Verification: D-037 Scope & FTS Engine Status

**Query Date:** 2026-08-23  
**Repo:** `Agno-MCP-Platform`  
**Question:** Does D-037 ("full-text search is the FIRST retrieval layer") bind the `/v1/records` browser, and was an engine chosen?

---

## 1. D-037 Location & Exact Text

**File:** `docs/DECISION_LOG.md`  
**Line:** 92  
**Scope:** Ingest sequencing (both EVIDENCE and AI-CHAT data classes)

**Exact quote:**
> Sequencing (both classes): ingest = parse → custody hash → land (no vectors, no chunks) → **full-text search available immediately** (PG tsvector / DuckDB FTS — engine TBD at build) → chunking (hybrid semantic+fixed, `docs/planning/agno-chunking-strategy.md`) tuned afterward, applying the SAME legal/timeline/code/general split as the D-036 KB collections → embed per-domain last.

---

## 2. Was the Engine Chosen After 2026-07-11?

**Status:** NO — still TBD.

**Search Results:**
- **DECISION_LOG.md:** No subsequent decision (D-038 onwards) names a specific FTS engine.
- **ADR-0058 (Investigation search):** Addresses search modes (Find Evidence, Reconstruct Event, Discover Patterns) but does NOT choose tsvector vs DuckDB FTS.
- **D-063 (Investigation Search and Behavioral Analysis):** Accepted product target; does NOT specify the FTS engine.
- **COORDINATION.md, R10E Retrieval lane:** Listed as "Proposed contracts; bake-off required" — no activation, no engine decision.
- **DEBT.md:** No mention of FTS engine choice.

**Conclusion:** The decision remains **"engine TBD at build"** (2026-07-11 state persists).

---

## 3. What Does D-037 Actually Scope?

**Scope Boundaries:**

D-037 is explicitly about **ingest pipeline sequencing** for TWO data classes:
1. **EVIDENCE / text messages / forensic records** → fully normalized into PG relational `source.*` tables (court-defensible, with custody hashes H1/H2/H3)
2. **AI-CHAT TRANSCRIPTS + KB content** → land in DuckDB columnar (light touch, NOT forensic normalization)

**Key language:**
> "This DECOUPLES parser-tables/RESTART-0001 from the still-open embedder bench + KB-substrate sparse build (D-034) + gateway work — ingest is now on its own track."

**What D-037 does NOT explicitly bind:**
- The operator **records browser** (`GET /v1/records`) is not mentioned by name or intent.
- D-037 does not say "operators must query records using FTS" or "the browser endpoint must use tsvector."
- D-037 says FTS will be "available immediately" after land, but does not mandate that all record retrieval uses it.

**Distinction:** D-037 authorizes FTS as a capability in the ingest stack; it does not prescribe it as the ONLY or even the primary retrieval path for the operator UI.

---

## 4. Full-Text Indexes in the Baseline Schema

**File:** `sql/bootstrap/schema_baseline.sql`

### Expression Indexes (Generated, Not Stored Columns)

1. **`idx_normrec_fts`** (line 11539)
   ```sql
   CREATE INDEX idx_normrec_fts ON working.normalized_record 
   USING gin (to_tsvector('english'::regconfig, COALESCE(content, ''::text)));
   ```
   - Table: `working.normalized_record`
   - Type: Expression index (GIN)
   - Lexeme config: English
   - Column: `content`

2. **`idx_att_ocr_fts`** (line 11112)
   ```sql
   CREATE INDEX idx_att_ocr_fts ON working.attachment 
   USING gin (to_tsvector('english'::regconfig, ((COALESCE(ocr_text, ''::text) || ' '::text) || COALESCE(transcription, ''::text))));
   ```
   - Table: `working.attachment`
   - Type: Expression index (GIN)
   - Lexeme config: English
   - Columns: `ocr_text` + `transcription` (concatenated)

### Other Full-Text Capable Indexes on `working.*`

3. **`idx_normrec_trgm`** (line 11574)
   ```sql
   CREATE INDEX idx_normrec_trgm ON working.normalized_record 
   USING gin (content public.gin_trgm_ops);
   ```
   - Table: `working.normalized_record`
   - Type: Trigram GIN (approximate substring/fuzzy search)
   - Column: `content`

### Summary

- **2 tsvector FTS indexes** (English stemming, word-boundary search)
- **1 trigram index** (fuzzy/approximate substring matching)
- **NO stored tsvector column** (only expression indexes)
- **No DuckDB FTS indexes** in PG schema (they would be defined in DuckDB, not here)

---

## 5. Actual Usage in the Codebase

**Search for:** `to_tsvector`, `plainto_tsquery`, `websearch_to_tsquery`, `@@` (tsvector match operator)

**Result:** NO MATCHES in Python code.

- Searched all `*.py` files in `server/` and subdirectories.
- Only non-relevant match: `double@@domain.com` (email address in a test file, not a tsvector operator).
- **No Python code invokes any FTS predicate.**

**Conclusion:** The indexes are **defined but never queried**. They exist as infrastructure but are not wired to any retrieval logic.

---

## 6. Current Implementation of `GET /v1/records?q=`

**File:** `server/api/inspect_routes.py`  
**Endpoint:** Line 249  
**Query construction:** Lines 259–264

```python
@app.get("/v1/records")
async def list_records(
    artifact_id: str | None = Query(None),
    run_id: str | None = Query(None),
    q: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    resolved_artifact_id = _resolve_artifact_id(artifact_id, run_id)
    
    where = ["nr.artifact_id = :artifact_id"]
    params: dict[str, Any] = {"artifact_id": resolved_artifact_id}
    if q:
        where.append("nr.content ILIKE :q")  # Line 262
        params["q"] = f"%{q}%"                # Line 263
    where_clause = " AND ".join(where)
```

**Current Search:** `nr.content ILIKE :q` (substring match, case-insensitive)

**Exact Line:** 262

---

## 7. Semantic Difference: ILIKE vs. Full-Text Search

### Current Behavior (ILIKE with `%q%`)

Finds **any substring occurrence**, case-insensitive:
- Query: `test`
- Matches: "test", "testing", "Test case", "protest", "attest", "contestant", "retest"
- Does NOT discriminate on word boundaries
- Fast for short queries; poor precision at scale

### Proposed Behavior (tsvector with Porter Stemming)

Finds **whole-word or stemmed-variant matches** only:
- Query: `test` → Porter stemmer produces lexeme "test"
- Matches:
  - "test" (exact)
  - "testing" (stems to "test")
  - "tests" (stems to "test")
  - "retesting" (stems to "test", found as a token)
- Does NOT match:
  - "protest" (stems to "protest", different lexeme)
  - "attest" (stems to "attest", different lexeme)
  - "contestant" (stems to "contest", different lexeme)
- Word boundary enforcement: "test" is a discrete token, not a substring within "protest"

### Impact on Results

| Scenario | ILIKE `%test%` | tsvector "test" |
|----------|---|---|
| "test message" | ✓ | ✓ |
| "testing hypothesis" | ✓ | ✓ |
| "this protest was" | ✓ | ✗ (different word) |
| "in contest of" | ✓ | ✗ (different word) |
| "under attestation" | ✓ | ✗ (different word) |

**Key difference:** Substring match includes intra-word hits; FTS does not.

---

## Summary & Conclusion

### Is the search change already authorized by D-037?

**PARTIALLY — with caveats:**

✓ **Authorized for ingest pipeline:** D-037 explicitly authorizes FTS as "the FIRST retrieval layer" for records immediately after landing.

✗ **NOT explicitly bound to `/v1/records` browser:** D-037 addresses ingest sequencing, not operator UI retrieval. The browser endpoint is separate machinery.

✗ **Engine still TBD:** No decision has chosen `tsvector` vs `DuckDB FTS` vs any other engine. The statement "(PG tsvector / DuckDB FTS — engine TBD at build)" remains current (2026-07-11 state, no update found).

✗ **No implementation required by any decision yet:** The FTS indexes exist in the schema, but zero Python code uses them. Activating FTS for `/v1/records` would require:
1. **Owner sign-off** on which FTS engine (Postgres tsvector assumed here, but still TBD)
2. **Explicit API decision** scoping the browser's search behavior
3. **Code change** to switch from ILIKE to tsvector predicates

### Recommendation

**The search change still needs a decision.** D-037 is infrastructure authorization, not usage authorization. A new decision or task ticket should:
- Confirm that `/v1/records?q=` should use FTS (not just "FTS is available")
- Specify the engine (Postgres `to_tsvector` + `plainto_tsquery` / `websearch_to_tsquery`)
- Clarify ranking/scoring (if any; `ts_rank` or `ts_rank_cd` if needed)
- Document the semantic change (word-boundary search, no intra-word substrings)
- Update the browser endpoint code to use the FTS predicates

---

_Byline: Claude Code · Haiku 4.5 · 2026-08-23_
