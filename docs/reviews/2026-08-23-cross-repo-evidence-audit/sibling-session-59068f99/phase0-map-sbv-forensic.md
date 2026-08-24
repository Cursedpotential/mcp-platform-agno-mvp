> _Byline: Claude Code · Opus 5 · 2026-08-23_

# SBV-forensic capability map

Repo root read: `C:\Users\matts\AppData\Local\Temp\claude\...\scratchpad\sbv-forensic` (a
single-commit, `git subtree --squash` snapshot — `git log` shows exactly one commit,
`b0ec509`, "Phase 5a — native Go automation endpoints", 2026-07-10; no fuller history is
present in this checkout). `SPEC.md`, `CUSTODY.md`, `UPSTREAM.md` read in full before any code.

**Doc-drift flag up front:** `UPSTREAM.md`'s "Changed files" list (written 2026-07-09) only
covers the H1/H2/H3 custody layer. It does **not** mention `internal/automation.go`,
`internal/automation_handlers.go`, `internal/export.go`, or `internal/automation_test.go` —
all four exist in the tree, are fully wired, and were added one day later by commit `b0ec509`
("Phase 5a"). `UPSTREAM.md` is stale relative to the actual fork delta; this map treats the
code + commit message as ground truth over the doc where they disagree.

---

## 1. Fork delta (upstream `lowcarbdev/sbv` → this fork)

Two additive layers, confirmed against the single commit's diff stat and file contents:

**Layer A — forensic custody (per `UPSTREAM.md`, verified in code):**
| File | Status | Purpose |
|---|---|---|
| `internal/custody.go` | new | H1/H2/H3 hash primitives, `imports` table, `rawCaptureReader` |
| `internal/custody_test.go` | new | determinism/known-answer/raw-not-normalized/e2e tests |
| `internal/parser.go` | modified | H1 threaded through `SaveUploadedFile`; H2-per-element + H3-fold wired into `ParseSMSBackupStreaming` |
| `internal/database.go` | modified | `content_hash` column (`ensureCustodyColumns`), `imports` table, `content_hash` folded into read paths |
| `internal/models.go` | modified | `ContentHash` field on `Message` + `CallLog` |
| `internal/handlers.go` | modified | `HandleHashes` (`GET /api/hashes/:importID`) |
| `internal/autoimport.go` | modified | auto-import path also computes H1 (`internal/autoimport.go:268`) |
| `main.go` | modified | registers `GET /api/hashes/:importID` (`main.go:117`) |

**Layer B — "Phase 5a" native automation (commit `b0ec509`, NOT in `UPSTREAM.md`):**
| File | Status | Purpose |
|---|---|---|
| `internal/automation.go` | new | job registry (`ExtractJob`), `StartExtractJob`/`runExtract`, backup enumeration |
| `internal/automation_handlers.go` | new | 4 HTTP handlers (extract/status/export/backups) |
| `internal/export.go` | new | JSON/CSV export synthesis, custody-stamped |
| `internal/automation_test.go` | new | handler tests incl. an H1 cross-check (extract vs. independent hash) |
| `main.go` | modified | +4 route registrations (`main.go:123-126`) |

Everything else (`auth.go`, `auth_handlers.go`, `middleware.go`, `settings.go`,
`heic_enabled.go`/`heic_disabled.go`, `cors_middleware.go`, all of `frontend/`) is inherited
upstream SBV, unmodified by the fork's stated changes. SBV holds **no Postgres/database
credentials** for any external evidence store per `UPSTREAM.md` — it only computes hashes and
exposes them over REST; a separate Python custody gate (`server/evidence/custody.py`,
`server/evidence/tools/sbv_sms.py` — outside this repo, referenced but not vendored here)
cross-checks and records them.

---

## 2. Ingest

**Format:** Android "SMS Backup & Restore" XML export only (`<smses>` root, `<sms>`, `<mms>`,
`<call>` child elements) — `internal/parser.go:24-97` defines the exact schema
(`SMSBackup`/`SMSEntry`/`MMSEntry`/`MMSPart`/`MMSAddr`/`CallEntry`). No other backup format
(no iOS, no Google Takeout, no other Android tool) is parsed. Confirmed by `backend/testdata/sample_backup.xml:1-3` (`<?xml ...?><smses count="95">`).

