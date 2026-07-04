# Court-Safety & Blank-Slate Critique — Forensic DB Architecture

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Reviewer role: COURT-SAFETY & BLANK-SLATE critic. Scope: CONTEXT_PACK + sections 01–21.
> Verdict orientation: The package is *unusually* court-safety-aware (five-lane discipline, HITL
> gating, append-only provenance, bitemporal honesty, both-parties guardrails are all genuinely
> present and well-engineered). The findings below are the places where, **despite** that care, the
> design still (a) bakes conclusory/inflammatory language into the data model itself, (b) lets
> analytical/legal characterizations leak into the "fact" lanes, (c) leaves the both-parties /
> full-cycle modeling as *promissory* while the partner-adverse machinery is adopted-and-ready, or
> (d) treats sensitive case facts as given. Each is a real residual risk, not a restatement of a
> gap the package already neutralizes.

---

## SEVERITY-RANKED FINDINGS

### F1 — Conclusory / legal-conclusion vocabulary is hard-coded into schema enums and field names (CRITICAL, non-court-safe language)
**Where:** `03-canonical-data-model.md` §8.3 (`analysis.finding.pattern_category` enum) and §8.2
(`analysis.reactive_context` columns); echoed in `06` edge types and `10`/`13` label sets.

The controlled vocabulary the system can express is itself the conclusion — there is no neutral
observable layer beneath the loaded term. Examples baked into the enum / column names:
- `pattern_category`: `medical_neglect`, `character_assassination`, `false_claims_third_parties`,
  `court_order_manipulation`, `parenting_time_interference`, `substance_child_safety`,
  `financial_or_housing_manipulation`. Several are **legal conclusions** (`medical_neglect` is a
  judicial finding of neglect; `parenting_time_interference` is a legal characterization) or presume
  falsity/intent (`character_assassination`, `false_claims_third_parties`).
- `reactive_context` field *names*: `parental_identity_attack_indicator`,
  `child_access_pressure_indicator`, `alienation_context_indicator`, `gaslighting_context_indicator`,
  `weaponized_reaction_indicator`, and `vulnerability_trigger_type='child_as_leverage'`.

**Why it survives the HITL gate:** HITL controls *promotion to court*, but the internal record can
only ever name the adverse conclusion. A detector row `pattern_category='medical_neglect'` /
`finding_kind='hypothesis'` against a named parent — even unreviewed and never exported — is a
defamation/prejudice exposure if the database is ever reached in discovery, and it pre-frames the
human reviewer toward the conclusion the field already states. Court-safe design separates the
neutral descriptor ("records relating to a medical appointment", surface observable) from the
conclusory label ("neglect"); this model collapses them. **Recommend:** a two-layer vocabulary — a
neutral `observation_descriptor` (court-safe, what is literally seen) distinct from any
`proposed_characterization`, with the characterization layer existing only inside the gated
analysis/legal lane and never as a bare category on a finding/event/person.

