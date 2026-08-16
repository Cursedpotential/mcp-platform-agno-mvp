# Pending Owner Decisions — Surreal Investigation Phase 0

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Status:** PENDING OWNER RULING — compact review packet only
> **Authority:** Not an ADR; no schema, migration, activation, corpus copy, or deployment authority.

## Answer first

Six decisions block the disposable Phase-1 design. The recommended compact ruling is:

`S1–S6 recommended. Keep every R9 activation hold. Defer E1–E5 to measured gates.`

The recommendations use tribunal-style reasoning for hard-to-reverse isolation/authority choices
and pre-mortem checks for their failure behavior.

## S1 — As-lived retrieval boundary

### Verdict

**Recommended:** once the disposable slice proves parity, the as-lived walk gets evidence and
memory only through its immutable, reconciled Surreal context. PostgreSQL may supply canonical
control/approval metadata, but the walk cannot fall back to broad Weaviate, Neo4j, PostgreSQL
evidence search, or another run's memory.

**Alternative:** federate every store directly under a common HorizonContext.

**Confidence:** Medium.

**Reasoning:** exclusive context access creates one auditable contamination boundary. Federation
reduces projection lag but multiplies filter/compiler/fallback paths. Because Surreal is still
experimental, no production agent binding follows from this ruling; Phase 1 first proves the
reconciled slice.

**What would change this:** Surreal cannot meet recall/reconciliation/availability gates, while a
federated implementation proves identical immutable membership and zero leaks on every adapter.

## S2 — Physical isolation shape

### Verdict

**Recommended:** use a new disposable Surreal environment/database for the spike; never touch the
parked legacy deployment. Within it, require `matter_id` on all case material and a distinct
context namespace per walk/run/agent role. Do not create one database per Matter for the current
single-owner MVP; reevaluate for multi-tenant use.

**Alternative:** one shared context or one database per Matter immediately.

**Confidence:** Medium.

**Reasoning:** one shared context cannot prevent silent cross-run contamination. Database-per-Matter
adds lifecycle/operations before the single-owner product needs it. Environment isolation plus
mandatory Matter and run-role namespaces gives the disposable slice a testable middle boundary.

**What would change this:** a Surreal permission/namespace limitation prevents reliable row/context
isolation, or a multi-owner requirement arrives before Phase 1.

## S3 — Revocation, mismatch, and outage behavior

### Verdict

**Recommended:** promotion correction/revocation is append-only. It marks affected projection
objects ineligible, quarantines the context, and triggers reconciliation/rebuild. Hash mismatch,
missing membership, stale revision, or Surreal outage blocks/pauses the as-lived walk. There is no
automatic fallback to broader evidence stores.

**Alternative:** serve stale state with a warning or fall back to canonical/broad retrieval.

**Confidence:** High.

**Reasoning:** stale/fallback retrieval creates a silent future-fact path; a blocked run is visible
and recoverable. Prior projection history remains auditable without becoming searchable.

**What would change this:** only an owner-approved explicitly non-evidentiary degraded mode that is
technically unable to persist beliefs, findings, summaries, or exports.

## S4 — Candidate claims in walk memory

### Verdict

**Recommended:** the walk may record its own uncertain candidate belief only when derived solely
from horizon-eligible inputs and labeled as candidate/uncertain. It may not import corpus-wide
candidate claims or Semantica findings created with a broader horizon. Those belong to a separate
investigation role until reviewed.

**Alternative:** bar all candidates from walk memory, or expose all labeled candidates.

**Confidence:** Medium.

**Reasoning:** barring the walk's own hypotheses makes belief reconstruction artificial; exposing
broader candidates launders hindsight into the ignorant experience. Origin HorizonContext and
uncertainty must travel with the belief event.

**What would change this:** tests show agents systematically treat labeled candidates as facts, in
which case candidate storage should remain outside walk memory.

## S5 — Uncertain realization time

### Verdict

**Recommended:** preserve an uncertainty interval and use its latest plausible bound for as-lived
eligibility unless an approved realization event supplies a defensible point. Never substitute
recorded/ingested time or silently choose the earliest bound.

**Alternative:** earliest-bound eligibility or a guessed midpoint.

**Confidence:** High.

**Reasoning:** the latest bound is conservative against contamination. It may delay a fact in the
ignorant walk, but that limitation is explicit; the alternatives can reveal it too early.

**What would change this:** authenticated evidence narrows the realization time, creating a new
approved realization event/revision.

## S6 — Independent corroboration

### Verdict

**Recommended:** derivative copies sharing custody/content lineage count as one source family until
review proves independence. Dossiers display raw hit count and independent-source count separately.

**Alternative:** count each file/message/export as independent corroboration.

**Confidence:** High.

**Reasoning:** duplicate exports, forwarded messages, screenshots, and quoted threads otherwise
inflate support and can turn one assertion into apparent corroboration.

**What would change this:** provenance proves independent observation/creation despite later shared
content lineage.

## Explicit deferrals — no ruling needed for Phase 1

| ID | Decision | Safe disposition |
|---|---|---|
| E1 | Named vectors versus profile-specific collections | Keep current profile-specific isolation until bake-off |
| E2 | Embedding/reranking/chunk profiles | Select by gold-corpus results, not vendor tables |
| E3 | Behavior taxonomy, discovery budgets, and lens calibration | Hold until Phase 5 design and labeled corpus |
| E4 | TraceIQ precision/retention/geo inference | Hold until Phase 6 |
| E5 | Graphiti replacement and official Spectron adoption | Graphiti stays baseline; decide after measured Phase 7 bake-off/license review |

Case Prep transformation remains draft-only under the accepted conduct-first boundary. Its exact
approval workflow is a later mutation decision and does not block the disposable source/span,
claim/dossier/fact, and walk-memory slice.

## Review effect

Approving S1–S6 authorizes recording the decisions in the decision log/ADRs and refining the
**disposable** Phase-1 design. It does not authorize:

- applying migrations `0026`–`0030` or creating a production migration;
- activating or altering the parked Surreal deployment;
- copying any real corpus or exposing full normalized text;
- deploying services or binding a production/as-lived agent;
- replacing Graphiti, Weaviate, Neo4j, or PostgreSQL;
- skipping the synthetic and later live planted-future-fact gates.
