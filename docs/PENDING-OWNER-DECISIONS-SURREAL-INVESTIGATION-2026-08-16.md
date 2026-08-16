# Owner Decisions — Surreal Investigation Phase 0

> _Byline: Codex · GPT-5 · 2026-08-16 · rulings synchronized 2026-08-16_
>
> **Status:** ACCEPTED BY OWNER 2026-08-16 — S1–S6 resolved
> **Authority:** Not an ADR; no schema, migration, activation, corpus copy, or deployment authority.

## Answer first

The owner resolved all six decisions through a hyperfocused one-at-a-time review:

`S1 A · S2 B · S3 A plus immutable historical snapshots/rewalk · S4 A · S5 C plus
mandatory HITL clarification · S6 A.`

Every R9 activation hold remains in force. E1–E5 remain deferred to measured gates.

## S1 — As-lived retrieval boundary

### Verdict

**Accepted:** once the disposable slice proves parity, the as-lived walk gets evidence and
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

**Accepted:** use a new disposable Surreal environment for the spike; never touch the parked
legacy deployment. Within it, use one shared Surreal Context for the product/environment world.
Require `matter_id` on case material, represent each execution with first-class `walk` and
`walk_step` records, and bind experiential beliefs/observations to `walk_id`. Promoted evidence
and facts are stored once rather than duplicated per walk.

**Rejected alternatives:** a distinct Context/namespace per walk/run/role, or one database per
Matter immediately.

**Confidence:** High after owner clarification and review against the documented Spectron
Context/scope/session model.

**Reasoning:** a Context partitions a product/environment world; scopes partition shared material
within it, while walk records represent platform-specific horizon execution. The corpus remains
single-copy. Safety comes from mandatory Matter, walk, horizon, projection-revision, and policy
predicates on experiential reads/writes plus walk-aware caches, profiles, consolidation, and
prompt assembly. Any Context-wide facility that cannot prove those bindings is barred from the
as-lived path.

**What would change this:** live tests prove cross-walk bleed cannot be prevented at every stateful
surface, or a future product/environment requires absolute world isolation.

## S3 — Revocation, mismatch, and outage behavior

### Verdict

**Accepted:** promotion correction/revocation is append-only. It marks affected projection
objects ineligible, quarantines the affected Matter/projection revision, and triggers
reconciliation/rebuild. Hash mismatch,
missing membership, stale revision, or Surreal outage blocks/pauses the as-lived walk. There is no
automatic fallback to broader evidence stores. Before repair, the system seals an immutable,
read-only walk snapshot containing the exact horizon, manifests/hashes, belief state, context and
decision traces, versions, and failure cause. After refresh it starts a new walk linked by
`rewalk_of` and produces a before/after experiential delta. The old snapshot is replayable but
never active retrieval state.

**Alternative:** serve stale state with a warning or fall back to canonical/broad retrieval.

**Confidence:** High.

**Reasoning:** stale/fallback retrieval creates a silent future-fact path; a blocked run is visible
and recoverable. Prior projection history remains auditable without becoming searchable.

**What would change this:** only an owner-approved explicitly non-evidentiary degraded mode that is
technically unable to persist beliefs, findings, summaries, or exports.

## S4 — Candidate claims in walk memory

### Verdict

**Accepted:** the walk may record its own uncertain candidate belief only when derived solely
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

**Accepted:** preserve the uncertainty interval and compute its midpoint only as a proposal.
Mandatory HITL clarification must approve the midpoint, select another evidence-supported point,
narrow the interval, or leave it unresolved. Until approval, the proposal is not eligible for
as-lived retrieval. Never substitute recorded/ingested time.

**Rejected alternatives:** silently use the earliest/latest bound or an unreviewed guessed point.

**Confidence:** High for the review boundary; empirical calibration of reviewer guidance remains.

**Reasoning:** the full interval preserves uncertainty while the midpoint gives the reviewer a
clear starting proposal. Mandatory cited review prevents an estimate from being laundered into a
fact or horizon timestamp.

**What would change this:** authenticated evidence narrows the realization time, creating a new
approved realization event/revision.

## S6 — Independent corroboration

### Verdict

**Accepted:** derivative copies sharing custody/content lineage count as one source family until
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

The S1–S6 rulings authorize recording the decisions in the decision log/ADRs and refining the
**disposable** Phase-1 design. It does not authorize:

- applying migrations `0026`–`0030` or creating a production migration;
- activating or altering the parked Surreal deployment;
- copying any real corpus or exposing full normalized text;
- deploying services or binding a production/as-lived agent;
- replacing Graphiti, Weaviate, Neo4j, or PostgreSQL;
- skipping the synthetic and later live planted-future-fact gates.
