# R10 Phase 0.2 Pre-Mortem — Unresolved-Question Inventory

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Task status:** COMPLETE FOR REVIEW — documentation only
> **Production apply/deploy:** NONE

## Verdict

The most likely failure is treating every unknown as an owner decision, overwhelming review and
causing empirical questions to be answered by intuition instead of tests.

**Confidence:** High.

## Failure modes and controls

| Failure | Severity | Control | Falsifying evidence |
|---|---:|---|---|
| Owner packet becomes a 33-question backlog | High | Questions routed by owner/empirical/contract/operational class | More than the blocking subset appears as immediate required rulings |
| An open question silently receives a default decision | High | Defaults are labeled holds, never implicit approval | Implementation cites a “recommended hold” as an accepted architecture choice |
| Phase 1 begins with isolation/revocation unresolved | Critical | UQ-01/02/04/07 are Phase-1 blockers | Physical schema/projector work begins before rulings |
| R10 erases R9 release holds | Critical | Separate unchanged R9 hold table | Any document implies Phase 0 authorizes 0026–0030 apply/deploy |
| Vendor/model choices are frozen without evidence | Medium | Profile/chunk/vector questions routed to bake-off | A model/collection choice is called locked before corpus results |
| Deferred TraceIQ questions block the immediate slice | Medium | Latest-safe-point classification | Phase 1 is paused solely for Phase-6 geo details |

## Validation evidence

- Reconciled all seven open-design items from the accepted blueprint and all unresolved items in
  the R10 handoff and goal hierarchy.
- Added missing dependency questions for revocation, failure fallback, source independence,
  uncertain time, and Graphiti replacement thresholds.
- Preserved the exact R9 holds from the R9 handoff and release-custody record.
- Every question has a resolution class, latest safe point, safe hold, and required evidence.
- Focused owner routing is explicit; no question is marked resolved.
- No runtime, data, external service, migration, or deployment state changed.

## Rollback/quarantine path

Supersede the inventory after owner review or move it to `to_be_deleted` if rejected. Never
delete it. There is no runtime rollback because the task is documentation only.

## What would change the verdict

- The owner explicitly asks to decide the full inventory in one session.
- A supposedly empirical choice proves irreversible before a disposable bake-off.
- A new governing ADR resolves or removes one of the listed questions.
