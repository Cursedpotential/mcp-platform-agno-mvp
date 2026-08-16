# R10 Phase 0.3 Pre-Mortem — Gold Corpus and Evaluation Gates

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Task status:** COMPLETE FOR REVIEW — specification only
> **Production apply/deploy/corpus copy:** NONE

## Verdict

The load-bearing failure is optimizing an average retrieval score while a single future fact,
cross-scope item, or unreviewed claim leaks into an agent-visible surface.

**Confidence:** High.

## Failure modes and controls

| Failure | Severity | Control | Falsifying evidence |
|---|---:|---|---|
| Quality average hides a safety failure | Critical | E1–E9 are binary and non-compensable | A profile advances after one leak because average nDCG is high |
| Synthetic corpus is too clean | High | Adversarial negatives, duplicates, ambiguity, stale hashes, failures | No cases require abstention, contradiction, or recovery |
| Gold labels confuse irrelevant with ineligible | Critical | Separate eligibility/relevance/missing states | A future fact is scored merely “not relevant” after ranking |
| LLM judge grades deterministic invariants | High | Deterministic checks are mandatory | Judge prose is sole evidence for locator/horizon/provenance success |
| Real evidence is copied under “evaluation” | Critical | T0 only now; T1/T2 require separate approvals | Any custody-backed source enters the bundle without source approval |
| One model/profile wins globally | Medium | Per-domain/question reporting and isolated spaces | Cross-space raw cosine averages or micro-average-only selection |
| Graphiti is replaced on a headline score | High | Identical bake-off plus binary gates and owner threshold | Replacement before replay/isolation/rebuild proof |

## Validation evidence

- Coverage includes every domain required by G8: legal, conversational, behavioral, code,
  table, OCR, temporal, geo, exact citation, paraphrase, mixed-domain, and contamination.
- Metrics cover retrieval, routing, calibration, locator accuracy, latency, cost, storage,
  reindex/rebuild, and horizon contamination.
- Gates explicitly cover every forbidden future-fact surface named by the runtime migration plan.
- Evaluation distinguishes extraction, claims, facts, beliefs, and court-safe work products.
- T0/T1/T2 custody tiers prevent Phase 0 from authorizing a real corpus copy.
- No runtime, service, schema, migration, corpus, or external state changed.

## Rollback/quarantine path

Thresholds are provisional and may be superseded after the first baseline. If the specification
is rejected, move it to `to_be_deleted`; do not delete it. No data rollback is needed.

## What would change the verdict

- An owner-approved risk model that makes another binary safety gate equally or more important.
- Baseline data showing a proposed usefulness threshold is statistically unsound.
- A lawful/ethical requirement that prevents using even synthetic examples for one category.
