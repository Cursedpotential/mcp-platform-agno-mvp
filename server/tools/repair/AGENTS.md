# server/tools/repair/ — streaming repair + structural chunking

> _Byline: Claude Code · Opus 5 (1M) · 2026-08-02_
>
> Nested map. Parent: `../AGENTS.md`. Root: `../../../AGENTS.md`.

## What's here

Damaged-input handling for every text format this corpus arrives in, plus
structural PDF repair. One router, several engines, one reporting contract.

```
types.py      Chunk / RepairEvent / RepairReport / Detection  (stdlib ONLY)
encoding.py   charset detection + STREAMING decode (never read_text)
detect.py     format routing from a bounded head read (content > extension)
chunkers.py   the structural iterators: xml / html / json / ndjson / csv / pdf
engines.py    format -> engine registry, availability probe, iter_chunks()
pdf.py        STRUCTURAL PDF repair via QPDF/pikepdf (rebuild the file itself)
quarantine.py damaged-file lifecycle: rewrite clean / flag / quarantine
```

## The four rules

1. **Never read a whole file.** Every path streams. `encoding.open_text()` is
   the only sanctioned text reader; it wraps a binary handle in an incremental
   decoder so memory stays flat regardless of file size. Measured: a 400 MiB
   XML peaks at **821 MiB** via `read_text()` and **28 MiB** via `iter_chunks()`.
2. **Never write over the original.** Repaired output always goes to a NEW
   path; `write_repaired()` and `repair_pdf()` both raise rather than overwrite
   their input, because the original bytes are the custody anchor (H1).
3. **Never repair silently.** Every fix is a `RepairEvent` carrying a severity.
   `lossy` means evidence could have been lost; gate on it.
4. **Never import a repair library at module scope.** See below.

## Damaged-file lifecycle (`quarantine.py`)

Owner directive 2026-08-02: *"Write a new repaired file and quarantine the
damaged file. Or at the very least flag it as damaged so that it doesn't
continue being parsed out."* Three escalating actions, safest default first:

| Action | Touches disk | Use |
|---|---|---|
| `flag_damaged()` | ledger only | **default.** Ingest calls `DamageLedger.should_skip()` and stops re-parsing a known-bad file every run |
| `write_repaired()` | writes a NEW file | streaming rewrite to a clean, re-parsable file |
| `quarantine_file()` | verified copy + ledger | opt-in, `dry_run=True` by default, manifest via `plan_quarantine()` first; original remains owner-controlled |

Quarantine is not the default because two standing rules constrain it: never
delete, and a full manifest precedes any copy job with approval explicit rather
than inferred. The verified copy is additive; the original remains in place
and the SHA-keyed ledger prevents re-ingestion until the owner decides its
final disposition.

The ledger is **keyed by sha256**, not path: paths move, content does not, so a
flagged artifact stays flagged across a reorganisation. It is append-only —
later entries supersede earlier ones on read, and history is never rewritten.
Default location `docs/reports/damaged-artifacts.jsonl` (gitignored; filenames
can carry PII).

## Severity taxonomy (the point of `types.py`)

| Severity | Meaning | Example |
|---|---|---|
| `cosmetic` | nothing informational changed | BOM stripped |
| `structural` | shape fixed, content preserved | tag auto-closed, ragged row padded |
| `lossy` | bytes discarded or reconstructed | control char removed, OCR output, repaired PDF |

Only `lossy` can cost evidence. A silent repair is indistinguishable from the
parser bug that dropped 516 body-less MMS: nothing raises, the counts just come
out smaller.

## Format → engine

| Format | Engine | Chunk | Notes |
|---|---|---|---|
| `xml` | lxml `recover=True` + `iterparse` | element subtree | recovers **while streaming** |
| `html` | lxml HTML parser | element subtree | recovering by design |
| `json` | ijson → json-repair fallback | array item | fallback capped at `JSON_REPAIR_MAX_BYTES` |
| `ndjson` | per-line | object | one bad line costs one line |
| `csv` | CleverCSV dialect + ragged repair | row | **never truncates**; extras go to `__overflow__` |
| `pdf` | `extract.text` tiered | page | see the PDF split below |
| `image` | Tesseract OCR | page | always lossy |

## ⚠ Function-local imports are mandatory

`registry.load_builtin_tools()` walks `server/tools/` **recursively** and
imports every module whose final path segment does not start with `_`. That
walk also runs inside the dep-light `docker/tools` facade, which mounts the
whole `server/` tree but installs almost none of its dependencies.

A module-level `import lxml` anywhere here would FATAL-loop the facade — the
same failure mode `../AGENTS.md` warns about for `server.contracts`, and which
the ADR-0033-era outage already paid for once.

So `available()` probes with `find_spec` (no execution) and `engine_for()`
returns `None` when a library is missing, turning "dependency absent" into a
routed, reportable state instead of a crash.

## ⚠ XML/HTML element lifetime

The yielded Element is valid **until the next iteration** — it is cleared and
unlinked as soon as the consumer asks for the next one. That is what keeps
memory flat. `list(iter_xml(...))` returns a list of *emptied* elements.

Copy what you need inside the loop (`dict(elem.attrib)`), or pass
`materialize=True` and accept the memory cost.

## PDF: repair and extraction are different problems

- **`pdf.py` — repair.** The file does not open: damaged cross-reference table,
  missing trailer, truncated tail. QPDF rebuilds the xref by scanning for
  object markers. Nothing can extract until this succeeds.
- **`../extractors/extract_text.py` — extraction.** The file already opens;
  pull text out of it (native pypdf/pdfplumber → Tesseract OCR).

`inspect_pdf()` is read-only triage returning `healthy` / `reconstructed` /
`encrypted` / `unrecoverable`. **`reconstructed` is the dangerous status**: the
file opens fine in any reader, so it looks healthy while actually being damaged
— only `Pdf.get_warnings()` reveals it.

Two traps already paid for here:
- qpdf recovery is **not** on the `pikepdf` logger and **not** in Python's
  `warnings`. Both were tried and captured nothing. `Pdf.get_warnings()`, read
  *inside* the `with` block, is the only reliable source.
- Status must key on **any** warning, not a keyword allowlist. Gating on
  reconstruction keywords reported a file that made qpdf say "can't find PDF
  header" as `healthy`.

## Usage

```python
from server.tools.repair import detect, iter_chunks, RepairReport

report = RepairReport()
for chunk in iter_chunks(path, report=report):
    if chunk.ok:
        handle(chunk.node)
report.summary()          # funnel counters for the ingest ledger
```

```python
from server.tools.repair import inspect_pdf, repair_pdf

health = inspect_pdf(path)                      # read-only
if health.needs_repair:
    result = repair_pdf(path, dest)             # NEW file, never in place
    result.provenance()                         # -> custody ledger row
```

## Scripts

- `scripts/repair_smoke.py` — routing on real files, damage recovery, and a
  streaming proof that measures peak working set in child processes.
- `scripts/pdf_triage.py` — sweep a tree, classify every PDF, optionally repair
  the damaged ones into a separate output tree.

## How to add an engine

1. Write the iterator in `chunkers.py`, yielding `Chunk` objects. Third-party
   imports go **inside** the function.
2. Add an `EngineSpec` to `ENGINES` in `engines.py`. Use `requires` for
   all-of dependencies, `any_of` when one of several will do.
3. Add the signature to `detect.py` (`_BINARY_SIGS` or `_classify`).
4. That is all — `iter_chunks()` routes by format automatically.
