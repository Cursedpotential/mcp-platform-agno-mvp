# Claim Verification: SBV Custody + Legal-Workspace (14 claims)

> Verifier: Claude Code (general-purpose agent) · Sonnet 5 · 2026-08-23
> Base: `E:/AI_Workspace/Projects/the-platform-workspace`

---

## Part A — SBV (`Agno-MCP-Platform/vendored/sbv/`)

### Claim 1 — "base64 BLOBs in a general-purpose `messages` table with no evidentiary hash field, no chain-of-custody column"

**Verdict: PARTIAL (refuted on the material point)**

(a) Media storage — `internal/database.go:78-110` (and the per-user variant at
`:192-224`):
```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type INTEGER NOT NULL DEFAULT 1,   -- 1=SMS, 2=MMS, 3=call
    address TEXT NOT NULL,
    body TEXT,
    ...
    media_type TEXT,
    media_data BLOB,
    ...
);
```
`messages` is genuinely one unified table for SMS/MMS/call records (`record_type`
discriminator), and `media_data` is a `BLOB` column — so "general-purpose table"
and "BLOB" are both accurate. However, `internal/parser.go:311,324` shows the
data is **base64-*decoded* before storage** (`base64.StdEncoding.DecodeString(part.Data)`
→ `msg.MediaData = data`), so it is stored as raw decoded binary in the BLOB,
not as base64 text. The claim's literal phrase "base64 BLOBs" is imprecise but
the substance (media in a BLOB column on the messages table) is correct.

