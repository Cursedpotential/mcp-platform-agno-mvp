# Phase 1 — Disposable Surreal Slice Design

> _Byline: Codex · GPT-5 · 2026-08-16 · ADR-0059 amendment Codex · GPT-5 · 2026-08-18_
>
> **Status:** LOGICAL DESIGN BASELINE, amended by ADR-0059. Later D3/D4 authority covered only
> the exact isolated T0 target/implementation. The pre-ADR-0059 R14 target was run and stopped;
> amended artifacts have local tests but no current live-store rerun. Every production hold remains.
> **Authority:** [PROJECT_CANON.md](PROJECT_CANON.md), D-064,
> [ADR-0056](adr/0056-surrealdb-governed-analytical-and-walk-memory-surface.md),
> [ADR-0057](adr/0057-claim-centered-evidence-assembly-and-established-facts.md),
> [ADR-0058](adr/0058-investigation-search-and-behavioral-analysis-modes.md), the accepted
> [ADR-0059](adr/0059-first-party-and-acquired-third-party-message-projections.md),
> [Phase-0 contracts](CONTRACTS-2026-08-16-surreal-investigation-phase0.md),
> [evaluation specification](EVALUATION-2026-08-16-surreal-investigation-phase0.md), and
> [R12 handoff](HANDOFF-2026-08-16-R12-surreal-investigation-owner-rulings.md).

> **Historical drafting checkpoints:** R12 confirms the hard boundary: Phase 1 may be designed,
> but no Surreal target, schema, migration, deployment, corpus copy, or agent binding is
> authorized. The repository advanced from the recorded R12 resume point at `30973f7` through
> later platform-maintenance commit `741307a`; those hashes identify drafting history, not the
> repository's current head. Subsequent platform work does not expand the Surreal authorization
> boundary above; every R9 activation hold remains active. Current repository state must always
> be verified from Git and the newest handoff rather than inferred from this design document.

> **Supersession addendum (2026-08-18, Codex · GPT-5):** the “not authorized” sentence in the
> historical R12 paragraph above is retained as history. The later D3/D4 ruling authorized only
> the named isolated synthetic target and implementation. It did not authorize deployment by
> this documentation pass, production data, production Horizon/agent binding, parked-target use,
> or Graphiti replacement.

## 1. Answer first

Phase 1 should be a **T0-synthetic, disposable, contract-driven vertical slice** that proves one
small claim-to-fact path and one as-lived walk without touching production data or infrastructure.
It compares an isolated Surreal projection with the Graphiti baseline using the same frozen inputs,
policies, questions, and failure injections. PostgreSQL remains the conceptual canonical authority;
the slice may use only a fixture-backed implementation of its platform contracts until separate
database authority is granted.

The proposed experiment identifier is **`phase1-surreal-t0-slice-r1`**. This is a documentation
label only. It is not a Surreal namespace/database name, service name, endpoint, credential, or
creation instruction. Before any physical work, the owner must approve an exact target and prove
that it is not the parked legacy `data-surreal` deployment.

Success proves only that this disposable slice may proceed to a separately reviewed next gate. It
does not authorize production schema, corpus movement, deployment, production-agent binding,
Horizon activation, Graphiti replacement, or adoption of any owner-packet E1–E5 deferred choice.

## 2. Hard boundary and non-goals

This design does not authorize or specify:

- a Surreal namespace, database, table, record, index, vector, or SDK layout;
- target creation, credentials, secrets, networking, Compose/Coolify changes, or service activation;
- use of the parked legacy deployment or any existing Surreal data;
- migrations `0026`–`0030`, a new migration, or any PostgreSQL/production write;
- T1 redacted material, T2 custody-backed material, or a copy of any real corpus;
- a production agent, the live as-lived path, or broad-store retrieval fallback;
- Graphiti replacement, official Spectron adoption, or production cutover;
- an embedding/reranking winner, vector-layout decision, TraceIQ representation, behavioral
  taxonomy/budget, or Case Prep release workflow.

Every R9 hold remains active. A design choice that requires one of these actions becomes a new
owner decision; it is not silently filled in during implementation.

## 3. Slice question

The slice answers one bounded question:

> Can the platform project a frozen synthetic authority set into an isolated shared Context,
> assemble an auditable claim dossier and reviewed fact, walk the evidence without future leakage,
> pause and resume a healthy walk, seal on drift, and create a linked rewalk—while preserving
> exact provenance, Matter/walk isolation, reproducibility, and parity evidence against Graphiti?

It does not answer whether Surreal should replace Graphiti or become production infrastructure.

## 4. Frozen T0 slice manifest

The Phase-1 corpus is a new immutable revision of the existing T0 manifest. It reuses the planted
future-fact oracle and adds only the minimum synthetic objects needed for end-to-end coverage.
No source text may resemble or be derived from the owner's real evidence.

| Item | Minimum slice content | Purpose |
|---|---|---|
| Matters | Matter A plus a cross-Matter decoy | Prove mandatory Matter isolation |
| Sources | 6–10 fabricated sources including first-party messages and one acquired-third-party conversation with immutable hashes/revisions | Exercise source/span authority without real corpus |
| Third-party attribution | Actual sender, recipients, and participants; owner absent | Prevent fabricated first-party attribution |
| Promotion states | Full synthetic source, manifest-only source, selected-span source, revoked source | Prove partial exposure and revocation |
| Evidence roles | Supporting, contradicting, qualifying, contextual, unresolved, missing expected | Build a non-confirmatory dossier |
| Derivative lineage | At least three raw copies in one source family plus one independent source | Prove raw-hit versus independent-source counts |
| Claims | One horizon-eligible candidate plus one broader-horizon forbidden candidate | Prove walk-local uncertainty and candidate isolation |
| Realization | Zero-to-many links per message, including several approved/proposed dates | Prove plural derived knowledge without changing source availability |
| Walks | Two same-Matter walks with different modes/roles plus one cross-Matter walk | Prove shared-Context isolation |
| Horizons | First-party post-occurrence, third-party pre/post-acquisition, realization-specific, and hindsight controls | Prove source possession and later understanding separately |
| Faults | Healthy pause, stale hash, revoked promotion, missing membership, simulated outage | Prove resume versus seal/reconcile/rewalk behavior |

The manifest pins source, parser, normalizer, chunk, embedding, retrieval, projection, policy,
prompt, tool, model-route, and evaluation versions even when a deterministic test double supplies
one of those stages. Each run records what was real, simulated, skipped, or unavailable.

## 5. Logical slice topology

```text
frozen T0 manifest + review decisions
                  |
                  v
fixture-backed canonical contract adapter
                  |
          promotion plan + receipts
          /                       \
         v                         v
isolated Surreal candidate      isolated Graphiti baseline
         \                         /
          identical HorizonContexts,
          questions, budgets, and faults
                  |
                  v
trace capture -> deterministic gates -> itemized comparison report
```

The fixture-backed canonical adapter represents PostgreSQL's authority boundary without creating
or mutating a database. It emits platform-owned contracts and immutable decisions; neither
projection may author or amend them. Projection-native identifiers appear only in typed receipts.

The candidate and baseline must consume the same ordered input events. They may have different
native representations, but they receive identical eligible membership, horizons, questions,
budgets, and fault schedule. Any baseline limitation is reported, not hidden by changing its input.
The Graphiti baseline is logical at this stage too: a future execution must use a separately
approved isolated test target, never the live production graph.

## 6. Shared Context and walk isolation

The logical world contains one shared product/environment Context. Promoted knowledge is stored
once in that Context and is always Matter-scoped. A walk is an execution identity, not a Context,
truth clock, or duplicated corpus.

Every as-lived stateful operation is bound to:

- `matter_id`, `walk_id`, `run_id`, `agent_role`, and immutable `horizon_id`;
- projection revision and reconciliation status;
- promotion, retrieval, prompt, tool, model-route, and policy versions;
- an eligible-record manifest and ordered activation-step hash.

Walk-generated candidate beliefs bind to their origin walk and may use only horizon-eligible
inputs. The broader-horizon candidate is invisible to the ignorant walk even if it is explicitly
labeled uncertain. Cache, profile, consolidation, summary, prompt-assembly, and trace facilities
that cannot prove these bindings are disabled for the as-lived path.

## 7. Minimal vertical journey

1. **Freeze authority inputs.** Content-address the T0 manifest, source classes/acquisition,
   actual participants, synthetic promotion decisions,
   realization revisions, scope, source-family rulings, policies, and expected outputs.
