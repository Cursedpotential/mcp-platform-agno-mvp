# SBV, ChatMiner, SMS Backup & Restore, and parser gap review — 2026-08-02

> _Byline: Codex · GPT-5 · 2026-08-02_

## Purpose

This handoff records the code-level and discussion-level audit of the platform's
SBV integration, ChatMiner integration, SMS Backup & Restore XML/CSV support,
parser registry, custody connection, and emerging streaming-repair layer.

It supplements, rather than replaces, the broader
[`HANDOFF-2026-08-02-semantica-platform-review.md`](HANDOFF-2026-08-02-semantica-platform-review.md),
which covers Semantica, AgentOS, the database topology, the knowledge-horizon
mechanism, PAL/Dev, and the recommended platform topology.

The most important conclusion is:

> **Do not treat the current SBV path as a trustworthy primary evidence parser
> yet.** SBV itself has useful parsing, media, and independently implemented
> custody capabilities, but the platform adapter reads the service account's
> entire persistent activity database after each upload rather than the records
> belonging to that upload. It can therefore attribute old records to a new
> artifact. The primary adapter also drops bodyless/attachment-only messages
> that the Python fallback correctly retains.

The correct topology is to keep SBV as an isolated extraction worker, require
an import-scoped result contract, and make PostgreSQL's custody/raw/working
layers the system of record. ChatMiner should remain a format-parser library
behind the same platform-owned ingestion contract, not become a separate data
store or custody authority.

## Scope and method

The review combined four evidence sources:

1. Current repository source, tests, SQL migrations, planning documents, and
   the vendored SBV and ChatMiner trees.
2. Prior project discussions recovered from local Claude session history,
   including owner corrections, real-file results, and unresolved design work.
3. DuckDB ad-hoc scans over the repository and JSONL discussion corpus.
4. Focused test execution against the current worktree.

The DuckDB repository scan covered 1,378 textual files and approximately
16.1 million characters. It found 87 SBV-related files, 84 ChatMiner-related
files, 89 SMS Backup/XML-related files, and 446 parser-related files. The
discussion scan covered 4,156 Claude JSONL logs (about 1.11 GB), with a
narrower pass over the current project and a broader workspace pass. Raw term
counts were used only to locate material; tool output and repeated quoted text
make those counts unsuitable as decision counts.

No persistent DuckDB state file existed, so the queries ran in ad-hoc mode with
external access disabled and the repository or log locations explicitly
allowlisted. Failed exploratory queries were corrected and rerun: unsupported
`read_text(ignore_errors=...)`, an invalid `size(content)` call, too-narrow
`allowed_paths` globs, and a vendored binary matched by an over-broad text glob.
The successful scans used `length`, `allowed_directories`, and text-only
extensions. These recovered errors do not change the findings.

The earlier PowerShell/OneDrive concern was also checked. Login-shell startup
still emitted a `Microsoft.WinGet.CommandNotFound` module error from the
OneDrive-hosted profile during one read-only command. Re-running the repository
inspection with profile loading disabled produced clean commands and the same
source results. The PowerShell startup error therefore did not invalidate or
change any recommendation here.

## Executive findings