(b) Hash / custody column — **FALSE**. `internal/custody.go`'s
`ensureCustodyColumns()` (called from `InitDB`/`InitUserDB` at `database.go:159`)
adds `messages.content_hash TEXT` (the H2 hash) and creates an `imports` table
with `file_hash` (H1), `chain_hash` (H3), and `canon_version` columns — plus
`import_records`, `import_rejections`, `import_attachments`,
`import_audit_events`, etc. `CUSTODY.md` documents this in full:
> "`messages.content_hash TEXT` — the H2 for that record ... `imports(id,
> file_hash, record_count, chain_hash, canon_version, imported_at)` — one row
> per upload/auto-import batch (H1 + H3 + count)."

So the claim's first half (a) is roughly right (with a minor "base64" imprecision);
its second half (b) — "no evidentiary hash field, no chain-of-custody column" —
is directly contradicted by the schema and by `pkg/custodyhash` /
`internal/custody.go`.

---

### Claim 2 — "no export path into the `analysis.normalized_record` bitemporal schema"

**Verdict: REFUTED**

`server/analysis/sbv_transcript.py:1-27` (the Go-engine parse path used by the
context lane) states explicitly:
> "Downstream is byte-for-byte identical — PG `working.context_record` →
> change-detection → Weaviate/Graphiti — so the ONLY thing the engine choice
> changes is who does the parsing."

And the evidence-lane path, `server/tools/parsers/messaging/sbv_sms.py`,
maps SBV's universal-import rows to `NormalizedRecord` objects
(`_map_universal_record`, called at `sbv_sms.py:420`) which are the same
contract written into Postgres by the ingest/store layer used across the
platform (`server/contracts/records.py::NormalizedRecord`).

Caveat: the schema is `working.normalized_record`, **not**
`analysis.normalized_record` — see Claim 13 below, migration `0014` moved it.
So there both IS an export path, and the schema name in the claim is stale
either way. Not "no export path" — REFUTED.

---

### Claim 3 — "no visible bridge connecting SBV's SQLite output to the Go `internal/custody.go` hashing module"

**Verdict: REFUTED**

This claim is self-contradicting on its face (it names the very module it says
is unconnected). `internal/custody.go` is not a dangling/unused file:

- It is invoked from `InitDB`/`InitUserDB` (`database.go:159`,
  `ensureCustodyColumns`) to migrate the `content_hash` column and `imports`
  table into every database.
- `CreateImport`/`FinalizeImport`/`RecordImport` (in `custody.go`) are the
  read/write path for the `imports` table that every upload goes through.
- The H1/H2/H3 primitives it exposes (`HashFileH1`, `HashRecordH2`, `ChainH3`)
  now delegate to the decoupled `pkg/custodyhash` package (2026-08-11 refactor;
  `custody.go:60-79`), which is imported by `internal/engine.go`'s streaming
  parser to fold H3 as records stream in — this is the parser layer directly
  using the custody module, not a "no bridge" situation.
- On the Python side, `server/tools/parsers/messaging/sbv_sms.py:307-361`
  (`_reconcile_custody`) calls SBV's `GET /api/hashes/:importID` endpoint
  (served by `ImportRecord`/`GetImport`/`GetLatestImport` in `custody.go`) and
  feeds the H1/H2s/H3 into `server/evidence/custody.py::reconcile_sbv_import`
  — see the cross-check below. `_reconcile_custody` is called in the main
  `parse()` flow at `sbv_sms.py:426`, not dead code.

---

### Claim 4 — SBV documents a 100,000-message practical limit

**Verdict: CONFIRMED (with a scope caveat)**

`README.md:126`, under "Known Issues":
> "There is currently a 100k message limit per conversation. To see older
> messages, filter by date."

This is a genuine, documented limit. Caveat: it is a **per-conversation** UI
display limit, not a corpus-wide import cap — `internal/settings.go:28`
(`GetDefaultSettings`) sets `MessageLimit: 100000` as the default
`ConversationSettings.MessageLimit`, a per-user, per-conversation setting, and
the universal-import engine (NDJSON/CSV/email/etc.) shows no evidence of a
matching import-time record cap. The claim as stated ("100,000-message
practical limit") is close enough to the documented text to count as
confirmed, but "practical limit" undersells that it's scoped to one
conversation view, not the whole tool.

---

### Claim 5 — SBV is Android-only

**Verdict: REFUTED**

`UNIVERSAL_IMPORTS.md`'s plugin table lists (format ID → source):
`smsbackuprestore-xml` (Android SMS Backup & Restore XML), `ndjson`, `csv`,
`messages-transcript`, **`imessage-txt`**, **`imessage-html`**,
**`facebook-messenger-html`**, **`facebook-messenger-json`**,
**`google-voice-html`**, **`email-eml`**, **`email-mbox`**,
**`google-chat-json`**. iMessage (Apple/iOS), Facebook Messenger, Google Voice,
generic email (EML/MBOX), and Google Chat are all first-class supported import
formats with dedicated detection/parsing/projection logic described in detail
in that document. SBV originated as an Android SMS Backup & Restore viewer
(the README's headline description), but the "universal import engine" fork
this repo actually contains is explicitly multi-platform. "Android-only" is
false for the code under test.

---

### Claim 6 — SBV "functions today as a human-facing browsing tool rather than an evidence-pipeline component"

**Verdict: REFUTED**

`UNIVERSAL_IMPORTS.md:1-8` states the fork's purpose directly:
> "This fork extends SBV from an SMS Backup & Restore viewer into an isolated,
> format-pluggable evidence parsing and inspection worker... The platform
> custody gate remains authoritative and must independently verify H1 and
> persist its own append-only custody events."

And `server/analysis/sbv_transcript.py:1-20` documents it as "the GO parse
engine for the context lane," reachable via `SBV_BASE_URL`
(in-cluster `http://platform-tools:8085`), invoked as one of two swappable
parser engines (`engine="go"` vs `engine="python"`) feeding the same
`NormalizedRecord` → Postgres → change-detection → Weaviate/Graphiti pipeline.
It is also driven headlessly via `SBVClient`/`SBVError` in
`server/tools/_sbv_client.py` and `server/tools/parsers/messaging/sbv_sms.py`
without any human browsing the SBV UI. SBV plainly *also* remains a
human-facing browsing tool (that UI still exists per the README screenshots),
but characterizing it as functioning "rather than" a pipeline component is
false — it is wired into the platform's automated ingest path today.

---

### Cross-check — `server/evidence/custody.py::reconcile_sbv_import()`

**Verdict: EXISTS, and materially affects Claims 2 and 3 as already reflected above.**

`server/evidence/custody.py:470-546` defines `reconcile_sbv_import()`:

```python
def reconcile_sbv_import(
    src, source_meta, *, sbv_file_hash, sbv_record_hashes=None,
    sbv_chain_hash=None, actor="server.tools.parsers.messaging.sbv_sms",
) -> dict:
    """Cross-check SBV's H1 against our own, then record H2/H3 evidence + events."""
    ref = ingest_artifact(src, source_meta)   # our INDEPENDENT H1 (+ write-once blob)
    our_h1 = ref.sha256
    verified = bool(sbv_h1) and sbv_h1 == our_h1.lower()
    ... emits "verified" or "integrity_violation" custody_event ...
    if verified:
        # records SBV's H2s and H3 as evidence_hash rows (levels H2/H3)
```

