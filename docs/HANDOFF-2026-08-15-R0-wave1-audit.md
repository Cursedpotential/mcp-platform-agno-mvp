# HANDOFF — R0 Wave-1 Independent Audit (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: COMPLETE
BUILD_STATUS: FAIL

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Branch | `main` equals `origin/main`; reviewed work is uncommitted |
| Unit suite | 688 passed, 24 skipped |
| Ruff lint | Passed for `server tests` |
| Mypy | Passed for `server` |
| Format gate | Failed: `server/evidence/derivation.py` would be reformatted |
| Migrations | `0026–0029` exist in the working tree and were not applied by this review |

## Findings / work done

- `base_version` is not a complete corpus/content version; it hashes identifiers and selected clocks rather than every retrieval-affecting field.
- Reproducibility checks compare against the current live store, so old runs cannot be reproduced after later ingestion.
- The walk ledger stores identifiers while pass grants deny canonical content; the proposed pass reader lacks a complete content path.
- Agent “binding” adds realization tools but does not bind the agent to an immutable derived corpus.
- Unresolved later-realization proposals fall back to `occurred_at`, leaking a quarantined fact into the as-lived view.
- Supersession can also revert visibility to `occurred_at` and reveal a fact sooner.
- The `visible_from` cache has no production invalidation/refresh path.
- SQL grants are advisory while the application uses the superuser `ai` role.
- Derivation repeatedly scans the case and duplicates cumulative slices, producing avoidable time/storage growth.

## UNRESOLVED (mandatory)

- Exact salvage boundary for migrations `0026–0029` — implementation has useful schema concepts, but immutable-manifest and quarantine defects require redesign before application.
- Live rollback scripts were not rerun during this documentation persistence stage.

## Pending owner decisions

- Hold Wave-1 cutover — WHAT: keep migrations unapplied · WHY: silent hindsight leakage and non-replayable manifests invalidate the core claim · APPROACH: repair in place versus replace with new migrations · SHORTCOMINGS: in-place repair is faster but risks preserving misleading names/contracts. Recommendation: salvage concepts, replace unsafe behavior before apply.

## Next steps (work in order)

1. Freeze the immutable manifest contract from R2.
2. Map each existing migration object to keep/replace/quarantine.
3. Implement append-only realization decisions and pending quarantine.
4. Replace the corpus/version hash.
5. Add post-ingestion replay tests and format the derivation module.
6. Rerun rollback validations and the full quality suite.

## Owner working-style contract

- Structured replies; confirm before changes; never hard-delete; byline every artifact; verify before claiming done.