| Priority | Finding | Consequence |
|---|---|---|
| P0 | SBV upload is followed by unfiltered `GET /api/activity`, which returns the service user's whole persistent corpus, not the new import | Old records can be stored under the new artifact and falsely associated with its custody event |
| P0 | The SBV adapter drops every message whose body is empty or `null` before considering MMS media | Attachment-only and empty-body message events disappear on the designated primary path |
| P0 | The Go parser logs and continues after per-record decode, conversion, or insert failures; the platform does not persist those rejects | A completed import can have unexplained missing evidence with no platform-visible rejection rows |
| P0 | SBV custody reconciliation is opt-in and fail-open, and it requests `hashes/latest` rather than a returned import ID | Parsing can succeed without custody; concurrent or stale state can bind hashes to the wrong import |
| P0 | The declared XML count and SBV import count are not enforced against parsed + rejected output | “Completed” does not mean the export is reconciled |
| P1 | The Python client loads the complete XML and multipart body into RAM; all activity and normalized records are also accumulated as lists | The end-to-end primary path is not multi-GB safe despite the Go parser itself streaming |
| P1 | Python XML detection and malformed recovery, messaging CSV, most ChatMiner parsers, and several other parsers read whole files | Large exports can create avoidable memory pressure or hit ChatMiner's 50 MB hard limit |
| P1 | Parser preference is implicit module import order, not explicit policy | Renaming or discovery changes can silently change the primary parser |
| P1 | The database has rejection/reconciliation tables and views, but the active Python ingestion path has no writer for `raw_rejected` or the XML `record_count_claimed` | The visibility schema promises a funnel that the runtime does not currently populate |
| P1 | The new repair package is untracked, untested, and not wired into parsers/workflows | It is promising design work, not a functioning recovery layer yet |
| P2 | ChatMiner's `message_hash` is a 16-hex-character hash of normalized message content, not raw-source H2 | It is useful for semantic/content identity but must never be labeled custody evidence |
| P2 | Many ChatMiner IDs are generated with `uuid4`, and its timestamps use deprecated naive `utcnow()` defaults | Re-ingest provenance can drift and emits current deprecation warnings |
| P2 | The platform mixes ChatMiner-backed wrappers with bespoke parsers under one broad transcript capability | Detection and fallback can work, but conformance and equivalence are not centrally enforced |

## What is implemented now

### SBV forensic fork

The vendored SBV fork is substantial and useful. Its Go parser incrementally
decodes `<sms>`, `<mms>`, and `<call>` elements. It computes:

- H1: SHA-256 over the raw uploaded file bytes.
- H2: SHA-256 over the exact raw XML bytes of each successfully inserted source
  element, before normalization.
- H3: an order-sensitive fold over the H2 values, with empty-string genesis and
  a line-feed separator.

The fork exposes `content_hash` on activity records and an imports row through
`GET /api/hashes/:importID`. Platform-side custody correctly distinguishes the
SBV construction with `h3-chain-sbv-genesisempty-v1`; legacy
`h3-chain-v1` rows remain read-only. This must remain separate from the valid
Case Bible construction that uses H1 as genesis and no line-feed separator.

SBV also provides per-user SQLite isolation, full-text search, conversation and
activity views, media handling, HEIC/3GP conversion support, calls, and a web UI.
Those are useful operator/extraction features. They do not make SBV's SQLite
database a platform source of truth.

### Platform SBV adapter

`server/tools/parsers/messaging/sbv_sms.py` registers
`messages.sms-xml-sbv` under `parse.sms-xml`. It is selected only when the file
ends in `.xml` and `SBV_SERVICE_PASS` is set. It health-checks, uploads, polls
progress, retrieves activity, maps messages/calls into `NormalizedRecord`, and
optionally asks `server.evidence.custody` to reconcile SBV hashes.

The workflow implements the owner's no-silent-substitution rule. A primary
failure pauses by default. With `allow_fallback=True`, it records the failed
attempt, identifies the alternate parser, and marks stored records with
alternate-parser provenance. This is a strong design choice and should remain.

### Python SMS Backup & Restore XML fallback

`server/tools/parsers/messaging/sms_xml.py` incrementally parses valid XML with
stdlib `ElementTree.iterparse`. It maps SMS, MMS, and calls; distinguishes SMS
and call type codes; produces call-blocking forensic flags; and now preserves
bodyless events and attachment-only MMS. Attachment metadata excludes raw
base64 while retaining a base64-text digest useful for distinguishing items
within an export.

It exposes a streaming `iter_records()` API with an `on_reject` callback, but
the registry `parse()` path still accumulates all normalized records. The
workflow does not call `iter_records()` and does not provide a rejection writer.
Malformed XML falls back to reading and sanitizing the entire file.

### SMS Backup & Restore CSV

`messaging_csv.py` now recognizes the real
`address, readable_date, type, body, read, contact_name` shape. Numeric SMS type
codes map correctly: 1 inbound, 2/4/5/6 outbound, and 3 left undirected. The
original row is preserved in `attrs.raw_row`. This closes the specific CSV
capability hole found in 262 files.

