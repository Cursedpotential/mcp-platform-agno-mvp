# server/evidence/ — the evidence spine

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