### F2 — `love_bombing` / `escalation` as `timeline.event.event_type` leaks an analytical-lane characterization into the EXTRACTED-fact event spine, and labels positive conduct conclusorily (HIGH; lane-discipline + fairness)
**Where:** `03` §4.1 (`timeline.event.event_type` enum includes `love_bombing`, `escalation`,
`repair_attempt`, `positive_interaction`); `11-multipass-workflow.md` Phase 9 ("An event is still an
extracted fact ... it carries no relational interpretation yet"); `03` §0.1 `cycle_phase` enum.

The package's own core invariant is that the event spine carries facts, not interpretation
(Phase 9, lane-flow §02 §4.3). But `event_type='love_bombing'` / `'escalation'` ARE relational
interpretations — characterizations of intent — sitting on rows whose `data_tier` is `extracted` or
`inferred`. The lane-invariant CHECK in §13 enforces tier vs `model_id`/review on findings, but does
**not** prevent a conclusory `event_type` on an extracted-tier event. So the one structural property
the whole package exists to provide (fact ≠ characterization) is breachable at the timeline level.

Separately, `love_bombing` is a *sensitive, intent-presuming* label: it reframes affection as
manipulation. The "model the full relational cycle" guardrail exists so positive/neutral conduct is
preserved **neutrally** as context/contrast — coding positive interactions as "love_bombing" is the
opposite of neutral and actually *weaponizes* the positive record, undercutting the both-parties
fairness goal. **Recommend:** restrict event_type to neutral kinds (`message_exchange`,
`exchange_handoff`, `affectionate_interaction`); move `love_bombing`/`escalation`/`repair` to the
HITL-gated `analysis.relational_classification` only (where `requires_human_review` already
defaults true), and add a CHECK forbidding interpretive event_types on `extracted`-tier events.

### F3 — Both-parties / full-relational-cycle modeling is PROMISSORY; the partner-adverse machinery is adopted-and-ready (HIGH; "fails to model the full relational cycle / user's own conduct" at parity)
**Where:** `06` §14.1, `03` §14.1, `11` Phase 14, `14` I, A-11/R-LEG-2 in `15`.

The package repeatedly concedes "salem_v3 models **only** adversarial conduct," and the balancing
constructs — `:CyclePhase`/`:REACTION_TO`/`:CONTRASTS_WITH`, `conduct_party`, `positive_behaviors.ttl`
mapping — are flagged **"needs owner sign-off," "must extend," not yet built.** Meanwhile the adverse
tooling is concrete and adopted *now*: `detection_patterns.py` (256-pattern, DARVO),
`behavioral_patterns.ttl`, `seed-patterns.ts (~303)`, `hurtlex`, and salem's
`USED_TACTIC`/`EXPLOITED_VULNERABILITY`/`DISPARAGES`. The counterweight is essentially a **single**
`.ttl` of positive behaviors. Net effect: the system will surface vastly more adverse candidates than
positive/repair/own-conduct ones, skewing the (single, fatigue-prone — R-HR-2 rated *Critical*)
reviewer's queue toward the partner-adverse narrative. The "model the user's own conduct" requirement
is then met largely by *running the same adversarial detectors on the user's own messages*
(`risk_kind='self_incrimination'`) — fairness of a punitive kind, not genuine parity of positive vs
negative modeling. The R11 ("one-sided cycle modeling") review trigger is a real mitigation but is a
*detection-of-imbalance* check layered on top of a structurally imbalanced detector set.
**Recommend:** treat the positive/neutral/repair/own-repair detector lane as a **build-time
prerequisite at parity with the adverse lane** (not a Phase-D add-on), and gate any partner-adverse
finding's court-eligibility on the presence of same-window cycle/context modeling (make R11
structural, not advisory).

### F4 — Real, sensitive case facts (child's name, deceased-mother/grief, "she moved") are embedded as given anchors/illustrations and the worked examples default to a partner-adverse narrative (HIGH; allegation-as-context-fact + privacy)
**Where:** `03` §5.2 (`temporal.anchor` example "when Kailah was sick"); `03` §8.2
`vulnerability_trigger_type='deceased_mother_reference'`, `grief_trigger_indicator`; `08` §6.2/§6.7
("after she moved", GPS-contradicts-"I was at home all evening"); `09` §12 step-4
("love-bombing→devaluation cycle").

Two problems. (1) **Sensitive specifics treated as established:** the design uses the real child's
name and specific vulnerability facts (a deceased mother, a child illness) as schema illustration and
as `anchor`/`vulnerability_trigger` values. Section `14` J states vulnerability data is tracked "only
where evidence supports," yet these appear as *given*. Even labeled "illustrative," embedding the real
child's name and grief facts is itself a privacy lapse and risks the scaffolds being read as asserted
findings. (2) **Adverse-default framing:** the marquee worked examples are predominantly
partner-adverse scenarios ("she was at home all evening" contradicted by GPS; "love-bombing
→devaluation"). Each is carefully captioned and the GPS one commendably refuses "she lied" — but the
*cumulative* choice of the adverse-to-partner case as the canonical illustration models the system's
default posture as adverse, the very one-sidedness the guardrails forbid. **Recommend:** scrub real
identifiers from all illustrative material (use `MINOR_x`, `PARTY_B`); balance worked examples with
at least one where the gathered evidence **undercuts the user's own framing** (Example B in `12`
§14.13 does this — make it the norm, not the exception) and one neutral/positive-cycle example.