The implementation still reads the entire CSV, splits it into lines, and then
materializes normalized and original row dictionaries before producing another
full record list. Splitting lines also cannot preserve legal CSV fields that
contain embedded newlines as faithfully as a streaming `csv` reader over the
file handle.

### ChatMiner

The platform vendors ChatMiner and uses it through
`server/tools/_chatminer_adapter.py`. Active ChatMiner-backed wrappers cover:

- ChatGPT official export and shared-chat markdown.
- Claude Code simple JSONL and Claude markdown.
- Gemini JSON and Chrome-extension markdown.
- Perplexity GDPR JSON, markdown, and plugin markdown.
- Generic role-marked markdown as a lower-confidence fallback.

The adapter preserves verbatim content, content type, sender, source index,
source metadata, parser confidence, and a content hash. It prefers an original
export conversation ID when the parser exposes one. It hard-fails below the
detection threshold, on errors with no conversations, and on zero messages.
Those guards prevent a silent empty parse from being treated as success.

ChatMiner is not used for SMS Backup & Restore parsing. That separation is
appropriate: ChatMiner is an AI-chat format normalizer; SBV and the platform
SMS parser are device-message evidence parsers with different custody and media
requirements.

## Detailed gap analysis

### 1. SBV results are not import-scoped — P0

The platform calls `client.upload(path)`, waits, then calls
`client.all_activity()`. SBV's activity endpoint queries the current user's
messages table. It has no import filter and the messages schema has no import ID
link. Because the service account database is persistent and inserts are
idempotent, the result is the entire accumulated corpus for that account.

This creates several failure modes:

- Upload B after A can return both A and B, and the workflow can store A's
  records under B's artifact.
- Re-uploading a file can return existing rows while the new imports row counts
  only records successfully inserted during the current parse.
- The H2 list gathered from returned records can contain hashes unrelated to
  the `hashes/latest` H1/H3 batch.
- A clean-looking record count can grow as the SBV account ages even if the new
  file contains fewer records.

This is the highest-risk issue because it can create affirmative false
provenance, not merely drop data.

**Required correction:** the upload response must return an immutable import
ID. Every inserted message/call must carry that import ID, and the API must
provide `GET /api/imports/:id/activity` (or an equivalent export stream). The
platform must reject any result not scoped to the returned ID. Until that
contract exists, use an isolated ephemeral SBV database per ingest or do not
designate SBV as primary.

### 2. Primary/fallback record sets are not equivalent — P0

The Python fallback was corrected after a real 636 MiB export demonstrated that
dropping empty bodies lost 516 MMS records. It preserves attachment-only MMS and
even empty-body message events when timestamp/counterparty evidence exists.

The SBV adapter still starts `_map_message()` with:

```python
text = (body or text or "").strip()
if not text or text == "null":
    return None
```

That decision is made before examining media. Therefore the chosen primary
silently reproduces the exact evidence-loss bug fixed in the fallback. It also
assigns only type 2 to the owner role; outbox/failed/queued records (4/5/6) are
outbound-authored in the CSV logic but become counterparty-authored here.

**Required correction:** define one canonical SMS/MMS/call mapping module and
make both transports feed it. Add a shared conformance fixture whose expected
records include captionless media, newline-only MMS, failed/queued/outbox SMS,
unknown contacts, calls, and duplicate records. Primary and fallback outputs
must match except for explicitly documented transport-only metadata.

### 3. Record loss is logged but not accounted for — P0

The Go loop continues after XML decode, conversion, and database insert errors.
Only successfully inserted records receive H2 membership and contribute to the
imports `record_count`. This is operationally resilient but forensically
incomplete: the service can finish successfully after losing individual source
elements.

The XML root's `count` is read only for progress. The platform has DDL for
`evidence.artifact_metadata.record_count_claimed`, `evidence.raw_rejected`, and
reconciliation views, but repository search found no active Python writer for
the claimed count or rejected rows. `sms_xml.iter_records(on_reject=...)` is not
used by the workflow.

