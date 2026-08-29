# Documentation Patch Report — Phase-0 Owner Rulings

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Decision authority:** D-064; owner reviewed S1–S6 one at a time.

## Outcome

The Phase-0 documentation now records the accepted boundaries without beginning physical schema,
activation, corpus transfer, deployment, Graphiti replacement, or production-agent work.

## Applied patches

| Drift class | Files | Correction |
|---|---|---|
| Intent mismatch | ADR-0056, contracts, owner packet, blueprint, canon | Replaced per-walk Context/namespace isolation with one shared product/environment Context, Matter scopes, first-class walk records, and walk-bound experiential state |
| Missing coverage | ADR-0056, contracts, evaluation, threat tests | Added immutable failure snapshots, active-retrieval denial, linked clean rewalks, and attributable experiential delta |
| Intent mismatch | Contracts, packet, goals, evaluation | Replaced latest-bound realization with interval-preserving midpoint proposal plus mandatory HITL clarification and preapproval denial |
| Missing coverage | ADR-0057, contracts, evaluation | Separated raw derivative-hit count from independent-source-family corroboration |
| Status drift | Decision log, canon, goals, blueprint, question inventory, packet | Recorded D-064 and changed S1–S6 from pending recommendations to accepted owner rulings |
| Test coverage | Framework-neutral Phase-0 contract test | Added shared-walk, sealed-snapshot/rewalk, HITL midpoint, and source-family cases |

## Deliberately not applied

- The owner-packet filename still begins `PENDING-...` so existing links remain stable; its title and
  status clearly say the rulings are accepted.
- R11 remains an immutable point-in-time handoff showing the original 14-test review state; R12
  supersedes it as the current resume point.
- No physical table names, SurrealQL, SDK binding, adapter, migration, or deployment files were
  introduced.
- No empirical choices E1–E5 were promoted into architecture decisions.
- No historical files or records were deleted or moved.

## Validation

See `plans/R11-PHASE0-OWNER-RULINGS-pre-mortem-2026-08-16.md` and the R12 handoff for final command
evidence and remaining holds.
