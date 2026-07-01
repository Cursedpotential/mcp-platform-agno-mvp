---

## Appendix: Open critic findings still requiring human attention

Three independent critics reviewed the package: completeness (`review/completeness.md`), court-safety /
blank-slate (`review/court_safety.md`), and gap/staleness (`review/gap_staleness.md`). The staleness axis came
back **clean** (no superseded decision is silently inherited — see the Staleness summary above), and the
court-safety reviewer judged the package "unusually court-safety-aware" overall. The items below are what
those reviews flagged as **substantive and unresolved** — they were deliberately **not** rewritten during
assembly (per the no-invention rule) and require a human decision before this design is used to produce any
output about a real case. One mechanical fix *was* applied inline: the single real child-name in a §3
illustration was scrubbed to `[MINOR_1]`/`[PARTY_B]`.

### F — Court-safety findings (from `review/court_safety.md`) — highest priority

- **F1 (CRITICAL) — Conclusory/legal-conclusion vocabulary is hard-coded into schema enums and field names.**
  `analysis.finding.pattern_category` (`medical_neglect`, `character_assassination`,
  `false_claims_third_parties`, `court_order_manipulation`, `parenting_time_interference`, …) and
  `analysis.reactive_context` field names (`parental_identity_attack_indicator`,
  `gaslighting_context_indicator`, `weaponized_reaction_indicator`, `vulnerability_trigger_type='child_as_leverage'`)
  *are themselves the conclusion* — there is no neutral observable layer beneath the loaded term. HITL gates
  *promotion to court* but the internal record can only name the adverse conclusion, which is a
  defamation/prejudice exposure if reached in discovery and pre-frames the reviewer. **Recommended fix
  (substantive — not applied):** introduce a two-layer vocabulary — a neutral `observation_descriptor`
  (what is literally seen) distinct from a `proposed_characterization` that exists only inside the gated
  analysis/legal lane, never as a bare category on a finding/event/person. *Refs: §3 §8.2/§8.3, §6, §10, §13.*

- **F2 (HIGH) — `love_bombing`/`escalation` as `timeline.event.event_type` leaks an analytical
  characterization into the extracted-fact event spine** and conclusorily labels positive conduct. This
  breaches the package's own core invariant (the event spine carries facts, not interpretation) and
  *weaponizes* the positive record, undercutting both-parties fairness. **Recommended fix:** restrict
  `event_type` to neutral kinds; move `love_bombing`/`escalation`/`repair` to the HITL-gated
  `analysis.relational_classification`; add a CHECK forbidding interpretive `event_type` on `extracted`-tier
  events. *Refs: §3 §4.1/§0.1, §11 Phase 9.*

- **F3 (HIGH) — Both-parties / full-relational-cycle modeling is promissory while the partner-adverse
  machinery is adopted-and-ready.** The adverse tooling (`detection_patterns.py` 256-pattern/DARVO,
  `behavioral_patterns.ttl`, `seed-patterns.ts ~303`, hurtlex, salem `USED_TACTIC`/`EXPLOITED_VULNERABILITY`/
  `DISPARAGES`) is concrete now; the counterweight is essentially a single `positive_behaviors.ttl` plus
  not-yet-built `:CyclePhase`/`:REACTION_TO`/`:CONTRASTS_WITH` constructs. The system will surface far more
  adverse than positive/own-conduct candidates, skewing the (single, fatigue-prone) reviewer queue.
  **Recommended fix:** treat the positive/neutral/repair/own-conduct detector lane as a **build-time
  prerequisite at parity** with the adverse lane (not a Phase-D add-on), and make the R11 "one-sided cycle"
  check **structural** (gate adverse-finding court-eligibility on same-window cycle/context modeling) rather
  than advisory. *Refs: §6 §14.1, §3 §14.1, §11 Phase 14, §14 I, §15 R-LEG-2.*

- **F4 (HIGH) — Real, sensitive case facts embedded as given anchors/illustrations; worked examples default
  to a partner-adverse narrative.** The real child's name and specific vulnerability facts (deceased mother /
  grief, a child illness, "she moved") appear as schema illustrations and `vulnerability_trigger_type` values,
  and the marquee worked examples are predominantly adverse-to-partner. **Partial inline fix applied:** the
  one literal child-name occurrence in §3 was scrubbed to `[MINOR_1]`/`[PARTY_B]`. **Still open
  (substantive):** scrub remaining sensitive specifics from all illustrative material; balance worked
  examples with at least one where the evidence undercuts the *user's own* framing and one neutral/positive
  example. *Refs: §3 §5.2/§8.2, §8 §6.2/§6.7, §9 §12, §12 §14.13.*

- **F5 (HIGH, blank-slate carryover) — Person-level `is_flagged` boolean and the "watchlist /
  problematic_locations_contacts" construct label a human as flagged/problematic, ungated and
  evidence-unlinked.** Unlike findings, `is_flagged` is a bare conclusory attribute on the person record with
  no evidence link, lane, confidence, or review gate — adopted from TraceIQ *without court-safety
  remediation*. **Recommended fix:** remove `is_flagged` as a bare person attribute; express any concern only
  as an evidence-linked, lane-typed, HITL-gated `analysis.finding` about specific conduct; redesign the
  watchlist as an evidence-gathering-task construct (already present in §12), not a person/contact denylist.
  *Refs: §3 §3.1, §13 R10, §10 §2.8.*

