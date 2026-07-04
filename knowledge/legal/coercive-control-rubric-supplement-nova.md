# Coercive Control Rubric — Supplementary Source (Nova / AWS)

> **Status:** SECONDARY / mining source. Companion to the primary
> `knowledge/legal/coercive-control-classification-rubric.md`. Do NOT treat as the
> canonical rubric — capture it here to **mine for supplementary additions** to the
> primary.
>
> **Provenance:** owner-run Amazon **Nova** (AWS) playground session, captured 2026-07-04.
> Synthetic examples only; no PII. AWS content filters **blocked two of the prompts**
> outright (the longitudinal Cluster-B analyzer template, and the expanded good/bad
> example addendum) — those sections are absent by refusal, not omission. What the model
> *did* return is preserved below with its distinctive contributions flagged.
>
> **Why it's worth keeping despite the refusals:** Nova formalizes a few things the
> primary rubric handles more loosely. See **Curator's Note** at the end for the
> extraction candidates.

---

## Distinctive contributions vs. the primary rubric (quick index)
1. **RR vs IM as first-class labels.** Primary treats reactive-vs-malicious as a
   distinction *table*; Nova promotes **Reactive Response (RR)** and **Intentional
   Malice (IM)** to full classification labels alongside CC/OC, each with its own
   example set. Useful for a 4-way classifier head.
2. **"Resolution" criterion.** Adds a resolution/closure dimension (CC = no genuine
   resolution / control persists; OC = compromise or mediation) the primary criteria
   table doesn't name explicitly.
3. **Standalone `isolation_tactics` and `emotional_manipulation` JSON categories** —
   the primary folds isolation under triangulation and uses `love_bombing_discarding_cycle`;
   Nova splits them out.
4. **`pattern_summary` with `frequency` + `trend`** per category in the JSON — a compact
   escalation-trend field worth mirroring.

---

## 1. Base Rubric (Nova) — Coercive Control vs. Ordinary Conflict

