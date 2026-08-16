# Gold Corpus and Evaluation Specification — Surreal Investigation Phase 0

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Status:** PROPOSED FOR OWNER REVIEW — specification plus synthetic contract canary
> **Corpus state:** No production corpus copied; no sensitive corpus authorized for evaluation.

## 1. Purpose

This specification determines whether a later disposable Surreal/investigation slice is safe,
reproducible, and useful. It is not a model leaderboard. A high average score cannot compensate
for horizon leakage, broken custody resolution, silent scope expansion, or authority laundering.

The evaluation harness must run against platform-owned contracts so the same cases can compare
PostgreSQL, Weaviate, Neo4j, Graphiti, Surreal, models, and orchestration adapters without making
their native objects the gold labels.

## 2. Corpus tiers and custody

| Tier | Content | Allowed now? | Purpose |
|---|---|---:|---|
| T0 synthetic | Fabricated people, sources, claims, contradictions, future facts, and locators | Yes | Contract, safety, and deterministic CI tests |
| T1 redacted/derived | Owner-approved excerpts with irreversible redaction and retained source bindings | No; separate approval | Realistic retrieval/chunking calibration without full source exposure |
| T2 custody-backed real | Selected original/normalized evidence under existing custody and source-promotion policy | No; separate source-level approval | Final pre-production relevance/provenance validation |

Phase 0 creates only T0 specifications and the planted-future-fact fixture. T1/T2 material must
not be copied to Surreal or a test bundle merely because this document exists.

Each corpus version is immutable and content-addressed. Amendments produce a new version and a
diff; prior labels remain available for replay.

## 3. Gold manifest contract

Every corpus release contains a machine-readable manifest with:

- corpus ID/version/hash, creation/review actors, sensitivity tier, and allowed environments;
- every source's synthetic/custody ID, source kind, revision, H1/content hash, language,
  modality, authority/review state, promotion scope, and disclosure/temporal axes;
- structural atoms, exact typed locators, retrieval chunks, chunk-policy versions, and known
  derivative/independence groups;
- claims and expected supporting, contradicting, qualifying, contextual, duplicate, unresolved,
  and missing-expected evidence;
- established-fact labels only where a simulated/real governed review is part of the case;
- immutable scopes, horizon steps, planted canaries, expected eligible IDs per step, and expected
  ignorant/hindsight realization delta;
- questions, intent, acceptable answers/abstentions, required citations, prohibited conclusions,
  and required disconfirmation paths;
- lens/diagnosis/court-language labels for behavior and Case Prep cases;
- version pins for parser, normalizer, chunker, classifier, embeddings, reranker, store adapter,
  prompt, tool policy, model route, and evaluation code.

Gold labels distinguish “not relevant,” “not eligible,” and “relevant but missing.” Those states
cannot be collapsed into one negative class.

## 4. Minimum corpus composition

The first accepted T0 corpus contains at least 72 questions over at least 36 synthetic sources.
Cases may cover several cells, but every row below needs at least four questions and both positive
and negative examples.

| Family | Required coverage |
|---|---|
| Legal/document | Exact clause/citation, paraphrase, competing revisions, authority levels |
| Conversations | Turn-safe chunks, pronouns, cross-conversation corroboration, late discovery |
| Email/messages | Thread ordering, quoted duplicates, attachments, sender/time ambiguity |
| Tables/structured | Row/column locators, exact values, aggregation traps, missing rows |
| OCR/media-derived | OCR error, page/region locator, conflicting transcript, low confidence |
| Code/platform | Symbol locator, version drift, domain-routing ambiguity |
| Temporal | Valid versus realized versus recorded versus decision versus observed time |
| Geo/TraceIQ-ready | Point/interval uncertainty, co-location versus causation, time-zone ambiguity |
| Claim/fact | Candidate versus fact, support/contradiction/qualification, supersession |
| Behavioral | Positive, negative, ambiguous lens cases; alternative explanations; no diagnosis |
| Court language | Internal shorthand to conduct-first draft; citation and release blockers |
| Contamination | Highly similar future facts, old-source/late-realization facts, hidden metadata leaks |
| Isolation | Cross-Matter, cross-run, ignorant/hindsight namespace, unauthorized profile |
| Failure/recovery | Partial projection, stale hash, timeout, budget exhaustion, rebuild/replay |

