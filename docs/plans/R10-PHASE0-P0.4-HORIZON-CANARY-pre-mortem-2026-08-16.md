# R10 Phase 0.4 Pre-Mortem — Planted-Future-Fact Contract Canary

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Task status:** COMPLETE FOR REVIEW — synthetic fixture and test-only reference harness
> **Live adapter proof:** NOT RUN / NOT CLAIMED
> **Production apply/deploy/corpus copy:** NONE

## Verdict

The single most dangerous false success is a test that proves the reference predicate but is
later described as proof that live PostgreSQL, Weaviate, Neo4j, or Surreal prefilters work.

**Confidence:** High.

## Failure modes and controls

| Failure | Severity | Control | Falsifying evidence |
|---|---:|---|---|
| Contract test is misreported as live proof | Critical | Module/docstring and this record explicitly say test-local only | A handoff marks a store adapter verified from this suite alone |
| Test hides only future occurrence, not late realization | Critical | Two canary shapes: future-occurring and old-source/late-realized | Fixture lacks `occurred_at < horizon < visible_from` |
| Filtering occurs after top-k | Critical | Deliberately bad pipeline must shrink `k` to zero | Bad pipeline still passes or eligible-before-ranking trace contains canary |
| Canary leaks through non-retrieval state | Critical | Check prompt, handoff, WAL, belief, summary, observation, trace envelopes | Canary literal appears in any early serialized surface |
| Cross-Matter/revoked/candidate material sneaks into hindsight | High | Authority, promotion, and Matter gates apply in every mode | Those IDs enter hindsight results |
| Test imports a current framework/store client | Medium | AST import assertion and stdlib-only reference logic | Forbidden client import appears |
| Synthetic fixture is mistaken for gold corpus completion | Medium | Evaluation spec calls it one T0 canary only | Phase 0 claims the 72-question corpus exists |

## Validation evidence

- Fixture includes highly similar future-occurring, old-source/late-realization, hindsight-only,
  other-Matter, revoked-projection, and candidate-only canaries.
- Reference test requires filtering before ranking and preserves the requested eligible `k`.
- Known-bad rank-then-filter behavior is asserted to fail by shrinking `k` to zero.
- Every agent-visible surface named in the migration invariant is checked for the canary literal.
- Unsupported prefilter proof fails closed for PostgreSQL, Weaviate, Neo4j, and Surreal labels.
- Tests contain no Agno/AG2/Graphiti/Surreal/Weaviate/Neo4j/database-client dependency.
- Focused execution: `uv run pytest -q tests/test_surreal_investigation_phase0_contract.py`
  passed **14/14**. Ruff check and format check passed after the first format check identified
  and the repository formatter corrected one formatting-only defect.
- No live database, vector store, graph, memory service, model, corpus, migration, or deployment
  was contacted or changed.

## Required later proofs

1. PostgreSQL real predicate/compiler execution against a disposable canonical-image fixture.
2. Weaviate real dictionary-filter request and server-side eligible candidate trace.
3. Neo4j real predicate-before-expansion query.
4. Isolated Surreal real predicate-before-vector/graph traversal query.
5. Graphiti/Surreal belief projection check proving the canary never entered memory/traces.

Each proof must use the same fixture semantics and show returned IDs plus pre-ranking eligibility,
not merely an answer string.

## Rollback/quarantine path

The fixture and test are synthetic and removable only by moving them to `to_be_deleted` for owner
review. No runtime rollback exists because no runtime state changed.

## What would change the verdict

- Live adapter executions produce the same trace and are separately recorded.
- A store cannot expose pre-ranking evidence, requiring a stronger external proof design.
- The owner changes the set of surfaces considered part of agent experience.
