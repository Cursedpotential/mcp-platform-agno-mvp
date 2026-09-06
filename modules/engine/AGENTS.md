# modules/engine — the Go engine

> _Byline: Claude Code · Opus 5 · 2026-09-02 (created; this directory had no AGENTS.md,
> only AGENT_MEMORY.md — the atomicity rule below is why that gap mattered)._
> drift-fix 2026-09-06 Claude Code · Sonnet 5.1: D-137..D-141 rename applied in this
> module — package `uiw` -> `proffer`, `uiwworker` -> `profferworker`,
> `UniversalImportWorkflow` -> `ProfferWorkflow`, task queue `universal-import-v1` ->
> `proffer-v1`, module path -> `github.com/Cursedpotential/probata/engine`. The n8n
> webhook path segments and `N8N_UNIVERSAL_IMPORT_*` env var names are UNCHANGED
> pending a coordinated rename with the deploy/n8n lane (see
> docs/reviews/ for the day's rename report)._

This module owns custody hashing, acquisition, format decoding, parsing, chunking,
normalization, and the Proffer (formerly UIW / Universal Import Workflow) stage graph. It is its own Go
module (`go.mod` here, not at the repo root) — build and test from this directory:

```bash
go build ./...   # from modules/engine/
go vet ./...
go test ./...
```

## Package map

| Package | Owns |
|---|---|
| `acquisition/` | sealing source objects; the scheme router (`file://`, `upload://`, `r2://`, `b2://`) |
| `parser/` | the parser contract + registry; one adapter selected by declared coverage |
| `adapters/` | concrete parser adapters over the decoder library |
| `chunk/` | deterministic document-markdown chunking (separate from parsing by ruling) |
| `normalize/` | normalized-record production |
| `stagegraph/` | the 26 Proffer stages and their dependency edges |
| `proffer/` | the Temporal workflow: sequencing, gates, signals, queries |
| `profferworker/` | worker wiring — where resolvers and repositories are constructed |
| `activities/` | Activity bodies |
| `postgres/` | repositories; the schema admission probe |
| `runtimeapi/` | HTTP surfaces and filesystem boundaries |

## Boundaries that are rulings, not preferences

- **Custody hashing never moves.** It stays in Go, computed over raw bytes before any
  decoding or normalization (H1 -> H2 -> H3 -> only then normalize). `pg_duckdb`
  transforms; it never writes custody.
- **Parsing and chunking are separate stages, not two halves of one.** Already-
  normalized text (markdown, plain text, AI work products) routes straight to
  `chunk/` with no parse step.
- **The API boundary admits only `upload://` and `r2://`.** `file://` exists for
  internal sealed refs. Wire every scheme through `acquisition.NewSchemeRouter` — a
  resolver registered directly is the defect that blocked all ingest until
  2026-09-02 (`docs/reviews/2026-09-02-uiw-rehearsal-acquisition-seam.md`; historical filename, predates the D-140 proffer rename).

## ATOMICITY — every unit must be assignable to a Temporal Activity

> _Owner directive · 2026-09-02. Binding on every directory below this file.
> Reinforces the 2026-08-25 boundary ruling, ADR-0061, and D-077._

**Write every unit of work so it can be handed to one Temporal Activity, and never
conflate multiple processes into one unit.**

Owner, 2026-09-02: *"Everything needs to be modular so that it can be assigned to
Temporal activities. We can't be conflating or mixing a bunch of processes into one.
Yes, the engine can call individual ones, but it's going to be calling the Activity
more likely than 99.9% of the time."* And: *"Or to be added into an n8n node which
gets run as an activity, however that shape looks."*

Rules, in force everywhere:

1. **One unit does one thing.** A parser parses and does nothing else (owner,
   2026-08-29: *"they parse, they do nothing more"*). A chunker chunks. A hasher
   hashes. If a function does two of those, it is wrong and must be split before it
   is wired to anything.
2. **Hashing is its own Activity family and is never folded into parsing, chunking,
   or normalization.** Custody hashing is separate machinery with its own boundary
   (D-077, four hash moments; see `docs/reference/HASH-TAXONOMY-2026-08-29.md`).
3. **The Activity is the normal caller.** Direct in-process calls stay legitimate —
   but the overwhelmingly common path is invocation *as*, or from *within*, a
   Temporal Activity. Design signatures for that: bounded inputs, bounded outputs,
   no ambient state, no hidden I/O, deterministic given its inputs, safely
   retryable. An Activity may be retried; anything that breaks on a second identical
   call is a defect.
4. **Three call shapes, one unit.** The same unit must serve all of them without
   knowing which is in play: (a) called directly in-process; (b) invoked as a
   Temporal Activity; (c) **wrapped as an n8n node that is itself executed as, or
   from within, an Activity.** n8n owns the visual flow, Temporal owns durability,
   the unit owns one job. A unit that needs to know its caller has a boundary
   violation in it.
5. **Pass references, never payloads.** Source bytes and bundles move by locator
   (`upload://`, `r2://`, sealed `file://`), never through Temporal history, an n8n
   payload, or a PostgreSQL activity request.
6. **No orchestration inside a unit.** Sequencing, fan-out, retries, and human gates
   belong to the workflow (`modules/engine/proffer`) and to n8n's visual flow — never
   buried inside a parser, decoder, chunker, or repository method.
7. **New capability = new Activity, registered in the stage graph.** Do not widen an
   existing Activity to cover a second concern because it is convenient.

The test before adding or editing anything here: *could this be scheduled on its own,
retried, wrapped as an n8n node, and reasoned about in isolation?* If not, it is not
finished.

