# Lane 3 — Gap Analysis: vendored/sbv (SMS Backup Viewer, "sbv-forensic")

> Byline: Claude Code · Sonnet 5 · 2026-08-23
> Repo: `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform/vendored/sbv`
> Method: read the fork's own docs, then verified every claim against the Go source
> (~11,585 LOC across `internal/` + `pkg/custodyhash/`, excluding tests; 12 `_test.go` files).
> Everything below is marked **VERIFIED** (read the actual code/route/schema) or **INFERRED**
> (doc claim I did not independently re-derive, e.g. the 5 GiB streaming claim).

---

## 1. What the fork added over upstream

`UPSTREAM.md` (dated 2026-07-09) claims the fork adds "H1/H2/H3 hashing over the RAW source
bytes" via `internal/custody.go`, and lists 8 changed files. **VERIFIED but STALE.** That
changed-file list is accurate for the 2026-07-09 snapshot but has not been updated since — the
fork has grown substantially past it without a corresponding UPSTREAM.md revision (doc drift,
flagged in §7).

Git history (`git log --oneline -- vendored/sbv`) shows the real shape: one `git subtree` merge
(`137d204`), **one** subsequent upstream sync (`b3c2d1e`, 12 upstream commits), and **nine**
fork-only feature commits building:

- `c4c5c06` — original H1/H2/H3 custody hashing (P1-4)
- `813f3b2` — headless automation endpoints (`/api/automation/*`)
- `a2092fb` — hashing-audit repairs + CSV support
- `5ebffd1` — the **universal import engine** (12 format plugins) + governed repair slice
- `d44d3f1` — decoupled `pkg/custodyhash` (canonical H1/H2/H3 implementation)
- `604f03c` — raw-span golden test hardening
- `4accbf2` — ChatGPT export decoder (13th format, **undocumented** — see §3)
- `6f0ff74` — path/image-build hardening

**VERIFIED**: `pkg/custodyhash/custodyhash.go` exists and is exactly what `CUSTODY.md` and the
2026-08-11 addendum in `UPSTREAM.md`/`CUSTODY.md` describe (see §2). `internal/custody.go` is
confirmed to be a thin delegating shim (`func HashFileH1(path string) ... { return
custodyhash.HashFileH1(path) }`, etc.), not a second implementation.

## 2. Custody hashing — exact construction, doc-vs-code match

**VERIFIED — code matches CUSTODY.md word-for-word.** `pkg/custodyhash/custodyhash.go:31-52`:

```go
CanonH1       = "h1-rawbytes-v1"                 // sha256(raw file bytes), lowercase hex
CanonH2       = "h2-rawelement-v1"                // XML: sha256(raw <sms>/<mms>/<call> element bytes)
CanonH2Record = "h2-rawrecord-v1"                 // non-XML: sha256(raw logical record bytes)
CanonH3       = "h3-chain-sbv-genesisempty-v1"    // genesis = "", chain_i = sha256(chain_{i-1} + "\n" + H2_i)
CanonH3Legacy = "h3-chain-v1"                     // ambiguous pre-2026-08-02 tag, read-only, never restamped
```