### F5 — Person-level `is_flagged` boolean and the "watchlist / problematic_locations_contacts" construct label a human as flagged/problematic, ungated and evidence-unlinked (HIGH; prejudicial, blank-slate carryover)
**Where:** `03` §3.1 (`entity.person.is_flagged`, "adopts TraceIQ"); `13` R10 ("Watchlist / alert
severity ... `severity`, `reason_flagged` from split `problematic_locations_contacts`"); `10` §2.8
(stalking/surveillance pattern lane).

Unlike findings (evidence-linked, tiered, HITL-gated), `is_flagged` is a **bare conclusory attribute
on the person record** with no specified evidence link, lane, confidence, or review gate, carried
over verbatim from TraceIQ without a court-safety re-think (a blank-slate-carryover failure: prior
work adopted *un-remediated*). A "problematic contacts watchlist" and a person row reading
`is_flagged=true` are surveillance-flavored, person-level characterizations; "the system flagged
her/him as problematic" is prejudicial and impeachable if reached in discovery, and it characterizes a
**human** rather than a piece of evidence. **Recommend:** remove `is_flagged` as a bare person
attribute; express any concern only as an evidence-linked, lane-typed, HITL-gated `analysis.finding`
about specific conduct, never as a standing label on the person; rename/redesign the watchlist lane
to an evidence-gathering-task construct (it already exists in `12`) rather than a person/contact
denylist.

---

## SECONDARY OBSERVATIONS (lower severity, noted for completeness)

- **"reactive abuse" as a system-proposed label** (`01` §1.3.3; `13` R1; `14` I): the term itself is
  clinically contested and non-court-safe; even as a gated hypothesis, having the system *propose* it
  invites a characterization courts and evaluators view skeptically. Prefer "reaction in temporal
  context" descriptors and let a human supply any clinical framing.
- **`medical_neglect` / `substance_child_safety` detector categories** can surface
  mandatory-report-adjacent content; the CSAM tripwire (`14` B.4) is excellent, but a
  `medical_neglect` *finding against a parent* is a serious conclusory label that should require the
  strongest (dual) review, not the standard finding gate.
- **Lane-invariant CHECK gap** (`03` §13): the enforced CHECK covers `raw` having no `model_id` and
  `legal_conclusion` requiring an approved review — good — but nothing structurally stops a conclusory
  `event_type`/`pattern_category` value at the wrong tier (see F1/F2). The invariant is enforced on
  *promotion* but not on *vocabulary*.
- **Causation handled well** (`:CAUSED` is `hypothesis`-only, `08` §4.2, `06` §4) — credit where due;
  no finding.
- **Strengths worth preserving:** the GPS-vs-stated example explicitly refusing "she lied" (`08`
  §6.7), the bitemporal interpretation-revision/self-blame model (`03` §5.3, `08` §5), the
  `explanation_vs_excuse` field and R9 anti-self-justification trigger (`03` §8.2, `13` R9), and the
  append-only "preserve prior interpretations" discipline are all genuinely court-safe and should not
  be diluted in addressing the above.

---

## BLANK-SLATE CHECK (separate axis)
The package is **not** a blank slate and is exemplary on this axis: it adopts salem_v3, TraceIQ V4.1,
geo_v5, the doc-intelligence/Semantica provenance pattern, and the salvaged parser/pattern corpus,
with an explicit, queryable import/crosswalk lane (`03` §11–12). The one blank-slate *failure* is F5:
prior work (`is_flagged`, `problematic_locations_contacts`) was adopted **without court-safety
remediation**. The lesson generalizes — adoption should pass each donor field through a court-safety
filter, not just a schema-mapping filter.
