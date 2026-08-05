> _Byline: Claude Code · Sonnet · 2026-07-11_

# Parser & extractor capability reference

Per-format capability + example docs for every atomic tool registered under
`server/tools/parsers/` and `server/tools/extractors/` (DOC_DEBT item #3, HANDOFFS HA.2).
Grouped exactly like the package on disk: `parsers/messaging` (9), `parsers/ai_chat` (11),
`parsers/generic` (2), `extractors` (1) — 23 tools total, 1:1 with the live registry
(verified via `load_builtin_tools()`; see "Verifying this doc" at the bottom).

Ground truth = the code. Each section below documents, from the module's own
`@register` decorator and body: the registered id + capability + `accepts()` rule,
the exact input grammar (with a realistic snippet), the output shape (RecordTypes,
notable `attrs` keys, participants/conversation_id derivation, DisclosureTier), the
edge cases it actually handles, its provenance, and a runnable example invocation.

## Shared mechanics (read once, apply everywhere)

### The capability-resolution mesh

Every tool self-registers via `@register(id=..., capability=..., description=...,
accept=...)` in `server/tools/registry.py`. Callers resolve by **capability**
(e.g. `parse.imessage`), not by hard-coded module — `registry.resolve(capability,
media_hint, size_bytes)` returns every registered tool for that capability whose
`accepts()` predicate passes, **in registration order** (first = preferred, rest =
substitution candidates). Registration order is import order, which
`load_builtin_tools()` derives from `pkgutil.walk_packages` — i.e. **alphabetical by
module path** within each capability. That's why file naming is sometimes
load-bearing: `sbv_sms` sorts before `sms_xml` (SBV preferred, pure-Python
fallback second) and `whole_file_fallback` was deliberately renamed to sort after
every structured `parse.transcript` parser (see its own section).

**Defer-by-raising** is the substitution protocol: a parser that accepts a file by
extension but then discovers on content-sniff that it's the *wrong* format (or
detects zero usable records) raises `ValueError`/`RuntimeError` instead of
returning an empty/wrong result. The workflow executor catches that and tries the
next same-capability candidate. This is how `imessage_html.py` and
`facebook_messenger_html.py` coexist on the same `.html` extension, and how every
chatminer-backed wrapper hard-fails when `ParsedMessage` count is zero (see
`_chatminer_adapter.run_chatminer_parser`) — a parser must never silently produce
empty evidence.

Example — asking the mesh who can handle a file, then running the preferred one:

```python
from server.tools.registry import load_builtin_tools, registry

load_builtin_tools()
candidates = registry.resolve("parse.imessage", media_hint="chat.html", size_bytes=4096)
tool = candidates[0]  # preferred; candidates[1:] are substitution fallbacks
result = tool.run({"path": "chat.html"})
```

### Forensic guarantees

1. **No wall-clock timestamps, ever.** A parser has no legitimate reason to read
   the current clock for an *event* timestamp — event times come from the source
   data only. `tests/test_no_fabricated_timestamps.py` AST-scans every module
   under `server/tools/parsers/` and `server/tools/extractors/` and fails the
   suite if any of them calls `datetime.now`/`.utcnow`/`date.today`/`time.time`.
   When a timestamp fails to parse, every module below returns `None` (never a
   synthesized "now") and — for the hand-written messaging parsers — retains the
   original string in `attrs["raw_timestamp"]` so nothing is lost, just not
   trusted as an event time. `_ALLOWED` in that test is deliberately empty: there
   is currently no parser with a legitimate non-event wall-clock use, and adding
   one requires an explicit, commented exception.
2. **Custody only in the SBV lane.** Per-record forensic custody-hash
   reconciliation (H1/H2/H3) is wired into exactly one parser —
   `messages.sms-xml-sbv` — and only when `SBV_CUSTODY_ENABLED` is set; it lazily
   imports `server.evidence.custody` so the dependency-light tools facade (which
   has no sqlalchemy) doesn't break when the flag is off. No other parser in this
   document touches custody hashing.

---

## parsers/messaging (9)

### messages.imessage-html

- **File**: `server/tools/parsers/messaging/imessage_html.py`
- **Registered**: `id="messages.imessage-html"`, `capability="parse.imessage"`,
  `accept=lambda hint, size: hint.lower().endswith((".html", ".htm"))`.
- **INPUT**: ReagentX/imessage-exporter's `--format html` output (or the owner's
  customized fork of it). Two DOM shapes are handled:
  - **Stock exporter grammar** (`div.message > div.sent|div.received > p > span.timestamp
    + span.sender`):
    ```html
    <div class="message">
      <div class="received imessage">
        <p><span class="timestamp"><a href="#">May 17, 2022  5:29:42 PM</a></span>
           <span class="sender">Jane Doe</span></p>
        <hr><div class="message_part"><span class="bubble">On my way</span></div>
      </div>
    </div>
    ```
  - **Owner-custom exporter variant** (a flat `div.bubble.from-me|from-them` +
    sibling `div.meta`, PROVEN on a 1918-message real sample):
    ```html
    <div class="bubble from-them">Running late, sorry</div>
    <div class="meta">Jane Doe - 2026-05-17 05:29 PM</div>
    ```
- **OUTPUT**: `RecordType.message` (or `.call` when the reconstructed content matches a
  call phrase like "missed call"/"facetime", or `.event` for `div.announcement` rows).
  `conversation_id` = the file's stem. `participants` = `["owner", ...senders]` built
  from the document then backfilled onto every record. `role` = `"owner"` for sent
  messages, else the sender label. `disclosure_tier` is always `contemporaneous`.
  Notable `attrs` keys: `platform`, `format`, `direction`, `service`, `raw_timestamp`,
  `sender_label`, `attachments` (kind/uri/text per item), `tapbacks`, `edited` +
  `edited_history`, `is_deleted`, `is_reply`, `retracted`, plus `read_receipt` /
  `expressive` / `reply_thread` / `subject` when present. The owner-custom variant adds
  `variant: "owner-custom"` and `sequence_number` (used as a same-minute sort tiebreak,
  since that grammar is minute-precision only).