`FoldChain(chain, h2) = HashBytes([]byte(chain + "\n" + h2))` at `custodyhash.go:113-115` is the
single fold implementation; `internal/engine.go`'s streaming H3 and the batch `ChainH3` both call
it, so a streaming import and a batch import cannot diverge (this was explicitly the point of the
2026-08-11 decouple documented in `CUSTODY.md`'s "Tag crosswalk note").

This is a genuine positive example of the project's own hard rule ("hash-chain/canon tags must
name the exact construction, not just a version") being *followed*, including the documented
2026-08-02/08-11 correction where an ambiguous `h3-chain-v1` tag was caught colliding with a
different-but-valid Case Bible construction (genesis = H1, `sha256(prev_hex + h2_hex)`) and was
renamed to `h3-chain-sbv-genesisempty-v1` with the legacy tag frozen read-only for old rows
(`internal/custody.go:44-46`, `ChainCanonVersion = custodyhash.CanonH3Legacy`).

**A third, distinct hash chain exists and is correctly *not* conflated with H3**:
`internal/evidence_audit.go` implements `AuditCanonV1 = "sbv-audit-sha256-chain-v1"` — a
per-import tamper-evident audit trail over *derived operations and human review actions*
(attachment reference resolution, etc.), built by JSON-marshalling a payload struct (not raw byte
concatenation) and chaining `previous_hash`. The code comment is honest about its limits: "A local
hash chain detects modification when verified; an external signed checkpoint is required for
independent proof" (`evidence_audit.go:5-6`), and `HandleImportEvidenceReport`
(`universal_handlers.go:289-320`) surfaces exactly that caveat in its JSON response:
`"assurance": "tamper-evident when the audit chain verifies; independently signed external
checkpoint not configured"`.

**Cross-check honesty**: `CUSTODY.md` states the Python side (`server/evidence/custody.py`)
independently re-derives H1 and compares, but does **not** independently re-derive H2/H3 — it
records SBV's values as-is. This is stated as a known, explicit trust boundary, not hidden. I
confirmed the referenced Python files exist in the parent repo
(`server/evidence/custody.py`, `server/tools/sbv_sms.py`, `server/tools/_sbv_client.py`) — the
doc isn't describing vaporware, though I did not audit the Python side's actual behavior
(**INFERRED** that it does what the SBV-side doc claims).

## 3. Universal imports — 13 formats implemented, 12 documented

`UNIVERSAL_IMPORTS.md` lists 12 format plugins in a table. **VERIFIED all 12 are real,
registered importers**, each with `Format()`, `Priority()`, `Detect()`, `Run()` and a
`func init() { RegisterImporter(...) }` call:

| Doc format ID | File | Registered |
|---|---|---|
| `smsbackuprestore-xml` | `internal/sms_xml_importer.go` | yes |
| `ndjson` | `internal/ndjson_importer.go` | yes |
| `csv` | `internal/messaging_csv_importer.go` | yes |
| `messages-transcript` | `internal/messaging_txt_importers.go` | yes |
| `imessage-txt` | `internal/messaging_txt_importers.go` | yes |
| `imessage-html` | `internal/messaging_html_importers.go` | yes |
| `facebook-messenger-html` | `internal/messaging_html_importers.go` | yes |
| `google-voice-html` | `internal/google_voice_html_importer.go` | yes |
| `email-eml` | `internal/email_importers.go` | yes |
| `email-mbox` | `internal/email_importers.go` | yes |
| `google-chat-json` | `internal/google_chat_importer.go` | yes |
| `facebook-messenger-json` | `internal/facebook_json_importer.go` | yes |

**Doc gap (confirmed, not inferred):** `internal/chatgpt_json_importer.go` (`Format() =
"chatgpt-official-json"`, `Priority() = 820`) is a 13th, fully registered importer — streaming
decoder for ChatGPT's `conversations.json` export, added in commit `4accbf2` — that appears
**nowhere in `UNIVERSAL_IMPORTS.md`'s format table or plugin list**. The file's own header cites
"ADR-0049 Gap 2" and a 2026-08-12 signature fix, i.e. it postdates `UNIVERSAL_IMPORTS.md`'s last
edit (file mtime 2026-08-08 11:36). This is exactly the "doc drift" failure mode the project's own
hard rule warns about — a new capability shipped without the SSOT doc being updated in the same
turn.

Everything else in the "Implemented and follow-on source status" table
(`UNIVERSAL_IMPORTS.md`) checks out against files present: Google Chat "Partial", Google Voice
HTML "Implemented", EML/MBOX "Implemented", Facebook JSON "Implemented for one file" all have
corresponding `.go` files and `_test.go` files. PST/OST is honestly marked "Unsupported" and I
found no PST parser in the code — consistent.

The MMS large-attachment streaming path (128 KiB transfer buffer, 64 KiB reader buffer, files
written under `data/<user-id>/artifacts/import-<id>/attachments/`, base64 replaced by a marker in
a sanitized spool) is **VERIFIED present** in `internal/sms_xml_importer.go` (constant
`mmsStreamBufferBytes = 128 << 10`, comment block at line ~918 in the underlying parser
confirming "H2: hash the RAW `<mms>` element bytes ... BEFORE any conversion/base64-decode"). The
doc's disclosed limit — a literal 5+ GiB fixture was never run, only inferred from the
constant-buffer loop — is an honest, appropriately-hedged claim (**INFERRED**, and the doc says so
itself).

## 4. Search — real FTS5, but it does NOT cover the new import formats

**VERIFIED**: `internal/database.go` creates `messages_fts` as a genuine `CREATE VIRTUAL TABLE ...
USING fts5(body, address, contact_name, ...)` with INSERT/UPDATE/DELETE triggers keeping it in
sync with `messages` rowid-for-rowid (`database.go:123-148` and a second copy for the older schema
path at `:236-259`). `SearchMessages` (`database.go:1074+`) runs a real `MATCH` query with
`snippet(messages_fts, 2, '<mark>', '</mark>', '...', 50)` for highlighted excerpts. This is not a
LIKE-based fake — it is real FTS5, exactly as `SPEC.md` claims.

**Gap (confirmed by absence, not inference)**: FTS5 indexing exists **only** over the legacy
`messages` table, which is populated by the XML SMS/MMS/call importer's legacy projection path.
I grepped for any `import_records`-backed FTS table or index and found none
(`grep -rn "import_records.*fts\|fts.*import_records"` → no matches). `HandleImportRecords`
(`universal_handlers.go:209-232`) only filters by `kind` and `status` query params — there is no
`q=` full-text parameter anywhere in the universal-import read API. **This means the 13
universal-import formats (email, iMessage, Facebook Messenger, Google Chat/Voice, CSV, NDJSON,
ChatGPT export) are invisible to `GET /api/search` and to the FTS5 index entirely** — the only way
to find something in an EML/MBOX/Facebook/Google Chat import is to page through
`/api/imports/:id/records` client-side. For a forensic tool whose whole value proposition is
"find the message that matters," this is a significant, unadvertised limitation. Neither
`UNIVERSAL_IMPORTS.md` nor `SPEC.md` states this — it has to be inferred from the schema and route
list, which itself is a documentation gap.

**Exposure**: search is exposed only over the authenticated REST API (`GET /api/search`, cookie
session auth via `protected` Echo group in `main.go`), consumed today by the embedded React UI
(`frontend/src/components/Search.jsx`, not read in depth but present per `SPEC.md`'s file tree).
There is no separate machine-auth (API key/service token) path — the same session cookie the
browser UI uses is required, which matters for §6 (platform integration).

## 5. Evidence bundling / export — no PDF/attestation bundle; print-to-PDF is the only "PDF" path

Grepped the whole repo (Go + frontend) for `pdf|exhibit|attest|bundle|print|report`. Findings:

- **No server-side PDF generation anywhere.** The only Go matches for "pdf" are an attachment
  file-extension regex (`messaging_txt_importers.go:18`) and test fixture filenames. There is no
  PDF library in `go.mod`.
- **"Export PDF" in the UI is `window.print()`.** `frontend/src/components/MessageThread.jsx:383`
  (`handleExportPDF`) opens `/conversation/:address/print` in a new window
  (`frontend/src/components/PrintView.jsx`), which renders a print-styled DOM and calls
  `window.print()` (`PrintView.jsx:89/127/139`) after media finishes loading — i.e. it delegates
  to the browser's native "Print to PDF" dialog. This produces a plain conversation transcript
  with **no custody hash, no H1/H2/H3, no import ID, and no attestation text anywhere on the
  page** (confirmed by reading `PrintView.jsx` in full — it renders `conversation`, `messages`,
  `calls`, dates, and media only). It is a viewer convenience feature, not an evidentiary export.
- **`internal/export.go` is a real, native (Go-side, headless) export**, added in the "Phase 5a"
  commit, that dumps the full corpus as JSON or CSV via `/api/automation/export/:id`, and *does*
  attach the custody summary (`ExportResponse.Custody *ImportRecord`, carrying H1/H3/canon tags)
  — but it emits raw data, not a formatted/printable exhibit, and it draws from the legacy
  `GetActivity` read path (same universal-import blind spot as search: it walks `messages`/`calls`
  activity, not `import_records`, so a CSV/EML/Facebook import's records are **not** included in
  this export either — confirmed by reading `CollectExport`, which calls only `GetActivity`).
- **The actual attestation surface is `GET /api/imports/:id/report`**
  (`HandleImportEvidenceReport`, `universal_handlers.go:289-320`), which *is* real and
  well-built: it returns import metadata, attachment manifests, attachment references, and the
  full tamper-evident audit-event chain with a `verified`/`broken_at_event_id` self-check. This is
  the closest thing to a "custody attestation," but it is a JSON API response, not a
  human-readable/printable exhibit, and it is **completely undocumented in `UNIVERSAL_IMPORTS.md`**
  (its own "Inspect" route list at the API section omits `/report` entirely — another confirmed
  doc gap).

**Bottom line for Q5**: there is no single "export this conversation as a court-ready PDF exhibit
with embedded hashes" feature. The pieces exist (custody JSON report, custody-stamped JSON/CSV
corpus export, print-to-PDF transcript) but they are three disconnected artifacts, none of which
combines the human-readable transcript with the machine-verifiable custody chain in one document.

## 6. Integration with the parent platform — genuinely an isolated worker, not a co-tenant

**VERIFIED**: `go.mod` has exactly two direct non-framework dependencies
(`mattn/go-sqlite3`, `golang.org/x/time`) plus Echo, UUID, bcrypt/crypto, term, and a forked
`libheif-go`. **Zero** Postgres/pgx/database driver beyond SQLite, **zero** outbound HTTP client
calls anywhere in the Go source (`grep -rn "http.Get\|http.Post\|http.Client\|http.NewRequest"` →
no matches), **zero** references to `mcp` as a protocol/package (the only "postgres" hit in the
whole tree is a code comment in `custody.go` explaining that SBV deliberately does *not* hold
Postgres credentials). This matches `UPSTREAM.md`'s and `UNIVERSAL_IMPORTS.md`'s explicit design
statement ("SBV holds no database credentials... it only computes hashes and exposes them over
its REST API") — verified, not just claimed.

Deployment (`compose.yaml`, confirmed): SBV runs as its own container (`ghcr.io/lowcarbdev/sbv`),
own port `8081`, own bind-mounted SQLite files under `./data`, own healthcheck. The parent
platform's Python side (`server/tools/sbv_sms.py`, `server/tools/_sbv_client.py`,
`server/evidence/custody.py` — all confirmed present in the platform repo) is the one that reaches
*into* SBV over HTTP, pulls `/api/imports/:id`, independently re-verifies H1, and writes its own
append-only Postgres `evidence_hash`/`custody_event` rows. **Direction of integration is
one-way and pull-based**: platform → SBV, never SBV → platform. This is a clean, defensible
isolation boundary for a forensic tool (SBV never needs write access to the evidence-of-record
store), but it also means SBV cannot push/notify the platform — the platform must poll
`/api/imports` or be told an import finished by whatever kicked off the upload.

**Media-as-BLOB**: `SPEC.md`/`README.md` say media is stored as BLOBs in SQLite.
**VERIFIED still true for the legacy XML path**: `internal/database.go:92` and `:206` both define
`media_data BLOB` on the `messages` table, and `parser.go` base64-decodes MMS parts directly into
that column (`parser.go:311,324`). **However**, the newer universal-import MMS path
(`sms_xml_importer.go`, §3 above) streams large attachments to the filesystem
(`data/<user-id>/artifacts/import-<id>/attachments/`) instead of the DB — so there are now **two
different attachment-storage strategies live in the same binary depending on which code path
handled the upload** (`/api/upload` legacy vs `/api/imports` universal engine — confirmed both
routes exist and both call into the same `smsXMLImporter`/parser machinery per `main.go:124` and
`:144`, with `ProcessUploadedFile` in `parser.go:744` explicitly taking a mutex, "Serialize it with
automation/universal imports so overlapping requests cannot cross-attribute progress or dedup
outcomes" — i.e. the two paths are known by the authors to share global state and were
deliberately serialized to avoid corruption, which is itself a sign of architectural strain from
running two import pipelines side by side).

**Multi-GB corpus implication**: for the *legacy* XML path, every MMS image/video is still a BLOB
inside a single-writer SQLite file per user (`sbv_[uuid].db`). SQLite handles large BLOBs
adequately for read-heavy workloads, but a single writer-locked file holding many GB of case
evidence media is a real operational risk for a multi-case forensic corpus: no per-case
sharding, no S3/R2 offload for the legacy path, and file growth is unbounded within one SQLite
file (mitigated only by the "100k message limit per conversation" caveat in `README.md`, which is
a *display* limit, not a storage limit). The universal-import filesystem path is a strict
improvement here but is not (yet) the path the primary `/api/upload` UI flow uses for existing
users' habitual "upload SMS backup" workflow.

## 7. Fork maintenance risk

- **Divergence is heavy and one-directional.** 9 fork-only feature commits vs. 1 upstream sync
  commit since the original subtree merge (`git log --oneline -- vendored/sbv`, counted directly).
  The changed-file list in `UPSTREAM.md` covers only the *original* custody-hashing commit
  (`c4c5c06`) and is silent on everything from `813f3b2` onward — automation endpoints, the entire
  universal-import engine (`internal/importer.go`, `engine.go`, 8 new importer files,
  `universal_handlers.go`, `evidence_audit.go`, `export.go`), and `pkg/custodyhash`. Pulling
  upstream today would touch `parser.go`, `handlers.go`, `database.go`, `models.go`, and `main.go`
  — all five are now deeply intertwined with fork-only custody/universal-import code, so a
  `git subtree pull` is realistically a manual merge exercise, not a mechanical one, despite
  `UPSTREAM.md`'s "Updating from upstream" section presenting it as a simple 3-command recipe.
- **No vendored-inside-vendored weirdness found.** `go.mod`'s only forked dependency is
  `github.com/lowcarbdev/libheif-go` (pinned to a specific commit, with a code comment explaining
  why — a CGO build fix for libheif ≥1.19), which is a normal, well-documented pin, not nested
  vendoring.
- **Two live import pipelines sharing one SQLite schema** (§6) is itself a maintenance/complexity
  risk independent of upstream sync: two code paths (`/api/upload` legacy, `/api/imports`
  universal) both write into `messages`/`imports`, guarded by a single mutex
  (`importExecutionMu`) rather than being unified into one pipeline. The authors are clearly aware
  of this (the mutex and its comment exist specifically to prevent cross-attribution), but it is
  debt, not a finished migration.
- **Test coverage** is present and specifically targeted at the custody-critical paths: 12
  `_test.go` files including `custody_test.go` (determinism, known-answer, raw-not-normalized,
  streaming), `universal_engine_test.go`, and per-importer tests
  (`facebook_json_importer_test.go`, `email_importers_test.go`, `google_chat_importer_test.go`,
  `google_voice_html_importer_test.go`, `chatgpt_json_importer_test.go`,
  `attachment_conversion_test.go`, `automation_test.go`, `handlers_test.go`, `parser_test.go`). I
  did not execute `go test ./...` (out of scope for a read-only gap analysis; `DEVELOPMENT.md`
  notes `fts5` build tag is required, `heic` additionally requires libheif), so pass/fail state is
  **unverified**, only test *existence* is confirmed.

---

## Summary of doc-vs-code discrepancies found (all separately noted above, collected here)

1. `UPSTREAM.md`'s "changed files" list is stale — silent on everything after the original
   custody-hashing commit (automation, universal-import engine, `pkg/custodyhash`, evidence audit,
   export).
2. `UNIVERSAL_IMPORTS.md`'s format table lists 12 plugins; a 13th (`chatgpt-official-json`,
   `internal/chatgpt_json_importer.go`) is fully implemented, registered, and tested but absent
   from the doc.
3. `UNIVERSAL_IMPORTS.md`'s "Inspect" API route list omits `GET /api/imports/:id/report`
   (`HandleImportEvidenceReport`), which is the actual tamper-evident attestation endpoint —
   arguably the most evidentially important route in the whole universal-import surface.
4. No doc anywhere states that FTS5 search and the native export (`/api/automation/export`) only
   cover the legacy XML-derived `messages`/`calls` tables, not the 13 universal-import formats'
   `import_records`. This has to be inferred from the schema/route audit.