**Parser location:** `internal/parser.go`.
- `ParseSMSBackup` (`parser.go:104`) — non-streaming, whole-document decode (unused by the
  live upload/automation paths — see §8, orphaned).
- `ParseSMSBackupStreaming` (`parser.go:814`) — the actual production path. Streams via
  `xml.Decoder` + a custom `rawCaptureReader` (`custody.go:122-167`) so raw byte spans can be
  captured for H2 alongside incremental per-record DB inserts (batch size effectively 1 on the
  interactive upload path, 100 on auto-import/automation-extract).

**Two ingest entry points, both call `ParseSMSBackupStreaming`:**
1. **Interactive upload** — `POST /api/upload` → `HandleUpload` (`handlers.go:30`) →
   `SaveUploadedFile` (`parser.go:711`, computes H1 while streaming to a temp file) →
   background goroutine `ProcessUploadedFile` (`parser.go:744`) → `ParseSMSBackupStreaming`.
   Temp file is deleted after processing (`parser.go:746-751`).
2. **Auto-import** — `internal/autoimport.go`. A background service
   (`NewAutoImportService`, started in `main.go:159-161`) polls every user's
   `data/<uuid>/ingest/` directory once a minute (`autoimport.go:27,42-48`), waits for file
   stability (5s unchanged size/mtime, `autoimport.go:226-247`), computes H1
   (`autoimport.go:268`), parses, then moves the source file to `data/<uuid>/complete/` with a
   per-import `.log` (never deleted — this is the durable evidence retention path,
   `autoimport.go:177-221`).
3. **Headless/agent-driven** (Phase 5a) — `POST /api/automation/extract` → `StartExtractJob` →
   `runExtract` (`automation.go:148-221`), which calls the identical `HashFileH1` +
   `ParseSMSBackupStreaming` pair on a caller-supplied server-visible path. Unlike upload, the
   source file is opened read-only and **never deleted** (`automation.go:20-21,182`) — explicitly
   evidence, not scratch.

**Attachments/media:** MMS `<part>` elements carry base64 in the `data` attribute
(`MMSPart.Data`, `parser.go:79`). `convertMMSEntry` (`parser.go:193-354`) base64-decodes the
**first** non-SMIL, non-text media part only (`parser.go:310-330` — "Only store first media
item"; multi-attachment MMS beyond the first part are dropped from `media_data`, though
covered by H2 since H2 hashes the whole raw `<mms>` element). vCards (`text/vcard`,
`text/x-vcard`, `text/directory`) are treated as media, not body text (`parser.go:309-318`).
SMIL presentation markup is stripped (`parser.go:304-306`). Media is stored as a raw `BLOB`
(`media_data` column, `database.go:92`) — **not base64 in the DB**, base64 only exists
transiently as the XML attribute value before decode. HEIC images are optionally converted to
JPEG via libheif (`internal/heic_enabled.go` / `heic_disabled.go`, build-tag gated); 3GP/MKV
video and AMR audio are transcoded to MP4/MP3 via shelling out to `ffmpeg`
(`parser.go:464-521`, `parser.go:539-582`) — conversion happens **on read** (`HandleMedia`,
`handlers.go:464-562`, triggered by `?transcode=true`), not at ingest time, so the stored BLOB
is always the original bytes.

**Phone normalization:** `normalizePhoneNumber` (`internal/utils.go:8-45`) strips
non-digits and coerces 10/11-digit US numbers to `+1XXXXXXXXXX`. This happens only on the
**normalized** record path (`convertSMSEntry`/`convertMMSEntry`/`convertCallEntry`), strictly
after H2 hashing of the raw element — the custody chain never sees normalized data (verified
by `custody_test.go:94-112`, `TestHashRecordH2_RawNotNormalized`).

---

## 3. Custody & hashing — THE KEY AREA

`CUSTODY.md` was verified line-for-line against `internal/custody.go`, `internal/parser.go`,
and `internal/custody_test.go`. **No discrepancy found** — the doc is accurate. Ordering
contract, as stated and as coded:

```
H1 (raw file)  ->  H2 (raw per-record)  ->  H3 (chain)  ->  (only THEN) normalize
```

### H1 — file-level (`h1-rawbytes-v1`)

