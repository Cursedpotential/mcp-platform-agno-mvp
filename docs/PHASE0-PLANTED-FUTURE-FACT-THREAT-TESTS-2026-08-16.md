# Phase 0 — Planted Future-Fact Horizon-Leak Tests

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Status:** Threat-test contract plus validated synthetic oracle vectors.
> **Integration status:** BLOCKED — target store/service adapters do not yet implement this contract.

## 1. Threat model

An as-lived agent is contaminated if an ineligible fact influences candidate generation,
ranking, query expansion, summaries, memory, tool selection, context, or final output—even when
the fact is later removed from displayed results. The test oracle therefore observes the whole
trace, not only the answer.

The adversary is accidental system behavior: high semantic similarity, stale caches, graph/geo
joins, summary reuse, scope expansion, belief-memory crossover, or adapter filter loss.

## 2. Threat-case contract

Each `ThreatCase` records:

- case/contract version, attack vector, store/stage under test, and immutable policy hash;
- Matter, scope revision, source revision set, horizon mode/cutoff, and disclosure tiers;
- planted sentinel fact and semantically similar eligible controls;
- occurrence, realization/visibility, recording, approval, and source-span state;
- forbidden and allowed result IDs at each checkpoint;
- positive-control horizon at which the planted fact must become visible;
- expected filter/authorization attestation and fail-closed error behavior.

Synthetic sentinel text is unique per case and must not occur in prompts, test names, expected
answers, or logs shown to the agent before the positive-control horizon.

## 3. Required attacks

| ID | Attack | Required assertion |
|---|---|---|
| HF-01 | Future fact has the highest vector similarity | Prefilter removes it before top-k; eligible results still fill k |
| HF-02 | Event occurred earlier but was realized later | `realized_at` controls visibility; occurrence alone cannot leak it |
| HF-03 | Fact sits outside approved spans of a partially approved source | Manifest is visible, planted text is not searchable |
| HF-04 | Neo4j/Surreal graph neighbor crosses the horizon | Expansion predicate runs before neighbor scoring/traversal return |
| HF-05 | TraceIQ geo join finds a later-known location fact | Temporal/authorization predicate applies inside the geo query |
| HF-06 | Future fact influences query generation | Planner context and generated queries contain zero sentinel tokens |
| HF-07 | Hindsight cache/summary is reused in as-lived mode | Policy/scope/revision mismatch causes miss or fail-closed invalidation |
| HF-08 | Behavioral outward discovery crosses frozen scope | Discovery stays separate; original closed-set result is unchanged |
| HF-09 | Derived pass uses stale horizon-policy revision | Materialization is quarantined/rebuilt; never served as current |
| HF-10 | Hindsight Graphiti belief enters an as-lived run | Context mismatch excludes belief; it may remain an auditable lead elsewhere |
| HF-11 | Cross-Matter semantic match dominates ranking | Matter prefilter removes it before all ranking/traversal stages |
| HF-12 | Reranker/model sees raw unfiltered candidates | Input trace proves only eligible candidate IDs reach the reranker/model |

## 4. Stage assertions

For every forbidden sentinel:

- `forbidden_candidate_count == 0` after the store eligibility stage;
- `forbidden_reranker_input_count == 0`;
- `forbidden_query_influence_count == 0`;
- `forbidden_context_token_count == 0`;
- `forbidden_memory_write_count == 0`;
- `forbidden_answer_token_count == 0`;
- `cross_scope_result_count == 0`;
- missing/stale/unverifiable filter attestation produces a typed failure, not partial success.

When enough eligible records exist, filtering before top-k must still return the requested k.
The positive control must retrieve the planted fact under hindsight or after its realization.
A threat case that blocks both forbidden and positive controls is broken, not safe.

## 5. Store and orchestration matrix

Run relevant cases independently against:

- PostgreSQL canonical retrieval/views;
- Weaviate dictionary prefilters before vector/hybrid ranking;
- Neo4j graph/path queries with predicates inside traversal;
- Surreal document/graph/vector queries in the isolated spike;
- Graphiti run-scoped belief retrieval;
- federated fusion/reranking;
- derived pass materializations and checkpoints;
- query-planner, summary, response, and tool-result caches;
- model/reranker input and final agent context.

Store adapters must record the submitted filter in a redacted trace. A post-hoc result filter
cannot satisfy the test.

## 6. Paired-run oracle

The as-lived and hindsight sides receive the same question, route policy, tools, and budgets but
different immutable horizon policies. Their traces remain separate. The planted fact must be:

- absent from every as-lived stage before visibility;
- present in the hindsight positive control;
- present in an as-lived rerun only after the cutoff passes `visible_from`;
- represented in the delta as newly available evidence, not as an earlier hidden intuition.

## 7. Executable Phase-0 vectors

`tests/fixtures/surreal_investigation_phase0_horizon.json` contains the first synthetic canary
covering high-similarity future occurrence, old-source/late realization, hindsight-only,
cross-Matter, revoked projection, and candidate-only shapes.
`tests/test_surreal_investigation_phase0_contract.py` validates:

- versioned fixture semantics and the reference eligibility predicate;
- prefilter-before-ranking behavior on PostgreSQL, Weaviate, Neo4j, and Surreal labels;
- zero forbidden visibility or agent-visible/query-generation influence;
- later/hindsight positive controls and the expected realization delta;
- full eligible-result fill and detection of known-bad rank-then-filter behavior;
- fail-closed behavior when an adapter cannot prove prefilter support;
- absence of runtime/store client imports from the contract test.

Focused Phase-0 result: **14 passed**, with Ruff lint and format checks passing. This proves the
oracle data is internally coherent. It does **not** prove a production adapter,
store, cache, planner, model, or agent is safe. Phase-1+ adapters must consume these same vectors
and attach their traces before integration status can change from `BLOCKED`.

HF-03 through HF-12 remain required integration cases even where the first synthetic canary
models their authority/scope failure only indirectly. Later fixtures extend this contract; they
do not weaken or replace the first canary.

## 8. Failure handling

On contamination: stop the run, quarantine its checkpoint/materialization, record the policy,
scope, candidate IDs, adapter revision, and first contaminated stage, and require a clean rerun.
Never repair a contaminated as-lived result by merely deleting the offending sentence.