- **EDGE CASES**:
  - *Content-sniff vs Facebook HTML*: `.html`/`.htm` is shared with
    `facebook_messenger_html.py`. `looks_like_imessage_html()` checks for the iMessage
    DOM shape; if that fails AND `looks_like_owner_imessage_html()` also fails, the
    parser raises `ValueError` so the mesh defers to the Facebook parser.
  - Timestamps that fail `_parse_ts`/`_parse_owner_ts` become `None`, never a fabricated
    "now" — the raw string survives in `attrs["raw_timestamp"]`.
  - Attachments, tapbacks, replies, edits and read receipts are all captured into
    `attrs` rather than dropped (forensic ingest contract).
  - When a message has no text but does have attachments/deletion/tapbacks, `content`
    is synthesized as a descriptive placeholder (e.g. `"[2 attachment(s)]"`) rather than
    left empty.
- **PROVENANCE**: `provenance="custom parser written to imessage-exporter
  exporters/html/templates grammar"` — hand-written to the exporter's askama template
  shape, not chatminer-backed.
- **EXAMPLE INVOCATION**:
  ```python
  from server.tools.registry import load_builtin_tools, registry
  load_builtin_tools()
  result = registry.get("messages.imessage-html").run({"path": "chat_with_jane.html"})
  ```

### messages.imessage-pdf

- **File**: `server/tools/parsers/messaging/imessage_pdf.py`
- **Registered**: `id="messages.imessage-pdf"`, `capability="parse.imessage"`,
  `accept=lambda hint, size: hint.lower().endswith(".pdf")`.
- **INPUT**: imessage-exporter has no native PDF exporter, so an iMessage PDF is a
  **print-to-PDF of the TXT (or HTML) output** — a born-digital PDF that carries a real
  text layer in the exporter's TXT grammar (see `messages.imessage-txt` for that
  grammar's shape).
- **OUTPUT**: identical shape to `messages.imessage-txt` (it re-uses that module's
  `parse_txt_text()` engine on the extracted text), except `source` is re-stamped to
  `"imessage-pdf"` and `attrs["format"]` is overwritten to `"pdf"` on every record.
- **EDGE CASES**:
  - Text extraction is tiered: `pypdf.PdfReader` first, `pdfplumber` fallback; if
    neither import succeeds, raises `RuntimeError` (a clear "install a PDF backend"
    error, not a silent failure).
  - After extraction, `looks_like_imessage_txt(text[:8192])` content-sniffs the result;
    if the exporter's timestamp-header grammar isn't found, raises `ValueError` — this
    is also the escape hatch for a *scanned* iMessage PDF (no real text layer), which
    the module docstring says should be routed through `extract.text`'s OCR pool first.
  - Inherits the TXT engine's "never fabricate a timestamp" behavior (`_parse_ts`
    returns `None` on garbage — see the shared forensic guarantee at the top of this
    doc).