2. **Compile eligibility.** Produce an inspectable pre-ranking/traversal eligibility plan for each
   adapter. Unsupported or unverifiable predicates return a typed failure.
3. **Plan projection.** Produce canonical membership and content hashes plus a write plan. This is
   a dry contract artifact until target creation and implementation are separately approved.
4. **Project the approved subset.** In a future authorized execution, project manifests, approved
   spans/full synthetic normalized content, exact locators, chunks, relationships, temporal state,
   and receipts. Original bytes remain outside the projection.
5. **Open one investigation.** Start from one candidate claim, execute bounded support,
   contradiction, qualification, alternative, and missing-evidence searches, then freeze a dossier.
6. **Simulate governed review.** An attributable T0 reviewer decision establishes one immutable
   synthetic fact with exact evidence links. The candidate and rejected hits remain preserved.
7. **Run the as-lived walk.** Advance through fixed horizons; record eligible sets, retrieval,
   query generation, context, belief events, responses, and state hashes.
8. **Run positive controls.** Execute hindsight and the approved later horizon with identical
   policies and budgets, then produce the expected realization delta.
9. **Prove healthy resume, then inject failure.** Pause at an exact checkpoint, resume the same
   walk with equal state/trace/belief/retrieval references, then introduce revocation/hash drift.
   Pause the affected execution,
   quarantine the projection revision, and seal a non-resumable snapshot.
10. **Reconcile and rewalk.** Rebuild from canonical decisions, create a new linked `rewalk_of`,
    and attribute input/projection changes separately from prompt/model/tool/reasoning changes.
11. **Compare baseline and candidate.** Publish per-case results, raw traces, resource use, failures,
    skips, and remediation. No aggregate score may hide a binary-gate failure.

## 8. Investigation and fact-assembly limits

The single `ClaimInvestigation` has an inspectable plan before execution and fixed ceilings for
hops, candidates, elapsed time, context, and model cost. Its mandatory stages include a
disconfirming query, an alternative-explanation query, derivative-family grouping, and an
expected-missing-evidence check.

The frozen `FactDossier` includes every selected and rejected hit, contradiction, qualification,
gap, limitation, budget termination, and source-independence decision. Review never refreshes it
in place. The established fact is synthetic, atomic, immutable, and linked to exact source spans;
it is not a court-safe export.

## 9. Failure, sealing, and disposal behavior

Revocation, missing membership, stale content hash, projection mismatch, or an unverifiable outage blocks the
affected as-lived read. The system must not serve stale state or fall back to broad PostgreSQL,
Weaviate, Neo4j, Graphiti, another walk, or a sealed snapshot.

Before reconciliation, the walk snapshot binds its horizon, eligible manifest, projection/state
hashes, belief events, retrieved context, traces, versions, and failure cause. It is immutable,
read-only, replayable, non-resumable, and excluded from active retrieval. Repair produces a new
projection revision and linked rewalk.

A healthy pause instead writes a distinct resumable checkpoint and preserves the same walk
identity. If the original projection guard or any checkpoint hash/reference no longer reconciles,
the pause becomes terminal and follows the seal/rewalk path.

At experiment end, the future physical target is stopped, access is revoked, and its final
manifest/report is preserved for review. No automated deletion or destructive cleanup is part of
this design; disposal remains an explicit owner action.

## 10. Target identity and preflight proof

The proposed experiment label is `phase1-surreal-t0-slice-r1`. Before creating anything, a
separate approval packet must provide:

1. the exact host/environment, service identity, endpoint, namespace/database choices, and data
   locations;
2. owner approval for target creation, credentials, implementation, and any required network or
   deployment change;
3. a denylist showing that `data-surreal`, its endpoint, volumes, credentials, and
   `compose.data-surreal.yaml` path are not reused;
4. a read-only inventory proving the selected target is absent/new and the parked legacy target
   remains read-only and unchanged;
5. unique least-privilege credentials and an explicit no-production-route assertion;
6. a stop/quarantine procedure that does not permanently delete files or data;
7. an approved physical design reviewed against every contract and gate in this document.

Any ambiguity, alias, shared volume, credential reuse, or inability to prove negative identity is
a stop condition. Merely renaming the parked deployment does not create an isolated target.