**Required correction:** every encountered source element needs one terminal
outcome: accepted, rejected-with-reason, or deduplicated-with-link. Capture the
export's declared count before parsing. Make success contingent on:

`claimed = accepted + rejected + explicitly accounted duplicate`

If a format has no trustworthy claim, record “no claim” rather than treating
zero/null as reconciled.

### 4. Custody is optional and can bind to the wrong batch — P0

The evidence workflow performs platform H1 custody first, which is good. But
SBV's independent reconciliation is enabled only by `SBV_CUSTODY_ENABLED`.
Import failure, hash endpoint failure, or the facade's missing SQLAlchemy import
all return `None`; parsing continues. There is no degraded-custody state.

The adapter ignores the upload response and requests `hashes/latest`. This is a
race/staleness contract even if current deployment normally has one caller.
`wait_for_processing()` also treats `idle` as success without binding progress
to a job/import token.

**Required correction:** upload returns `{job_id, import_id}`; polling and hash
retrieval require that identifier. Custody reconciliation must be mandatory for
the “SBV forensic primary” quality tier. If the platform intentionally permits
an extraction-only tier, store a visible degraded status and never describe it
as independently custody-verified.

### 5. Streaming exists inside components, not end to end — P1

The Go XML decoder is streaming, but the Python client calls `fh.read()`, then
constructs a second multipart byte string. A 667 MiB file therefore has at least
the source bytes and multipart body resident before networking overhead. The
client then accumulates every activity page in a list, the adapter accumulates
every `NormalizedRecord`, and the workflow hands another list to storage.

The Python fallback streams XML parsing but its normal registry path also
accumulates records. Its detection reads the entire file merely to inspect the
first 4 KiB, and malformed recovery reads the entire file again. ChatMiner reads
each file as a string and refuses files above 50 MB. Messaging CSV reads the
whole export and duplicates it across several in-memory shapes.

**Required correction:** make the ingestion contract batch-oriented:

```text
source stream -> structural chunks -> map -> raw batch insert -> checkpoint
              -> rejected/repair events -> reconciliation -> working promotion
```

The registry may still expose a convenience list API for small files, but the
evidence workflow must use an iterator/batch protocol with backpressure.

### 6. Parser selection is an accidental policy — P1

`ToolRegistry.resolve()` returns registration order. Recursive module discovery
happens to import `sbv_sms` before `sms_xml` alphabetically. The SBV module's own
docstring relies on that filename ordering.

**Required correction:** add explicit priority and quality metadata to the tool
contract, for example:

- `priority`
- `quality_tier` (`forensic`, `standard`, `salvage`)
- `streaming`
- `custody_capabilities`
- `max_safe_size`
- `supported_variants`
- `conformance_version`

Selection should be deterministic policy, and the selected parser plus policy
version should be stored with every run.

### 7. The repair layer is promising but not operational — P1

The untracked `server/tools/repair/` work introduces bounded encoding detection,
structural chunking for XML/JSON/NDJSON/CSV/HTML, severity-ranked repair events,
loss accounting, and optional engines such as lxml recovery, ijson,
json-repair, and CleverCSV. Its principles match the forensic need: structural
chunks rather than arbitrary byte chunks, original files never rewritten,
lossy repair made visible, and large non-streaming fallbacks capped.

At review time it has no dedicated tests, no parser imports it, no workflow
persists its `RepairReport`, and no runtime writer connects its events to the
database. It is also concurrent uncommitted work and was not modified in this
audit.

**Required correction:** first test the repair primitives with malformed and
truncated fixtures; then wire one format at a time, beginning with SMS XML and
messaging CSV. Do not bulk-convert all parsers before the ledger, rejection, and
reconciliation writers exist—the observability contract is the acceptance
criterion.

### 8. ChatMiner identity and custody semantics need tightening — P2