- **PROVENANCE**: `provenance="native pypdf/pdfplumber text layer ->
  imessage_txt.parse_txt_text; OCR fallback via extract.text"` — not chatminer-backed;
  delegates within this same package (`imessage_txt.py`), not the vendored parser core.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("messages.imessage-pdf").run({"path": "chat_with_jane.pdf"})
  ```

### messages.imessage-txt

- **File**: `server/tools/parsers/messaging/imessage_txt.py`
- **Registered**: `id="messages.imessage-txt"`, `capability="parse.imessage"`,
  `accept=lambda hint, size: hint.lower().endswith(".txt")`.
- **INPUT**: `imessage-exporter --format txt` output — one flat text file per
  conversation with no machine delimiter between messages; a message block is
  recognized structurally as a timestamp header line followed by a sender line:
  ```
  May 17, 2022  5:29:42 PM
  Jane Doe
  Running late, sorry

  May 17, 2022  5:31:05 PM (Read by you after 1 hour, 49 seconds)
  Me
  No worries, see you at 6
  ```
  Announcements are a single timestamp+action line (e.g. `"May 17, 2022  5:00:00 PM
  Jane Doe named the conversation \"Trip Planning\"."`).
- **OUTPUT**: `RecordType.message`/`.call`/`.event`. `conversation_id` = caller-supplied
  (the registered `parse()` uses the file's stem). `participants` = `["owner",
  ...senders]`. Notable `attrs`: `platform`, `format`, `direction`, `raw_timestamp`,
  `sender_label`, `attachments` (path-heuristic detected lines), `tapbacks` (parsed
  `{kind, who, raw}`), `edited`/`edited_history`, `is_deleted`, `is_reply`, `markers`,
  plus `read_receipt`/`expressive`/`transcriptions`/`reply_thread` when present.
- **EDGE CASES**:
  - `_parse_ts` returns `None` on anything that doesn't match the exporter's exact
    `"%b %d, %Y %I:%M:%S %p"` grammar — directly covered by
    `tests/test_no_fabricated_timestamps.py::test_imessage_parse_ts_returns_none_on_garbage_not_now`.
  - Body parsing (`_parse_body`) recognizes and routes: deleted-message marker,
    reply-context marker, SharePlay start/end, shared-location start/stop, attachment
    missing/does-not-exist, `Transcription: ` prefixed lines, `Sent with ` expressive
    tag, `Edited … later:` history rows, and path-shaped lines (heuristic:
    `~/`, `C:\`, `/Attachments/`, `/Library/`, or a trailing file extension) as
    attachments.
  - Reply sub-blocks are 4-space indented; captured verbatim into
    `attrs["reply_thread"]`.
  - Records sort by `occurred_at` (unparseable ones sort to `datetime.min`, not
    dropped).
  - Exposes `parse_txt_text()` and `looks_like_imessage_txt()` as the shared engine
    reused by `messages.imessage-pdf`.
- **PROVENANCE**: `provenance="custom parser written to imessage-exporter
  exporters/txt/templates grammar"` — hand-written, not chatminer.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("messages.imessage-txt").run({"path": "chat_with_jane.txt"})
  ```

### messages.facebook-html

- **File**: `server/tools/parsers/messaging/facebook_messenger_html.py`
- **Registered**: `id="messages.facebook-html"`, `capability="parse.facebook"`,
  `accept=lambda hint, size: hint.lower().endswith((".html", ".htm"))`.
- **INPUT**: Facebook's "Download Your Information" HTML export. Two layouts observed
  in the wild:
  - **legacy**: `<div class="message"><div class="meta">Sender - <ts></div><p>body</p>`
    ```html
    <div class="message">
      <div class="meta">Jane Doe - Jan 5, 2026, 3:47 PM</div>
      <p>See you tomorrow</p>
    </div>
    ```
  - **card**: `<div class="_a6-g">` with `_a6-h` (sender), `_a6-p` (body), and a sibling
    `_a6-o > _a72d` timestamp node.
- **OUTPUT**: `RecordType.message` only (no call/event synthesis in this module).
  `conversation_id` = file stem. `participants` = senders seen in document order.
  `attrs`: `platform="facebook"`, `format="html"`, `msg_type` (heuristically classified
  `media`/`share`/`system`/`text` from body keywords), `meta` (raw meta text, truncated
  to 200 chars), and `direction` **only** when `payload["owner_name"]` (or
  `payload["source_meta"]["owner_name"]`) is supplied — without it, direction is simply
  absent, never guessed.
- **EDGE CASES**:
  - Tries `_structure_legacy()` first; if it yields zero rows, falls back to
    `_structure_card()`; if both yield zero, raises `ValueError` (defers to the mesh —
    including back to `messages.imessage-html` if this file was actually an iMessage
    export).
  - `_parse_fuzzy_date()` tries 13 different `strptime` formats across 3 string
    variants (raw, `" at "` → `", "`, comma-stripped) — Facebook's HTML timestamp
    rendering has drifted across export vintages.
  - A row with no parseable timestamp, or an empty body, is dropped from that row (not
    hard-failed) — but the module never invents a timestamp for a row it does keep.
- **PROVENANCE**: `provenance="port of dial-stack ts-mcp-server
  FacebookExportParser.ts (cheerio->BeautifulSoup)"`.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("messages.facebook-html").run({"path": "messages.html", "owner_name": "Matt Salem"})
  ```

### messages.facebook-json

- **File**: `server/tools/parsers/messaging/facebook_messenger_json.py`
- **Registered**: `id="messages.facebook-json"`, `capability="parse.facebook"`,
  `accept=lambda hint, size: hint.lower().endswith(".json")`.
- **INPUT**: the modern Facebook "Download Your Information" JSON export —
  `messages/inbox/<thread>/message_1.json` (`message_2.json`, ... for long threads).
  Accepts either a single `message_N.json` file or a thread **directory** (globs
  `message_*.json` and merges chronologically):
  ```json
  {
    "participants": [{"name": "Jane Doe"}, {"name": "Matt Salem"}],
    "messages": [
      {"sender_name": "Jane Doe", "timestamp_ms": 1715980182000,
       "content": "See you tomorrow ЁЯШК"}
    ],
    "title": "Jane Doe",
    "thread_path": "inbox/janedoe_abc123"
  }
  ```
  (`ЁЯШК` above is exactly what a raw emoji looks like in the file before repair — see
  the mojibake edge case.)
- **OUTPUT**: `RecordType.message` or `.call` (`msg_type == "Call"` or
  `call_duration is not None`). `conversation_id` = `thread_path` (falls back to
  `title`). `participants` = every participant name in the thread (mojibake-repaired).
  `attrs`: `platform="facebook"`, `msg_type`, `thread_title`, `media` (list of
  `{kind, uri}` for photos/videos/audio_files/gifs/files/sticker), `is_call`,
  `call_duration_seconds`, `reactions` (list of `{reaction, actor}`), `share`
  (`{link, text}`).
- **EDGE CASES**:
  - **Mojibake repair is the headline edge case**: Facebook double-encodes UTF-8 as
    latin-1 in every string field, so emoji/accented text arrives garbled. `_fix()`
    round-trips every text field through `s.encode("latin-1").decode("utf-8")`
    (no-op, caught by `UnicodeEncodeError`/`UnicodeDecodeError`, if the string was
    already clean).
  - Messages with no text synthesize a searchable placeholder: `"Call (Ns)"` for calls,
    `"[sent N attachment(s): kinds]"` for media, `"[shared] <text> <link>"` for shares,
    or `"[<type>]"` for other non-generic types.
  - A message with no content, no media, and no share is dropped entirely (`return
    None` in `_map_message`) — "reaction-only / empty system noise", the one place in
    this module that intentionally discards a source row rather than preserving it.
  - Validates each file has both `messages` and `participants` keys; otherwise raises
    `ValueError` naming the offending file (defers to the mesh, e.g. for a JSON file
    that isn't a Facebook export at all).
- **PROVENANCE**: `provenance="custom FB DYI JSON parser (donor
  FacebookExportParser.ts handles only the HTML variant)"` — no chatminer/TS donor for
  this exact shape.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("messages.facebook-json").run({"path": "inbox/janedoe_abc123/"})
  ```

### messages.messaging-csv

- **File**: `server/tools/parsers/messaging/messaging_csv.py`
- **Registered**: `id="messages.messaging-csv"`, `capability="parse.messages-csv"`,
  `accept=lambda hint, size: hint.lower().endswith(".csv")`.
- **INPUT**: any messaging CSV export that isn't the owner's specific transcript-marker
  grammar (iMazing, AnyTrans, SMS Backup CSV, Google Voice, generic spreadsheet dumps).
  **Column-flexible**: a large alias table maps varied headers onto normalized fields
  (`timestamp`/`text`/`sender`/`direction`/`service`/`chat`/`attachment`/...). Example
  header shape:
  ```
  Message Date,Sender,Text,Service,Chat Session
  2026-05-17 17:29:42,Jane Doe,Running late sorry,iMessage,Jane Doe
  ```
- **OUTPUT**: `RecordType.message` or `.call` (detected from call-phrase tokens in the
  text/direction blob). `conversation_id` = the `chat`-alias column value, or the file
  stem. `role`: `"owner"` when direction is outbound or the sender literal is
  `"me"`/`"you"`; otherwise the sender label/id. `attrs.raw_row` carries the **entire
  original row, every original header verbatim** — the forensic contract that nothing
  the CSV carried is silently dropped even if this parser doesn't recognize the column.
  `source`/`platform` are detected per-row from a service/protocol column
  (`imessage-csv`, `sms-csv`, `whatsapp-csv`, or generic `messages-csv`).
- **EDGE CASES**:
  - stdlib `csv` only (no pandas) — the facade stays dependency-light.
  - `csv.Sniffer` auto-detects the delimiter (`,;\t|`); falls back to `csv.excel` on
    sniff failure. `utf-8-sig` read tolerates a BOM.
  - `looks_like_messages_csv()` requires a timestamp-ish column AND a text-ish column
    AND at least one of sender/direction/service/sender-id — a gate against grabbing
    an arbitrary unrelated CSV — else raises `ValueError` naming the headers seen.
  - `_parse_dt()` tries ISO/epoch via the shared `parse_timestamp` helper first, then
    detects bare epoch-millisecond strings, then 16 additional `strptime` formats.
    Unparseable dates become `None`, sorted to `datetime.min`.
- **PROVENANCE**: `provenance="custom column-flexible CSV parser (no upstream app
  emits a canonical messaging CSV)"`.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("messages.messaging-csv").run({"path": "imazing_export.csv"})
  ```

### messages.transcript-marker

- **File**: `server/tools/parsers/messaging/messaging_transcript.py`
- **Registered**: `id="messages.transcript-marker"`,
  `capability="parse.messages-transcript"`, `accept=lambda hint, size:
  hint.lower().endswith((".txt", ".csv"))`.
- **INPUT**: the owner's unified transcript-marker grammar, shared by a plain-text SMS
  export AND a mislabeled iMessage "CSV" that is actually this same marker grammar (not
  a tabular table):
  ```
  [2026-05-17 05:29 PM] Jane Doe:
  Running late, sorry
  [2026-05-17 05:31 PM] Me:
  No worries, see you at 6
  ```
  Each `[YYYY-MM-DD HH:MM AM/PM] Speaker:` line opens a new message; every following
  non-empty line (or, for `.csv`, every following row's first cell) is appended to that
  message's body until the next marker.
- **OUTPUT**: `RecordType.message`/`.call`. **`conversation_id` is derived from
  content, not the filename** — the single non-owner speaker seen across the file (a
  documented real-world gotcha: one sample CSV named `8102689630` was actually the
  `+18103533592` thread). `attrs`: `platform="messages"`, `format="transcript"`,
  `direction`, `speaker_label`, `raw_timestamp`, `sequence_number` (same-minute sort
  tiebreak, since the grammar is minute-precision).
- **EDGE CASES**:
  - **Route by content, not extension**: this parser is offered for both `.txt` and
    `.csv`, and sniffs for at least one marker line in the first ~40 non-empty cells
    *in `parse()`*; if none is found it raises `ValueError` so a tabular CSV falls
    through to `messages.messaging-csv` and a stock imessage-exporter `.txt` falls
    through to `messages.imessage-txt`.
  - **Silent-empty guard**: if markers are detected but zero records result, raises
    `RuntimeError` explicitly rather than emitting empty evidence.
  - Speakers are never blended — one record per marker block, no cross-speaker
    merging.
- **PROVENANCE**: `provenance="ported from PROCESS de-risk harness
  parse_csv_transcript + shared SMS/iMessage transcript grammar"`; record counts were
  PROVEN by PROCESS against real samples (810/7,406/11 msgs on the SMS `.txt`; 7,187
  msgs on the iMessage transcript-CSV — see the module docstring for the exact spec
  reference).
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("messages.transcript-marker").run({"path": "8102689630.csv"})
  ```

### messages.sms-xml-sbv (primary)

- **File**: `server/tools/parsers/messaging/sbv_sms.py`
- **Registered**: `id="messages.sms-xml-sbv"`, `capability="parse.sms-xml"`,
  `accept=lambda hint, size: hint.lower().endswith(".xml") and _sbv_enabled()`
  (`_sbv_enabled()` is true only when `SBV_SERVICE_PASS` is set — without it this tool
  simply never offers itself, no hard dependency on a running SBV).
- **INPUT**: the same "SMS Backup & Restore" Android XML schema as
  `messages.sms-xml` (see that section for the grammar), but instead of parsing it
  in-process this module **uploads the file to SBV** (`ghcr.io/lowcarbdev/sbv`, a Go
  microservice) via `_sbv_client.SBVClient`, waits for async processing
  (`wait_for_processing()`), then pulls the parsed result back over
  `GET /api/activity` (SBV's paginated "everything" stream of messages+calls).
- **OUTPUT**: same shape as `messages.sms-xml` (`RecordType.message`/`.call`,
  `conversation_id` = counterparty, `participants=[OWNER, other]`, same
  `_SMS_TYPE`/`_CALL_TYPE` direction maps and forensic call-block `flags`) — deliberately
  kept identical so downstream code never cares which of the two ran. The one addition:
  `attrs["content_hash"]` — SBV's H2 per-record custody hash of the **raw source XML
  element**, computed by SBV before normalization (not a hash of the NormalizedRecord
  itself). `attrs["parser"] = "sbv"` on every record.
- **EDGE CASES**:
  - **Mesh preference by import order**: this module and `messages.sms-xml` both
    register `capability="parse.sms-xml"`; alphabetically `sbv_sms` < `sms_xml`, so SBV
    registers first and is tried first (assuming `accepts()` passes).
  - **Fail loudly to trigger fallback**: if `client.health()` is false, raises
    `SBVError` immediately — the workflow's substitution loop then tries
    `messages.sms-xml`. Likewise, an empty `all_activity()` result on a non-empty file
    raises `SBVError` rather than returning zero records silently.
  - **Custody reconciliation is opt-in and lazy**: `_reconcile_custody()` only runs when
    `SBV_CUSTODY_ENABLED` is set, and lazily imports `server.evidence.custody` *inside*
    the function (not at module top) specifically so importing this module in the
    dependency-light tools-facade — which has no sqlalchemy — doesn't fail; on failure
    it returns `None` (skips cleanly) rather than raising.
- **PROVENANCE**: `provenance="SBV REST API wrapper (lowcarbdev/sbv) — primary
  SMS-XML parser; sms_xml.py is the pure-Python fallback"`. Auth/endpoint details are in
  `server/tools/_sbv_client.py` (session-cookie auth against SBV's `/api/` surface,
  cracked from the upstream Go source and verified live 2026-06-25).
