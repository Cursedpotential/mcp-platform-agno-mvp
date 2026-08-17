# HANDOFF — R14 Phase-1 Surreal Live Core Pass (2026-08-17)

> _Byline: Codex · GPT-5 · 2026-08-17_

STATUS: CORE LIVE GATES PASS; FULL R13 GATE SET PARTIAL; TARGET STOPPED
BUILD_STATUS: 20 ISOLATED TESTS PASS; FOCUSED RUFF PASS; FULL REPOSITORY SUITE NOT RERUN

## Answer first

The named synthetic target `data-surreal-phase1-t0-r1` produced a real one-shot `PASS` report on
commit `ed55a75` and was then stopped through Coolify. Host Docker truth after the stop was zero
running and zero exited containers for compose project `hastprr4a99tvpdi4c2k8i36`. The isolated
network, active terminally quarantined RocksDB state, and two earlier quarantined states remain
preserved. Nothing was deleted.

This is a **core-gate pass, not full Phase-1 completion**. R13 also requires live sealed-snapshot,
linked-rewalk, and export/import parity gates. Those are represented in schema or local contracts
but are not implemented or reported by the live runner. Do not claim that they passed.

Every R9 hold remains active. No real corpus, parked Surreal deployment, PostgreSQL migration,
production Horizon route, production agent, or Graphiti replacement was touched.

## Live report evidence

| Field | Observed value |
|---|---|
| Runner exit | `0` |
| Report status | `PASS` |
| Server / SDK | SurrealDB `3.2.3` / Python SDK `2.0.0` |
| Manifest hash | `sha256:422921d66a4164a4c14dbfdb27a584557b296c0d7782178a46111b0146317089` |
| Membership hash | `sha256:0eb54f32c7d54ffc5e73e60cfc523978ec4c805818b9f2928f1756f2de67bf95` |
| Content hash | `sha256:f0c8e4bb483ffc32ca0094f0719229bae425204cfaaf6c7cd2a1308f8a1357f8` |
| Reconciled hash | `sha256:461c7cdb51c54445d8a446ad673658971d379812812ff99f3e48476776fd277c` |
| Synthetic object count | `8` |
| Duration | `954.82 ms` |

The following live gates were true:

- early as-lived exact match: `safe-contemporaneous-a`, `safe-contemporaneous-b`;
- late as-lived positive control: `future-occurring-canary`,
  `late-realized-old-source-canary`;
- hindsight positive control: `hindsight-only-canary`, `future-occurring-canary`;
- retrieval plan observed before ranking;
- forbidden auditor write left no `context:forbidden` record;
- terminal projection quarantine returned no as-lived results.

## Repairs completed

- `12da549` — retain only allowlisted structured Surreal denial metadata.
- `4b5d378` — authenticate the record JWT before the scoped `use` RPC. The live structured denial
  proved that pre-authentication `use` was rejected as a guest method.
- `ed55a75` — verify forbidden-write denial by database postcondition rather than exception shape.
  Surreal permissions returned an empty result for the denied create.
- Isolated runner suite advanced from 15 to **20 passing tests**; focused Ruff and `git diff
  --check` passed after each change.

## Preserved target state

- Active path: `/data/agno/experiments/phase1-surreal-t0-r1/t0_slice_r1.db`; contains the final
  core-PASS projection in terminal `quarantined` state.
- Preserved prior state:
  `/data/agno/experiments/phase1-surreal-t0-r1/quarantine/sealed-20260816-credential-rotated/`.
- Preserved failed core run:
  `/data/agno/experiments/phase1-surreal-t0-r1/quarantine/failed-20260817-negative-write-observation/`.
- Network `phase1-surreal-t0-r1` remains preserved and internal-only.
- Coolify app UUID remains `hastprr4a99tvpdi4c2k8i36` on `ovh-files`; restart only through
  Coolify and verify territory through host Docker state.

## Hook-launcher repair performed during resume

The repeated Claude Code `Access is denied (os error 5)` hooks were traced to `python`/`python3`
resolving to Microsoft WindowsApps aliases even though uv-managed Python exists. User settings,
the repository DB-write hook, and active/durable Claude Never Forgets, Hookify, and Bedrock hook
manifests were rebound to the verified uv-managed interpreter at
`C:/Users/matts/.local/bin/python3.exe` (repository-local hook uses `uv run python`). All eight JSON
files parse, and the six observed failure entry points smoke-tested successfully. Claude Code must
restart once to load the edited hook commands. No plugin was disabled or removed.

## Exact next slice

1. Extend the synthetic runner to create an active walk, seal an immutable non-resumable
   `walk_snapshot` after the injected drift, and prove the snapshot is excluded from active reads.
2. Reconcile into `projection-t0-r2`, create a new walk, and persist a `rewalk_of` relation to the
   sealed predecessor; prove both walk and projection identities changed.
3. Produce a deterministic sanitized export of the T0 projection, import it into a separately
   isolated disposable database/path within the same approved target boundary, and compare the
   pinned hashes/counts/retrieval outputs. Do not use or contact the parked legacy deployment.
4. Add these three results to the one-shot report and require all gates before changing Phase-1
   status to complete.
5. Re-run focused gates, then the full repository suite before a final completion claim.