## 11. Gate matrix

| Gate | Phase-1 evidence required | Failure effect |
|---|---|---|
| E0 Contract neutrality | Existing framework-neutral suite stays client/import free | Stop |
| E1 Horizon | HF-01–HF-12 produce zero forbidden influence before ranking through final output; positive controls work | Quarantine run and projection |
| E2 Scope/isolation | Zero cross-Matter, cross-walk, cross-role, cache/profile, or scope-revision bleed | Stop |
| E3 Authority | No candidate, belief, rank, or projection object appears as fact or released work product | Stop |
| E4 Provenance | Every cited/fact assertion resolves to exact span, source revision, and synthetic custody binding | Stop |
| E5 Promotion | Manifest-only/selected-span exposure holds; revocation and mismatch fail closed | Seal and reconcile |
| E6 Reproducibility | Manifests, dossiers, eligible sets, receipts, snapshots, state hashes, and rewalk deltas reproduce | Stop |
| E6a HITL time | Unapproved midpoint has zero realization/belief-view visibility without hiding an independently source-available message; approval is attributable and revisioned | Stop |
| E6b Corroboration | Derivative raw hits do not inflate independent-source count | Stop |
| E7 Bounded investigation | Budgets, disconfirmation path, and termination reason are complete | Stop |
| E8 Behavioral safety | Not exercised beyond a negative no-diagnosis/no-release assertion; reported as out of slice | No behavioral promotion claim |
| E9 R9 hold | No held migration, production service, corpus, parked target, or Horizon activation is touched | Abort task |

Retrieval metrics are reported per question family, but no usefulness threshold can average away a
binary failure. A result that blocks both the forbidden item and its later/hindsight positive
control is broken, not safe.

## 12. Required reports and receipts

A future authorized run must produce:

- immutable corpus, scope, policy, projection, and question manifests with hashes;
- target-negative-identity attestation and approval references;
- projection plans/receipts and reconciliation membership/content-hash diffs;
- adapter-submitted prefilter traces and eligible counts before ranking/traversal;
- planner, reranker/model-input, prompt/context, belief-write, answer, cache, and trace canary scans;
- claim plan, EvidenceHits, source-family analysis, frozen dossier, review, and fact links;
- walk steps, belief-event chain, sealed snapshot, linked rewalk, and classified MemoryDiff;
- candidate-versus-Graphiti per-case results, latency/resources, failures, skips, and remediation;
- an itemized durable run report that distinguishes contract proof, simulated behavior, and
  observed live behavior.

## 13. Approval sequence

Phase 1 is intentionally split so design acceptance cannot imply infrastructure authority:

1. **D1 — design review:** approve, revise, or reject this logical slice and its pre-mortem.
2. **D2 — physical proposal:** choose and review exact target, physical schema, adapter, SDK,
   credentials, isolation, and stop/quarantine plan. No creation yet.
3. **D3 — creation authority:** separately approve creation of the named disposable target and
   synthetic-only access.
4. **D4 — implementation authority:** separately approve physical schema/adapter code and test
   execution against that target.
5. **D5 — result review:** accept or reject measured findings. Passing does not authorize
   production adoption, corpus copy, agent binding, or Graphiti replacement.

No later gate is inferred from an earlier one.

## 14. Design completion criteria

This design is ready for owner review when:

- the T0 slice and vertical journey are bounded and understandable without a physical schema;
- every D-064 ruling is exercised by at least one planned positive and negative proof;
- every Phase-0 non-negotiable gate is mapped to evidence and a failure action;
- the parked deployment and all R9 holds are explicitly protected;
- candidate and baseline receive identical frozen inputs without declaring a winner in advance;
- target, physical implementation, infrastructure, corpus, and production authority remain
  separate decisions.

The accompanying
[pre-mortem](plans/R12-PHASE1-DISPOSABLE-SLICE-pre-mortem-2026-08-16.md) is normative for stop
conditions and proof obligations during any later authorized implementation.

The separately prepared
[D2 physical proposal](PHASE1-DISPOSABLE-SURREAL-D2-PHYSICAL-PROPOSAL-2026-08-16.md) names and
reviews the proposed target, schema, adapter, SDK, credential identities, isolation, and quarantine
plan. It remains a proposal and grants no D3 creation or D4 implementation authority.