- **EXAMPLE INVOCATION** (requires `SBV_SERVICE_PASS` set and SBV reachable):
  ```python
  registry.get("messages.sms-xml-sbv").run({"path": "sms-20260517.xml"})
  ```

### messages.sms-xml (pure-Python fallback)

- **File**: `server/tools/parsers/messaging/sms_xml.py`
- **Registered**: `id="messages.sms-xml"`, `capability="parse.sms-xml"`,
  `accept=lambda hint, size: hint.lower().endswith(".xml")`.
- **INPUT**: the Android "SMS Backup & Restore" XML schema — `<smses>` with `<sms>`/
  `<mms>` children, `<calls>` with `<call>` children. Attributes carry epoch-millisecond
  `date`, `address`/`contact_name`, and a `type` whose integer meaning differs between
  messages and calls:
  ```xml
  <smses>
    <sms address="+18105551234" date="1715980182000" type="1"
         contact_name="Jane Doe" body="Running late, sorry" />
  </smses>
  ```
  MMS bodies live in nested `<parts><part ct="text/plain" text="..."/>`.
- **OUTPUT**: `RecordType.message`/`.call`. `conversation_id` = counterparty (contact
  name, else address/number). `participants=[OWNER, other]`. `attrs` for messages:
  `channel` (`sms`/derived), `direction` (`received`/`sent`/`draft`/`outbox`/`failed`/
  `queued`), `raw_type`, `address`, `contact_name`. `attrs` for calls: `channel="call"`,
  `call_type`, `duration_seconds`, `blocked` (bool), `forensic_flags` — a list of
  human-readable strings such as `"call actively rejected"`, `"number on refuse/block
  list"`, `"outgoing call with 0 duration - did not connect"` (call-blocking pattern
  ported from the dial-stack `ConflictAnalysisApp`).