At least 20% of questions are adversarial negatives where the correct response is abstention,
“insufficient evidence,” a contradiction, or a blocked run. At least 20% require multi-source
assembly. At least 10% are derivative-copy traps.

## 5. Question and expected-output specification

Each question records:

| Field | Meaning |
|---|---|
| `intent` | Find Evidence, Reconstruct Event, Discover Patterns, closed behavior, or paired delta |
| `scope_id` / `horizon_id` | Immutable eligible universe and mode |
| `question_type` | Exact, paraphrase, relational, temporal, geo, contradiction, pattern, or export |
| `gold_evidence_ids` | Complete known eligible evidence set, with relevance grades |
| `forbidden_ids` | Ineligible future/cross-scope/unapproved/invalid projection items |
| `required_trace_steps` | Mandatory filters, disconfirmation, and source-resolution work |
| `answer_key` | Atomic expected assertions, acceptable alternatives, and abstention conditions |
| `citation_key` | Exact source/span/locator requirements |
| `delta_key` | Expected as-lived belief, hindsight result, and realization delta |
| `language_key` | Prohibited diagnosis/causation/court-safety overclaims |
| `budget` | Hop, result, time, context, and model-cost ceilings |

## 6. Metrics

### Eligibility and contamination

- future-fact leakage count and rate, measured before ranking and across every agent-visible surface;
- unauthorized Matter/run/role/profile leakage;
- eligible candidate count before ranking and returned eligible `k`;
- fail-closed rate for unsupported/unverifiable filters;
- closed-scope expansion count and query-generation contamination.

### Retrieval and routing

- Recall@k, Precision@k, MRR, nDCG, and abstention quality by domain/question type;
- route accuracy, multi-label F1, calibration, and selective-review/abstention curves;
- exact locator accuracy, citation completeness, and source-resolution success;
- independent-source grouping precision/recall and duplicate inflation rate;
- contradiction/qualification recall and missing-expected-evidence detection.

### Investigation and fact review

- plan completeness, mandatory disconfirmation execution, budget compliance, and termination reason;
- hit-role classification F1;
- dossier reproducibility hash and reviewer agreement;
- fact-to-span provenance completeness and improper candidate-to-fact promotions.

### Memory and replay

- temporal reconstruction, contradiction/supersession correctness, as-of search, and invalidation;
- Matter/run/role namespace isolation;
- deterministic replay/state-hash equality and old-run replay after later ingestion;
- projection acknowledgement, orphan detection, rebuild parity, and backup/restore parity.

### Behavioral and Case Prep

- observed-conduct grounding, alternative-explanation coverage, limitation disclosure, and
  repetition accuracy;
- lens calibration and abstention, kept separate from authenticated diagnosis;
- conduct-first transformation fidelity, exact citations, prohibited shorthand rate, and
  false court-safe/release claims.

### Operations

- p50/p95/p99 latency, cost, context tokens, storage amplification, projection lag, reindex/rebuild
  time, and failure recovery by profile and question type.

## 7. Non-negotiable gates

These gates are binary. They are never averaged into a quality score.

| Gate | Requirement |
|---|---|
| E0 Contract neutrality | Contract tests run without importing Agno, AG2, AI SDK, Graphiti, SurrealDB, Weaviate, Neo4j, or a database client |
| E1 Horizon | Zero planted future-fact leakage in retrieval, prompts, handoffs, coordination WALs, beliefs, summaries, observations, and traces; filters are proven pre-ranking/traversal |
| E2 Scope/isolation | Zero cross-Matter, cross-run, cross-role, or closed-scope silent expansion |
| E3 Authority | Zero candidate/extraction/belief objects represented as established facts or court-safe exports without their review chains |
| E4 Provenance | 100% of cited/established assertions resolve through exact spans/chunk generations to a custody-backed source revision |
| E5 Promotion | Partial approval exposes only manifest plus approved spans; revocation/hash mismatch blocks reads and reconciliation fails closed |
| E6 Reproducibility | Same corpus, scope, versions, and deterministic components reproduce manifests, dossiers, eligibility sets, and projection/state hashes |
| E7 Bounded investigation | Every run records and obeys hop/result/time/context/cost limits and executes the required disconfirmation path |
| E8 Behavioral safety | No lens becomes a diagnosis; no discovery silently changes closed scope; no draft is labeled court-safe without release review |
| E9 R9 hold | No test setup applies 0026–0030, deploys, activates parked Surreal, copies the real corpus, or binds a production agent |

