# Unresolved Questions — Surreal Investigation Phase 0

> _Byline: Codex · GPT-5 · 2026-08-16 · owner-ruling update 2026-08-16_
>
> **Status:** ACTIVE INVENTORY — S1–S6 questions resolved by D-064; remaining rows stay open
> **Default rule:** if a blocking question is unresolved, the dependent phase remains held.

## How to read this inventory

Questions are separated by decision owner and latest safe decision point. “Recommended hold” is
the behavior while unresolved; it is not an implicit architecture ruling. The companion owner
packet contains only the small subset that requires owner judgment now.

## Resolved by owner on 2026-08-16

The historical question rows remain below for traceability, but their former holds no longer
control. D-064 resolves them as follows:

| Questions | Resolution |
|---|---|
| UQ-01 | After parity, the as-lived walk reads evidence/memory only through reconciled Surreal; no broad-store fallback |
| UQ-02 | One shared Context per product/environment; Matter scopes plus first-class walk records and walk-bound experiential state |
| UQ-04, UQ-07 | Fail closed; seal an immutable historical snapshot, reconcile/rebuild, then begin a linked rewalk |
| UQ-08 | Walk-generated candidate beliefs are allowed only from horizon-eligible inputs and remain explicitly uncertain |
| UQ-16 | Count independent source families; report raw derivative hits separately |
| UQ-18 | Preserve the interval, propose its midpoint, require HITL clarification, and withhold until approval |

Physical tables, adapter behavior, reconciliation algorithms, and live proof remain unresolved
where separately routed below; the owner rulings do not authorize implementation.

| Class | Resolution route |
|---|---|
| Owner | Values, risk tolerance, authority, or product meaning; owner ruling required |
| Empirical | Gold-corpus bake-off or disposable spike; do not decide from vendor claims |
| Contract | Integration review against the Phase-0 logical contracts |
| Operational | Named target/credentials/deployment approval; never inferred from design approval |

## A. Historical Phase-0 blockers and remaining implementation questions

| ID | Question | Class | Latest safe point | Recommended hold while open | Evidence/decision needed |
|---|---|---|---|---|---|
| UQ-01 | May the as-lived walk retrieve evidence/memory only through its reconciled Surreal context, or may it federate directly to other stores? | Owner | Before Phase-1 adapter design | No as-lived agent read path | Owner selects isolation model; contract tests prove no fallback leak |
| UQ-02 | What physical isolation boundary separates environment, Matter, walk, run, and agent role in Surreal? | Owner | Before physical schema | No shared production namespace | Owner selects boundary; threat model and disposable isolation test |
| UQ-03 | How are contract/API versions negotiated and retired? | Contract | Before first adapter | One explicit experimental version; reject unknown versions | Compatibility matrix and golden serialization fixtures |
| UQ-04 | What is the canonical response to promotion revocation, correction, or hash mismatch in a projection? | Owner | Before projector implementation | Quarantine context and fail reads closed; never delete history | Owner accepts append-only invalidation/rebuild behavior |
| UQ-05 | What minimum promoted unit enters the Phase-1 slice? | Contract | Before fixture selection | Manifest plus selected approved spans only | One synthetic source fixture with exact locators and hashes |
| UQ-06 | Which reconciliation receipt/hash algorithm defines projection parity? | Contract | Before projector implementation | No “healthy” projection claim without exact membership/content reconciliation | Deterministic fixture and rebuild comparison |
| UQ-07 | What happens if Surreal is incomplete or unavailable during an as-lived walk? | Owner | Before any agent binding | Block/pause; do not fall back to broader stores | Owner selects fail-closed versus explicitly degraded non-evidentiary mode |
| UQ-08 | Are candidate claims allowed inside walk memory, and under what label? | Owner | Before walk-memory slice | Candidates may drive a separate investigation only; no canonical walk conclusion | Owner confirms separation of candidate leads and agent belief/fact state |

## B. Blocks Phase 2 retrieval and embedding work

| ID | Question | Class | Latest safe point | Recommended hold while open | Evidence/decision needed |
|---|---|---|---|---|---|
| UQ-09 | Weaviate named vectors or profile-specific collections? | Empirical/owner | Before Phase 2 | Preserve current profile-specific collection rule | Reindex cost, filter parity, operational isolation, and retrieval bake-off |
| UQ-10 | May walk-memory and promoted-corpus objects reuse an embedding profile? | Empirical | Before memory vectorization | Treat profiles as distinct | Domain/task bake-off and contamination analysis |
| UQ-11 | Which embedding/reranking profiles win for each source kind and question type? | Empirical | Before any model lock | No static vendor-table choice | Gold-corpus results with version, cost, latency, privacy, and storage |
| UQ-12 | How are incompatible spaces fused? | Contract/empirical | Before cross-profile search | Rank fusion plus reranking; never average raw similarity scores | RRF/reranker comparison and calibration report |
| UQ-13 | What chunk policies apply to legal, conversation, email, code, table, OCR, and geo inputs? | Empirical | Before bulk projection | Preserve structural atoms/exact locators; no universal chunker | Per-kind locator and retrieval evaluation |
| UQ-14 | What proves a store filtered before ranking/traversal? | Contract | Before adapter acceptance | Adapter ineligible for as-lived use | Explain/trace evidence plus planted-fact test at `k` |

## C. Blocks Phase 3 claim/fact implementation

