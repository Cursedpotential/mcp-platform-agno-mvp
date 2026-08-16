# HANDOFF — R13 Phase-1 Surreal T0 Reboot Checkpoint (2026-08-16)

> _Byline: Codex · GPT-5 · 2026-08-16_

STATUS: PAUSED FOR OWNER REBOOT; DISPOSABLE TARGET STOPPED AND SEALED
BUILD_STATUS: LOCAL GATES PASS; LIVE ADAPTER FAILS CLOSED AT PROJECTION; LIVE SUCCESS NOT CLAIMED

## Answer first

The desktop may be rebooted safely after this handoff commit is pushed. The only new remote
surface, Coolify application `data-surreal-phase1-t0-r1`, has zero running or exited containers.
Its isolated network and host data path remain preserved; Docker cleanup was explicitly disabled.

Resume from this packet, not from chat memory. R12 remains the authority for the owner rulings,
and the D3/D4 authorization packet governs only the named synthetic T0 target. Every R9 hold and
every production/parked-Surreal/corpus/migration/Graphiti/production-agent restriction remains in
force.

## Governing state

- Owner rulings: [R12](HANDOFF-2026-08-16-R12-surreal-investigation-owner-rulings.md).
- D3/D4 authority and target preflight:
  [authorization packet](PHASE1-DISPOSABLE-SURREAL-D3-D4-AUTHORIZATION-PREFLIGHT-2026-08-16.md).
- Design and failure controls:
  [Phase-1 design](PHASE1-DISPOSABLE-SURREAL-SLICE-DESIGN-2026-08-16.md) and
  [pre-mortem](plans/R12-PHASE1-DISPOSABLE-SLICE-pre-mortem-2026-08-16.md).
- Last implementation commit before this checkpoint: `6135b7b`.
- Push destination remains only `Cursedpotential/mcp-platform-agno-mvp`; the lowcarbdev push URL
  remains disabled.

## Exact disposable target

| Field | Value |
|---|---|
| Coolify application | `data-surreal-phase1-t0-r1` |
| Application UUID | `hastprr4a99tvpdi4c2k8i36` |
| Host | `ovh-files` / `100.91.190.107` |
| Host path | `/data/agno/experiments/phase1-surreal-t0-r1` |
| Network | `phase1-surreal-t0-r1`, internal only |
| Namespace / database | `phase1_surreal` / `t0_slice_r1` |
| Context | `phase1_surreal_t0_slice_r1` |
| Surreal image | `surrealdb/surrealdb@sha256:e908d5d47f8dfacf955d5679487a06c75a4a8338f49e137582d4fd6ed63ddef2` |
| Corpus | Fabricated T0 inputs only; no project corpus copied |

The target has no published host port. Its generated Coolify hostname returned a plain `404` and
did not expose a Surreal endpoint. The parked legacy deployment and retired `ovh-data` host were
not contacted.

## Territory observed before pause

- SurrealDB reached healthy state as UID/GID `65532:65532` on the isolated RocksDB path.
- The one-shot runner never produced a successful report. It failed closed at
  `stage=projection` with `NotAllowedError: Method not allowed`.
- Earlier lifecycle denials for `version` and `detach` were corrected by commit `6135b7b`; the
  remaining projection denial is unresolved.
- A diagnostic exposed the disposable bootstrap password in command metadata. The credential was
  immediately treated as compromised. The rotation statement invalidated the exposed value, but
  its successful response was not recognized, so the transient replacement was neither printed
  nor retained. A harmless authentication probe proved the exposed value no longer works.
- Coolify now stores a separate fresh random value, with no secret printed. It intentionally does
  not unlock the sealed existing RocksDB state. That disposable state must be quarantined and
  reinitialized before another run; it must not be silently reused.
- The application was stopped through Coolify with `docker_cleanup=false`. Direct host observation
  after the request showed `running_containers=0`, `all_containers=0`, preserved network count `1`,
  and the host path present with mode `0700`, UID/GID `65532:65532`.
- Coolify still reported `running:healthy` after the containers stopped. Treat that field as stale
  control-plane state; Docker observation is the territory.

## Commits and checks completed

- `62cc467` — isolated Surreal Phase-1 slice, framework-neutral runner, and Workbench `/surreal`.
- `4ce32d0` — readiness `attach` RPC allowance.
- `bcde048` — runner failure-stage reporting.
- `91c681c` — retry-safe schema bootstrap.
- `6135b7b` — exact SDK lifecycle RPC allowances.
- Isolated runner tests: **15 passed** after the multi-statement failure regression was added.
- Phase-0 plus workspace Surreal tests: **20 passed**.
- Focused Ruff: **PASS**.
- SurrealQL schema and filtered retrieval validation: **PASS**.
- Workbench production build and ESLint, including `/surreal`: **PASS**.
- Full repository suite was not rerun after the Phase-1 implementation; do not infer a full green
  build from the focused gates.

The Workbench Surreal page uses the official SurrealDB Studio launcher and labels the surface
`projection, not authority`. It contains no credential or public database endpoint. It has not
been deployed as part of this slice.

## Resume procedure

1. Read this packet, R12, the D3/D4 authorization packet, and the Phase-1 pre-mortem.
2. Fetch and prove `main == origin/main`; inspect the worktree before editing.
3. Verify the Coolify application is stopped using host Docker state, not only Coolify's stale
   status field. Verify the preserved path and network.
4. Quarantine the inaccessible disposable RocksDB directory without deleting it, then initialize
   a clean state for this exact approved T0 target. Never print rendered container arguments or
   credentials; use environment variables and stdin.
5. Start/redeploy only through Coolify. Keep cleanup disabled and keep the target internal-only.
6. Instrument the projection call narrowly enough to report the structured denied method/function/
   target without exposing secrets, then fix the least-privilege permission set.
7. Run the complete live early/late/hindsight, negative-write, quarantine, sealed-snapshot,
   linked-rewalk, and export/import parity gates. A live success claim requires an actual report.

Do not create another target, copy real corpus data, apply PostgreSQL migrations `0026`–`0030`,
contact the parked Surreal deployment, activate production Horizon reads, bind a production agent,
or replace Graphiti.
