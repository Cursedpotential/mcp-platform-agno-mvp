# ADR-0049: SBV is the universal parsing system — all transcripts, all parsing, mostly Go, repair reachable, SBV GUI retained

- Status: ~~**PROPOSED** — owner stated the target 2026-08-10; this ADR writes down the gap between
  that target and the code. **No port starts until this is signed.**~~ **ACCEPTED with amendment.
  Amended 2026-08-12 (owner rulings; DECISION_LOG D-049/D-051):** the universal-parser DIRECTION
  stands, but the parse step is **engine-DYNAMIC** — Go (SBV) OR Python (chatminer registry) with
  explicit `--engine`/`--format` override; it is NOT dedicated to either. Code shipped: `2605fa5`
  (engine-dynamic parse), `57ec156` (detection router, Go-primary), `4accbf2` (first SBV AI-chat
  decoder). The "**mostly** Go" reading is amended: Go-primary *via the detection router*, Python
  remains a first-class engine. The 4 gaps below (repair engine in Go, Go AI-chat decoders,
  two detection registries, GUI surface) still stand.
- Date: 2026-08-10
- _Byline: Claude Code · Opus 5 · 2026-08-10 (drift-fix 2026-08-12 Claude Code · Kimi K3:
  status amended PROPOSED → ACCEPTED-with-amendment per D-049/D-051)_
- Extends ADR-0048 (which established the Go engine as the ingestor core). Where ADR-0048 said
  "every future *evidence* format is a decoder module," this ADR widens the target to **all
  parsing** and names what is missing.

## 2026-08-29 supersession boundary — ADR-0061

> _Correction: Codex · GPT-5 · 2026-08-29. The dated analysis below is retained visibly; this
> section states which application-shape and authority conclusions no longer govern._

**Status: accepted historical direction, amended in 2026-08-12, and superseded in part by
ADR-0061.** The common Go-selected parser contract survives. The "single all-encompassing SBV app,"
SBV-owned GUI/storage/auth/hashing, and permanent Python-orchestrator conclusions do not.

Current authority is:

1. Workbench owns the unified shell, verified operator context, and authentication boundary. The
   storage-free SBV client is the composed message/pipeline-preview presentation and owns no canonical
   state.
2. The Go coordinator selects one registered parser by declared coverage and quality. Go-native and
   governed `platform-tools` implementations share that contract; Python does not independently choose
   the destination or permanently orchestrate the platform. Temporal durably schedules load-bearing
   activities, and n8n supplies bounded visual integration/agent workflow bodies and signals.
3. UIW context-source/raw-record/raw-generation fingerprints occur before parsing for integrity and
   reproducibility. They are not evidence H1/H2/H3. At governed promotion, custody verification dispatches
   only on the exact algorithm, hash level, canonical byte recipe, ordered membership, construction tag,
   and writer/version tuple. The platform promotion H3 is
   `h3-chain-h1genesis-hexconcat-v1`; an SBV empty-genesis/newline import receipt is never interchangeable.
4. SBV's current streaming MMS decoder iterates every part. The current platform gap is the parse-only
   attachment boundary: there is no immutable platform attachment sink/locator, so the adapter advertises
   `SupportsAttachments: false` and rejects attachment-bearing records. Historical SQLite remains a lossy
   migration source and is not canonical.
5. Preview reads and decisions require UIW-native, correlation-aware platform APIs keyed by the UIW
   workflow/source/run identities. UIW identifiers must never be passed to legacy `/v1/records` or legacy
   run-event SSE endpoints as though those namespaces were interchangeable.

The remainder of this ADR is the contemporaneous 2026-08-10/12 rationale and gap inventory. It is useful
history, but its superseded all-in-one application and authority statements are not implementation orders.

## Context

Owner statement, 2026-08-10, verbatim:

> "sbv is supposed to be the universal parsing system / rewritten in Go / adapted for all parsing /
> with repair and hashing"