Any E1–E9 failure blocks promotion regardless of retrieval quality.

## 8. Provisional usefulness thresholds

These thresholds are proposed starting points for the synthetic corpus and require owner review
after baseline results. They do not override the binary gates.

| Measure | Proposed threshold |
|---|---:|
| Exact/known evidence Recall@10 | >= 0.95 |
| Paraphrase/cross-source Recall@20 | >= 0.90 |
| nDCG@10 by question family | >= 0.85 |
| Exact locator accuracy | >= 0.99 |
| Required contradiction/qualification Recall@20 | >= 0.95 |
| Route macro-F1 | >= 0.90 |
| Evidence-role classification macro-F1 | >= 0.90 |
| Independent-source grouping F1 | >= 0.95 |
| Correct abstention on adversarial negatives | >= 0.95 |
| Paired-delta expected-element recall | >= 0.95 |

Results must include confidence intervals and raw per-case failures. A domain cannot be hidden by
micro-averaging across easier domains.

## 9. Evaluation protocol

1. Freeze corpus manifest and calculate its content hash.
2. Register profiles and versions before running; reject unpinned components.
3. Build projections only from allowed synthetic promotion decisions.
4. Run contract and planted-leak tests before quality evaluation.
5. Run each retrieval profile on the identical eligible universe and questions.
6. Record raw candidate sets, eligibility proof, ranks, reranker inputs/outputs, and traces.
7. Run Investigation Search with mandatory disconfirmation and fixed budgets.
8. Replay memory and paired-delta cases from the same ordered belief events.
9. Score deterministically where possible; use blinded human review for behavior/wording.
10. Publish a durable itemized report with failures, skips, versions, cost, and remediation.
11. Repeat after rebuild to prove reconciliation and state-hash parity.

LLM judges may supplement but never replace deterministic eligibility, locator, provenance,
authority, scope, budget, and hash assertions.

## 10. Model/profile bake-off rule

- Compare profiles per source kind and question type, never with one global winner.
- Keep incompatible vector spaces isolated. Fuse ranks and rerank; do not average raw scores.
- Include current/self-hosted candidates and privacy/cost constraints, not only flagship vendors.
- Report truncation and input-task configuration. A mislabeled query/passage mode is a failed run.
- Prefer the simplest profile meeting gates and usefulness thresholds; marginal quality must be
  weighed against reindex cost, latency, availability, privacy, and storage.
- A configuration being accepted is not proof it works; require an observed write and read.

## 11. Graphiti versus Surreal bake-off

Both systems receive the identical synthetic event stream, HorizonContexts, query set, and
failure injections. Compare:

- reconstruction at each step and after later corrections;
- contradiction/supersession and current/as-of views;
- exact upstream provenance and materialization acknowledgement;
- namespace isolation and invalid context denial;
- invalidation, replay, rebuild, backup/restore, and orphan repair;
- hybrid retrieval usefulness, latency, storage, CPU/RAM, and operational complexity.

Graphiti remains the baseline unless the owner accepts measured parity/superiority. The weighted
replacement threshold is an open owner decision; no average score can waive E1–E9.

## 12. Required Phase-0 artifacts and exit

Phase 0 is ready for owner review when the repository contains:

1. the logical data/service contracts;
2. the unresolved-question inventory;
3. this gold/evaluation specification;
4. a synthetic planted-future-fact fixture and executable framework-neutral contract tests;
5. per-task pre-mortems and validation evidence;
6. a compact owner decision packet.

Phase 1 remains unauthorized until the owner accepts the contracts, mandatory gates, planted
leak behavior, and blocking decisions. R9 activation holds remain independent and unchanged.

The stage-by-stage adversarial matrix is specified separately in
`PHASE0-PLANTED-FUTURE-FACT-THREAT-TESTS-2026-08-16.md`.