- **EDGE CASES**:
  - **Streaming parse**: uses `xml.etree.ElementTree.iterparse` with elements cleared
    after mapping, so multi-GB backup dumps don't blow up memory.
  - **Malformed-XML fallback**: if the stream hits an `ET.ParseError` (stray
    ampersands are common in these dumps), retries by reading the whole file,
    sanitizing (stripping control chars, escaping bare `&` not already part of a valid
    entity) and parsing the sanitized string — a slower, more-RAM path used only as a
    last resort.
  - A message with empty/`"null"` body is dropped (`_map_sms` returns `None`), but
    calls are always emitted regardless of content.
  - Content-sniffs the file head for `<smses`/`<calls`/`<sms `/`<call ` before parsing;
    raises `ValueError` otherwise.
- **PROVENANCE**: `provenance="port of dial-stack ts-mcp-server/src/tools/
  SmsXmlParser.ts + ConflictAnalysisApp call-block logic"`.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("messages.sms-xml").run({"path": "sms-20260517.xml"})
  ```

---

## parsers/ai_chat (11)

Nine of these eleven wrappers are **thin `@register` shims that delegate entirely to
the vendored chatminer parser core** (`server/vendored/chatminer/parsers/*.py`) via
`server/tools/_chatminer_adapter.run_chatminer_parser()`. Their shared shape, documented
once here rather than nine times:

- Body is exactly `return run_chatminer_parser(<VendoredParserClass>, payload)` (or,
  for `transcripts.generic-md`, with `min_confidence=0.25` — a deliberately looser gate
  since it's the catch-all structured parser).
- `run_chatminer_parser()`: instantiates the vendored parser, calls its
  `can_parse(content, path)` detector; if the confidence score is below
  `DEFAULT_MIN_CONFIDENCE` (0.5, unless overridden), **raises `ValueError`** so the mesh
  tries the next `parse.transcript` candidate — this is the "defer by raising" pattern
  applied at the chatminer boundary. Then calls `parser.parse_file(path)`; if it errored
  with zero conversations, raises `ValueError`. Then flattens every
  `ParsedConversation`/`ParsedMessage` into `NormalizedRecord`s via
  `to_normalized_records()`; if that yields zero records, **raises `ValueError`
  ("parsed 0 messages — hard-fail, no silent-empty")**.
- `message_to_record()` (the actual chatminer→NormalizedRecord mapping): `record_type`
  is always `RecordType.message`; `source` = the vendored parser's declared
  `source_format` with `_` replaced by `-` (e.g. `chatgpt_official` → `chatgpt-official`);
  `conversation_id` **prefers the original export's own conversation id**
  (`conv.metadata["conversation_id"]`) over chatminer's own `uuid4()`-per-parse id, so
  re-ingesting the same export is deterministic; `role` comes from
  `msg.sender_role.value` (chatminer's `MessageRole` enum: user/assistant/system/tool/
  unknown); `participants` = unique sender display names in first-appearance order.
  `attrs` always carries `message_id`, `message_hash` (`msg.compute_hash()` — a
  per-message SHA-256, the forensic content-fidelity anchor for this whole family),
  `content_type`, `sender`, `source_file`, `source_format`, `source_index`,
  `confidence`, plus `language`/`message_metadata`/`conversation_title`/
  `conversation_metadata` when the vendored parser populated them.
- Provenance line for each is `"vendored: chatminer/parsers/<module>.py"`.
- Note the vendored package itself (module-by-module internals: detection heuristics,
  regexes, segmentation) is **not** re-documented here — that's the separate DOC_DEBT
  chatminer item (see the note added to `docs/DOC_DEBT.md`). What's below is the
  wrapper contract each of these nine tools guarantees, plus the source-format shape
  taken verbatim from each vendored module's own docstring so a caller knows what to
  feed it.

### transcripts.chatgpt-official

- **File**: `server/tools/parsers/ai_chat/chatgpt_official.py` →
  `server/vendored/chatminer/parsers/chatgpt_official.py::ChatGptOfficialParser`.
- **Registered**: `id="transcripts.chatgpt-official"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith(".json")`.
- **INPUT**: the official ChatGPT data export `conversations.json` — a mapping-tree
  structure (not a flat list):
  ```json
  {
    "title": "Conversation Title",
    "create_time": 1712345678.0,
    "mapping": {
      "uuid-1": {
        "message": {"author": {"role": "user"}, "content": {"parts": ["Hello"]},
                     "create_time": 1712345678.0},
        "children": ["uuid-2"]
      }
    }
  }
  ```
- **OUTPUT/EDGE CASES/PROVENANCE**: see the shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.chatgpt-official").run({"path": "conversations.json"})
  ```

### transcripts.chatgpt-share

- **File**: `server/tools/parsers/ai_chat/chatgpt_share.py` →
  `.../chatminer/parsers/chatgpt_share.py::ChatGptShareParser`.
- **Registered**: `id="transcripts.chatgpt-share"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".md", ".txt"))`.
- **INPUT**: markdown produced by ChatGPT's "Share" feature / browser-export
  userscripts:
  ```
  **User:** Matthew Salem (matt.salemnet@gmail.com)
  Created: 7/25/2025 7:48 | Updated: 7/25/2025 13:00 | Exported: 8/21/2025 13:53
  Link: https://chatgpt.com/c/...
  [Your message content]

  **Response:**
  [Assistant response content]
  ```
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.chatgpt-share").run({"path": "chat-export.md"})
  ```

### transcripts.claude-ai-export

- **File**: `server/tools/parsers/ai_chat/claude_ai_export.py` — **NOT
  chatminer-backed**, a standalone custom parser.
- **Registered**: `id="transcripts.claude-ai-export"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith(".json")`.
- **INPUT**: the claude.ai data-export `conversations.json` — a list of conversation
  objects, each with a `chat_messages` array:
  ```json
  [{
    "uuid": "conv-123", "name": "Case strategy",
    "chat_messages": [
      {"sender": "human", "text": "Summarize the timeline", "created_at": "2026-05-17T17:29:42Z"},
      {"sender": "assistant", "content": [{"type": "text", "text": "Here's the summary..."}],
       "created_at": "2026-05-17T17:29:50Z"}
    ]
  }]
  ```
- **OUTPUT**: `RecordType.message`. `conversation_id` = `conv["uuid"]`. `role` =
  `"user"` if `sender == "human"` else `"assistant"`. `participants =
  ["owner", "claude"]` (constant, not derived per-conversation). `attrs =
  {"conversation_title": <name or "untitled">}`. `occurred_at` via the shared
  `parse_timestamp()` helper (epoch or ISO-8601).
- **EDGE CASES**:
  - Text is read from `msg["text"]` first; if empty, falls back to concatenating
    `content` blocks where `block["type"] == "text"`.
  - A message with no text at all (after both attempts) is skipped — not hard-failed,
    just omitted from the record list (there is no records-empty guard on this module,
    unlike several siblings).
  - Detects the format by checking the first conversation has a `chat_messages` key;
    otherwise raises `ValueError("not a claude.ai export (no \`chat_messages\`)")`.
- **PROVENANCE**: `provenance="new module (no prior extracted parser)"`.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.claude-ai-export").run({"path": "conversations.json"})
  ```

### transcripts.claude-code

- **File**: `server/tools/parsers/ai_chat/claude_code.py` →
  `.../chatminer/parsers/claude_code.py::ClaudeCodeParser`.
- **Registered**: `id="transcripts.claude-code"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".jsonl", ".json"))`.
- **INPUT**: chatminer's own simplified JSONL grammar — one flat `{role, content,
  timestamp}` object per line:
  ```
  {"role": "user", "content": "...", "timestamp": "2025-01-15T10:30:00Z"}
  {"role": "assistant", "content": "...", "timestamp": "2025-01-15T10:30:05Z"}
  ```
  **Important distinction** (this surprised the doc author enough to call it out):
  this is a *different, simpler* shape than the *real* Claude Code CLI session export —
  that shape is handled by the sibling `transcripts.claude-code-jsonl` (below), which is
  NOT chatminer-backed. Both accept `.jsonl`; the registry offers both under
  `capability="parse.transcript"` and the mesh's confidence-gate / defer-by-raising
  sorts out which one actually matches a given file.
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.claude-code").run({"path": "session.jsonl"})
  ```

### transcripts.claude-code-jsonl

- **File**: `server/tools/parsers/ai_chat/claude_code_jsonl.py` — **NOT
  chatminer-backed**, a standalone custom parser.
- **Registered**: `id="transcripts.claude-code-jsonl"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith(".jsonl")`.
- **INPUT**: the **real** Claude Code CLI session `.jsonl` — one JSON event per line,
  richer than chatminer's `ClaudeCodeParser` shape above: `type` is `"user"` or
  `"assistant"`, `message.content` may be a string or a list of typed blocks, plus
  `sessionId`, `timestamp`, `uuid`:
  ```
  {"type": "user", "message": {"content": "Summarize the timeline"}, "sessionId": "abc123", "timestamp": "2026-05-17T17:29:42Z", "uuid": "evt-1"}
  {"type": "assistant", "message": {"content": [{"type": "text", "text": "Here's the summary..."}]}, "sessionId": "abc123", "timestamp": "2026-05-17T17:29:50Z", "uuid": "evt-2"}
  ```
- **OUTPUT**: `RecordType.message`. `conversation_id` = `sessionId` (falls back to the
  file stem). `role` = the raw `type` value (`"user"`/`"assistant"`).
  `participants = ["owner", "claude-code"]`. `attrs = {"event_uuid": ...}`.
- **EDGE CASES**:
  - **Only text blocks become records — tool-call noise is deliberately dropped**
    (`_event_text()` only extracts `content` strings or `{"type": "text"}` blocks; tool
    invocations/results in the same session are silently excluded because "knowledge
    value lives in the prose", per the module docstring).
  - Only `type in ("user", "assistant")` events are considered at all — system/other
    event types are skipped outright.
  - Malformed JSON lines are skipped (`try/except json.JSONDecodeError: continue`)
    rather than aborting the whole file.
  - Two-tier hard-fail: `line_count == 0` raises `ValueError("empty file...")`; a
    non-empty file that yields zero text records raises `ValueError("no user/assistant
    text events — not a Claude Code session (hard-fail, no silent-empty)")`.
- **PROVENANCE**: `provenance="rewrite of extracted-code/parsers/chat-exports/
  ClaudeCodeJSONLParser"`.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.claude-code-jsonl").run({"path": "session.jsonl"})
  ```

### transcripts.claude-md

- **File**: `server/tools/parsers/ai_chat/claude_md.py` →
  `.../chatminer/parsers/claude_md.py::ClaudeMdParser`.
- **Registered**: `id="transcripts.claude-md"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".md", ".txt"))`.
- **INPUT**: Claude conversations copy-pasted into markdown — no standard export
  format, just "Human:"/"Assistant:" markers or `**You:**`/`**Claude:**`, or Anthropic
  console XML-tag style:
  ```
  Human: What's the timeline for the May incident?

  Assistant: Based on the records, here's the timeline...
  ```
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.claude-md").run({"path": "claude_conversation.md"})
  ```

### transcripts.gemini-chrome

- **File**: `server/tools/parsers/ai_chat/gemini_chrome.py` →
  `.../chatminer/parsers/gemini_chrome.py::GeminiChromeParser`.
- **Registered**: `id="transcripts.gemini-chrome"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".md", ".txt"))`.
- **INPUT**: exports from the Google Gemini Chrome extension — markdown with an emoji-
  delimited message grammar, filename pattern `Google_Gemini_YYYY-MM-DD_HHMM.md`:
  ```
  Google Gemini
  Conversation Details
  Exported on: 12/9/2025, 4:34:05 PM | Total Messages: 5
  🤖 Assistant (4:34:00 PM)
  [Message content...]
  👤 You (4:34:05 PM)
  [Follow-up question...]
  ```
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.gemini-chrome").run({"path": "Google_Gemini_2026-05-17_1729.md"})
  ```

### transcripts.gemini-json

- **File**: `server/tools/parsers/ai_chat/gemini_json.py` →
  `.../chatminer/parsers/gemini_json.py::GeminiJsonParser`.
- **Registered**: `id="transcripts.gemini-json"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith(".json")`.
- **INPUT**: Gemini JSON exports (Google Takeout or similar — distinct from the Chrome
  extension's markdown export above):
  ```json
  {"messages": [
    {"author": "user", "content": "...", "timestamp": "..."},
    {"author": "model", "content": "...", "timestamp": "..."}
  ]}
  ```
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.gemini-json").run({"path": "gemini_export.json"})
  ```

### transcripts.perplexity-gdpr

- **File**: `server/tools/parsers/ai_chat/perplexity_gdpr.py` →
  `.../chatminer/parsers/perplexity_gdpr.py::PerplexityGdprParser`.
- **Registered**: `id="transcripts.perplexity-gdpr"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith(".json")`.
- **INPUT**: Perplexity's official GDPR data export — a `conversations.json` (part of a
  larger export bundle that also includes an XLSX and an `assets/` directory, of which
  only the JSON is consumed here):
  ```json
  {"conversations": [{
    "uuid": "abc-123", "title": "Timeline Analysis", "updated_at": "2026-01-31T14:25:58Z",
    "answers": [{"content": "# Answer\nmarkdown content...",
                 "citations": [{"title": "Wikipedia", "url": "https://..."}],
                 "created_at": "2026-01-31T14:25:58Z"}]
  }]}
  ```
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.perplexity-gdpr").run({"path": "conversations.json"})
  ```

### transcripts.perplexity-md

- **File**: `server/tools/parsers/ai_chat/perplexity_md.py` →
  `.../chatminer/parsers/perplexity_md.py::PerplexityMdParser`.
- **Registered**: `id="transcripts.perplexity-md"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".md", ".txt"))`.
- **INPUT**: the **generic fallback** for Perplexity markdown that doesn't match the
  plugin exporter's structured pattern — copy-paste from the web interface without a
  `## Sources` section.
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above. Being the
  fallback within the Perplexity family, it's tried after `transcripts.perplexity-
  plugin` fails detection (both accept `.md`/`.txt`; the mesh's confidence gate decides).
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.perplexity-md").run({"path": "perplexity_chat.md"})
  ```

### transcripts.perplexity-plugin

- **File**: `server/tools/parsers/ai_chat/perplexity_plugin.py` →
  `.../chatminer/parsers/perplexity_plugin.py::PerplexityPluginParser`.
- **Registered**: `id="transcripts.perplexity-plugin"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".md", ".txt"))`.
- **INPUT**: Perplexity conversations exported via browser plugin/userscript, with
  Perplexity's distinctive `## Sources` formatting:
  ```
  # [Query Title]

  [Answer content with markdown formatting]

  ## Sources
  1. [Title](URL)
  2. [Title](URL)

  ---

  # [Next Query]
  ```
- **OUTPUT/EDGE CASES/PROVENANCE**: shared chatminer-wrapper contract above.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.perplexity-plugin").run({"path": "perplexity_export.md"})
  ```

---

## parsers/generic (2)

### transcripts.generic-md

- **File**: `server/tools/parsers/generic/generic_md.py` →
  `.../chatminer/parsers/generic_md.py::GenericMdParser`.
- **Registered**: `id="transcripts.generic-md"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".md", ".txt"))`. Calls
  `run_chatminer_parser(GenericMdParser, payload, min_confidence=0.25)` — a
  **deliberately lower** confidence gate than every other chatminer wrapper's default
  0.5, since this is the structured-parser catch-all: it should accept a wider range of
  ad hoc role-marker markdown before the mesh falls all the way through to the
  whole-file fallback below.
- **INPUT**: any markdown with recognizable conversation role markers not covered by a
  source-specific parser:
  ```
  **User:** message
  **Assistant:** response

  > User: message
  > Assistant: response

  # User
  message
  # Assistant
  response
  ```
- **OUTPUT/EDGE CASES**: shared chatminer-wrapper contract described at the top of
  `parsers/ai_chat`, with the 0.25 confidence floor noted above.
- **PROVENANCE**: `provenance="vendored: chatminer/parsers/generic_md.py"`.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.generic-md").run({"path": "unknown_chat.md"})
  ```

### transcripts.markdown (whole-file fallback)

- **File**: `server/tools/parsers/generic/whole_file_fallback.py`
- **Registered**: `id="transcripts.markdown"`, `capability="parse.transcript"`,
  `accept=lambda hint, size: hint.endswith((".md", ".txt"))`.
- **INPUT**: any non-empty `.md`/`.txt` file — no grammar requirement at all. This is
  the deliberate last-resort unit: when nothing structured fits, the **whole file
  becomes one record**, and the knowledge engine chunks it downstream.
- **OUTPUT**: exactly one `RecordType.message` record. `conversation_id` = file stem.
  `role="transcript"`, `participants=["owner"]`, `content` = the full file text
  (stripped), `attrs={"original_name": ...}`. No `occurred_at` is set (left `None` —
  there's no per-file timestamp to derive one from).
- **EDGE CASES**:
  - **Naming is load-bearing**: the module docstring flags that auto-discovery imports
    `server.tools` modules alphabetically and registration order doubles as
    substitution preference, so this module is deliberately named to sort *after*
    every structured `parse.transcript` parser (it was previously `markdown_transcript.py`,
    which sorted *before* the Perplexity wrappers and was silently swallowing their
    `.md` inputs before they got a chance to match). This tool never rejects a
    non-empty file, so it must always be the last candidate the mesh tries.
  - Raises `ValueError("empty file — nothing to parse")` on an empty/whitespace-only
    file — the one case it does defer on.
- **PROVENANCE**: `provenance="new module (deliberate whole-file fallback)"` — not
  chatminer-backed, not a port.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("transcripts.markdown").run({"path": "unstructured_notes.txt"})
  ```

---

## extractors (1)

### documents.extract-text

- **File**: `server/tools/extractors/extract_text.py`
- **Registered**: `id="documents.extract-text"`, `capability="extract.text"`,
  `accept=lambda hint, size: hint.lower().endswith((".pdf", ".png", ".jpg", ".jpeg",
  ".tiff", ".tif", ".bmp", ".gif"))`.
- **INPUT**: any PDF or raster image that needs a text layer extracted **before**
  format parsing runs — the general OCR/text-extraction pass, not tied to any one
  downstream parser (e.g. `messages.imessage-pdf` extracts its own text natively and
  does not currently call through this tool, but is the intended consumer for a
  *scanned* iMessage PDF per its own docstring).
- **OUTPUT — different shape from every parser above**: this is explicitly **NOT**
  `NormalizedRecords`; it returns `{"text": <joined pages>, "pages": [<per-page text>],
  "stats": {"method", "ocr_used", "page_count", "char_count", "low_confidence", "ext"}}`
  — a pre-parse utility output, consumed by a caller that then routes the text into an
  actual parser.
- **EDGE CASES (tiered, cost-aware extraction)**:
  1. **Tier 1 — native text layer** (free, instant): `pypdf.PdfReader` preferred,
     `pdfplumber` fallback, for born-digital PDFs.
  2. **Sparsity check**: average characters-per-page is compared against
     `_SPARSE_CHARS_PER_PAGE = 16`; if the native layer is absent or below that
     threshold, the PDF is treated as scanned/image-only and escalated to Tier 2 —
     unless the caller passed `payload["native_only"]=True`, in which case it stays at
     Tier 1 and a `None` pages result raises `RuntimeError` instead.
  3. **Tier 2 — Tesseract OCR** (local, CPU-only, no `$` cost): `pytesseract` +
     `pdf2image` for PDFs (rasterize each page then OCR), or `pytesseract` + `Pillow`
     directly for image inputs. Missing OCR stack raises a `RuntimeError` with an
     explicit install hint rather than failing silently.
  4. **Tier 3 — heavy OCR / document-AI is NOT implemented here.** The module
     docstring is explicit that a stateless tool can't call a remote provider, so when
     the result comes back `low_confidence` (`not text`), escalation to a paid/vision
     OCR provider is the **caller's** responsibility, `$`-gated and opt-in.
  - Image inputs always go straight to OCR (`ocr_used=True`); there is no "native text
    layer" concept for a raw image.
- **PROVENANCE**: `provenance="document-intelligence layer (native pypdf/pdfplumber
  + Tesseract); vision OCR tier escalated by the caller"`.
- **EXAMPLE INVOCATION**:
  ```python
  registry.get("documents.extract-text").run({"path": "scanned_letter.pdf"})
  ```

---

## Verifying this doc

Every id above must appear in the live registry (23 tools):

```bash
uv run python -c "from server.tools.registry import load_builtin_tools, registry; load_builtin_tools(); print(sorted(t.id for t in registry.all()))"
```