> `H1 = lowercase_hex( SHA-256( raw file bytes ) )`

Code (`internal/custody.go:47-59`):
```go
func HashFileH1(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	buf := make([]byte, 1024*1024)
	if _, err := io.CopyBuffer(h, f, buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
```
On the interactive-upload path H1 is instead computed streaming-while-copying to the temp
file, same primitive (`internal/parser.go:727-737`):
```go
hasher := sha256.New()
_, err = io.Copy(tempFile, io.TeeReader(file, hasher))
...
fileHash := hex.EncodeToString(hasher.Sum(nil))
```
Both are a plain SHA-256 over unmodified bytes — claimed byte-identical to the (out-of-repo)
Python `server/evidence/custody.py::_sha256_file`; not independently verifiable from this
repo alone since that file isn't vendored here, but the Go-side construction is a bog-standard
SHA-256 with no reformatting, consistent with the claim.

### H2 — per-record (`h2-rawelement-v1`)

> `H2 = lowercase_hex( SHA-256( raw source XML element bytes ) )` — exact bytes of one
> `<sms.../>`, `<mms>...</mms>`, or `<call.../>` element, opening `<` through closing `>`
> inclusive, leading inter-element whitespace trimmed, captured **before** `DecodeElement`'s
> result is normalized.

Code (`internal/custody.go:77-79`):
```go
func HashRecordH2(rawElement []byte) string {
	return HashBytesSHA256(rawElement)
}
```
Wired at each of the three element types in `ParseSMSBackupStreaming`, e.g. for `<sms>`
(`internal/parser.go:866-885`, identical pattern repeated for `<mms>` at `parser.go:904-928`
and `<call>` at `parser.go:951-969`):
```go
if elem.Name.Local == "sms" {
	var sms SMSEntry
	err := decoder.DecodeElement(&sms, &elem)
	...
	// H2: hash the RAW <sms> element bytes BEFORE any conversion.
	endOff := decoder.InputOffset()
	h2 := HashRecordH2(trimLeadingXMLSpace(cr.slice(startOff, endOff)))
	cr.discardBefore(endOff)

	msg, err := convertSMSEntry(sms)
	...
	msg.ContentHash = h2
```
`startOff` is captured via `decoder.InputOffset()` **before** `decoder.Token()` reads the next
token (`parser.go:839`), and the raw byte span is pulled from a sliding-window buffer
(`rawCaptureReader`, `custody.go:122-167`) that retains only the not-yet-discarded portion of
the input stream (bounded memory — `custody.go:154-167`). Leading whitespace between elements
is trimmed by `trimLeadingXMLSpace` (`custody.go:102-113`) so the hashed span begins exactly at
`<`.

Determinism/raw-not-normalized proof: `custody_test.go:94-112` constructs two `<sms>` elements
whose addresses (`5551234567` vs `555-123-4567`) normalize identically via
`normalizePhoneNumber`, and asserts their H2s **differ**; a third variant differing only in
attribute whitespace also produces a different H2. This is the load-bearing forensic property.

### H3 — batch chain (`h3-chain-v1`)

Left fold over ordered per-record H2s, separator `"\n"`:
```
chain_0 = prevChain                                   # "" for a fresh import batch
chain_i = lowercase_hex( SHA-256( chain_{i-1} + "\n" + H2_i ) )
H3      = chain_n
```

Code, verbatim (`internal/custody.go:91-97`):
```go
func ChainH3(orderedH2s []string, prevChain string) string {
	chain := prevChain
	for _, h2 := range orderedH2s {
		chain = HashBytesSHA256([]byte(chain + "\n" + h2))
	}
	return chain
}
```
Called once, at the end of a full parse pass, over the full ordered slice of every record's H2
in that batch (`internal/parser.go:992-999`):
```go
chainHash := ChainH3(recordHashes, "")
if _, err := RecordImport(userDB, fileHash, len(recordHashes), chainHash); err != nil {
	slog.Error("Error recording import custody row", "error", err, "file_hash", fileHash, "records", len(recordHashes))
}
```
`recordHashes` (`parser.go:831`) accumulates H2s in strict source/parse order across **all
three** record types interleaved as they appear in the file (SMS, MMS, and calls share one
ordered slice — confirmed by the e2e test `custody_test.go:185-251`, which mixes one `<sms>`
and one `<call>` and checks `ChainH3([]string{smsH2, callH2}, "")` matches). Order-sensitivity
and the empty-batch identity (`ChainH3(nil, "") == ""`) are asserted in
`custody_test.go:142-152`.

