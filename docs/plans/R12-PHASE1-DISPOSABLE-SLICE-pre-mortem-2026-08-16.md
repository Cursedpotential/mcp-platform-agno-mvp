# R12 Phase-1 Disposable Surreal Slice — Pre-Mortem

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Scope:** Design and failure analysis only. No target, schema, credential, database, service,
> corpus, migration, deployment, production agent, or Graphiti replacement is authorized or
> created.
>
> **Companion design:**
> [PHASE1-DISPOSABLE-SURREAL-SLICE-DESIGN-2026-08-16.md](../PHASE1-DISPOSABLE-SURREAL-SLICE-DESIGN-2026-08-16.md)
>
> **D2 proposal:**
> [PHASE1-DISPOSABLE-SURREAL-D2-PHYSICAL-PROPOSAL-2026-08-16.md](../PHASE1-DISPOSABLE-SURREAL-D2-PHYSICAL-PROPOSAL-2026-08-16.md)
>
> **Execution addendum — 2026-08-16:** the owner separately approved D3/D4 for the exact
> synthetic T0 target. This pre-mortem now governs that execution; it still grants no production,
> corpus, migration, agent-binding, or Graphiti-replacement authority.
> _Addendum byline: Codex · GPT-5 · 2026-08-16._

## 1. Premise

Assume the disposable slice was declared successful and six months later the result proved
unsafe, irreproducible, or operationally misleading. The most likely cause is not a spectacular
crash; it is a quiet boundary failure that made the ignorant walk smarter, a candidate look true,
or a disposable experiment look production-ready.

Any stop condition below blocks the affected run. Horizon, authority, provenance, promotion,
scope, or R9-hold failures are never downgraded to partial success.

## 2. Failure matrix

