# server/evidence/ — the evidence spine

> _Byline: Claude Code · 2026-07-27; navigation refresh by Codex · GPT-5.6-Sol · 2026-08-29._

> Nested map. Parent: `../AGENTS.md`. Root: `../../AGENTS.md`.

## What's here

The Part-1 spine: chain-of-custody ingest → normalize → store → named workflows.
Since ADR-0035, `evidence/` is purely the evidence bounded context — the tool
registry (`tools/`) and the G4 gateway (`tool_finder/`) both moved out to
`server/tools/` (see `../tools/AGENTS.md`).

| File | Role |
|---|---|
| `custody.py` | THE single entry gate. `ingest_artifact()`: sha256 (H1) → dedupe → write-once blob → append-only `evidence` schema row. Also cross-checks SBV's independently-derived H1/H2/H3 chain hashes (`verify_sbv_import`). **The ONLY writer of the `evidence` schema.** H1/H2/H3 hashing happens BEFORE normalize — custody is upstream of everything. |
| `normalize.py` | **Deprecated re-export shim** (ADR-0035) — `from server.contracts.records import *`. Do not add new code here; import `server.contracts.records` directly. Kept for stragglers, nothing deleted. |
| `store.py` | Persists normalized records to `working.normalized_record` + feeds the knowledge engine (Weaviate `Platform_knowledge`, ADR-0040, domain-tagged). |
| `workflows.py` | Named, custody-gated workflows on native `agno.workflow` (`chat-transcript`, `sms-xml`). Each parse step resolves the best-fit tool from `server.tools.registry` by capability, with automatic substitution on rejection. |
| `cli.py` | `uv run python -m server.evidence ...` — `import`, `tools`, `workflows`, `verify`. |
| `config/` | Evidence-domain config. |

## Invariants

- Evidence is immutable and append-only: `custody.py` is the only writer of the
  `evidence` schema. Everything derived lands in `analysis` or the knowledge engine.
- `knowledge_time` remains row-write audit time. Governed horizon availability is computed through
  `working.source_available_from(record_id)` and must be enforced before retrieval; never use
  `knowledge_time` as the horizon predicate.
- Agent DB connections ride the read-only engine (ADR-0005) — sub-agents physically
  cannot write to `evidence`, enforced at the connection level, not by convention.
- `server/evidence/__init__.py` uses lazy (PEP 562) exports so light consumers (the
  tools-facade container) can use `registry`/`ToolRegistry` (re-exported from
  `server.tools.registry` for back-compat) without dragging in sqlalchemy/agno.

## Relevant ADRs

- ADR-0018 — bitemporal evidence memory + disclosure-tier
- ADR-0033 — `server/` repack (this package's current home)
- ADR-0035 — tool registry + gateway extracted out; record contract moved to
  `server/contracts/records.py` (`normalize.py` shim explains why — read it, don't
  restate it here)

---

> _Sprint-mode policy REMOVED 2026-08-25 on owner order ("you're grounded — remove it entirely"). Confirm-and-discuss-before-changing is back in force._

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
   belong to the workflow (`modules/engine/uiw`) and to n8n's visual flow — never
   buried inside a parser, decoder, chunker, or repository method.
7. **New capability = new Activity, registered in the stage graph.** Do not widen an
   existing Activity to cover a second concern because it is convenient.

The test before adding or editing anything here: *could this be scheduled on its own,
retried, wrapped as an n8n node, and reasoned about in isolation?* If not, it is not
finished.