That is the target. The code does not meet it yet. ADR-0048 is easy to misread as "done" because
its engine half genuinely shipped in PR #18 (`aacf21c`, 2026-08-06) — but the engine covers
**messaging and email only**, and the repair layer it is credited with is not in Go at all.

This ADR exists so the gap is written down once, in a citable place, instead of being rediscovered
by each new agent. A `/smart-explore` pass on 2026-08-10 was already misled twice by stale claims
in this area.

## Current state (verified 2026-08-10, not inherited from a prior report)

| Capability | Go (`vendored/sbv/internal/`) | Python (`server/tools/`) |
|---|---|---|
| Detection / routing | ✓ `DetectImporter` priority registry (`importer.go:180`) | ✓ **separate** registry — `@register` + capability (`registry.py:57`) |
| Messaging + email decoders | ✓ **12** registered | ✓ 9 — **duplicate coverage** |
| AI-chat decoders | ✗ **zero** | ✓ 11 (`parsers/ai_chat/`) |
| Generic / blob fallback | ✗ | ✓ 2 (`parsers/generic/`) |
| Custody hashing H1/H2/H3 | ✓ `custody.go` (`HashFileH1`, `HashRecordH2`, `ChainH3`) | partial — own H1 + reconcile against SBV |
| **Repair layer** | ✗ **none** | ✓ **full** — `detect`, `chunkers`, `engines`, `pdf`, `quarantine`, `encoding`, `cloud` |

The 12 registered Go decoders: `mbox`, `eml`, `facebook_json`, `google_chat`, `google_voice_html`,
`messaging_csv`, `imessage_html`, `facebook_html`, `imessage_txt`, `transcript`, `ndjson`,
`sms_xml`.

**Correction to ADR-0048:** its "Alternatives considered" section rejects a second Go binary on the
grounds that the merged SBV engine "already provides streaming core, custody hashing, storage,
dedup, reconciliation, **and a repair lane**." The repair lane claim is **false**. Repair lives in
Python at `server/tools/repair/`. The only repair-shaped code in Go is a narrow reversible mojibake
fix inside one importer (`facebook_json_importer.go:610`). The rejection still stands on the other
four grounds; only the repair claim is wrong.

## Decision (proposed)

**SBV becomes the single all-encompassing parsing application — based mostly in Go** — handling
**all transcripts and all parsing**: messaging, email, AI chats, documents, and whatever comes
next, behind one detection registry with custody hashing.

**"Mostly Go" is deliberate, and the repair engine may stay Python.** Owner, 2026-08-10:

> "if the repair engine can be called on and utilized inside of the go application and still be
> python then it's fine"

So repair needs a **call seam**, not a rewrite. What matters is that the Go app invokes repair as
part of its own pipeline and records the repair events in the same ledger. Implementation language
is not the requirement — reachability and governance are.

**It stays the SBV *app*, with its functional GUI — not a headless library.** Owner, 2026-08-10:
"it's supposed to be modelled after the SBV app with the functional GUI / remember it's a fork of
sorts." The deliverable is the running application, extended; a decoder that parses correctly but
never appears in the UI is not done.

Python keeps orchestration (Agno/AgentOS), workflow gating, and the evidence/context lane policy.
Python stops being a second parsing implementation.

### Fork and app-shape constraints (verified 2026-08-10)

- **It is a fork, vendored as a git subtree** at `vendored/sbv/`, Go module
  `github.com/lowcarbdev/sbv`. History shows subtree squashes plus a real upstream sync
  (`b3c2d1e`, 12 upstream commits). `UPSTREAM.md` tracks the relationship.
- **Remote naming is a trap — do not guess.** `sbv-real` → `lowcarbdev/sbv` (the true upstream).
  `sbv-fork` **and** `sbv-upstream` both → `Cursedpotential/sbv-forensic` (our fork). A future
  agent reading "sbv-upstream" as upstream will pull the fork.
