# R10 Phase 0.1 Pre-Mortem — Framework-Neutral Contracts

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Task status:** COMPLETE FOR REVIEW — documentation only
> **Production apply/deploy:** NONE

## Verdict

The most dangerous failure is a contract that calls Surreal “derived” while allowing a
projection-native assertion, ID, or memory to become canonical without PostgreSQL review.

**Confidence:** High.

## Failure modes and controls

| Failure imagined after six months | Severity | Control in the contract | Evidence that would falsify success |
|---|---:|---|---|
| Surreal becomes a second authored truth | Critical | One-way authority, ProjectionReceipt, canonical rebuild | Any write path establishes/revises a fact from Surreal state alone |
| Candidate text is called a fact | Critical | Separate ClaimCandidate, dossier, review, EstablishedFact | An extractor/model score can set fact authority |
| One ID collapses source/chunk/vector/fact identities | High | Separate identity layers and adapter locators | Rechunking changes an evidence/fact ID |
| An old source leaks a later-discovered fact | Critical | Approved `visible_from`, immutable HorizonContext, prefilter rule | Any as-lived port uses `knowledge_time` or post-filtering |
| Partial approval exposes full text | Critical | Explicit promotion scopes and span-only eligibility | One approved span makes source-level text searchable |
| Behavioral shorthand becomes diagnosis/court wording | High | BehavioralFinding separation and CasePrepCandidate | Lens label appears as authenticated diagnosis or release-ready wording |
| “Neutral” contract hard-codes a framework/schema | Medium | Platform IDs and semantic fields only; physical choices explicit | Contract imports or requires an Agno/Surreal/Postgres client object |

## Validation evidence

- Reviewed against ADR-0056, ADR-0057, ADR-0058, the Phase-0 goal tree, and the accepted blueprint.
- Cross-checked ADR-0045 horizon semantics: `knowledge_time` is audit-only and the contract uses
  approved realization/occurrence-derived `visible_from`.
- Cross-checked existing `NormalizedRecord` and Matter/CourtCase public contracts; no existing
  public identifier was redefined.
- PostgreSQL compatibility review applied: logical relations remain normalized; evolving states
  are not prematurely frozen as database enums; no migration or physical table is proposed.
- No application, schema, migration, deployment, corpus, or external service was touched.

## Rollback/quarantine path

The new documents can be superseded before owner acceptance. If rejected, move them to
`to_be_deleted` for owner review; never hard-delete them. No runtime rollback exists because no
runtime state changed.

## What would change the verdict

- An accepted architecture decision making a projection authoritative.
- A proven requirement for projection-native identity to cross the public boundary.
- Owner rejection of the five-clock or immutable-fact model.