It exactly matches the mechanism `CUSTODY.md`'s "Cross-check on the Python
side" section describes, and its caller
(`server/tools/parsers/messaging/sbv_sms.py::_reconcile_custody`, line 307)
is invoked from the live `parse()` entry point at line 426 — not orphaned code.
It is gated behind an opt-in env var (`SBV_CUSTODY_ENABLED`) and a defensive
lazy import (the slim tools-facade lacks SQLAlchemy), so it is *not* always
active, but the wiring and the function both genuinely exist and do what
`CUSTODY.md` claims. This directly refutes claim 2 (an export/verification
path does exist) and claim 3 (custody.go is not just referenced but actively
used on both the Go and Python sides).

---

## Part B — Legal-Workspace (`Legal-Workspace/`)

### Claim 7 — `eyecite_adapter.py` + `citation_gate.py` give native legal-citation parsing and gating

**Verdict: CONFIRMED**

Both files exist at `Legal-Workspace/api/legal_workspace/services/`:

- `eyecite_adapter.py` (72 lines) wraps the `eyecite` library
  (`from eyecite import get_citations`) to parse citation structure from text,
  producing `ParsedCitation` (raw/normalized/reporter/volume/page/year/court/
  validated/known_reporter) and a `ParseResult`. Its own docstring is explicit
  about scope: "eyecite structure parse. Not a citator. Not
  subsequent-history... `is_citator_verified` is always false."
- `citation_gate.py` gates *release* of a document on two axes:
  - `validate_factual_citations()` blocks any factual statement whose
    assertion isn't `ReviewState.APPROVED` in the imported source package, or
    lacks a `span_locator`.
  - `validate_authority_citations()` blocks any authority citation with an
    empty identifier, no pinned `snapshot_hash`, an `unpublished_opinion`
    level (flagged for human weight review), or an `is_citator_verified=True`
    flag set without a reviewed subsequent-history check.

So: real structural citation parsing (via eyecite, not custom regex) + a real
release gate that blocks on unapproved facts / unpinned authorities /
unreviewed citator claims. Confirmed as described.

---

### Claim 8 — README states "Do not treat this as court-safe"

**Verdict: CONFIRMED, verbatim**

`Legal-Workspace/README.md:17`:
> "conclusion. Do not treat this as court-safe."

(Full sentence context implies a preceding clause about outputs not being a
legal conclusion; the "Do not treat this as court-safe" clause is exact.)

---

### Claim 9 — PRIV module is "keyword-only hypothesized markers, not a legal conclusion"

**Verdict: CONFIRMED, near-verbatim**

`Legal-Workspace/api/legal_workspace/domain/privilege.py:1-22`:
```python
"""Keyword first-pass privilege / sensitivity markers.
Hits are hypothesized markers only. Never a privilege determination,
work-product claim, or other legal conclusion. No LLM. Does not
route Confidential Mode.
"""
DISCLAIMER = (
    "Keyword first-pass only. Hits are hypothesized markers, not a privilege "
    "determination, work-product claim, confidentiality holding, or other "
    "legal conclusion. A court decides privilege. Do not treat this scan as "
    "advice, and do not treat AI chat as attorney-client privileged."
)
```
The claim's phrasing ("keyword-only hypothesized markers, not a legal
conclusion") is a close paraphrase of this exact language.

---

### Claim 10 — domain layer includes Bates numbering, redaction, and DOCX export services

**Verdict: CONFIRMED — all three exist and do what their names suggest**