- **Full stack, both halves in scope:** Go backend (`main.go`, `internal/`, `backend/`) and a
  Vite/React frontend (`frontend/` — `package.json`, `vite.config.js`, `src/`).
- **Every new decoder owes GUI surface**, not just an API route: import visible in the run/progress
  view, records browsable and searchable, custody hashes inspectable. This is what the fork already
  does for SMS/MMS.
- **Fork discipline holds.** Changes must stay rebasable onto `lowcarbdev/sbv`; the in-app docs
  (`SPEC.md`, `CUSTODY.md`, `UNIVERSAL_IMPORTS.md`, `DEVELOPMENT.md`) are part of the deliverable
  and drift the same way repo docs do.

## What decides Go vs Python (owner, 2026-08-10)

The split is **not** a language preference. Two owner statements set the rule:

> "go is critical for files that could blow out a memory store if not handled correctly"

> "it can have python features if they function as part of the app and can be called on both by
> the app in a workflow and by API atomically"

**The criterion: Go owns anything that must ingest unbounded input.** If a component can be handed
a multi-GB file and has to survive it, it belongs in Go with real streaming. Everything else may
stay Python.

**The Python contract — dual invocation.** A Python component qualifies only if it is callable
**both** ways:

1. **In a workflow** — as a step the app drives end to end.
2. **Atomically over the API** — one call, one job, standalone, no workflow required.

A Python helper reachable only from inside a workflow does not meet the bar.

### Verified against the criterion, 2026-08-10 — this inverts the priority

**The repair layer already complies.** It streams throughout (38 streaming constructs), and
`repair/encoding.py:5` states the rule outright: *"There is exactly one rule in this module: never
call `path.read_text()`."* Repair is not the memory risk.

**The parsers are the memory risk.** Nine Python parsers load whole files into memory:

| Parser | Site |
|---|---|
| `sms_xml` (malformed-XML fallback) | `messaging/sms_xml.py:294` |
| `claude_ai_export` | `ai_chat/claude_ai_export.py:28` |
| `facebook_messenger_html` | `messaging/facebook_messenger_html.py:132` (BeautifulSoup, whole file) |
| `facebook_messenger_json` | `messaging/facebook_messenger_json.py:134` |
| `imessage_html` | `messaging/imessage_html.py:399` (BeautifulSoup, whole file) |
| `imessage_txt` | `messaging/imessage_txt.py:479` |
| `messaging_csv` | `messaging/messaging_csv.py:184` |
| `messaging_transcript` | `messaging/messaging_transcript.py:69` |
| `whole_file_fallback` | `generic/whole_file_fallback.py:34` |

The codebase already names the hazard. `sms_xml.py:252-255`: the malformed-XML fallback *"calls
`path.read_text()` on the whole file, which is exactly what streaming exists to avoid … rather than
silently ballooning to multi-GB."*

### The memory-safety job is mostly ROUTING, not new decoders (verified 2026-08-10)

**Seven of those nine risky parsers already have a streaming Go decoder.** Every Go decoder takes
`Run(sink ImportSink, r *bufio.Reader)` — all 12 confirmed. The only `io.ReadAll` calls in the
engine are on a **bounded** `limited` reader, which is the safe pattern.

| Risky Python parser (whole-file) | Go decoder that already exists | Go detection |
|---|---|---|
| `sms_xml.py:294` | `smsXMLImporter` | `.xml` + `<smses`/`<calls` |
| `facebook_messenger_json.py:134` | `facebookJSONImporter` | `.json` + `"participants"` |
| `facebook_messenger_html.py:132` | `facebookHTMLImporter` | html + `_a6-g`/`_a6-h` |
| `imessage_html.py:399` | `imessageHTMLImporter` | html + `class="message"` + sent/received |
| `imessage_txt.py:479` | `imessageTXTImporter` | `.txt` + `imessageHeaderRE` |
| `messaging_csv.py:184` | `messagingCSVImporter` | `.csv` + header sniff |
| `messaging_transcript.py:69` | `transcriptImporter` | `.txt`/`.csv` + `transcriptMarkerRE` |
| `claude_ai_export.py:28` | **none** | — |
| `whole_file_fallback.py:34` | **none** | — |

