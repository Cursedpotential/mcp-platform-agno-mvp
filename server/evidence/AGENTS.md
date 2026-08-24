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
| `cli.py` | `python -m server.evidence ...` — `import`, `tools`, `workflows`, `verify`. |
| `config/` | Evidence-domain config. |

## Invariants

- Evidence is immutable and append-only: `custody.py` is the only writer of the
  `evidence` schema. Everything derived lands in `analysis` or the knowledge engine.
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

<!-- live-testing-policy:start -->
## Testing & Deployment Policy — LIVE ONLY, SPRINT MODE

> _Owner directive 2026-08-20 · recorded by Claude Code · Opus 5._
> _Supersedes any prior testing, staging, or change-approval guidance in this file._

- **Sprint mode is the default.** Bias to action. Ship the smallest working increment now,
  verify it live, keep moving. Do not stall on approval gates for routine work.
- **All testing is live testing.** Verify against the real deployed service, real data, real
  endpoints. A proxy signal is not verification.
- **No out-of-band testing.** No mocks, stubs, or synthetic fixtures standing in for a real
  dependency. A green unit test is not evidence the thing works.
- **No stubs. Write the whole function.** If it is a function, implement it fully. A stub is
  permitted ONLY when the real data or upstream service genuinely does not exist yet.
- **Any stub that must exist is marked LOUDLY and tracked.** Inline `# STUB:` / `// STUB:` at the
  site, plus an entry in `docs/URGENT-TODO.md`. A silent stub is a defect.
- **Ship and watch.** If it works, it stays up. If it breaks, fix it and put it back up.
  Breakage is the feedback loop, not a reason to stage.
- **On success, purge the test data.** Clear every row and artifact the live run created, then
  move on. Test data must never become canonical.
- **On failure, adjust in place and retry live.** Fix the real thing and run it again — never
  retreat to a mock, a staging copy, or a parallel instance to "prove" it.
- **No parallel stacks.** One live instance per service. No shadow deploys, no staging copies,
  no side-by-side `v2` beside `v1` — replace in place.
- **Fix forward.** Roll back only to restore service, never as a substitute for fixing the cause.
- **Mid-task feedback is QUEUED, not switched to.** If input arrives that is not about the task in
  flight, append it to `docs/URGENT-TODO.md` and keep going. Finish the current task; address the
  queued item at the point that work was already scheduled. Do not context-switch mid-task.

**Still stop and ask for:** destroying data, terminating/wiping a host, anything outward-facing
(publishing, sending, paying), and irreversible spend. Sprint mode removes ceremony, not judgment.
<!-- live-testing-policy:end -->