ChatMiner's `compute_hash()` returns only the first 16 hex characters of SHA-256
over the normalized message content. Its docstring calls this chain-of-custody,
but it excludes source framing, author, timestamp, index, and raw bytes. Two
identical messages share it by design. It is not SBV H2 and not a custody hash.

Many ChatMiner parsers generate conversation and message IDs with UUID4. The
adapter repairs conversation determinism only when source metadata contains an
original ID; generated message IDs still change across parses. ChatMiner also
uses naive `datetime.utcnow()` for processing metadata, causing the seven
deprecation warnings seen in the focused test run.

**Required correction:** rename the field to `content_fingerprint`, retain the
full digest, and keep it explicitly outside `evidence_hash`. Derive stable IDs
from `(artifact H1, parser version, source conversation ID/index, source message
index)` while retaining source-native IDs separately. Use timezone-aware UTC.

### 9. ChatMiner capability is only partially adopted — P2

The vendored project includes artifact extraction, topic segmentation, pipeline
helpers, discovery, and standardized types, but the platform adapter uses the
format parsers only. That is sensible for the evidence spine: artifacts and
topics are derived analysis, not raw parsing. The gap is not that these features
are unused; it is that the boundary is undocumented and their results have no
candidate/provenance storage contract.

**Required correction:** keep ChatMiner parsing in the deterministic parse
stage. If artifact or topic features are adopted, run them after raw storage as
derived candidates, link each result to record IDs and extractor version, and
send them through the same review/promotion layer recommended for Semantica.

## Recovered decisions and discussion context

The prior discussions establish these owner requirements and corrections:

- Common parsers, schemas, hashing, tables, targets, and DuckDB-assisted tooling
  should be reusable by every caller, not rebuilt inside each app or agent.
- Each file type should be proven on one representative file before thousands
  are processed.
- CSV/XML/JSON repair should operate on structural chunks, preserve originals,
  reconstruct what can be recovered, and make every loss visible.
- A large SMS export originally lost 516 bodyless MMS. The corrected Python
  parser retained them and reached the export's exact claimed count.
- A previous attestation insert was unscoped and fabricated corroboration; this
  is directly analogous to the SBV whole-account activity problem. Queries that
  produce evidence must be scoped to the exact artifact/import.
- Completion gates must be deduplication-aware, but deduplication must remain an
  explicit accounted outcome rather than disappearing from counts.
- Operators need to see raw, normalized, spine, derived, rejected, skipped,
  passed, and repaired outcomes. “Saved somewhere” is not enough without an
  artifact-level reconciliation.
- Both H3 constructions are valid but must have distinct canon tags.
- SBV remains the intended Go primary, the pure-Python parser the fallback, and
  ChatMiner the AI-chat parser family—but “primary” is conditional on observed
  correctness, not configuration acceptance.

## Recommended target topology

```text
Immutable source file
        |
        v
PostgreSQL custody gate: H1 + acquisition + source metadata
        |
        +-------------------------------+
        |                               |
        v                               v
SBV worker (SMS XML)             Platform parser worker
ephemeral/import-scoped          ChatMiner / Python / repair engines
H2/H3 + media extraction         deterministic structural chunks
        |                               |
        +---------------+---------------+
                        v
Platform ingest contract
accepted | rejected | repaired | duplicate | parser/version | source position
                        |
                        v
PostgreSQL evidence.raw_* + artifact-level reconciliation gate
                        |
                        v
working.normalized_record (one canonical store; bitemporal fields)
                        |
                        +--> Semantica candidate extraction
                        +--> approved Neo4j evidence projection
                        +--> horizon-prefiltered Weaviate projection
                        +--> Graphiti belief state for the ignorant-agent walk
```

The key rule is that SBV and ChatMiner are workers, not databases in the
platform topology. SBV's SQLite may be an ephemeral working cache and UI, but
the result accepted by the platform must be import-scoped and reconciled.
ChatMiner's internal objects are an adapter format; `NormalizedRecord` plus raw
ledger/provenance is the platform contract.

## Implementation sequence

### Phase 0 — stop false provenance

1. Remove SBV from “forensic primary” eligibility until import-scoped reads are
   available; keep it callable in diagnostic/shadow mode.