**Scope: per-import-batch, not corpus-wide, not per-conversation.** One H3 (and one `imports`
row) is written per parse run — one per upload, one per auto-import file, one per
`/api/automation/extract` job. `prevChain` exists as a hook for chaining batches
end-to-end but is hardcoded to `""` at every call site in this repo (`parser.go:994`) — batch
chaining across imports is **not currently exercised**, only the primitive supports it.

### Storage & exposure

- `messages.content_hash TEXT` — H2 for that row. Added via idempotent migration
  `ensureCustodyColumns` (`custody.go:228-247`) rather than baked into the inline
  `CREATE TABLE` (verified: `content_hash` is absent from both inline `CREATE TABLE messages`
  blocks at `database.go:81-110` and `195-224`, and is ALTER-added after — `database.go:159,269`
  call `ensureCustodyColumns`).
- `imports(id, file_hash, record_count, chain_hash, canon_version, imported_at)` — one row per
  batch, `internal/custody.go:238-245`.
- `GET /api/hashes/:importID` — `internal/handlers.go:103-127` (`HandleHashes`); `:importID`
  may be numeric or `"latest"` (→ `GetLatestImport`, `custody.go:220-223`, "highest id").
  Returns the full `ImportRecord` JSON including the three canon-version strings
  (`FileHashCanon`/`RecordHashCanon`/`ChainCanon`, populated in `scanImport`,
  `custody.go:199-209`).
- `content_hash` is additionally surfaced in the read payloads: confirmed present in the
  `SELECT`s backing `GetMessages` (`database.go:554`), `GetCallLogs`/`GetAllCalls`
  (`database.go:621,664`), and `GetActivity`/`GetActivityByAddress` (`database.go:721`) — i.e.
  every record a user reads via `/api/messages`, `/api/calls`, `/api/activity` carries its own
  H2 as `content_hash` in the JSON (per `Message.ContentHash`/`CallLog.ContentHash`,
  `models.go:37,51`, both `json:"content_hash,omitempty"`).

### Independent verifiability / verifier

- **H1**: trivially re-derivable by anyone with the source file — `sha256sum <file>`.
- **H2**: re-derivable by extracting the exact raw element span (opening `<` to closing `>`,
  no surrounding whitespace) from the source XML and SHA-256'ing it. CUSTODY.md states this
  explicitly and it matches the code; there is **no built-in Go-side re-derivation tool** in
  this repo beyond the unit tests — `custody_test.go` re-derives H2/H3 independently as
  assertions, but nothing exposes a "verify this file against a recorded H1/H2/H3" CLI or
  endpoint. The actual **cross-check is delegated to the Python side**
  (`server/evidence/tools/sbv_sms.py::_reconcile_custody`, per CUSTODY.md — that file is
  **not present in this repo**, so its correctness is unverifiable from here; SBV's role per
  `UPSTREAM.md` is producer-only, not verifier).
- **H3**: re-derivable identically to the `ChainH3` code, and `custody_test.go:131-139`
  contains a hand-rolled independent re-implementation of the fold that is asserted equal to
  the real function's output — this is the closest thing to a "verifier" that ships in this
  repo, and it's a test, not a callable tool/endpoint.
- **No in-repo custody verifier endpoint or CLI exists.** `GET /api/hashes/:importID` only
  *serves* the recorded hashes; it does not recompute anything to check for tampering. The
  actual verify step (H1 re-derived independently, compared, `verified`/`integrity_violation`
  event emitted) is entirely on the Python side per CUSTODY.md's "Cross-check on the Python
  side" section — unauditable from this repo.

---

## 4. Search

One search surface: SQLite **FTS5** full-text search over message bodies.

- Schema: `messages_fts` virtual table (`database.go:124-132`, duplicated for per-user DBs at
  `database.go:236-244`) — `fts5(message_id UNINDEXED, address UNINDEXED, body, contact_name
  UNINDEXED, date UNINDEXED, content='messages', content_rowid='id')`. Only `body` is actually
  indexed for text matching; `address`/`contact_name`/`date` are stored but `UNINDEXED` (not
  searchable, just retrievable via the FTS row).