**So Gap 1 and Gap 3 are the same problem.** The safe Go decoders exist, but the Python registry
resolves format independently, so the whole-file Python path still gets selected. Fixing the
routing fixes the memory risk for seven of nine — no new decoder needed.

**Only two need real work:** `claude_ai_export` (a genuinely new AI-chat decoder) and
`whole_file_fallback` (which is already DEBT item 0 — ADR-0044 bans it from evidence and the ban is
unenforced; a routing fix may close both at once).

**Routing does not retire the Python fallbacks — they still have to be fixed.** Owner, 2026-08-10:
the Python SMS parser "is supposed to be iterative and it's supposed to write directly to a file
and not into memory … even though it's a backup." A fallback that exhausts memory is not a real
fallback. Tracked as **DEBT item 0b**, which also records the contract wrinkle: spilling to a file
changes the atomic tool's output shape, and per the dual-invocation rule both the workflow caller
and the API caller must handle it.

**Consequence for sequencing:** the repair call seam is an integration job, not a rescue. The
memory-safety work is mostly re-pointing routing at decoders that already stream, plus two new
pieces — far smaller than "port nine parsers to Go."

## The gap — four items, none of them Takeout

**Gap 1 — the Go app cannot call the repair engine.** ~~Port repair to Go.~~ **Corrected
2026-08-10 by owner: a port is NOT required.** The repair engine may remain Python. The actual gap
is that **no call seam exists** — `server/tools/repair/` is invoked only from the Python workflow,
and nothing in `vendored/sbv/internal/` reaches it. Today a file imported through the SBV app gets
no repair pass at all.

What this needs is an integration decision, not a rewrite: how the Go engine calls out to Python
repair mid-stream (subprocess, local HTTP service, sidecar), how repair events flow back into the
import ledger and custody record, and what happens when repair is unavailable. Keeping repair in
Python preserves the libraries it depends on — `lxml recover=True`, `ijson`, `json-repair`,
CleverCSV, QPDF — which was the main cost of a port.

**Gap 2 — no AI-chat decoders in Go.** Eleven Python parsers have no Go counterpart:
`chatgpt_official`, `chatgpt_share`, `claude_ai_export`, `claude_code`, `claude_code_jsonl`,
`claude_md`, `gemini_chrome`, `gemini_json`, `perplexity_gdpr`, `perplexity_md`,
`perplexity_plugin`. **This collides with ADR-0044**, which bars AI chats from the evidence schema.
Routing them through the custody engine is not automatically the same as promoting them to
evidence — but the boundary has to be restated explicitly before any port, or the ADR-0044 ban
becomes ambiguous.

**Gap 3 — two detection systems run in parallel.** Go `DetectImporter` and Python
`registry.resolve()` each decide format independently, and messaging is covered by both. Until one
is authoritative, "which parser ran?" has two possible answers. Retirement of the duplicate Python
messaging parsers is a mining exercise, not a delete — several carry forensic guarantees earned
the hard way (bodyless-MMS retention, outbound roles 2/4/5/6).

**Gap 4 — everything parsed in Python is invisible to the GUI.** The SBV frontend shows what the
Go engine imported. The 11 AI-chat parsers, the whole repair layer, and the Python messaging
parsers produce records the app cannot display, browse, or hash-inspect. Each port item therefore
carries a frontend slice, and "ported" without GUI surface does not count as done.

## Explicitly OUT of scope