- `services/bates.py` — `stamp_bates_pdf()` uses `pikepdf`/`pypdf` to overlay a
  footer (`{prefix}-{n:06d}`) onto every page of an owner-produced PDF.
  Explicit in its own docstring: "Bates stamp overlay on owner-produced PDFs.
  Not Agno evidence... Not court-safe." Result carries `court_safe: bool =
  False`.
- `services/redaction.py` — actually rewrites the PDF content stream to remove
  token bytes (not a black-box visual overlay): "Not a black-box overlay...
  Replaces token bytes inside the page content stream so they are gone from
  the stream text, not merely covered." Also explicitly `court_safe: bool =
  False`, `disclosure: str = "private_strategy"`.
- `services/docx_export.py` — `write_release_docx()` builds a local DOCX
  "final review copy" via `python-docx`, stamping `content_hash`,
  `package_id`, `state`, `filed: false`, and the list of `omitted_private`
  sections, with the sentence "This is not a filing and not court-safe."
  baked into the document body. Its own docstring: "Write a local DOCX for a
  release candidate. Not a filing... This is the Type 2 local stand-in" (PDF
  export is pending a renderer sidecar).

All three modules are internally consistent about NOT being court-filing-ready
outputs — they are owner-work-product tools with `court_safe`/`exportable`
flags hardcoded to false, which matches Claim 8's README language.

---

### Claim 11 — no service module implementing an 8- or 9-column Best-Interest-Factor courtroom matrix export

**Verdict: CONFIRMED**

`api/legal_workspace/domain/factors.py` defines the only "factor matrix" in
the codebase: `empty_factor_matrix()` (line 125) builds a `list[FactorEntry]`
for **MCL 722.23 factors (a) through (l) — 12 factors**, not 8 or 9. It is a
data-model scaffold (used by `services/workspace.py:156` to seed a new
workspace), not an export function. A repo-wide search for `matrix`,
`chronology`, `factor` under `api/legal_workspace/**` turns up only:
`db/models.py`, `db/store.py`, `domain/authority_library.py` (unrelated
"authority" matches), `domain/factors.py`, `domain/issue.py`,
`domain/templates.py`, and `services/workspace.py` — none of which implement a
tabular 8/9-column courtroom-matrix export. The only genuine "export" function
in the services layer is `workspace.py::_write_release_export`, which produces
a narrative markdown/DOCX release package (via `docx_export.py`), not a
factor-by-column matrix table. So: no such module exists — claim confirmed.

---

### Claim 12 — vLex verification-status taxonomy (`VERIFIED_PRIMARY`, `MIRROR_ONLY`, `BLOCKED`, `CONFLICTED`) has NOT been extended to factual claims about evidence

**Verdict: REFUTED (premise not found — no such taxonomy exists in this codebase at all)**

An exhaustive case-sensitive and case-insensitive grep for `VERIFIED_PRIMARY`,
`MIRROR_ONLY`, `CONFLICTED`, and `vlex` across `Legal-Workspace/` (all `.py`
and `.md` files, `.venv` excluded) and across the sibling `Agno-MCP-Platform/`,
`Legal-desktop/`, `extracted-code/`, `docs/`, and `plans/` directories returned
**zero matches** anywhere in the workspace. The taxonomy the claim names does
not exist under those identifiers in this repo.

What actually exists instead, for the two places this claim is plausibly
gesturing at:
- Authority/citation verification: `AuthorityCitation.is_citator_verified:
  bool` (a boolean, not a 4-state enum) plus `snapshot_hash`/`authority_level`
  fields (`citation_gate.py`, `authority_library.py`). `CuratedAuthority` uses
  `complete: bool` / `applicable: bool` / `skip_reason: str | None`.
- Factual-claim review state (the closest thing to "evidence" verification):
  `ReviewState(str, Enum)` in `contracts/source_package.py:15-19` = `CANDIDATE
  | APPROVED | REVOKED | QUARANTINED`.

Neither matches the claimed 4-value taxonomy. Since I cannot confirm the
taxonomy exists anywhere for it to have been "not extended," and cannot find
it defined in this codebase at all, the claim as stated does not hold up —
REFUTED (not merely unverifiable: this was a workspace-wide search, not a
narrow miss).

---

## Part C — schema naming

### Claim 13 — "The live bitemporal schema (`sql/0001`–`0018`) implements `analysis.normalized_record`"

**Verdict: REFUTED on both the schema name and the migration range**

- **Schema name**: `sql/0014_split_analysis_into_working_reference_ops.sql`
  (owner ruling quoted in the file: "the second level of tables, the spine and
  the projection - I don't like the analysis prefix, it's more working, just
  be like working prefix") moves `normalized_record` (along with other spine/
  projection tables) from `analysis` into a new `working` schema via `ALTER
  TABLE ... SET SCHEMA working` (migration body, lines 71-80+). The file's own
  header states the rule explicitly: "NO COMPATIBILITY VIEWS, NO ALIASES...
  Every caller moves in the same change or the change is not done." Confirmed
  in current code: `server/analysis/detection.py:36,353`,
  `server/api/inspect_routes.py` (multiple `FROM working.normalized_record`
  queries), `server/case_management/repository.py`, and
  `server/agents/tools/realization_tools.py` all reference
  **`working.normalized_record`**, not `analysis.normalized_record`. The
  `analysis` schema still exists post-0014, but is now scoped to conclusions
  only (findings/assertions/scores/review decisions), per the same migration's
  `COMMENT ON SCHEMA analysis`.
- **Migration range**: `Agno-MCP-Platform/sql/` contains **30** migrations
  (`0001_init_extensions.sql` through `0030_matter_case_foundation.sql`), not
  18. `0018_retrieval_axes.sql` exists but is well short of the current head.
  Citing "0001–0018" as "the live bitemporal schema" both undercounts the
  migration set by 12 files and predates the schema-name rename that happened
  in `0014` (which is inside the cited range but whose effect — the rename
  away from `analysis.normalized_record` — is the opposite of what the claim
  asserts).

**Correct statement**: the live schema is `working.normalized_record`
(current spine table), the platform is at `sql/0001`–`sql/0030`, and
`analysis.*` now means conclusions/findings only, not the record spine.

---

### Claim 14 — `docs/planning/forensic-db-reconciliation/migrations/0006_behavior_seed.sql` exists, merges nine behavioral-detection iterations incl. TTL ontology + `zep_salem_ontology_v3_final.py`; reconciliation report says DRAFT/paper-only, "Nothing here has been applied or diffed against the running DB"

**Verdict: CONFIRMED, all parts**

- File exists: `Agno-MCP-Platform/docs/planning/forensic-db-reconciliation/migrations/0006_behavior_seed.sql` (1,164 lines).
- Nine-iterations + source list, verbatim in the file (lines 9, 43, 46, 48):
  ```
  --    fragments (G1 analyzer-app, G2 seed-patterns.ts, G3 dial TTL, G4 E4, G5 agno-alpha,
  ...
  'G7 zep_salem_ontology_v3_final.py; G8 conversation logs; '
  ...
  'Additive superset of nine fragmented behavioral-detection iterations; patterns are hypotheses requiring human review.',
  ...
  'user-side compiled from fragmented iterations; patterns are hypotheses requiring human review'
  ```
  `G3 dial TTL` confirms the TTL-ontology source; `G7
  zep_salem_ontology_v3_final.py` confirms that exact filename is one of the
  nine merged iterations.
- Status language, verbatim in
  `docs/planning/forensic-db-reconciliation/FINAL_RECONCILIATION_REPORT.md:5-9`:
  > "**Status: DRAFT / paper-only.** Consolidates the per-domain
  > reconciliations (D1–D8), the draft schema (`RECONCILED_SCHEMA.sql`) + this
  > report. **Nothing here has been applied or diffed against the running
  > DB.** It HAS been reconciled against the captured live [introspection]..."

  Corroborated by `STATUS.md:30`: "**No DDL executed against the live DB.**
  `0005` is a reviewable draft."

All parts of Claim 14 confirmed exactly as stated.

---

## Summary table

| # | Claim | Verdict |
|---|---|---|
| 1 | SBV: base64 BLOBs, no hash/custody columns | PARTIAL (media-in-BLOB true w/ caveat; "no hash/custody column" REFUTED — content_hash + imports.file_hash/chain_hash exist) |
| 2 | SBV: no export path to `analysis.normalized_record` | REFUTED (exports to `working.normalized_record`/`working.context_record` via NormalizedRecord mapping) |
| 3 | SBV: no bridge to `internal/custody.go` | REFUTED (custody.go is live-wired: DB migration, import CRUD, H1/H2/H3 primitives, Python cross-check) |
| 4 | SBV: documented 100k-message limit | CONFIRMED (README.md:126; per-conversation display limit, not global) |
| 5 | SBV: Android-only | REFUTED (iMessage, Facebook Messenger, Google Voice, email, Google Chat all supported) |
| 6 | SBV: human-browsing tool, not pipeline component | REFUTED (wired into automated context/evidence ingest via sbv_transcript.py + sbv_sms.py) |
| CX | `reconcile_sbv_import()` exists | CONFIRMED — exists, matches CUSTODY.md description, wired into live parse() path (opt-in via env var) |
| 7 | Legal-Workspace: eyecite_adapter.py + citation_gate.py | CONFIRMED |
| 8 | README "Do not treat this as court-safe" | CONFIRMED (verbatim, README.md:17) |
| 9 | PRIV "keyword-only hypothesized markers" | CONFIRMED (near-verbatim, privilege.py) |
| 10 | Bates/redaction/DOCX export services | CONFIRMED (all three exist and do as described) |
| 11 | No 8/9-column Best-Interest matrix export | CONFIRMED (only matrix is 12-factor MCL 722.23 data model, no tabular export) |
| 12 | vLex taxonomy not extended to evidence | REFUTED (taxonomy not found anywhere in the codebase — premise unsupported) |
| 13 | `analysis.normalized_record`, sql/0001-0018 | REFUTED (it's `working.normalized_record` since migration 0014; 30 migrations exist, not 18) |
| 14 | 0006_behavior_seed.sql, nine iterations, DRAFT/paper-only | CONFIRMED, all parts, verbatim |
