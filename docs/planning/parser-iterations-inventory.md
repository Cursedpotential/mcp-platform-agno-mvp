> _Byline: Claude Code · Opus 4.8 · 2026-07-10_

> ⏸️ **FROZEN HISTORICAL SNAPSHOT — paths accurate as of 2026-07-10, NOT current.**
> This is a point-in-time catalogue, deliberately preserved (owner: "catalog EVERYTHING, preserve
> variants"). Do **not** use it to locate code. Module paths here pre-date the ADR-0035 tools
> subnamespacing — e.g. it says `server/tools/sbv_sms.py`, but the live module is
> `server/tools/parsers/messaging/sbv_sms.py`; likewise `messaging_transcript.py` now lives under
> `server/tools/parsers/messaging/`. For current locations read the live tree
> (`server/tools/parsers/{messaging,ai_chat,generic}/`). Status columns are also frozen — SBV's
> primary/shadow state in particular changed twice after this date (see DECISION_LOG D-040).
> Frozen 2026-08-10 — _Claude Code · Opus 5_

# Messaging & Social-Media Parser Iterations — Exhaustive Inventory

**Scope:** Every messaging / social-media evidence-source parser reachable from this machine, across all
iterations (local worktree, all git branches/remotes, donor/archive trees, the DuckDB iteration index).
Sources in scope: iMessage (html/txt/pdf), SMS/MMS (XML/CSV), Facebook Messenger (HTML/JSON),
generic messaging transcripts/CSV, phone-call logs, SBV (SMS Backup Viewer).
AI-chat/LLM-transcript parsers (chatgpt/claude/gemini/perplexity) are explicitly OUT OF SCOPE.

**Owner directive:** DO NOT dedupe or pick a winner. Catalog EVERYTHING, preserve variants. "If there's
multiple copies, KEEP multiple copies — we'll see which one works best."

---

## 0. Where I looked (coverage map)

| Location | What's there | How reached |
|---|---|---|
| `Agno-MCP-Platform/server/tools/*.py` (branch `main`) | **Canonical current Python lane** — 9 messaging parsers, all emit `NormalizedRecord` | on-disk worktree + `git show main:` |
| Git branch `origin/feat/messaging-parsers-owner-custom` | Owner's custom variants (`evidence/tools/`); divergent iMessage-HTML + pre-custody SBV + `markdown_transcript.py` | `git show`/`diff` (no checkout) |
| Git branch `origin/feat/home-parser-work` + `origin/reconcile/home-parser-work` | "home" parser work; smaller iMessage-HTML / messaging_csv variants | `git show`/`diff` |
| Git branch `origin/feature/sbv-forensic-fork` | Same Python set under `server/evidence/tools/` + **vendored SBV Go app** (`vendored/sbv/`) | `git ls-tree` |
| Git branch `origin/feature/facade-collapse-batch-a` | `server/tools/` layout + `server/agents/tools/sbv_tools.py` | `git ls-tree` |
| Git branch `origin/restructure/tools-layer` | Same parsers under `server/tools/` (the D-026 move) | `git ls-tree` |
| Git branch `origin/archive/v0.1.1-pre-reset` | Oldest reset point — only `scripts/mine_transcripts.py` survives | `git ls-tree` |
| Remotes `sbv-fork/main`, `sbv-upstream/main` | **SBV service source** (Go backend `internal/parser.go` + `custody.go`, React frontend) | `git show sbv-fork/main:` |
| `dev-resources/Archives/dial-stack/` | **TS lineage A** (ts-mcp-server tools, incl `(2)` dupes) + **TS lineage B** (loaders) | filesystem |
| `dev-resources/Archives/TheBigOne/` | TS lineage-B loaders (2 micro-variants) + `sms_backup_parser.py` (ConflictAnalysisApp) | filesystem |
| `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/` | ConversationExtractor `FacebookParser.py` (Autopsy/Jython), `sms_backup_parser.py`, TS-loose copies, SBV SQL schemas | filesystem |
| `extracted-code/parsers/messaging/` + `extracted-code/sbv/` | De-duplicated extraction of TS loaders + `sms_backup_parser.py` + SBV SMS SQL | filesystem |
| `Agno-MCP-Platform-alpha/.claude/worktrees/migration-plan-v8/…/loaders/` | TS lineage-B copies (migration snapshot) | DuckDB index |
| `D:\casebible\iterations_index.duckdb` (`iteration_index`, 2,080 rows / 12 iterations) | The owner's iteration catalog — queried for all parser-named files | DuckDB CLI v1.5.3 |

**Note on the "iteration index of ~2,080 artifacts across 12 branches/repos":** it is the DuckDB catalog
`D:\casebible\iterations_index.duckdb` (table `iteration_index`, 12 distinct `iteration` values totalling
2,080 rows). There is **no** markdown catalog of it in `docs/`. The 12 iterations: `dial-stack` (595),
`Agno-MCP-Platform` (595), `OTHER_RESOURCES_TO_SORT` (566), `TheBigOne` (87), `The_Platform_Archive` (80),
`_project_dirs_loose` (34), `Agno-MCP-Platform-alpha` (34), `extracted-code` (27), `dev_docs_artifacts` (18),
`mcp-tool-platform` (17), `TEMP_GITHUB_COMPARE` (17), `platform_pbackup` (10).

**Canonical output shape (current lane):** `NormalizedRecord` (Pydantic, `server/evidence/normalize.py`):
`record_type` (message|call|event|media), `source`, `conversation_id`, `role`, `participants[]`, `content`,
`occurred_at` (tz-aware, VALID time), `knowledge_time` (bitemporal), `disclosure_tier`, `attrs{}` (free-form
forensic sidecar). All current parsers return via `_common.records_out(...)` → identical shape; per-parser
richness lives in `attrs`. Registry (`server/tools/registry.py`) resolves a `capability` to an ordered list
(first = preferred, rest = substitution candidates per ADR-0023 dual-parser mesh); alphabetical module import
sets primacy for a shared capability.

---

## 1. iMessage parsers (html / txt / pdf)

| # | Variant / location | Format | Capability | Key logic & edge cases | Maturity | Deps | Output shape |
|---|---|---|---|---|---|---|---|
| 1 | `server/tools/imessage_html.py` (`main`, 445 ln) | imessage-exporter `--format html` + owner-custom `div.bubble.from-me/from-them` DOM | `parse.imessage` (`messages.imessage-html`, `.html/.htm`) | Content-sniff `looks_like_imessage_html`; raises `ValueError` to defer to FB parser. Direction sent/received. **Tapbacks**, **edits** (`edited_history`), **retraction** (`span.unsent`), **read receipts** (regex), attachments incl. `missing` kind, call detection, participant roster backfill, silent-empty content substitution. Naive TS → UTC, raw kept. | Production (proven on 1918-msg owner sample) | BeautifulSoup4 (`html.parser`) | Canonical NormalizedRecord (message/call/event) |
| 2 | `imessage_html.py` @ `origin/feat/messaging-parsers-owner-custom` (549 ln, **+104 vs main / 156 diff-lines**) | Adds a distinct **regex fallback** for the owner's exact HTML export | `parse.imessage` | Adds `_parse_owner_format_regex(raw, conv_id)` + `_strip_html()`; **bounded sibling scan** ("stop at next bubble to avoid cross-message attachment leakage"); reads `utf-8 errors=replace`. **Strongest attachment-leakage guard of the iMessage variants.** | Production variant | BeautifulSoup4 + regex | Canonical NormalizedRecord |
| 3 | `imessage_html.py` @ `origin/feat/home-parser-work` (437 ln, smaller) | exporter HTML | `parse.imessage` | Leaner/earlier cut of the HTML parser (−8 vs main); predates some edge-case handling. | Partial/earlier | BeautifulSoup4 | Canonical NormalizedRecord |
| 4 | `server/tools/imessage_txt.py` (`main`, 488 ln) | imessage-exporter `--format txt` — **shared grammar engine** `parse_txt_text` | `parse.imessage` (`messages.imessage-txt`, `.txt`) | Structural block grammar (timestamp header + sender + body); **announcements → `event`**; tapbacks (3 shapes), replies (4-space indent, verbatim), edit history, read receipts, attachments (path heuristics + missing), transcriptions, expressive, deleted, shareplay/shared_location; malformed lines skipped (fault-tolerant). Naive→UTC. | Production (matches exporter's own unit tests) | stdlib only | Canonical NormalizedRecord |
| 5 | `imessage_txt.py` @ `origin/feat/home-parser-work` (493 ln, 12 diff-lines vs main) | exporter TXT | `parse.imessage` | Minor divergence from main (±handful of lines). | Production variant | stdlib | Canonical NormalizedRecord |
| 6 | `server/tools/imessage_pdf.py` (`main`, 74 ln) | Born-digital iMessage PDF (print of txt/html export) | `parse.imessage` (`messages.imessage-pdf`, `.pdf`) | Thin adapter: extract native text via **pypdf → pdfplumber**, route through `imessage_txt.parse_txt_text`; `looks_like_imessage_txt` sniff; raises `ValueError` on scanned PDFs (defers to `extract.text` OCR). No OCR itself. | Production (thin) | pypdf OR pdfplumber + imessage_txt | Canonical NormalizedRecord |
| 7 | `imessage_pdf.py` @ owner-custom / home-parser branches (74 ln, ~8 diff-lines) | same | `parse.imessage` | Near-identical to main (cosmetic). | Production | pypdf/pdfplumber | Canonical NormalizedRecord |
| 8 | **TS lineage A** `dial-stack/…/ts-mcp-server/src/tools/ImessagePdfParser.ts` (126 ln) + byte-identical **`ImessagePdfParser (2).ts`** | iMessage PDF text | (TS MCP tool) | Two line-regexes (`Sender [ts]: msg` / `ts - Sender: msg`) + multi-line continuation; `isFromMe = sender=='me'`. Uses **`pdf-parse`** (dynamic import to dodge ESM/CJS + "brittle python calls"). ⚠ Timestamp parse failure **falls back to `now()`** (lossy). | Partial (`@ts-ignore`) | `pdf-parse`, node fs | Own `ImessageMessage` (text/timestamp/sender/isFromMe) |
| 9 | **TS lineage B** `…/server/mcp/loaders/pdf-imessage-parser.ts` (class `PDFImessageParser`, 145 ln) — copies in dial-stack, TheBigOne, mcp-tool-platform, extracted-code, alpha, TEMP_GITHUB_COMPARE, The_Platform_Archive, `_project_dirs_loose` (3 micro-variants: 4141 / 4174 / 4035 bytes) | iMessage PDF | (TS MCP loader) | Same regex/continuation/`isFromMe` logic **but shells out to Python** (`exec python3 pdf_extractor.py` w/ pdfplumber) — the "brittle python" lineage A replaced. Timestamp → `now()` on failure. | Partial/legacy | child_process(exec) + external pdfplumber script | Own `ImessageMessage` (+`rawData`) |

**Related (non-parser):** SBV/exporter conversion notes and the `extract.text` OCR pool handle scanned iMessage PDFs; not catalogued here.

## 2. SMS / MMS parsers (XML — SMS Backup & Restore; and CSV)

| # | Variant / location | Format | Capability | Key logic & edge cases | Maturity | Deps | Output shape |
|---|---|---|---|---|---|---|---|
| 1 | `server/tools/sbv_sms.py` (`main`, 260 ln) — ~~**PRIMARY**~~ **SHADOW** (DEMOTED 2026-08-02 (gap-review P0-1: unscoped /api/activity)) | SMS Backup & Restore XML via **SBV Go microservice** | `parse.sms-xml` (`messages.sms-xml-sbv`, `.xml` **AND** `SBV_SERVICE_PASS` set) | Uploads XML to SBV, `wait_for_processing`, pulls `/api/activity` (msgs+calls, auto-paginated). Same type maps + forensic call-block flags as the pure-Python fallback. **Custody H1/H2/H3**: `_reconcile_custody` (opt-in `SBV_CUSTODY_ENABLED`) pulls SBV's `file_hash`(H1)/`chain_hash`(H3) + per-record `content_hash`(H2, raw-element sha256) → `custody.reconcile_sbv_import`; custody import lazy-inside-fn (facade lacks sqlalchemy). **Silent-empty guard**: raises `SBVError` on 0 records / unhealthy → forces fallback. MMS media (HEIC/3GP/AMR) handled by SBV. | Production (owner-chosen primary) | `_sbv_client`, optional lazy `custody` | Canonical NormalizedRecord (+`parser=sbv`, `content_hash`, `thread_id`, `media_type`) |
| 2 | `sbv_sms.py` @ `origin/feat/messaging-parsers-owner-custom` **and** `feat/home-parser-work` (205 ln, **−55 vs main**) | same | `parse.sms-xml` | **Pre-custody** SBV variant — no `_reconcile_custody`, no H1/H2/H3 wiring. The custody cross-check was added on `main` via the SBV forensic fork (ADR-0033/0035). | Production (pre-forensic) | `_sbv_client` | Canonical NormalizedRecord (no custody block) |
| 3 | `server/tools/sms_xml.py` (`main`, 197 ln) — **FALLBACK** | SMS Backup & Restore XML (`<sms>/<mms>/<call>`) | `parse.sms-xml` (`messages.sms-xml`, `.xml`) | Pure-Python. `ET.iterparse` streaming (multi-GB safe) + on `ParseError` `_sanitize_xml` (strip control chars, escape bare `&`) & retry. **Direction-aware type maps differ SMS vs call** (same int, different meaning): `_SMS_TYPE` (1=recv,2=sent), `_CALL_TYPE` (1=in,2=out,3=missed,5=rejected,6=refused_list). **Forensic call-block flags** (type 5 rejected / 6 block-list / outgoing+0-dur = "did not connect") → `attrs.blocked/forensic_flags` + `[FORENSIC FLAG…]` in content. Epoch-**ms** → sec. MMS text from nested `<part ct="text/plain">`. | Production (port of dial-stack TS + ConflictAnalysisApp) | stdlib `xml.etree` | Canonical NormalizedRecord (message/call) |
| 4 | `sms_xml.py` @ owner-custom / home / restructure branches (197 ln, ~6 diff-lines) | same | `parse.sms-xml` | Near-identical to main (path/import cosmetics). | Production | stdlib | Canonical NormalizedRecord |
| 5 | **SBV Go backend** `internal/parser.go` (`sbv-fork/main`; vendored at `vendored/sbv/` on `feature/sbv-forensic-fork`) | SMS Backup & Restore XML — the actual engine behind variant 1 | (Go service, REST) | Full typed structs: `SMSBackup{smses,sms,mms,call}`, `SMSEntry` (address/date/type/body/read/thread_id/status/contact_name/…), `MMSEntry` (msg_box/ct_t/`parts>part`/`addrs>addr`/…), `MMSPart` (ct/name/chset/text), `CallEntry`. Full MMS parts + address-block identity resolution. `encoding/xml` decode. | Production (upstream fork) | Go stdlib `encoding/xml`, `crypto/sha256` | JSON over REST (SBV activity model) → normalized by `sbv_sms.py` |
| 6 | **SBV custody** `internal/custody.go` (`sbv-fork/main`) | custody hashing for the SMS XML import | (Go service) | Canonical H-chain: **H1** `h1-rawbytes-v1` = sha256(raw file); **H2** `h2-rawelement-v1` = sha256(raw XML element bytes, pre-normalization); **H3** `h3-chain-v1` = left-fold `sha256(chain_{i-1}+"\n"+H2_i)`. `HashFileH1` mirrors Python `custody.py::_sha256_file`; `newRawCaptureReader` captures raw element bytes during streaming decode. **The authoritative custody-hash implementation.** | Production | Go `crypto/sha256` | Hash strings exposed at `/api/hashes/{importID}` |
| 7 | **TS lineage A** `dial-stack/…/ts-mcp-server/src/tools/SmsXmlParser.ts` (177 ln) | SMS Backup & Restore XML (`sms`/`mms`/`call`) | (TS MCP tool) | **Streaming** line reader + manual depth tracking (multi-GB); **encoding fixes** (strip `\x00-\x1F`, escape stray `&`); `parseAttributeValue:false` (don't truncate long numbers/ms). **Forensic call-blocking** (type 5/6, outgoing+0-dur) ported from ConflictAnalysisApp. MMS as generic merge (no parts). | Production-leaning | `fast-xml-parser` | `NormalizedMessage{text, metadata{timestamp,sender,recipient,record_type,raw_data}}` (the closest TS "NormalizedRecord") |
| 8 | **TS lineage A (2)** `SmsXmlParser (2).ts` (205 ln, **+28, NOT a dupe**) | same | (TS MCP tool) | Superior revision: externalizes `CALL_TYPE_LABELS` to `constants.js`; **MMS attachment detection** (non-`text/*` parts → `has_attachments`/`attachment_count`); `record_type` gains `'mms'`; `optField()` adds `type_code/status_code/read_status/duration_seconds/result_label/message_box`. | Production (latest of pair) | `fast-xml-parser` | `NormalizedMessage` (+8 optional fields) |
| 9 | **TS lineage B** `…/server/mcp/loaders/xml-sms-parser.ts` (class `XMLSmsParser`, 158 ln) — many copies (4191/4202/4054-byte micro-variants) | SMS Backup & Restore XML, **`sms`/`mms` only** | (TS MCP loader) | Older ancestor: streaming depth-buffer, direction via type 1/2, **NO `<call>`**, **NO forensic blocking**, **NO sanitization**, does not disable `parseAttributeValue` (number-truncation risk). | Partial/legacy | `fast-xml-parser` | Own flat `SmsMessage` (text/timestamp/sender/recipient) |
| 10 | **Python forensic origin** `…/ConflictAnalysisApp/src/sms_backup_parser.py` (389 ln) — copies in TheBigOne (03_ & 05_), OTHER_RESOURCES_TO_SORT (TraceIQ/Junkyard, utilities/apps), `extracted-code/parsers/messaging/` | SMS Backup & Restore XML (`sms`/`mms`/`call`) | (CLI script) | **The origin of all the forensic call-blocking logic.** `iterparse`+`clear()` streaming; `parse_java_timestamp` (Java ms); **base64 guard** (`is_base64_block` >90% / len>50) excludes image blobs from MMS text, keeps only `ct="text/*"`; **MMS identity via `<addrs>`** (137=from, 130/151=to); call blocking (5 rejected / 6 refused_list / out+0-dur) + `find_blocking_evidence` with phone normalization (last-10-digits); SMS status 64=Failed; `search_for_pattern`; CSV export; `__main__` CLI. Contains **case-specific editorial comments**. | Production forensic tool | Python **stdlib only** | per-record `dict` (datetime/sender/message/direction/phone/status/msg_type; MMS adds recipients/has_attachments; calls add call_type_name/block_evidence) |
| 11 | **SBV SQL schemas** `salem_sms_tables_schema_final.sql` / `…_FINAL.sql` / `Salem_SMS_Tables_Complete_Deployment_2025-12-27.sql` / `SMS_DEPLOYMENT_EXECUTABLE.sql` — many copies (OTHER_RESOURCES_TO_SORT, TheBigOne/archive, Workbench, `extracted-code/sbv/`) | **DB target schema** for the SMS/SBV lane (not a parser) | n/a | PostgreSQL DDL for SMS/MMS/call tables (the destination the SBV/SMS parsers load into). Included for completeness of the SMS lane. | Deployment SQL | Postgres | tables, not records |

### CSV SMS
| # | Variant / location | Format | Capability | Key logic | Maturity | Deps | Output |
|---|---|---|---|---|---|---|---|
| 12 | `server/tools/messaging_csv.py` (`main`, 296 ln) | Generic messaging CSV (iMazing/AnyTrans/SMS-Backup-CSV/Google Voice/spreadsheet) | `parse.messages-csv` (`messages.messaging-csv`, `.csv`) | **Column-flexible** alias tables (ts/text/sender/dir/service/chat/read/attach), first-match wins; every original column kept verbatim in `attrs.raw_row` (forensic contract); `utf-8-sig` BOM tolerance; `csv.Sniffer` dialect/delimiter detection; direction incl. `is from me` boolean; timestamp cascade (ISO/epoch-sec/epoch-ms/large format table); `looks_like_messages_csv` guard; per-row source detection (imessage/sms/whatsapp). | Production (stdlib csv, no pandas) | stdlib `csv` | Canonical NormalizedRecord |
| 13 | `messaging_csv.py` @ `origin/feat/home-parser-work` (246 ln, **−50 vs main**) | same | `parse.messages-csv` | Earlier/leaner CSV variant (fewer alias keys / format rows). | Partial/earlier | stdlib | Canonical NormalizedRecord |

## 3. Facebook Messenger parsers (HTML / JSON)

| # | Variant / location | Format | Capability | Key logic & edge cases | Maturity | Deps | Output shape |
|---|---|---|---|---|---|---|---|
| 1 | `server/tools/facebook_messenger_json.py` (`main`, 152 ln) — **PREFERRED** | FB DYI JSON (`messages/inbox/<thread>/message_N.json`, or a thread dir) | `parse.facebook` (`messages.facebook-json`, `.json`) | **Mojibake repair** `_fix` (latin-1→utf-8 double-decode) on every text field; merges `message_*.json` chronologically; validates FB shape else raises→mesh fallback; **media** (`photos/videos/audio/gifs/files/sticker` → `{kind,uri}`); **reactions/tapbacks** (`attrs.reactions`); **call** detection (`type=Call`/`call_duration`→`RecordType.call`); shares; silent-empty guard skips reaction-only/system msgs, synthesizes searchable content for non-text; `timestamp_ms`→UTC. | Production (richest FB parser) | stdlib `json` | Canonical NormalizedRecord (message/call), rich `attrs` (media/reactions/share/thread_title) |
| 2 | `facebook_messenger_json.py` @ owner-custom (153 ln, ~9 diff-lines) | same | `parse.facebook` | Near-identical to main. | Production | stdlib | Canonical NormalizedRecord |
| 3 | `server/tools/facebook_messenger_html.py` (`main`, 167 ln) | FB DYI **HTML** export (legacy `div.message` + card `div._a6-g`) | `parse.facebook` (`messages.facebook-html`, `.html/.htm` — shares ext with iMessage HTML → mesh) | Two layouts (legacy meta `Sender - <ts>` + `<p>`, card `_a6-h`/`_a6-p`/`_a72d`); tries legacy then card, raises `ValueError` if neither (defers to iMessage HTML); **fuzzy timestamp** across many strptime formats + `at`/comma normalization → UTC; `msg_type` keyword classification; direction only if `owner_name` supplied; roster from senders. **Lossier** than JSON (no media URIs / reactions). | Production (lossier) | BeautifulSoup4 | Canonical NormalizedRecord (message only) |
| 4 | `facebook_messenger_html.py` @ home-parser-work (158 ln, smaller) | same | `parse.facebook` | Earlier/leaner FB-HTML cut. | Partial/earlier | BeautifulSoup4 | Canonical NormalizedRecord |
| 5 | **TS lineage A** `dial-stack/…/ts-mcp-server/src/tools/FacebookExportParser.ts` (265 ln) + byte-identical **`FacebookExportParser (2).ts`** | FB HTML export (Structure 1 `div.message` / Structure 2 obfuscated `_a6-g`) | (TS MCP tool) | `parseDateFuzzy` (space-before-AM/PM + regex formats); `detectDirection` via `ownName`; `detectMessageType` keyword sniff; `externalId = sha256(body+ISO)[:16]` dedup key; skips empty. Declares `attachments/recipient/threadName` but never fills them. **No reactions.** | Partial→production | `cheerio`, `uuidv7` | Own `ParsedFacebookMessage` (id/platform/sender/body/timestamp/direction/messageType/externalId) |
| 6 | **TS lineage B** `…/server/mcp/loaders/facebook-parser.ts` (class `FacebookHTMLParser`, 204 ln) — many copies (5904/5881/5700-byte micro-variants) | FB HTML export | (TS MCP loader) | **Streaming** line reader (not cheerio); uses **`node-html-parser`**; **extracts reactions/tapbacks** (`[data-testid="reaction"]` → `{emoji,user}`) — lineage A does NOT; msg_type via DOM+filename sniff; ⚠ timestamp→`now()` fallback; **NO direction/ownName**; keeps only first 500 chars of rawData. | Partial | `node-html-parser` | Own `FacebookMessage` (+reactions/threadId, −direction/externalId) |
| 7 | **Python Autopsy module** `…/ConversationExtractor/FacebookParser.py` (~138 ln, class `FbMsgParser`) — copies in ConversationExtractor_from_Gemini_Debris, _from_Satellite_Tools, `_project_dirs_loose` | FB Messenger **Android SQLite DB** (`threads_db2.db`/`mmssms.db`) — NOT HTML/JSON | (Autopsy/Jython ingest module) | JDBC SQLite; `SELECT thread_key`→per-thread `SELECT sender,text,timestamp_ms`; identity from `sender` blob (`user_key`/`name`) → first two distinct participants; epoch-ms→sec; skips None/empty; direction by matching sender to contact1/contact2 (receiver left None). Hardcoded 2-participant assumption. | Working but rough (CMU forensics module, 2024) | **Jython** — `java.sql`, `org.sleuthkit.autopsy` (won't run in CPython) | Autopsy domain objects `Conversation(Message…)` — wholly different model |

## 4. Phone-call log parsers

No standalone call-log parser module exists — **call logs are handled inline by the SMS-XML parsers** (`<call>` / `<calls>` elements), because SMS Backup & Restore emits calls in the same XML:

| Handler | Call support |
|---|---|
| `server/tools/sms_xml.py` (`main`) | Full: `_CALL_TYPE` (1=in,2=out,3=missed,5=rejected,6=refused_list), duration, **forensic call-block flags**, `RecordType.call`, `attrs.blocked/forensic_flags` |
| `server/tools/sbv_sms.py` (`main`) | Full: same type maps + block flags via SBV `/api/activity` |
| SBV Go `internal/parser.go` | `CallEntry` struct (typed) |
| TS lineage A `SmsXmlParser.ts` / `(2)` | Call type map + blocking flags (`5`/`6`/out+0-dur) |
| TS lineage B `xml-sms-parser.ts` | **NONE** — sms/mms only, no `<call>` |
| Python `sms_backup_parser.py` | Full: `call_type_name`, `is_blocked_indicator`, `find_blocking_evidence` w/ phone normalization — the origin of the forensic call logic |

## 5. SBV (SMS Backup Viewer) parsers

| # | Component / location | Role | Key logic | Maturity | Deps |
|---|---|---|---|---|---|
| 1 | `server/tools/sbv_sms.py` (`main`, 260 ln) | Python client-parser (PRIMARY `parse.sms-xml`) | See §2 #1 — upload/poll/activity + H1/H2/H3 custody reconcile | Production | `_sbv_client` |
| 2 | `server/tools/_sbv_client.py` (`main`, 358 ln) | Stdlib-only SBV REST client | Session-cookie auth (`POST /api/auth/login`, auto-`register` `mcp_service` on 401, one-retry re-login); multipart upload; `wait_for_processing` polls `/api/progress`; `all_activity` auto-paginates `/api/activity`; `hashes()` hits **forensic-fork-only** `/api/hashes/{importID}` (404 on stock). `SBV_BASE_URL` default `http://localhost:8085`. | Production | stdlib `urllib` only |
| 3 | SBV Go backend `internal/parser.go` (`sbv-fork/main`; vendored `vendored/sbv/` on `feature/sbv-forensic-fork`) | The XML→model engine | Full typed SMS/MMS/call/parts/addrs structs; `encoding/xml` | Production (fork) | Go stdlib |
| 4 | SBV Go `internal/custody.go` (`sbv-fork/main`) | H1/H2/H3 custody hashing | `HashFileH1`/`HashRecordH2`/`ChainH3`; canonical `h1-rawbytes-v1`/`h2-rawelement-v1`/`h3-chain-v1`; raw-capture reader | Production (fork) | Go `crypto/sha256` |
| 5 | `server/agents/tools/sbv_tools.py` @ `origin/feature/facade-collapse-batch-a` | Agno agent-tool wrapper exposing SBV as agent tools (facade collapse Batch A) | Wraps the SBV parse/hash flow for agent + CF federation (`/sbv/hashes` route) | Production (merged to main per log) | `_sbv_client` |
| 6 | `scripts/register_sbv_contextforge.sh` (multiple branches) | ContextForge registration of SBV as an MCP tool | shell | Ops script | — |
| 7 | Remotes `sbv-fork/main` & `sbv-upstream/main` | Full SBV app (Go backend + React frontend) — fork vs upstream | fork adds custody.go + `/api/hashes`; upstream is stock SMS Backup Viewer | Live fork | Go + JS |
| 8 | SBV SQL schemas (see §2 #11) | DB target for SBV imports | Postgres DDL | Deployment | Postgres |

## 6. Generic messaging transcript / CSV parsers

| # | Variant / location | Format | Capability | Key logic | Maturity | Deps | Output |
|---|---|---|---|---|---|---|---|
| 1 | `server/tools/messaging_transcript.py` (`main`, 179 ln) | Marker transcript `[YYYY-MM-DD HH:MM AM/PM] Speaker:` (SMS `.txt` or mislabeled iMessage "CSV") | `parse.messages-transcript` (`messages.transcript-marker`, `.txt`/`.csv`) | Route-by-content: sniff `_MARKER_RE`, **raise `ValueError` to defer** to `messaging_csv` (tabular) or `imessage_txt` (stock exporter); `_cells` unifies csv/txt walk; one record per marker (speakers never blended); **identity from CONTENT not filename** (filename can mislabel thread); **HARD-FAIL** `RuntimeError` if markers present but 0 records (silent-empty guard); minute-precision + `sequence_number` tiebreak; `utf-8-sig`. | Production ("PROVEN by PROCESS" harness) | stdlib `csv`/`re` | Canonical NormalizedRecord |
| 2 | `messaging_transcript.py` @ owner-custom (179 ln, ~6 diff-lines) | same | `parse.messages-transcript` | Near-identical to main. | Production | stdlib | Canonical NormalizedRecord |
| 3 | `markdown_transcript.py` @ `origin/feat/messaging-parsers-owner-custom` (40 ln) | Plain `.md`/`.txt` → one whole-file record | `parse.transcript` (`transcripts.markdown`, `.md`/`.txt`) | Deliberate **last-resort whole-file fallback** (accepts only `.md/.txt`; structured formats never reach it); raises on empty. On `main` this evolved into `server/tools/whole_file_fallback.py` (`parse.transcript`). | Production (fallback) | stdlib | Canonical NormalizedRecord (single record) |
| 4 | `server/tools/whole_file_fallback.py` (`main`) + `server/tools/generic_md.py` (`main`) | whole-file / generic markdown fallback | `parse.transcript` | Current `main` successors of `markdown_transcript.py`; least-specific catch-alls in the mesh. | Production (fallback) | stdlib | Canonical NormalizedRecord |
| 5 | `scripts/mine_transcripts.py` @ `origin/archive/v0.1.1-pre-reset`; `agents/transcript_miner.py` (owner-custom/home branches) → `server/agents/transcript_miner.py` (restructure) | Batch transcript-mining orchestrator (drives the parsers over a corpus) | n/a | Not a format parser — a runner that invokes the registry over a folder. Oldest surviving artifact at the v0.1.1 reset point. | Varies | registry | — |

## 7. Which variants look strongest (COMPARE, not a final pick)

- **iMessage HTML:** three live variants worth A/B-ing on the owner's real exports — `main` (445 ln, richest edge-case coverage: tapbacks/edits/read-receipts, proven on 1918-msg sample), **owner-custom (549 ln, the `_parse_owner_format_regex` + bounded-sibling attachment-leakage guard)**, and home-parser-work (437 ln, leaner). The owner-custom attachment-leakage guard is the one edge case `main` may not cover; **compare on a file where attachments interleave with messages.**
- **iMessage TXT/PDF:** `main` `imessage_txt.py` is the mature shared grammar engine and PDF just rides on it — low variance across branches; the TS `ImessagePdfParser` lineages are interesting only for the pdf-parse-vs-python-pdfplumber extraction tradeoff (both fall back to `now()` on bad timestamps — a forensic no-no vs the Python lane which keeps the raw timestamp).
- **SMS XML:** the dual-parser mesh (`sbv_sms` PRIMARY + `sms_xml` FALLBACK) on `main` is the most complete — it's the only lineage with **custody H1/H2/H3** (Go `custody.go` + Python reconcile). Compare `main` `sbv_sms` (260 ln, custody) vs the branch pre-custody `sbv_sms` (205 ln) only if custody wiring causes friction. `SmsXmlParser (2).ts` is the best TS variant (MMS attachment counting) if a TS path is ever revived. The Python `sms_backup_parser.py` is the **forensic ground-truth reference** (base64 exclusion + `<addrs>` identity + block-evidence) — worth diffing against `sms_xml.py` to confirm nothing was dropped in the port.
- **Facebook:** `facebook_messenger_json.py` (`main`) is clearly strongest (structured media + reactions + mojibake repair); HTML is the lossy fallback. Among donors, TS lineage-B `facebook-parser.ts` is the only one that extracts **reactions** — check the current JSON parser already covers that (it does) before discarding. The Autopsy `FacebookParser.py` is a **different capability entirely** (reads the Messenger SQLite DB, not an export) — keep it as the path for phone-image/DB extractions.
- **Custody:** Go `internal/custody.go` is the authoritative H1/H2/H3 implementation; `sbv_sms.py._reconcile_custody` + `custody.py` are the Python cross-check. This is the only custody-bearing lane — everything else is hash-free.

## 8. Gaps

- **No standalone call-log parser** — calls only ride the SMS-XML lane. A dedicated carrier-CSV / Google-Voice-calls / phone-provider call-log parser is absent (the CSV parser has `_CALL_TOKENS` detection but no dedicated call schema).
- **No WhatsApp / Instagram / Snapchat / Signal / Telegram parsers** anywhere (WhatsApp is only a per-row `source` label the CSV parser can *tag*, not a real `_chat.txt`/zip parser). The CSV alias tables mention whatsapp but there is no WhatsApp `.txt`/media-zip parser.
- **No native `chat.db` (macOS iMessage SQLite) parser** — the current lane only ingests *exports* (html/txt/pdf/csv). The only DB-level messaging parser found is the Autopsy Jython `FacebookParser.py` (Messenger Android SQLite), which can't run outside Autopsy.
- **MMS media in the pure-Python fallback** (`sms_xml.py`) extracts only `text/*` parts; binary MMS attachments (images/audio) are surfaced only via the SBV service path. If SBV is unavailable, MMS media is effectively dropped (text kept).
- **Timestamp-loss risk in TS lineages** — both TS iMessage-PDF and lineage-B Facebook parsers fall back to `now()` on parse failure (silently corrupts occurred_at); the Python lane instead retains the raw timestamp string. Not a gap in the current lane, but a trap if any TS parser is revived.
- **TS "NormalizedMessage" ≠ Python `NormalizedRecord`** — if any TS parser is ever brought forward, it needs a shim to the canonical Pydantic shape; only the SMS TS parser even approximates it.
- **SQL schemas vs current DDL** — the many `salem_sms_tables*.sql` deployment scripts predate the current forensic-DB reconciliation; whether they still match the live evidence/analysis schema is unverified here (out of parser scope, flagged for the DB reconciliation lane).