- Kept in sync by three triggers (`messages_ai`/`messages_ad`/`messages_au`,
  `database.go:135-150`) firing on INSERT/DELETE/UPDATE of `messages`.
- Query function: `SearchMessages` (`database.go:1045-1084`) — `SELECT ... FROM messages_fts
  JOIN messages ... WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?`, with an FTS5
  `snippet(...)` highlight (`<mark>`/`</mark>`, 50-token window).
- Endpoint: `GET /api/search?q=&limit=` → `HandleSearch` (`handlers.go:564-597`), protected,
  defaults `limit=100`.
- **Coverage gap:** because only `body` is indexed and call rows (`record_type=3`) have no
  `body`, calls are effectively unsearchable by content — the FTS row exists (insert trigger
  fires unconditionally) but matches nothing. Search is SMS/MMS-text-only in practice.
- No date-range or address filter on the search endpoint itself (SPEC.md's documented `q`,
  `start_date`, `end_date` params for `/api/search` are **not actually implemented** —
  `HandleSearch` only reads `q` and `limit` from query params; `start`/`end` are silently
  ignored. This is a SPEC.md/code mismatch, not a UPSTREAM.md one.).

---

## 5. Automation/API endpoints (full enumeration, cross-checked against `main.go`)

All routes below are read directly from `main.go:90-134`; "wired" means registered in
`main.go` **and** the handler function exists and is non-stub (verified for every handler in
this section by reading its source).