- **Google Timeline / location JSON — PARKED** by owner directive (2026-07-03, restated
  2026-08-09 and 2026-08-10). `internal/google_timeline_importer.go` does not exist and must not be
  proposed until the owner raises it.
- **New Google Takeout work generally — parked.** Note the precise boundary: Takeout decoders that
  **already ship** stay live and are not being un-shipped — `google_chat` emits
  `format = "takeout-messages-json"` (`google_chat_importer.go:212`), and `google_voice_html` and
  `mbox` are registered. Parking applies to *remaining* Takeout work, chiefly Timeline.
- None of the four gaps above is Timeline or Takeout work.
- **Rewriting the repair engine in Go** — explicitly ruled out by the owner 2026-08-10. Python is
  fine provided the Go app can call it.

## Open questions (blocking sign-off)

1. **ADR-0044 boundary.** If AI chats parse through the Go custody engine, does the
   evidence-schema ban still hold on the storage side alone? Owner ruling needed.
2. **Sequencing — three candidates, and the memory one may outrank the rest.** (a) Move the nine
   whole-file parsers behind Go streaming decoders, closing the "blow out a memory store" risk;
   (b) build the repair call seam; (c) close AI-chat/transcript coverage. (a) is the only one that
   is currently a live failure mode rather than a missing feature.
3. **Duplicate messaging parsers.** Retire the Python nine after Go parity is proven, or keep them
   as a comparison lane the way SBV itself was kept during its demotion?
4. **Repair call mechanism.** How does the Go app invoke Python repair — subprocess per file, a
   long-running local HTTP service, or a sidecar container? Each differs on latency, streaming
   support, deployment complexity, and what happens when repair is down (fail the import, or
   import unrepaired and flag it?).
5. **GUI depth per format.** Does every format need the full SMS/MMS treatment (thread browse,
   search, media, custody inspect), or a generic record view first with format-specific views
   added later?
6. **Fork divergence budget.** How far may the fork drift from `lowcarbdev/sbv` before upstream
   syncs stop being practical? A universal parser plus a repair layer is a large addition to a
   stock SMS viewer.
7. **Dual-invocation contract — retroactive or forward-only?** Every Python component must be
   callable both in a workflow and atomically over the API. Do the existing Python tools have to
   be audited and brought up to that bar now, or does it bind only new work?

## Consequences

- One parsing implementation, one detection registry, one custody chain — the "which parser ran?"
  ambiguity disappears.
- Every format gains repair and hashing for free, including AI chats and documents.
- Cost is real, but **smaller than a full port**: repair stays Python, so the bulk of the work is
  the call seam, the AI-chat/transcript decoders, and the GUI slices. Forensic guarantees pinned by
  Python tests must be re-pinned wherever their parser moves.
- A cross-language call seam is a new operational dependency: the Go app now needs Python repair
  present and healthy, which is a deployment and failure-mode concern the current split avoids.
- Until signed, **ADR-0048 remains the operative statement** and SBV stays a messaging/email
  engine. Nothing here authorises code changes.

## Alternatives considered

- **Leave the split as-is** (Go = evidence messaging, Python = everything else) — rejected by the
  owner's 2026-08-10 statement; also leaves AI chats permanently without custody hashing, and
  leaves SBV-imported files with no repair pass at all.
- ~~**Port the parsers but leave repair in Python** — rejected: a Go parser calling back into
  Python for repair reintroduces the two-system problem.~~ **REVERSED 2026-08-10 by the owner:
  this is the chosen approach.** "if the repair engine can be called on and utilized inside of the
  go application and still be python then it's fine." The two-system objection does not apply —
  one *application* owns the pipeline, and repair is a called component inside it.
- **Rewrite the repair engine in Go** — rejected by the owner 2026-08-10; also discards the
  mature Python repair libraries for no functional gain.
- **Rewrite parsing in Python instead of Go** — rejected: discards a shipped, tested Go engine with
  custody hashing already in it, and abandons the SBV app the GUI is modelled on.
