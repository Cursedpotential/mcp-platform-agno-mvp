# Verify 11: Custody Hashing Mandate & Flagged Fallback Mechanisms

**Question:** Is there a standing owner ruling that custody hashing is mandatory, and is there an existing mechanism for marking degraded-path records?

---

## 1. NO SILENT SUBSTITUTION Mandate (Verified Verbatim)

**Location:** `server/evidence/workflows.py:702-707`

```python
NO SILENT SUBSTITUTION (owner mandate 2026-07-02): if the PRIMARY tool fails,
the workflow STOPS by default and says exactly what failed. Passing
allow_fallback=True permits the substitution loop to continue autonomously,
but the run and every stored record are flagged as an ALTERNATE-PARSER parse
with the primary's failure recorded — a backup parse must never be
indistinguishable from the primary.
```

**Scope:** This mandate governs **parser choice and fallback behavior**, NOT custody hashing. It applies to the `build_sms_xml_workflow()` and related workflow builders. The "workflow STOPS" clause means the ingest stage halts by default; only explicit `allow_fallback=True` authorizes silent substitution with marking.

---

## 2. Mandate Reaches HTTP Ingest Path?

**YES.** The `ingest_file()` function in `server/ingest/service.py:264` honors the same rule:

- **Line 215:** `if not request.allow_fallback: raise` — primary parser failure halts unless explicitly allowed
- **Line 217-223:** On fallback, it chains attempts: `[{"tool": "sbv.go", "ok": False, "error": ...}, *attempts]` (logged, not silent)
- The fallback engine is explicitly tracked and returned in the response

**Difference from workflows.py:** `ingest_file` does NOT persist an `alt_parse` flag to the record attrs (workflows.py does at line 459). The HTTP service only logs the attempt chain; the record-level marking is left to downstream consumers.

---

## 3. Standing Ruling on Mandatory Custody Hashing?

**NO custody-hashing mandate found.** Search of:
- `docs/DECISION_LOG.md` — D-047 covers custody-hash **decoupling** (modularization), not mandatory use
- `docs/adr/0044*`, `docs/adr/0017*` — No mandatory custody language
- `docs/PROJECT_CANON.md` §5 — Custody is default for evidence lane (`custody_tier='full'`) but hashing itself is not stated as mandatory

**Key finding:** Custody **hashing** (H1/H2/H3 reconciliation) is **optional**, gated on `SBV_CUSTODY_ENABLED`:

```python
# server/tools/parsers/messaging/sbv_sms.py:338
if not os.getenv("SBV_CUSTODY_ENABLED"):
    return None
```

**Default:** No default — if unset, reconciliation is skipped silently, even on the SBV path. The comment (line 334) calls it "opt-in" with no mandate. This is a **convenience**, not a requirement.

---

## 4. Intended Default of `SBV_CUSTODY_ENABLED`?

**No documented intended default found.** Search results:
- No env-var defaults in `compose.yaml`, `deploy/exec.yaml`, or `.env` examples
- No docstring stating what production should use
- Comment at line 334 says "defensively lazy: the slim tools-facade has no sqlalchemy" — the opt-in exists because importing custody at module load would fail

**Implication:** The opt-in was a **build-out convenience** (avoid optional SQLAlchemy at parse time), not a deliberate governance choice. It is unclear whether the intended production default is ON or OFF.

---

## 5. Existing "Flagged Fallback" Mechanism

**YES — already exists and is actively used:**

| Component | Column/Field | Purpose |
|-----------|-------------|---------|
| **normalized_record.attrs** | `alt_parse` (boolean) | Set to `True` when fallback parser used |
| **normalized_record.attrs** | `alt_parse_detail` (dict) | Records `{primary, primary_error, used}` |
| **Code location** | `server/evidence/workflows.py:456-460` | Stamped on every record during store |

**Example** (workflows.py line 458-460):
```python
if ctx.get("alt_parse"):
    rec.attrs["alt_parse"] = True
    rec.attrs["alt_parse_detail"] = ctx.get("alt_parse_detail")
```

**Persistence:** JSONB column in `working.normalized_record.attrs`, indexed via GIN. **Already canonical** — this is where degraded-path records are marked.

**Note:** The HTTP `ingest_file()` path does NOT mark records at the HTTP level; the flag is set only within the workflow builders (sms-xml, chat-transcript, etc.). If `ingest_file` is called outside a workflow builder, alt_parse is not set.

---

## Summary

| Question | Answer |
|----------|--------|
| **Standing custody-hashing mandate?** | NO. Owner mandate 2026-07-02 covers **parser fallback**, not custody hashing. Custody is a separate default (tier='full' for evidence) but hashing reconciliation (SBV_CUSTODY_ENABLED) is optional, not mandatory. |
| **Mandate scope?** | Parser choice, fallback marking, audit trail. Does NOT require custody hashing. |
| **HTTP path honor it?** | YES. `allow_fallback` parameter gates silent substitution; attempts are chained and logged. Record-level marking is left to consumers. |
| **Existing flagged-fallback mechanism?** | YES. `normalized_record.attrs["alt_parse"]` + `alt_parse_detail` — already canonical, JSONB-indexed, actively stamped during store. Use this column to mark custody-free records. |
| **Intended default of SBV_CUSTODY_ENABLED?** | Not documented. Likely ON in production (hash reconciliation is valuable for forensics), but no owner ruling found. Current no-default is a **build convenience**, not policy. |

---

## Recommendation

If you are designing a custody-free fallback path:
1. **Reuse the existing `alt_parse` + `alt_parse_detail` mechanism** — it is already built, indexed, and persisted
2. **Consider custody hashing optional in production** — no mandate found, only default tier. If SBV_CUSTODY_ENABLED is unset, reconciliation is silently skipped (line 338)
3. **Document the intended default** — the opt-in was a build convenience; clarify in docs/DECISION_LOG or docs/PROJECT_CANON whether production should default to ON
4. **Extend alt_parse for custody-free records** — add a sub-key `custody_available: false` in `alt_parse_detail` to distinguish parser fallback from custody unavailability

_Byline: Claude Code · Haiku 4.5 · 2026-08-23_