| ID | Question | Class | Latest safe point | Recommended hold while open | Evidence/decision needed |
|---|---|---|---|---|---|
| UQ-15 | Exact physical schema for candidate claims, investigations, dossiers, facts, and evidence links? | Contract | After logical contract review | No production schema | Normalized design review and migration pre-mortem |
| UQ-16 | What constitutes an independent source versus a derivative copy? | Owner/contract | Before corroboration scoring | Group by custody/content lineage; do not count unresolved duplicates independently | Owner policy plus labeled derivative corpus |
| UQ-17 | Which actors may establish, qualify, contradict, supersede, or revoke facts? | Owner | Before mutation API | Owner/governed review only; agents propose | Auth/approval policy and audit contract |
| UQ-18 | How are uncertain event/realization times represented and scheduled? | Owner/contract | Before physical temporal schema | Preserve intervals/uncertainty; never invent a point timestamp | Owner policy for conservative as-lived eligibility |
| UQ-19 | What evidence-quality and authority floors vary by investigation intent? | Owner | Before investigator execution | Display all eligible classes but prohibit automatic establishment | Intent-specific review rubric |
| UQ-20 | How should “missing expected evidence” be represented without turning absence into proof? | Contract | Before dossiers | Mark as unresolved investigative gap | Review examples and wording rubric |

## D. Blocks Phase 4–5 Investigation Search and behavioral analysis

| ID | Question | Class | Latest safe point | Recommended hold while open | Evidence/decision needed |
|---|---|---|---|---|---|
| UQ-21 | Controlled behavioral-lens taxonomy, definitions, exclusions, and version owner? | Owner | Before behavior UI/agent | No production lens labels | Owner-reviewed taxonomy with non-diagnostic wording tests |
| UQ-22 | Default hop/result/time/context/model-cost budgets per intent? | Owner/empirical | Before outward discovery | Closed-set analysis only | Synthetic benchmark and owner-selected ceilings |
| UQ-23 | May discovery query generation use hindsight in an as-lived run? | Owner | Before paired mode | No; the as-lived side uses only visible material | Owner confirmation and query-trace leak tests |
| UQ-24 | What owner action admits discovered material into a scope revision? | Owner | Before scope revision API | Discovery remains separate | Explicit attributable accept/reject workflow |
| UQ-25 | What Case Prep transformation and approval path turns internal shorthand into conduct-first language? | Owner | Before export mutation | Draft-only; no court-safe status | Review workflow and wording corpus |
| UQ-26 | What is the acceptable false-pattern/abstention calibration by lens? | Empirical/owner | Before behavioral findings are relied upon | Findings remain candidates with limitations | Labeled positive/negative/ambiguous cases and owner threshold |

## E. Blocks Phase 6 TraceIQ projection

| ID | Question | Class | Latest safe point | Recommended hold while open | Evidence/decision needed |
|---|---|---|---|---|---|
| UQ-27 | Geo precision, uncertainty geometry, coordinate system, and retention policy? | Owner/contract | Before TraceIQ contract | No Surreal geo projection | PostGIS-authoritative contract and privacy review |
| UQ-28 | How are time-zone, device clock, interpolation, and impossible-travel uncertainty represented? | Contract | Before geo reconstruction | Preserve raw/normalized values and uncertainty; no silent correction | Gold trajectory fixtures and parity tests |
| UQ-29 | Which geo relationships may be asserted versus shown as correlations? | Owner | Before behavior/event use | Correlation/sequence only | Owner wording and evidence-quality policy |

## F. Blocks Graphiti/Surreal bake-off or optional cutover

| ID | Question | Class | Latest safe point | Recommended hold while open | Evidence/decision needed |
|---|---|---|---|---|---|
| UQ-30 | What measured threshold permits Graphiti replacement? | Owner/empirical | Before Phase 7 conclusion | Graphiti remains baseline | Owner accepts weighted gate; both systems run identical corpus/protocol |
| UQ-31 | Which Graphiti capabilities are mandatory: contradiction invalidation, communities, observations, custom types, provenance, as-of search? | Owner/contract | Before bake-off | Preserve all currently required contract behaviors | Capability checklist and observed live proof |
| UQ-32 | When may an official Spectron adapter be used? | Owner/operational | Before dependency adoption | Platform-owned implementation remains sufficient | Availability, license, export/rebuild, privacy, and parity review |
| UQ-33 | What retention/decommission evidence is required before removing a projection? | Owner/operational | Before any replacement | Keep service/data parked or quarantine files; never hard-delete | Counts, hashes, exports, rollback drill, owner approval |

## G. R9 activation holds carried unchanged

These are dependencies, not R10 questions, and Phase 0 does not resolve or weaken them:

| Hold | State |
|---|---|
| Migrations `0026`–`0030` | Unapplied; numerical ordering and owner approval required |
| Canonical custom-image baseline rehearsal | Outstanding |
| `WORKBENCH_API_KEY` and distinct service credential provisioning | Outstanding |
| Exact target apply/deployment authority | Not granted |
| Live Matter/Knowledge/Graphiti/Weaviate proof | Outstanding |
| R0/R2 replay and contamination defects | Horizon execution remains held |

## H. Decision routing summary

- **Resolved owner packet (D-064):** UQ-01, UQ-02, UQ-04, UQ-07/UQ-08, and
  UQ-16/UQ-18.
- **Later owner review:** UQ-17, UQ-19, UQ-21/UQ-22, UQ-24/UQ-25, and UQ-30.
- **Gold-corpus/bake-off:** UQ-09 through UQ-14, UQ-26, and performance aspects of UQ-30.
- **Post-contract implementation review:** UQ-03, UQ-05, UQ-06, UQ-15, UQ-17,
  UQ-19, UQ-20, and UQ-24.
- **Deferred to TraceIQ/optional cutover:** UQ-27 through UQ-29 and UQ-31 through UQ-33.
