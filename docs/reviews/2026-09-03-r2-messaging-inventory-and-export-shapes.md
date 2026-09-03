# R2 messaging inventory + export-shape research

> _Byline: Claude Code · Opus 5 · 2026-09-03._
>
> Owner authorized an R2 scan and public-docs research while case data was being
> prepared ("anything in R2 you can check away… find what you can"). This is a
> **listing-only** inventory — `rclone lsf --fast-list --files-only`, no
> downloads, no hashing (Class-B ops only, per the cost-aware transfer rule and
> the `CBCAT_NO_HASH` lesson that MD5-ing the corpus takes ~8 hours).

## What is in `r2:casebible-sorted`

**345,273 files · 1,183 GB** (complete listing, zero errors).

| Source signal | Files | Size |
|---|---:|---:|
| takeout | 79,255 | 583.2 GB |
| facebook / messenger | 49,603 | 33.9 GB |
| google-voice | 7,660 | 0.13 GB |
| snapchat | 2,528 | 0.91 GB |
| sms / mms | 1,130 | 85.8 GB |
| imessage / chat.db | 1,083 | 1.84 GB |
| whatsapp | 63 | 0.01 GB |

`r2:casebible-raw` was still enumerating at 182,000+ files when this was written.

## Parser coverage against what actually exists

| Source | Native export present | Screenshots / media | Parser |
|---|---|---|---|
| **Google Voice** | **7,006 `.html`** (15.2 MB) + 240 audio (`mp3`/`m4a`/`wav`) | 258 img | ✅ `google_voice_html` — **registered, zero blockers** |
| Facebook / Messenger | 49,603 files | — | ✅ `facebook_messenger_html` / `_json` |
| SMS / MMS | 1,130 files | — | ✅ `sms_xml`, `sbv_sms` |
| iMessage | 1,083 files | — | ✅ `imessage_txt` / `_html` / `_pdf` |
| **Snapchat** | **492 `.html` + 129 `.json`** = 621 | **1,852 img** + 41 `mp4` | ❌ **none** |
| **WhatsApp** | **6 `.txt` + 7 `.zip`** | 39 img | ❌ none for native `_chat.txt` |

### The immediate target is Google Voice

**7,006 HTML conversation files with a registered parser and no missing
dependency.** Nothing needs writing; it needs the tool gateway deployed and
then it can run. It is also evidentially strong: Google Voice Takeout emits
structured microformat markup (`<abbr class="dt" title="ISO-8601">` for
timestamps, `<cite><a class="tel">` for participants), so it parses precisely
rather than heuristically — and the 240 voicemail audio files come with
Google-generated transcripts, i.e. third-party-produced content rather than
device-produced.

### Snapchat has BOTH lanes, and they are not redundant

621 native export files **and** 1,852 screenshots. Those are not duplicates of
each other — see the export limitation below. The screenshots very likely
contain material the exports structurally cannot.

## Export-shape research (public docs; no case files opened)

### Snapchat — the export is incomplete BY DESIGN

`chat_history.json` + `chat_history.html` inside a ZIP, carrying sender names,
UTC timestamps, and message text; saved media lands in a separate `chat_media/`
folder.

**Only messages a participant explicitly SAVED (tap-and-hold) appear in the
export. Unsaved messages are never exported, and sent images/video/voice are
never exported at all.**

Two consequences, one technical and one evidentiary:

- Screenshots are not corroboration for Snapchat, they are frequently **the only
  record that will ever exist**. The OCR lane is the primary path for this
  source, not a fallback.
- **Absence from a Snapchat export proves nothing.** An opposing argument of the
  form "it is not in the export, so it did not happen" is invalid on its face
  for this platform, and that should be stated wherever Snapchat material is
  presented.

### WhatsApp — the timestamp is locale-ambiguous

`_chat.txt`, one line per message: `[timestamp] Sender: message`.

**The bracketed timestamp is formatted by the exporting device's locale** —
`%d/%m/%Y` or `%m/%d/%Y`. So `03/09/2026` is either 9 March or 3 September.
Guessing silently corrupts a timeline, which is unacceptable for evidence. The
parser must either take a declared locale per source version, or disambiguate
from unambiguous dates elsewhere in the same file (any day > 12 settles it) and
**refuse** rather than guess when the whole file is ambiguous.

Three further parsing hazards, all of which produce silent data loss if ignored:

- multi-line messages: continuation lines carry **no** timestamp header
- a sender display name containing a colon breaks naive `split(':')` parsing
- system events (missed calls, group membership changes, encryption notices) are
  timestamped lines with **no sender**. A missed-call line is evidence of a
  contact attempt, not noise — it must be retained, not discarded (D-136:
  extract everything).

Note the interaction with the fidelity digest: it seals the source's timestamp
**string verbatim**, so sealing is unaffected by the locale ambiguity. Deriving
`occurred_at` is what needs the locale resolved.

## Buildable now vs blocked

Buildable with no owner input:

1. Snapchat native export parser (`chat_history.json` / `.html`) — 621 files waiting
2. WhatsApp `_chat.txt` parser with declared/derived locale and refuse-on-ambiguous
3. Wiring `engine/fidelity` into normalization and promotion
4. Participant → `entity_mention` → `entity_resolution` → `id_xref` wiring

Blocked on the owner:

- **Tool gateway deployment** — needs a tagged Tailscale auth key minted and the
  shared materialize mount added to platform-tools. This blocks ALL 23 existing
  parsers from being callable as Activities, including the 7,006 Google Voice
  files that need no new code.
- OCR/VLM provider selection for ADR-0053 rung 3 (credential-gated, never
  benchmarked — G-19).

## Method note

The inventory used DuckDB over the raw `rclone lsf` output rather than
row-at-a-time iteration, per the repo's scan-tooling preference. Listing files
are in the session scratchpad, not committed — they are regenerable and contain
case-corpus paths.