Classification criteria (Nova's table):

| Feature | Coercive Control (CC) | Ordinary Conflict (OC) |
|---|---|---|
| **Intent** | Dominate, intimidate, or undermine autonomy | Express disagreement, resolve issues, or vent (not to control) |
| **Pattern** | Repeated, ongoing (not one-off) | Isolated/occasional; not a larger pattern |
| **Power Imbalance** | Clear imbalance; manipulation or isolation | Roughly equal standing; both retain agency |
| **Threats/Fear** | Explicit or implied threats, intimidation, fear induction | No threats; frustration but not fear-based |
| **Control Tactics** | Monitoring, isolation, gaslighting, financial/emotional manipulation | Disagreement on decisions, no attempt to control the other's choices |
| **Impact on Autonomy** | Victim's choices/actions/emotions restricted | Autonomy respected; seeks mutual understanding |
| **Resolution** | No genuine resolution; control persists | Aims at compromise/closure; relationship continues healthily |

**Rule:** label CC if ≥3 CC criteria met; label OC if ≥3 OC criteria met **and** no CC
criterion is strongly present.

### CC examples (correctly CC)
- "If you speak about this to anyone, I'll make sure you lose your job — no one will hire you after I'm done." → explicit threat, intent to silence/control.
- "You're grounded for a month if you see your friends again, and I'll track your phone to make sure you obey." → isolation, monitoring, punishment for autonomy.
- "Your opinions are worthless; I'll decide what's best for you because I know better than you ever will." → devaluation, overt control.

### Not-CC examples (ordinary)
- "We disagreed about the budget, so we compromised by splitting expenses evenly." → mutual resolution.
- "He was frustrated I forgot our date, but we talked it through and made up." → one-time, resolved.
- "She disagreed with my political view in the meeting but respected my right to speak." → disagreement with respect.

### OC examples (correctly OC)
- "We argued about where to vacation, but we chose a compromise destination we both liked."
- "My sibling and I debated house chores, then made a shared schedule."
- "He's upset I borrowed his car without asking, but we'll discuss boundaries later."

### Not-OC (actually CC)
- "She must ask my permission before buying anything, even a coffee, or I'll take away your allowance." → financial control.
- "If you ever leave me, I'll destroy your social media with fake posts to ruin your life." → threat of permanent harm.
- "I went through your messages because I don't trust you anymore — you're mine, and I'll check whenever I want." → monitoring, possessiveness.

---

## 2. Child + Court Adaptation (Nova) — adds RR vs IM as labels

Nova's four-way frame: **CC · OC · Reactive Response (RR) · Intentional Malice (IM)**.
Extra criteria rows beyond the base table:

- **Child as Instrument** — CC: child used for surveillance/messaging/leverage · OC:
  child discussed as practical co-parenting · RR: child *accidentally* becomes a
  messenger due to a parent's anxiety · IM: child *actively* exploited to spy/deliver threats.
- **Court as Weapon** — CC: frivolous motions/orders to harass · OC: good-faith legal
  requests · RR: legitimate but *overly frequent* requests driven by trauma · IM: courts
  used solely to drain resources or intimidate.
- **Fear/Threats** — RR: hypervigilance after gaslighting · IM: threats made to coerce.
- **Impact on Child** — RR: child reacts to a parent's anxiety · IM: child deliberately
  placed in the middle.
- **Resolution** — RR: temporary escalation from unresolved trauma · IM: continues or
  worsens despite mediation.

**Rule (Nova):** CC if ≥4 CC criteria (esp. *Child as Instrument* or *Court as Weapon*);
OC if ≥3 OC and no strong CC; **RR** if behavior stems from prior CC exposure but lacks
*intent* to harm; **IM** if deliberate, repeated, aimed to undermine the other parent.

### CC (child/court)
- "If you refuse to let me see the child every weekend, I'll file for full custody and accuse you of neglect — just like I did last year." → court as weapon + threat.
- "Don't tell the child about your new partner; if they hear it from you, I'll claim you're destabilizing them and get unsupervised visits revoked." → child as instrument + court leverage.
- "The child told me you yelled at them — now I'm filing an emergency custody modification. If you fight this, I'll make sure you lose all rights." → weaponizes child's report + frivolous action.

### Not-CC (good faith)
- "I missed your visitation because my car broke down — I'll reschedule, and maybe we can talk to a mediator about more flexible timing." → logistical, no control.
- "I'm concerned about the child's school performance and want to meet the teacher together. Let's pick a time that works for both of us." → collaborative.
- "After our argument, I asked the judge for a temporary custody review because I'm genuinely worried about safety — here's the documented evidence." → good-faith, evidenced.

### RR (reactive response) examples
- "After being gaslighted for years, I now double-check every text I send — my lawyer says it's just caution, not malice." → hypervigilance, self-protection.
- "I'm overly insistent on text confirmations for visits because he's canceled before — I'm not trying to control, just avoid getting hurt." → anxiety-driven, past-abuse origin.
- "I asked the judge for a custody evaluation because I genuinely fear for the child's safety after his emotional abuse — yes, I'm anxious, but it's not revenge." → fear-based, child-welfare intent.

### IM (intentional malice) examples
- "I fabricated texts to make it look like he hit the child — just to get full custody and cut him out of their life forever." → deliberate fabrication.
- "I tell the child to 'ignore Dad's calls' because I want to make him suffer — I don't care about their well-being." → child as instrument of revenge.
- "I file a motion every time he's late, even by 5 minutes, just to bankrupt him legally — he deserves it for leaving me." → courts to inflict harm.

---

## 3. ⛔ Blocked by AWS content filters (not returned)
- **Longitudinal Cluster-B analyzer LLM template** — *"The generated text has been blocked by our content filters."*
- **Expanded good/bad example addendum (4–5 per category)** — *"blocked by our content filters."*

> The primary rubric (`coercive-control-classification-rubric.md` §3 and §6) covers both
> of these — Nova's refusal is why the primary source is the canonical one.

---

## 4. Judge-Friendly JSON (Nova) — category + field differences

Nova's court JSON groups by behavior category with per-example `date` / `message` /
`sender` / `impact`, plus a `pattern_summary { frequency, trend }`, then an
`overall_summary_for_court { key_findings, impact_on_child, recommendations }`.

Categories Nova emits (note the deltas vs. the primary's 8 keys):
`financial_manipulation`, `triangulation`, **`isolation_tactics`** (standalone),
`legal_threats_and_manipulation`, **`emotional_manipulation`** (vs. primary's
`love_bombing_discarding_cycle`), `sexual_degradation_as_weapon`.

Shape (abridged):
```json
{
  "case_id": "...",
  "parties": {"party_A": "...", "party_B": "..."},
  "analysis_period": {"start_date": "...", "end_date": "..."},
  "behavior_categories": {
    "<category>": {
      "definition": "...",
      "observed_examples": [
        {"date": "...", "message": "...", "sender": "party_B", "impact": "..."}
      ],
      "pattern_summary": {"frequency": "Recurring (3+ over 8 months)", "trend": "Escalating ..."}
    }
  },
  "overall_summary_for_court": {
    "key_findings": ["..."],
    "impact_on_child": ["..."],
    "recommendations": ["..."]
  }
}
```

Court-safety notes Nova baked in (consistent with the primary): diagnostic-term-free,
behavior/impact/pattern-focused, every example tied to a specific date + message + observable outcome.

---

## Curator's Note — extraction candidates for the primary rubric

Fold these into the primary rubric / analyzer during the seed-reconciliation + calibration-set work:

1. **Promote RR and IM to explicit output labels** in the analyzer (currently the primary
   emits a `reactivity_assessment` string; Nova's 4-way CC/OC/RR/IM is a cleaner
   classifier target). Maps onto the 0006 `bias_caution` / reactive-vs-malicious posture.
2. **Add a "Resolution / closure" signal** to the criteria — "does control persist or does
   the exchange reach compromise" is a strong CC/OC discriminator the primary omits.
3. **Consider splitting `isolation_tactics`** out from `triangulation_isolation`, and keep
   an eye on whether `emotional_manipulation` should be a broader parent of
   `love_bombing_discarding_cycle` when the calibration set is built.
4. **Mirror `pattern_summary.trend`** (escalation direction) as a field — complements the
   existing `escalation_pattern`.
5. Nova's synthetic example sentences are usable **calibration rows** (they lean more
   overt/explicit than the primary's, which is good negative-space coverage for a
   classifier — real coercion is often subtler, so pair these with the primary's subtler examples).

**Do not** merge Nova's JSON category keys as-is — reconcile against the primary's 8-key
set + the 0006 `behavior_category` ontology first, so the schema stays single-source.