| Failure mode | Earliest warning | Prevention in the design | Required proof / stop condition |
|---|---|---|---|
| The parked `data-surreal` deployment is mistaken for the disposable target | Endpoint, credential, volume, Compose path, or service alias overlaps the legacy inventory | Use only the proposed experiment label until a separate target packet proves exact negative identity | Any overlap or ambiguity: stop before creation; a rename is not isolation |
| “Design approved” is treated as target/schema authority | A task begins creating resources or selecting physical records without D2–D4 approvals | Five explicit approval gates; repeat R9 and R12 holds in every handoff/report | Diff or external audit shows target, schema, migration, credential, deploy, or service mutation: abort and quarantine the work |
| Synthetic scope quietly grows into real corpus testing | T1/T2 IDs, real excerpts, custody paths, or production endpoints enter a manifest | T0-only manifest with allowed-environment and sensitivity fields; reject unknown source families | Any non-T0 source or unapproved endpoint: stop before projection |
| A future fact is filtered only after top-k | Candidate trace contains the sentinel, returned `k` shrinks, or reranker input includes a forbidden ID | Require compiled eligibility and store-side prefilter attestation before ranking/traversal | Forbidden candidate or reranker count above zero, or eligible-fill failure: quarantine projection |
| A late-realized old event leaks via occurrence time | Pre-realization results include the old event | Derive visibility from approved realization or occurrence under ADR-0045; never use recorded time | HF-02 fails or an unapproved realization revision is read: stop |
| Shared Context becomes shared experiential state | Walk A retrieves Walk B belief, summary, cache, profile, or consolidation output | Bind every stateful surface to Matter/walk/horizon/projection/policy; disable facilities that cannot prove it | Cross-walk or cross-role result count above zero: stop |
| Cross-Matter semantic similarity bypasses scope | Matter B decoy reaches candidates or graph expansion | Mandatory Matter predicate in reads, writes, caches, graph traversal, and prompt assembly | Cross-Matter candidate/influence count above zero: stop |
| Hindsight influences as-lived query generation without appearing in results | Generated query, tool choice, summary, or trace contains sentinel concepts | Scan every agent-visible and planner surface, not only final answers | Any forbidden query/context/tool influence: seal and quarantine |
| Partial source approval exposes full normalized content | Search finds text outside approved spans | Project manifest plus selected spans only; source-level approval is independent | Any unapproved text/token is searchable: revoke slice result and rebuild |
| Projection drift is served with a warning | Receipt/member hash differs but reads continue | Reconciliation is a precondition for as-lived reads; mismatch quarantines Matter/revision | Any stale/missing/extra/hash-mismatched object served: seal walk and stop |
| Broad-store fallback hides an outage | Surreal failure is followed by PG/Weaviate/Neo4j/Graphiti evidence retrieval | No evidence/memory fallback after the as-lived boundary; canonical PG is control metadata only | Any alternate-store evidence result during outage: gate failure |
| A sealed snapshot becomes active memory | New walk retrieves old snapshot state or resumes its identity | Snapshot is immutable, non-resumable, and excluded from active recall; start `rewalk_of` | Snapshot reconstructs historically but yields zero active retrieval results; otherwise stop |
| Reconciliation rewrites the original experience | Old state/trace hashes change or the same walk ID resumes | Append a new projection revision and linked walk; preserve old hashes and traces | Any mutation of sealed state or reuse of old walk identity: stop |
| A walk imports corpus-wide extraction candidates | Ignorant walk sees a candidate whose origin horizon is broader | Permit only walk-generated, explicitly uncertain beliefs from eligible inputs | Candidate origin lacks matching HorizonContext or eligible provenance: reject write |
| An uncertain midpoint becomes a realization fact | Midpoint appears in eligibility before a reviewer decision | Preserve interval and proposal separately; require attributable HITL decision and revision | Proposal has any preapproval visibility: stop; later approval must replay distinctly |
| Candidate, belief, or projection rank is presented as established fact | Output language or status skips dossier/review chain | Enforce separate authority classes and immutable governed review | Any fact lacks dossier hash, exact evidence links, and review decision: stop |
| Duplicate exports inflate corroboration | Raw-hit and independent-source counts rise together for derivatives | Group by custody/content lineage; keep counts separate until provenance review | Three derivatives count as one family; any inflation fails E6b |
| Confirmation bias survives the bounded investigation | Plan omits contradiction, qualification, alternatives, or missing evidence | Freeze mandatory disconfirmation stages before execution | Missing mandatory stage or unexplained skip: investigation fails |
| A chunk ID is accepted as provenance | Citation cannot resolve atom/span/source revision/custody binding | Require exact typed locator and content hash through the canonical resolver | Any selected assertion fails exact resolution: E4 failure |
| Candidate and Graphiti baseline receive different inputs | Manifests, horizon policies, budgets, or fault timing differ | One frozen event stream and paired run manifest; native-only limitations are reported | Manifest/policy hash mismatch invalidates comparison |
| Relation integrity is assumed from one mechanism | Missing endpoint, cross-scope edge, or changed edge count appears after export/import | Combine `TYPE RELATION ... ENFORCED`, adapter endpoint/scope validation, edge permissions, and exact export/import count/hash proof | Any missing, extra, cross-scope, or hash-changed edge: quarantine result |
| Non-deterministic components create false replay claims | State differs while versions/settings are incomplete | Pin deterministic inputs and report stochastic model limits separately | Missing version pin or unexplained state-hash drift: no reproducibility claim |
| A broken adapter looks safe because it returns nothing | Both forbidden sentinel and positive control disappear | Require later/hindsight positive controls and eligible-result fill | Positive control absent: test is broken, not passed |
| Sensitive sentinel or content leaks through observability | Logs/traces contain raw forbidden text before visibility | Use stable sentinel IDs/redacted traces and scan prompts, handoffs, WALs, summaries, and logs | Raw forbidden token on any agent-visible surface: contamination failure |
| Resource use makes the slice operationally meaningless | Rebuild, query, or storage cost is unbounded or unreported | Pin budgets and report latency, cost, storage amplification, and rebuild time per case | Missing budgets/telemetry or budget overrun without typed termination: fail E7 |
| “Disposable” triggers destructive cleanup | Automation proposes dropping data or permanently deleting files after the run | Stop/revoke/quarantine only; preserve final manifest and report for owner disposal | Any automated destructive cleanup step: stop and request owner direction |

