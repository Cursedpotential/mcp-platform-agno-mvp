# Coercive Control vs. Ordinary Conflict — Classification Rubric & LLM Templates

> **Provenance:** owner-curated LLM playground session (external model), captured 2026-07-04.
> Saved as a design/knowledge resource for the behavioral-detection lane. This is
> NOT platform output and NOT case material — every example sentence below is SYNTHETIC.
> Curated knowledge input (see `AGENTS.md` → `knowledge/`); never contains secrets or PII.
>
> **Domain:** legal_strategy / behavioral analysis.
>
> **Why it lives here (cross-refs):**
> - The **reactive-vs-malicious** distinction maps directly onto the 0006 seed's court-safety
>   posture — `bias_caution`, symmetric application, hypothesis-not-conclusion
>   (`docs/planning/forensic-db-reconciliation/BEHAVIORAL_DETECTION_EXPLAINED.md`).
> - The **LLM analyzer prompt** + **JSON output shape** are the design for the Part-2
>   meta-analysis pass that sits ABOVE the deterministic Pass-1 scanner
>   (`evidence/detection.py`). Machine-usable extracts of this doc live at
>   `evidence/config/coercive_control_analyzer_prompt.md` and
>   `evidence/config/court_safe_language_map.json`.
> - The **judge-friendly / diagnostic-term-stripping** map feeds court-export
>   work (port-backlog #13, D7 legal-export domain).
> - The **expanded good/bad example pairs** are annotator/classifier calibration
>   material — candidate rows for a future `detection_pattern` calibration set.
>
> **Court-safety carried from source:** describe behaviors, never diagnose; never
> equate self-protection or trauma reactivity with malice; require pattern +
> instrumental intent + absence of repair before flagging; symmetric application
> across both parties (Kubicki v. Sharpe caveat).

---

## 1. Base Rubric: Coercive Control vs. Ordinary Conflict

### Decision Criteria
Classify a sentence as **Coercive Control** if it exhibits **two or more** of:
- **Asymmetrical power** — one party seeks to dominate, restrict, or isolate the other without reciprocal agency.
- **Instrumental intent** — behavior used as a tool to gain compliance, not to resolve disagreement.
- **Pattern-oriented** — implies repetition, habituation, or ongoing surveillance (even if only hinted at).
- **Fear/dependency induction** — aims to instill fear, shame, guilt, or learned helplessness.
- **Violation of autonomy** — controls access to resources, social ties, bodily autonomy, or perception of reality.

Classify as **Ordinary Conflict** if it exhibits:
- **Reciprocal engagement** — both parties express views, even angrily; no clear power imbalance in intent.
- **Issue-focused** — centers on a specific disagreement (chores, money, plans), not global control.
- **Temporal boundedness** — one-time or episodic, not part of a larger pattern.
- **Repair potential** — language allows apology, negotiation, or mutual understanding.
- **Absence of instrumental domination** — no attempt to isolate, surveil, or erode self-trust.

> Single sentences may be ambiguous; classification is probabilistic. Context (surrounding text, history) improves accuracy.

### ✅ Positive Examples (Coercive Control)
1. "You're not allowed to see your friends anymore — I know what's best for you, and if you disobey, I'll cut off your phone." → *isolation, instrumental threat, fear induction, autonomy violation.*
2. "I checked your messages again — you deleted that text from your sister. Why are you hiding things? You know I only do this because I love you." → *surveillance, gaslighting justification, patterned monitoring.*
3. "If you leave this house, I'll tell everyone you're unstable — and no one will take your kids. You'd be nothing without me." → *reputation/custody threat, dependency induction, isolation via fear.*

### ❌ Negative Examples (Ordinary Conflict)
1. "I'm upset you forgot our anniversary — I felt ignored, and I need you to make it up to me." → *issue-focused, invites repair, no power assertion.*
2. "You left the dishes again — can we talk about a chore chart? I'm tired of doing everything." → *specific grievance, proposes solution, reciprocal.*
3. "I raised my voice during the argument — I'm sorry. Let's take a break and revisit this when we're calmer." → *accountability, repair, emotional regulation.*

### Implementation Notes
- **Threshold:** ≥2 coercive markers (reduces false positives from isolated anger).
- **Ambiguity:** mixed/unclear markers → flag for human review.
- **Cultural sensitivity:** focus on *patterns of domination*, not intensity alone.
- **NLP features:** pronoun asymmetry ("you always" vs. "I feel"); modal obligation verbs ("must," "not allowed"); threat syntax ("if you… then I…"); isolation lexicon; gaslighting phrases.

---

## 2. Adapted Rubric: Coercive Control Involving a Child (Post-Separation)

Three-way classification — **Coercive Control (instrumental/malicious)** vs.
**Reactive/Trauma-Driven** vs. **Ordinary Post-Separation Conflict**. Misclassifying
trauma responses as malice retraumatizes survivors; missing true instrumental control
risks ongoing harm to child and parent.

**COERCIVE CONTROL (Instrumental/Malicious)** — two or more of:
- **Child as pawn/leverage** — custody, visitation, or the child's affection used to manipulate, punish, or isolate.
- **Legal system as weapon** — frivolous/repetitive filings, false allegations, misuse of orders to harass, surveil, exhaust.
- **Procedural abuse pattern** — repeated motions, unjustified supervision requests, appeals despite rulings.
- **Undermining parental authority** — alienation campaigns via false narratives, coaching, trust erosion ("Mom/Dad doesn't love you").
- **Fear/dependency via child** — threats to restrict access, flee with the child, or claim the child is unsafe *without evidence*.
- **Lack of child-centered language** — focus stays on the parent's rights/control/punishment, not the child's well-being.

**REACTIVE/TRAUMA-DRIVEN** —
- **Hypervigilance/protective urgency** from lived experience (documenting, resisting unsupervised contact from fear).
- **Emotional dysregulation** from prolonged exposure — not intent to dominate.
- **Reestablishing safety/boundaries** — limiting contact, demanding supervision, documenting exchanges (often misread as "hostile").
- **No instrumental patterning** — responsive, not orchestrated.
- **Reflection/remorse when safe** — may regret tone but stands by core safety concerns.

**ORDINARY POST-SEPARATION CONFLICT** — issue-specific, reciprocal frustration,
repair-oriented, temporally bounded, child referenced as a shared concern.

### ✅ Coercive Control (instrumental use of child/system)
1. "I'm filing for emergency custody again — you know the judge hates you, and this time I've got the school nurse saying you're neglectful. You won't see them until they forget what you look like." → *court weaponization, false allegation, bond-severance threat, patterned legal abuse.*
2. "Every time you try to take them on a weekend, I call CPS and say you were drinking. It's not my fault they keep investigating — maybe you should stop giving them a reason." → *false reports, patterned harassment, denial of responsibility, child as pawn.*
3. "I told the therapist the kids say you hit them — not that it matters, but if they start questioning you, good. Keeps you busy and away from my life." → *coaching to lie, instrumental system use, explicit harassment motive.*

### ❌ Reactive/Trauma-Driven
1. "I supervised every exchange for six months after he choked me in front of them — I'm not letting him alone with them until I see concrete proof he's changed, and even then, I want a mediator present." → *protectiveness from lived experience; not patterned control.*
2. "I keep a log of every time he shows up late or high — not to punish him, but because last time he took them driving drunk and I almost lost them. I'm terrified it'll happen again." → *hypervigilance from prior danger; safety-focused, not punitive.*
3. "I yelled at him at the drop-off because he brought them back bedtime-numb from screens and sugar — I know I overreacted, but after months of him ignoring our agreement, I just snapped." → *dysregulation + repair attempt; reactivity, not coercive intent.*

### ⚖️ Ordinary Post-Separation Conflict
1. "We disagreed on Halloween — I wanted them home by 7, he said 8:30. We'll split the difference next year." → *issue-specific, compromise-oriented.*
2. "He's late again picking them up — I'm annoyed, but I know his job's unpredictable. Can we just agree to text if running late?" → *frustration without power intent, solution-focused.*
3. "I miss having them full-time, but I know they love their dad. It's hard, but I'm trying not to badmouth him in front of them — even when he forgets soccer practice." → *child-centered, protects the relationship.*

### 🔍 Key Distinctions: Reactive vs. Malicious

| Dimension | Reactive/Trauma-Driven | Malicious Coercive Control |
|---|---|---|
| **Trigger** | Response to real/perceived threat (history-based) | Initiative to dominate, punish, reassert control |
| **Intent** | Self-protection, child safety, boundary reclamation | Dominance, punishment, exhaustion, alienation |
| **Pattern** | Episodic, context-bound, decreases with safety | Persistent, escalates post-separation, systemic |
| **Use of child** | Protective buffering | Instrumental leverage |
| **Use of court** | Defensive, rare, justified | Repetitive, frivolous, retaliatory |
| **Response to limits** | May regret tone; stands by safety need | Escalates; sees limits as personal attack |
| **Child's voice** | Rooted in observed behavior/history | Often coached, inconsistent, uncorroborated |
| **Remorse/insight** | Possible once safe; reflects on overreaction | Rare; blames victim, denies harm, self as persecuted |

> Reactive behaviors often **mimic** coercive control superficially (limiting contact, documenting) but differ in **origin, flexibility, and responsiveness to safety**. True coercive control **persists even when safety is established** and **escalates in response to accountability.**

### Annotation heuristic
> *"If the other parent were suddenly cooperative, safe, and child-focused — would this behavior decrease or stop?"* — **Yes** → likely reactive/conflictual. **No** → likely instrumental control.

---

## 3. LLM Analyzer Prompt (Longitudinal, Court-Oriented)

> The full, machine-loadable prompt lives at
> `evidence/config/coercive_control_analyzer_prompt.md`. Summary of design:

**Role:** forensic linguistic analyst; analyze a longitudinal exchange between User A
and User B over a defined period. Identify behaviors consistent with coercive control,
Cluster-B-associated traits (behavioral red flags, *not* diagnoses), and instrumental
use of systems or children — always separating **malicious/patterned** from
**reactive/trauma-driven** from **normative**.

**Output:** structured evidentiary report in plain language for a judge/referee/evaluator.
Observable patterns, context, frequency, impact. No clinical jargon without explanation.

**Per-category:** ≥2 contextualized examples (quote + date/sequence); frequency & patterning;
malicious/reactive/normative classification. Flag as "Evidentiary Concern" only on
(1) repetition, (2) instrumental intent, (3) lack of remorse/repair when challenged —
unless clearly reactive.

**Eight categories:** financial abuse/economic control · gaslighting/reality distortion ·
love bombing/discarding cycle · triangulation/isolation · instrumental use of the child ·
legal threats/procedural abuse · sexual degradation/weaponized intimacy · Cluster-B
behavioral indicators (non-diagnostic, incl. reactive responses that MIMIC them).

**Guardrails:** do not diagnose; do not pathologize anger/grief/assertiveness; prioritize
child safety and parental autonomy; state uncertainty explicitly and defer to a human
evaluator.

---

## 4. JSON Output Shape (Machine-Readable)

> Canonical schema: `evidence/config/court_safe_language_map.json` carries the
> category keys + court-safe headings; the analyzer emits this envelope:

```json
{
  "analysis_metadata": {
    "timestamp": "ISO-8601", "analyzer_version": "…", "message_count": 0,
    "date_range": {"start": "…", "end": "…"},
    "parties": ["User A", "User B"], "confidence_threshold": 0.7
  },
  "behavioral_categories": {
    "<category_key>": {
      "present": true,
      "examples": [{"quote": "…", "context": "…", "timestamp_relative": "…", "pattern_indicator": "…"}],
      "frequency": "N incidents over M months",
      "escalation_pattern": "…",
      "likely_intent": ["…"],
      "reactivity_assessment": "not_reactive — …"
    }
  },
  "summary_assessment": {
    "coercive_control_burden": "low|moderate|high",
    "patterned_use_of_child_as_tool": true,
    "patterned_use_of_legal_system": true,
    "financial_control_present": true,
    "sexual_extortion_present": true,
    "reactivity_risk_low": true,
    "recommended_next_steps": ["…"],
    "notes_for_judge": "…"
  }
}
```

Category keys: `financial_control`, `gaslighting_reality_distortion`,
`love_bombing_discarding_cycle`, `triangulation_isolation`,
`instrumental_use_of_child`, `legal_threats_procedural_abuse`,
`sexual_degradation_weaponized_intimacy`, `cluster_b_traits_behavioral_indicators`.

Design: every example carries context + timestamp + pattern indicator (auditability);
`reactivity_assessment` explicitly labels non-reactive/instrumental behavior;
**behavioral descriptors only — no diagnostic terms**.

---

## 5. Judge-Friendly Diagnostic→Court-Safe Translation

> Guiding principle: **replace interpretive labels with descriptive evidence.** Machine
> map: `evidence/config/court_safe_language_map.json`.

| Internal category | Court-safe heading |
|---|---|
| financial abuse | Use of Money to Influence Behavior |
| gaslighting | Undermining Confidence in Memory or Judgment |
| love bombing / discarding | Alternating Between Extreme Praise and Harsh Criticism |
| triangulation | Involving Others to Gather Information or Influence Perceptions |
| parental alienation / child weaponization | Using the Child to Deliver Messages or Express Negative Views |
| procedural abuse | Repeated Use of Legal or Protective Systems Without Basis |
| sextortion / sexual degradation | Using Private or Sexual Content to Pressure or Humiliate |
| narcissistic traits | Patterns of Avoiding Responsibility and Shifting Blame |

Rendering rules: observed behavior (quote + dates/frequency) → whether it responded to
provocation → intent via hedged phrasing ("appears intended to," "suggests a pattern of,"
"consistent with efforts to") → impact. Include **Notable Absences** (no repair, no
accountability, escalation at limits) and **Considerations for the Court**. Never output
diagnostic terms; never imply intent without behavioral evidence; rule-based phrasing for
high-certainty findings, LLM only for fluent summarization (never inference).

---

## 6. Expanded Example Pairs (Annotator/Classifier Calibration)

Labels: ✅ *Problematic (Instrumental/Patterned)* · 🟢 *Appropriate (Reactive/Normative/Protective)*.

### 💰 Financial Control / Economic Abuse
- ✅ "I shut off the auto-pay for the kids' insurance — you'll have to cover it now, or they go without." *(after a visitation-change request)* — essential child benefit as leverage; retaliatory.
- ✅ "I'm not paying for the summer camp deposit until you agree to let them stay an extra week with me." — routine expense turned bargaining chip.
- ✅ "Every time you say no to me, I'm going to start charging you $50 'admin fee' for using the shared car." — arbitrary, escalating penalty for autonomy.
- 🟢 "You used the kids' savings account to buy concert tickets — I'm freezing it until you pay it back." *(other admits error, offers repayment)* — addresses a specific breach; allows repair.
- 🟢 "I've started putting aside money for emergencies — I suggest you do the same, since things feel unstable." — proactive, no strings.
> **Key:** problematic ties money to **compliance**; appropriate addresses **specific breaches** or offers **support without strings**.

### 🌀 Gaslighting / Reality Distortion
- ✅ "You're making it up — I never said I'd drop them off at 7. You're just trying to make me look bad." *(text shows the 7pm agreement)* — denial of documented fact.
- ✅ "Your therapist told me you're paranoid — said you think I'm poisoning the kids' food." *(therapist denies)* — fabricated professional opinion.
- ✅ "I don't know why you're so upset — I was perfectly calm. Maybe you're just tired and overreacting." *(recording shows raised voice)* — dismisses lived experience.
- 🟢 "You said you'd be home by 6, but you weren't. I waited — did you forget, or just not care?" *(delay admitted + apologized)* — names behavior; invites explanation.
- 🟢 "I remember it differently — let's check the message thread so we're both clear." — collaborative; invites verification.
> **Key:** problematic **denies reality / blames victim / fabricates consensus**; appropriate **seeks clarity, accepts fallibility.**

### 💘 Love Bombing / Discarding Cycle
- ✅ "You're my soulmate — I don't know how I'd survive without you." *[90 min later:]* "You're nothing but a manipulative liar. Stay away from me." *(repeats after boundary-setting)* — idealization→devaluation resets contact on the controller's terms.
- ✅ "I've been thinking about us all day — you mean everything to me." *[next day:]* "Don't text me unless it's an emergency." *(no trigger)* — affection withdrawn as punishment.
- 🟢 "Hey, just checking in — hope you're having a good week. How's school going for them?" — steady, child-focused, no swings.
- 🟢 "I miss the kids — can we talk about making handoffs smoother? I value your input." — cooperative; no idealization/devaluation.
- 🟢 "I know we're not getting back together — but I still care about you as the parent of my children. Let's try to be civil." — boundary + honesty without manipulation.
> **Key:** problematic uses **affection as bait / withdrawal as punishment**; appropriate is **steady, boundaried, non-transactional.**

### 👥 Triangulation / Isolation
- ✅ "I told your sister you called me a deadbeat dad — she hasn't replied to your texts since." *(term never used; sister confirms the report)* — family used to punish/isolate on a false claim.
- ✅ "The daycare teacher said you've been showing up late and smelling like alcohol — I've got it on file." *(teacher denies; nothing logged)* — fabricated third-party report.
- ✅ "I asked your mom to keep an eye on things — she said you let them stay up till midnight every night." *(no such conversation; logs normal)* — enlists ally without consent; spreads misinformation.
- 🟢 "Can your mom help with pickup Thursday? I've got a work conflict and trust her completely." — neutral, consensual, logistical.
- 🟢 "I'm not comfortable with them going to your sister's house after what she said last time — can we find another option?" *(observed incident)* — boundary from direct experience.
> **Key:** problematic **involves others without consent / fabricates input**; appropriate is **transparent, consensual, fact-based.**

### 👶 Instrumental Use of the Child
- ✅ "Tell your dad if he doesn't return the tablet by 5, I'm calling the judge and saying he steals from you." *(tablet simply left behind; return offered)* — child delivers a threat.
- ✅ "I had them draw a picture of our family — and you're not in it. I told them it's okay to feel that way." *(child later reports feeling pressured)* — shapes the child's perception; undermines the bond.
- 🟢 "They told me you yelled at them in the car — is that true? I'm worried they're scared of you." — open question; no assumption of guilt.
- 🟢 "I won't let them go with you until you show proof you've been to your meetings." *(prior documented relapses; time-limited)* — history-based safety condition; allows reintegration.
- 🟢 "Can you help them practice their piano piece? They've got a recital Friday." — neutral, developmental.
> **Key:** problematic **coaches / scripts / uses the child to deliver threats**; appropriate **asks openly, respects the child's neutrality, makes history-based safety requests.**

### ⚖️ Legal Threats / Procedural Abuse
- ✅ "I'm filing for emergency custody every Monday until you do what I say — consider this warning #1." *(3 filings in 5 weeks, all denied)* — repetitive non-meritorious filings.
- ✅ "I reported you to CPS for educational neglect — hope you like home visits." *(kids enrolled/attending; no concern)* — false report as harassment.
- 🟢 "After the last no-show, I filed a motion to enforce the parenting plan — you owe them 12 missed hours." *(documented; makeup offered)* — redress for an actual breach.
- 🟢 "Let's try co-parenting counseling before we go back to court — I'd rather not put them through this again." — de-escalation preference.
- 🟢 "The judge said if you miss one more exchange, they'll reconsider custody — so please, just be on time." *(accurate order summary)* — factual consequence, not fear.
> **Key:** problematic uses **threats of system involvement to control**, without basis or in excess; appropriate **enforces rights** or **suggests alternatives to litigation.**

### 🔥 Sexual Degradation / Weaponized Intimacy
- ✅ "I've got that video — send me $300 by tonight or I send it to your boss, your pastor, and the kids' school." — sextortion.
- ✅ "You're pathetic — the way you cried during sex like a little kid. No wonder nobody wants you." *(after declined reconciliation)* — sexual humiliation punishing boundary-setting.
- ✅ "I deleted the video — you don't have to worry. I just wanted you to know I still have power over you." *(later restored)* — false reassurance maintaining control; motive admitted.
- 🟢 "I'm not comfortable with sexting — please don't send those kinds of messages." *(sender stops when asked)* — clear limit; no shame.
- 🟢 "We're not together anymore — let's keep our talks about the kids and logistics only." *(mutually honored)* — appropriate post-separation boundary.
> **Key:** problematic **exploits intimacy for power / threatens exposure / uses shame to punish**; appropriate **sets clear limits without blame.**

### 🧠 Behavioral Indicators of High-Control Dynamics (Non-Diagnostic)
- ✅ "I'm the only one who's ever put them first — you've always been selfish." — grandiosity + devaluation.
- ✅ "Everyone in my family agrees you're difficult — you're the only one who sees it this way." *(no evidence of consensus)* — false consensus; isolates.
- ✅ "If you don't do what I say, I'll make sure everyone knows what you're really like." *(repeated after boundary-setting)* — reputational-harm threat.
- ✅ "I don't owe you an apology — I didn't do anything wrong. You're just too sensitive." *(after name-calling in front of the child)* — deflects accountability; blocks repair.
- 🟢 "I know I yelled — I'm stressed and they were pushing my buttons. I'll try to do better next time." *(followed by change)* — acknowledges behavior; effort to change.
- 🟢 "I'm having a hard time right now — not your fault, but I might be short-tempered. Bear with me." — self-aware; invites patience, not compliance.
- 🟢 "Let's take 24 hours before we reply to anything heated — agree?" *(mutually honored)* — proactive conflict reduction.
> **Key:** problematic shows **deflection, grandiosity, false consensus, threats of exposure** when challenged; appropriate shows **accountability, self-awareness, repair** — even when imperfect.

---

### Usage guidance (from the source session)
- **AI training:** fine-tune classifiers on **nuance** — a protective request ("Show proof you're sober") vs. a coercive one ("Do what I say or I'll say you're unfit").
- **Workshops:** blind-label examples, then discuss discrepancies to build threshold consensus.
- **Reports:** cite specific patterns when justifying concerns.
- **Self-reflection:** helps a parent recognize when their own communication slips under stress.

**Context, pattern, and intent — not isolated phrases — determine whether communication is coercive, reactive, or normative.**