| Method | Path | Auth | Handler | main.go:line | What it does |
|---|---|---|---|---|---|
| POST | `/api/auth/register` | public | `HandleRegister` | 90 | create account (bcrypt) |
| POST | `/api/auth/login` | public | `HandleLogin` | 91 | login, sets `sbv_session` cookie |
| POST | `/api/auth/logout` | public | `HandleLogout` | 92 | clear session |
| GET | `/api/auth/me` | protected | `HandleMe` | 99 | current user info |
| POST | `/api/auth/change-password` | protected | `HandleChangePassword` | 100 | update password |
| POST | `/api/upload` | protected | `HandleUpload` | 101 | upload XML backup (async, H1 computed) |
| GET | `/api/conversations` | protected | `HandleConversations` | 102 | list conversations, `start`/`end` filters |
| GET | `/api/messages` | protected | `HandleMessages` | 103 | messages for `address`; `type=call` → calls; `type=conversation` → paginated combined activity |
| GET | `/api/activity` | protected | `HandleActivity` | 104 | paginated timeline of messages+calls |
| GET | `/api/calls` | protected | `HandleCalls` | 105 | call log, paginated |
| GET | `/api/daterange` | protected | `HandleDateRange` | 106 | min/max dates in DB |
| GET | `/api/progress` | protected | `HandleProgress` | 107 | poll current upload progress |
| GET | `/api/media` | protected | `HandleMedia` | 108 | serve one media BLOB by message `id`, supports HTTP Range + `?transcode=true` |
| GET | `/api/media-items` | protected | `HandleMediaItems` | 109 | media metadata list for `address` (no bytes) |
| GET | `/api/search` | protected | `HandleSearch` | 110 | FTS5 search, `q`+`limit` |
| GET | `/api/settings` | protected | `HandleGetSettings` | 111 | per-user JSON prefs |
| PUT | `/api/settings` | protected | `HandleUpdateSettings` | 112 | update per-user JSON prefs |
| GET | `/api/analytics` | protected | `HandleAnalytics` | 113 | summary stats/top contacts/hourly+daily distributions (not in SPEC.md's table — undocumented-but-wired) |
| GET | `/api/hashes/:importID` | protected | `HandleHashes` | 117 | custody summary for one import (or `latest`) |
| POST | `/api/automation/extract` | protected | `HandleAutomationExtract` | 123 | kick off headless custody-preserving extraction of a server-visible path; `{path, filename?, wait?}` |
| GET | `/api/automation/status/:id` | protected | `HandleAutomationStatus` | 124 | poll an extraction job |
| GET | `/api/automation/export/:id` | protected | `HandleAutomationExport` | 125 | synthesized export (`?format=json\|csv`), custody-stamped; `:id` = `latest`/`all`/job-id |
| GET | `/api/automation/backups` | protected | `HandleAutomationBackups` | 126 | list `imports` rows + retained files in `ingest/`+`complete/` |
| GET | `/api/health` | public | inline closure | 129 | `200 OK` |
| GET | `/api/version` | public | `HandleVersion` | 134 | reads `/app/version.json` or `{"version":"dev"}` |
| GET | `/*` | public (static) | SPA fallback | 150 | serves `frontend/dist/index.html`, only if that dir exists |

Every handler above has a real, non-trivial body — none are stubs. All are reachable: the
`protected` group (`main.go:95-97`) requires `AuthMiddleware` + applies `NoCacheMiddleware`;
public routes bypass auth by design (register/login/logout/health/version/static).

`SPEC.md`'s API table (written pre-fork, upstream-only) is missing `/api/hashes/:importID`,
all four `/api/automation/*` routes, and `/api/analytics` — expected, since SPEC.md predates
those additions and was not updated (doc drift, consistent with the `UPSTREAM.md` gap in §1).

---

## 6. Export / evidence output

**Yes — native JSON/CSV export exists** (Phase 5a, `internal/export.go`), reachable at
`GET /api/automation/export/:id?format=json|csv`.

- `CollectExport` (`export.go:42-70`) walks the **entire** corpus via the same paginated
  `GetActivity` the `/api/activity` endpoint uses (1000-row pages), splitting into `[]*Message`
  and `[]*CallLog` — no separate/duplicated query path.
- `ExportResponse` (`export.go:27-36`) carries `format`, optional `job_id`, `message_count`,
  `call_count`, and — the provenance piece — `custody *ImportRecord` (the full H1/H3/canon
  summary). For JSON format, `messages`/`calls` arrays are populated directly (each message/call
  already carries its own `content_hash` H2, per §3). For CSV, `messagesToCSV` (`export.go:75-120`)
  builds a sorted union of all JSON keys as columns (mirrors the described Python facade's
  `csv.DictWriter` behavior) — the CSV header will include `content_hash` per row since it's a
  JSON field on `Message`/`CallLog`.
- `MediaData []byte` on `Message` is tagged `json:"-"` (`models.go:16`) — **media bytes are
  excluded from every export**, JSON or CSV; only `media_type`/`media_base64` (the latter never
  populated by this code path) would appear, so exports are metadata+text, not attachment
  bundles.
- Custody anchor resolution (`automation_handlers.go:126-145`): `:id` of `latest`/`all`/empty
  resolves to `GetLatestImport`; a specific id is looked up as a job id in the in-memory job
  registry and its `ImportID` used to fetch that job's specific `imports` row via `GetImport`
  — so an export can be pinned to the exact custody batch that produced it, not just "whatever
  is latest now."
- No PDF/exhibit-formatted output, no signature/attestation on the export bundle itself beyond
  the embedded `custody` JSON block — the export is a data dump with a hash pointer, not a
  self-verifying archive (e.g. no hash-of-the-export-file is computed).

---

## 7. Storage

SQLite, **one database file per user** (`sbv_[user-uuid].db`) plus one shared auth DB
(`sbv.db`). Schema, from `internal/database.go` (identical blocks for the shared/legacy `db`
at `database.go:81-165` and the per-user path at `database.go:195-283`):

**`messages`** (`database.go:81-110`, `content_hash` added by migration — see §3):
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `record_type` | INTEGER NOT NULL DEFAULT 1 | 1=SMS, 2=MMS, 3=call |
| `address` | TEXT NOT NULL | phone number(s), comma-joined for group MMS |
| `body` | TEXT | |
| `type` | INTEGER NOT NULL | direction/status code |
| `date` | INTEGER NOT NULL | unix seconds |
| `read` | INTEGER DEFAULT 0 | |
| `thread_id` | INTEGER | |
| `subject`, `media_type`, `media_data` (BLOB), `protocol`, `status`, `service_center`, `sub_id`, `contact_name`, `sender`, `content_type`, `read_report`, `read_status`, `message_id`, `message_size`, `message_type`, `sim_slot`, `addresses`, `duration`, `presentation`, `subscription_id` | various | |
| `content_hash` | TEXT | **H2**, added via `ensureCustodyColumns` |

Indexes: `idx_address`, `idx_date`, `idx_thread`, `idx_record_type`,
`idx_record_type_date`, `idx_address_date` (`database.go:112-117`), plus a **UNIQUE** index
that makes inserts idempotent (`database.go:121`):
```sql
CREATE UNIQUE INDEX idx_message_unique ON messages(record_type, address, date, type,
  COALESCE(body, ''), COALESCE(content_type, ''), COALESCE(message_id, ''), COALESCE(duration, 0));
```
Both `InsertMessage` and `InsertCallLog` use `ON CONFLICT DO NOTHING` against this index
(`database.go:335,382`) — re-ingesting the same source file is a no-op for already-present
rows, though note this dedup key does **not** include `content_hash`, so it dedupes on
normalized content equality, not on raw-byte identity.

**`messages_fts`** — FTS5 virtual table over `body` (see §4).

**`imports`** (`custody.go:238-245`): `id, file_hash (H1), record_count, chain_hash (H3),
canon_version, imported_at` — one row per parse batch.

**Auth DB (`sbv.db`, shared)**: `users`, `sessions`, `settings` tables per SPEC.md's
description — not re-verified against `auth.go` in this pass beyond confirming those handlers
exist and are wired (out of scope for this custody-focused map; flagged for a follow-up pass
if auth internals matter).

Per-user DB location: `data/<user-uuid>/` (per `ADMIN.md`), with `ingest/` (drop zone) and
`complete/` (processed, retained) subdirectories — these are the durable evidence-file
retention paths enumerated by `GET /api/automation/backups` (§5, §6).

---

## 8. Known-broken / disabled / dead code

Grepped `internal/` + `main.go` for `TODO`, `FIXME`, `STUB`, `XXX`, `panic(`,
"not implemented"/"unimplemented" — **zero matches across the entire Go source tree.** No
loud stubs, no panics, no unimplemented handlers.

Orphaned (defined, never called — verified by grepping for callers):
- **`ParseSMSBackup`** (`internal/parser.go:104-145`) — the non-streaming, whole-document
  parser. Not referenced anywhere outside its own definition; `parser_test.go` may exercise it
  in isolation (not confirmed in this pass) but no production code path (upload, auto-import,
  automation-extract) calls it. `ParseSMSBackupStreaming` is what's actually wired everywhere.
- **`InsertCallLogBatch`** (`internal/database.go:408-446`) — a transactional batch-insert
  helper for call logs. Zero callers anywhere in `internal/` or `main.go`. Notably it also
  **omits `content_hash` from its INSERT** (`database.go:419-423` — 8 columns, no
  `content_hash`), so if it were ever wired up it would silently produce custody-incomplete
  call rows; as-is it's simply dead code, not a live gap.
- **`extractGroupNameFromTrID`** (`internal/parser.go:393-433`) — the real logic is
  commented out (`/* ... */`, `parser.go:396-432`) and the function unconditionally
  `return ""` (`parser.go:395`). It's still *called* (`parser.go:343-344`, `convertMMSEntry`),
  so this is a live no-op rather than a fully orphaned function — RCS group-chat name
  extraction from `tr_id` is effectively disabled, silently returning empty every time.

Frontend has **zero references** to `hash`, `custody`, or `automation` (`grep -rl` over
`frontend/src/` returned nothing) — the entire custody + automation layer is API-only. It is
WIRED end-to-end at the HTTP/DB layer (confirmed by tests in §2/§3/§5), but not surfaced
anywhere in the React UI; a user browsing the SBV web app never sees a hash. This is expected
given the fork's stated purpose (agent/automation-drivable, Python-orchestrated), not a defect,
but worth flagging as "backend-complete, UI-absent."

SPEC.md documents `start_date`/`end_date` query params on `GET /api/search`
(§4 above) that `HandleSearch` does not read — a doc/code mismatch, not a code defect.

No Go toolchain was available to actually `go build`/`go vet`/`go test` this checkout (per the
original Phase 5a commit message, which notes the same constraint on the authoring box); all
findings above are from static reading + grep-verified call graphs, not a compiled/executed
build.