## 3. Stage kill gates

### Before physical proposal

- The logical design, T0 content matrix, and pre-mortem require owner review.
- No endpoint, namespace/database, schema, SDK, or credentials are inferred.
- All unresolved physical choices remain explicit.

### Before target creation

- Exact target identity and negative-identity proof against parked `data-surreal` are approved.
- Network, credentials, data locations, cost bounds, and stop/quarantine behavior are approved.
- Read-only inventory shows the parked deployment unchanged and the proposed target absent.
- Any ambiguity stops the task.

### Before adapter execution

- Physical design and implementation have separate approval.
- T0 manifest hash, policies, expected eligible sets, positive controls, and target allowlist are
  frozen.
- Connection guard denies every non-allowlisted endpoint and fails closed on missing identity.
- No migrations `0026`–`0030`, production database, or real corpus are reachable.

### Before an as-lived run

- Projection receipts reconcile membership and content hashes.
- Store-side prefilter plans are inspectable and proven to run before ranking/traversal.
- Matter/walk/horizon/revision/policy bindings cover caches, profiles, prompts, consolidation,
  summaries, traces, and belief writes.
- HF-01–HF-12 negative and positive-control setup is complete.

### Before reporting success

- E0–E9 results are itemized; skips and not-applicable cases are explicit.
- Every forbidden-influence counter is zero and all required positive controls pass.
- Dossier, fact, provenance, seal/rewalk, reproducibility, and source-family assertions pass.
- Candidate-versus-baseline inputs are hash-identical.
- The report says that passing does not authorize production adoption or Graphiti replacement.

## 4. Recovery rules

When a safety or integrity gate fails:

1. stop the affected run and block further as-lived reads;
2. preserve the first failing trace, manifest, versions, eligible/candidate IDs, and policy hashes;
3. quarantine the affected projection revision;
4. seal the walk snapshot without rewriting its result;
5. diagnose and reconcile from canonical synthetic decisions;
6. begin a new linked rewalk only after the relevant approval and proof are restored;
7. compare the two walks with explicit input, projection, policy, model, prompt, tool, and reasoning
   change classifications.

Never repair a contaminated result by deleting the sentence, trimming the trace, relabeling the
old walk, or silently rerunning until a passing sample appears.

## 5. R9 activation-hold ledger

| Hold | Phase-1 design treatment |
|---|---|
| Migrations `0026`–`0030` | Unapplied and unreachable; no new production migration |
| Canonical-image/full-baseline rehearsal | Still held; fixture-backed authority only |
| Credentials | D2 proposes principal identities but no value is selected, read, created, or changed |
| Exact target/deployment authority | D2 names a proposed target; creation/deployment still requires separate D3 approval |
| Live store/service proof | Not claimed by design or existing contract tests |
| Horizon execution | No production Horizon path or agent is activated |
| Parked Surreal deployment | Not contacted, altered, renamed, reused, or treated as disposable |
| Corpus/data authority | T0 synthetic only; T1/T2 require source-level approval |
| Graphiti replacement | Baseline remains; no cutover or retirement authority |

## 6. Residual risks after a passing slice

- A tiny T0 slice cannot prove production-scale recall, latency, operational recovery, or corpus
  heterogeneity.
- Test doubles cannot prove PostgreSQL outbox, live promotion, or deployment behavior.
- Synthetic locators and derivative families may be cleaner than real-world provenance.
- Model nondeterminism limits bit-for-bit agent replay even when eligible state is reproducible.
- Shared-Context safety remains adapter- and feature-specific; a future cache/profile feature can
  reopen the boundary.
- Graphiti parity on a micro-slice cannot determine replacement value.
- Passing Phase 1 creates evidence for another owner decision, not implementation momentum or
  implied production authority.