- **Secondary court-safety notes:** "reactive abuse" as a *system-proposed* label is clinically contested —
  prefer "reaction in temporal context" and let a human supply clinical framing (§1 §1.3.3, §13 R1, §14 I);
  a `medical_neglect` finding against a parent should require the strongest (dual) review, not the standard
  gate; the §3 lane-invariant CHECK enforces tier-vs-review on *promotion* but not on *vocabulary* (the F1/F2
  hole). The reviewer also credited genuine strengths to preserve: the GPS-vs-stated example that refuses
  "she lied" (§8 §6.7), the bitemporal interpretation-revision/self-blame model, the `explanation_vs_excuse`
  field + anti-self-justification trigger (§13 R9), and append-only "preserve prior interpretations."

### A — Gap-coverage residual misses (from `review/gap_staleness.md` §C) — "Lost" expansions

- **A-1 — Email is not a first-class evidence source type.** §1 G1 lists emails in scope but §10 has no Email
  extraction subsection (EML/MBOX/PST headers, threading, attachments, SPF/DKIM sender-auth). A whole evidence
  class has no extraction contract. *Decision needed: add an Email source-type subsection.*
- **A-2 — Alpha forensic-DB table survivors flagged "re-verify" but never mapped.** `bertConfigs`,
  `severityWeights` (the natural donor for §13's 10-axis scoring), `schemaResolvers` (distinct from the
  `schema-resolver.ts` tool), `forensicResults`, `patternCategories`, `hurtlexTerms/Categories`, plus the
  Drizzle `production-message` schema and the SQL deployment files. *Decision needed: confirm which exist on
  the live box and map the survivors.*
- **A-3 — SBV SMS-Backup&Restore cluster and 4GB-capable streaming-XML ingest are dropped.** The draft names
  in-memory parsers but carries no streaming/large-dump design; a real SMS backup can be multi-GB. Off-the-
  shelf SBV reuse (minimize-custom-code rule) is not considered. *Decision needed: adopt streaming ingest.*
- **A-4 — `normalized_messages` (raw-JSON landing) vs TraceIQ typed `messages` conflict is deferred, not
  resolved.** "Both: raw landing → typed projection" is proposed but every instance ends in needs-review
  rather than locking field-merge rules (esp. platform-hop reconstruction + blocked-call type 5/6). *This is
  the one known data-model conflict left open — see also Conflicting / B-1.*
- **A-5 — TraceIQ DuckDB analytical-views layer and `data_quality_metrics`+`trig_quality_check` are lost.**
  Completeness critic verified 0 hits for `vw_place_analytics`, `vw_route_patterns`, `vw_bouncy_trips`,
  `vw_overnight_activity`, `vw_city_summary`, and `data_quality_metrics`. Several are low-cost re-adopts.
  *Decision needed: re-adopt as adapted analytical-lane views / quality-audit pattern.*
- **A-6 — No as-deployed DDL verification.** The entire design is paper-only against an unverified live stack;
  `claude-context` is unindexed so even a code-level confirmation pass was not run. The draft correctly and
  repeatedly *flags* this (§11, §15 R-ST-5/6, §19) but does not reconcile any schema against the running
  `agno-postgres:18-duckdb` / Milvus / Neo4j DDL. **This is the single biggest cross-cutting blind spot.**
  *Lesser notes:* doc-intelligence `summaries`/`keywords` dropped from the adopted set; Semantica's
  conflict-detection/PROV-O model mapped only loosely (§11 P15); R5's two byte-identical copies flagged for
  dedupe but not yet extracted.

### B — Open conflicts (from gap/staleness + completeness)

- **B-1 — `normalized_messages` vs typed `messages` field-merge rules** remain unlocked (see A-4). Resolved in
  *principle* (raw landing → typed projection) but not in *rules*.
- **B-2 — README ADR index still labels ADR-0003 "Accepted."** The design recommends fixing it to "Superseded
  by 0013/0014/0027" (§21, §19, §15) but the fix is **not yet applied to the README** — it lives outside this
  document. *Action: edit the README ADR index.*

### C — Completeness / structural notes (from `review/completeness.md`)

- **C-1 — Deliverable count: 21 produced vs the master prompt's 23.** Sections 01–21 map to deliverables
  1–21. The Post-Scan Merge Report (now supplied in the front section) covers one; the second cross-cutting
  deliverable could not be confirmed because the literal 23-item MP list is not on disk (it lives only in the
  orchestrator transcript). Candidate missing artifacts with **no dedicated section**: a glossary, a
  standalone data dictionary, an access-pattern/query catalog, or an open-questions/assumptions register
  (the last partly exists as §15). *Action: orchestrator reconcile against the literal MP list.*
- **C-2 — Weakly-covered crosswalk rows at risk of silent loss** (1–2 grep hits): `flagged_entity` /
  `problematic_locations_contacts`, `multi_device` device-attribution, and the named raw-export JSON
  contracts (`google_timeline_schema.json`, `master_enriched_locations_schema.json`). Confirm these are
  intentionally folded vs accidentally dropped.
- **C-3 — Batch-drift check.** Sections 07/08/11 were drafted in an earlier batch than the rest; the
  completeness critic flagged verifying they reflect later cross-section decisions (notably the
  `normalized_messages`-vs-typed-`messages` reconciliation settled in §21). Structurally complete; content
  cross-check recommended.

### How to use this appendix

Treat **F1–F5** as blocking for any court-facing use, **A-1…A-6 / B-1** as the data-model/ingestion backlog to
close before the schema is built against the live boxes, and **B-2 / C-1…C-3** as housekeeping for the
orchestrator and SSOT maintainers. None of these were invented during assembly — each traces to a named
critic finding in `review/`.

---

> _End of document. DRAFT — human review required before any use. Assembled by Claude Code · Opus 4.8 (1M) · 2026-06-30 from 21 section drafts + 3 critic reviews, grounded in `discovery/CONTEXT_PACK.md` and `discovery/GAP_AND_STALENESS_REPORT.md`._