2. Prevent `all_activity()` output from entering a new artifact's ingest.
3. Add a test proving two sequential uploads cannot cross-contaminate results.
4. Make SBV adapter preserve bodyless/attachment-only messages and correct
   outbound role mapping.

### Phase 1 — bind and reconcile every import

1. Return job/import ID from upload.
2. Store `import_id` on SBV message/call rows and expose import activity.
3. Bind progress, output, and hashes to the same ID.
4. Capture source-declared count and every rejected/deduplicated element.
5. Fail the promotion gate on unexplained count differences or H1 mismatch.

### Phase 2 — make ingestion bounded and observable

1. Replace the in-memory multipart upload with a streaming client or shared-file
   handoff inside the trusted deployment boundary.
2. Add a batch/iterator parser protocol and raw batch writer.
3. Wire `raw_rejected`, repair events, and claimed-count metadata.
4. Integrate the repair layer into SMS XML, then CSV, with dedicated tests.

### Phase 3 — enforce parser conformance

1. Add explicit registry priority and capability metadata.
2. Build golden corpora per format and primary/fallback equivalence tests.
3. Store parser ID, version/commit, conformance version, attempts, repair
   summary, and alternate-parser status on the ingest run and raw rows.
4. Run SBV in shadow comparison until its output reconciles against the source
   claim and golden mapper.

### Phase 4 — harden ChatMiner

1. Separate content fingerprints from custody hashes.
2. Make IDs deterministic and timestamps timezone-aware.
3. Replace whole-file detection with bounded probes; add streaming parsers for
   large JSON/JSONL formats where practical.
4. Keep artifact/topic extraction in a versioned derived-candidate stage.

## Validation performed

The following focused test set passed on the reviewed worktree:

```text
tests/test_sms_xml.py
tests/test_messaging_csv_smsbr.py
tests/test_chatminer_adapter.py
tests/test_sbv_custody.py
tests/test_sbv_tools.py
tests/test_registry.py

39 passed, 7 warnings
```

The warnings are ChatMiner's deprecated naive `datetime.utcnow()` defaults.
These tests validate mapping helpers, small-file behavior, registry mechanics,
and mocked custody/tool calls. They do **not** validate a live SBV service,
sequential uploads, import-scoped results, concurrent imports, streaming memory,
claimed-count equality, rejection persistence, the untracked repair package, or
the complete custody-to-knowledge workflow.

## Acceptance criteria before re-ingesting the real corpus

- One upload returns only records belonging to that exact immutable import ID.
- Primary and fallback produce the same canonical records for the golden SMS
  corpus, including attachment-only and empty-body events.
- Every source element is accepted, rejected, or deduplicated with a durable
  reason/link; no element exists only in a log line.
- The export claim reconciles exactly, or the run is visibly blocked/degraded.
- SBV H1 matches platform H1, and H2/H3 belong to the same import as the output.
- A large-file probe demonstrates bounded memory across upload, parse, fetch,
  normalization, and store—not just inside the Go decoder.
- Parser selection is explicit and stored as run provenance.
- Repair events and lossy severity are queryable from the operator UI/API.
- Test/design data is wiped and re-ingested from immutable originals only after
  these conditions hold, consistent with the owner's 2026-08-02 ruling.

## Final recommendation

Keep all four pieces, but change their authority:

- **SBV:** isolated, import-scoped SMS/MMS/call extraction and independent
  H1/H2/H3 computation; no longer a persistent corpus source for ingestion.
- **Python SMS parser:** reference/fallback implementation and conformance oracle
  until SBV proves parity; then retain it as an independently implemented backup.
- **ChatMiner:** first-class AI-chat format library behind the platform contract;
  its hashes are fingerprints, and its higher-level outputs are derived candidates.
- **Repair layer:** shared structural recovery infrastructure, adopted one parser
  at a time only after ledger and reconciliation wiring exists.

This topology preserves the useful upstream capabilities without allowing an
upstream service's persistence model, API limitations, or silent per-record
failures to determine the platform's evidence truth.
