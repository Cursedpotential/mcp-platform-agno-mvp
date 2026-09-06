# Re-litigation pattern analysis + fix plan — 2026-09-02

> _Byline: Claude Code · glm-5.3:cloud · 2026-09-02._
> Scope: evidence gathered from the Opus/Fable session `da5b5108` ("greedy-seeking-koala",
> 2026-09-01T06:39 → 2026-09-02T19:41 EDT, 76 owner messages), `docs/DECISION_LOG.md`
> D-124…D-136, and the prior-rulings record (D-110, D-077, ADR-0052/0059, memory).
> Owner ask: compare how conflict resolution went today, identify what the other session is
> about to re-do, and produce a plan that stops settled questions being re-opened.
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## 1. What the Opus session is about to re-do (the interception)

The Opus/Fable session hit its 5-hour quota at 19:38 and 19:41 EDT — both of the owner's final
messages received synthetic 429s ("You've hit your session limit · resets 7:50pm"). When it
resumes, it will act on the pending 19:41 prompt:

> "It needs to be able to wrap the proper module in a Temporal Activity and call the
> Activity. Or if they're premade activities, just call the Activity. Then we can add a
> screen later… I don't know what the fuck the best way to do that is."

**That question is already settled — twice, on the same day:**

- **D-130** (recorded 2026-09-02) — every unit is one Activity, three call shapes, one unit,
  no orchestration inside a unit, new capability = new Activity registered in the stage graph.
- **AGENTS.md "ATOMICITY" block** (2026-09-02) — the same seven rules, written into root,
  `modules/engine/`, `server/`, and Workbench AGENTS.md files.
- The earlier pending message (19:38, hashing built around message content + timestamps) is
  likewise already settled by **D-136 clause 2** and **D-124/D-077** (hash moments/taxonomy).

**Risk when it wakes:** it answers with a fresh architecture conversation (activity-registry
design, "how should we shape this") — a design discussion re-opening D-130 — instead of
executing: wire the existing units as Activities per the recorded rules. The same risk exists
for the hashing half: re-proposing a hash taxonomy instead of applying D-136 clause 2
(content + timestamps are the immutable core) and D-124 (four hash *moments*, no H4).

**Paste-preamble for the resumed session:**

> D-130 + the AGENTS.md ATOMICITY block already settle this — don't re-design. Wrap the
> existing units as Temporal Activities exactly per D-130's three call shapes; call premade
> Activities where they exist; the "screen later" is a UIW/n8n concern, not a new unit.
> Hashing: D-136 clause 2 (content + timestamps immutable) + D-124 (four hash moments).
> Cite the D-number before proposing anything that touches these.

## 2. How conflict resolution went today (the pattern, with counts)

Today's session logged **13 decisions (D-124…D-136)** — and at least **7 of them are repairs
of re-opened, mis-read, or over-elaborated settled material**, not new decisions:

| Repair | What happened |
|---|---|
| D-128 (amends D-110) | D-110's "do not ask about this again" was mis-read as "the guards are gone, subject closed" — the owner had to re-litigate his own settled ruling to correct the reading. |
| D-133 | `deploy/authentik.yaml` was **built end-to-end on the rejected architecture** (Traefik forward-auth + outposts + letsencrypt) and had to be superseded before ever being deployed. |
| D-129 | The Workbench frontend stack existed only in `package.json` + a filed-away doc — never recorded as a standard, so every session re-discovered it by archaeology. Evidence.dev's *decision* was never reversed, but lapsed for lack of a record. |
| D-131 | SBV naming re-litigated ("SBV" meant three different things); donor-vs-fork distinction had to be ruled. |
| D-134 | Corrects the session's own earlier misreading of the Workbench loopback port mapping (called a bind bug; was correct). |
| D-136 (simplifies D-135) | D-135 elaborated the owner's ruling into a tiered form spec + ceremony; within ~30 minutes the owner issued the whole-rule simplification ("extract everything, don't modify messages/timestamps, that's all it is") which now governs. |
| 19:41 pending prompt | The owner re-stating, verbatim, the atomicity rule that D-130 + AGENTS.md had already recorded **that same morning**. |

**Multi-week repeat offenders** (the "discussed 14 times" set), visible across the log:

- **Hashing** — H2v1 lost → H2v2 canon → two H3 chains sharing one tag → "which four
  hashes?" confusion → D-124 (2026-09-02) finally reconciling 3 levels / 4 moments / 5 kinds.
- **Preview/intake restrictions** — read-only preview vs. custodian assertion, argued again
  2026-09-02 (D-135/D-136) after prior ingest-design rulings (ADR-0052/0059, D-123).
- **Immutability scope** — D-110 → D-128.
- **Feature flags** — D-110/D-125/D-126 read three different ways until D-127 pinned the
  principle.
- **Service identity/addressing** — Coolify proxy hostname confusion → D-132/D-133/D-134.

## 3. Root cause

The rulings ARE being recorded — `DECISION_LOG.md` is healthy. The defect is on the **recall
side**, and it is mechanical, not attitudinal:

1. **Recall is exhortation, not enforcement.** The 03:30 rule ("search past transcripts for
   the prior resolution and cite it; a proposal that re-opens a settled question is a
   defect") lives in CLAUDE.md and depends on each model voluntarily searching before
   proposing. Nothing intercepts a proposal that re-opens D-xxx.
2. **No topic index exists.** D-entries are (by design) dense prose walls. A model holding a
   new proposal cannot reliably *find* the prior ruling that governs it — there is no
   keyword→ruling lookup surface. `RULINGS-SHEET-2026-08-09.md` was exactly this artifact,
   built once, never maintained.
3. **Elaboration outranks the ruling.** D-135 showed the failure mode: the owner's verbatim
   ruling gets elaborated into ceremony, and the elaboration then reads as the rule until the
   owner strips it (D-136). Recording format lets elaboration masquerade as the decision.
4. **Sessions resume cold.** The stalled-session case (§1) is the acute form: a session that
   lost its context mid-thread wakes up and answers a settled question from scratch.

## 4. The fix plan

### F1 — Settled-Question Register (the missing index) — `docs/registers/SETTLED.md`

One greppable line per settled question, appended **at the same moment a D-entry or ADR is
recorded** (make it part of the recording checklist, so it cannot rot like RULINGS-SHEET did):

```
| topic keywords | ruling | one-line verdict | supersedes/superseded-by |
| hashing, custody hash, H1 H2 H3, four hashes | D-124, D-077, D-136-2 | 3 levels / 4 moments / 5 kinds; no H4; content+timestamps are the immutable core | — |
```

- DECISION_LOG/ADRs stay the authority; the register is only the lookup index.
- Seed it with today's repeat offenders (§2 list) + the big standing rulings
  (ADR-0045/0052/0053/0059, D-070, D-123, D-127, D-130, D-135/136).

### F2 — Mechanical recall: UserPromptSubmit hook — PROPOSED, needs owner sign-off

A small hook script greps `SETTLED.md` for the owner's prompt topic keywords and injects
matching rulings as `additionalContext`:

```
⚠ SETTLED — do not re-open without explicit owner sign-off:
  hashing → D-124, D-077 (3 levels / 4 moments / 5 kinds; no H4)
  temporal activity wrapping → D-130 + AGENTS.md ATOMICITY
```

This makes the 03:30 rule fire **before** the model proposes, in every session, for every
model (Claude Code, Codex, Gemini, OpenCode) that honors hooks — instead of relying on the
model remembering to search. Note: hooks load at session start, so it takes effect next
session; and the same injection can be ported to Codex/Gemini config as a prompt preamble
if their hook support differs.

### F3 — Cite-before-propose test, added next to the existing recall rule in AGENTS.md

The rule exists; add the one mechanical test that makes violations visible:

> Any proposal that touches a register topic must cite the governing D-number/ADR in its
> first line. A proposal that contradicts a cited ruling must open with "RE-OPENING D-xxx:
> <what changed>" and gets no build work until the owner signs off.

### F4 — Owner-verbatim-first recording convention

D-136 is the template: the owner's words are the ruling, recorded first and verbatim;
elaboration is recorded after and labeled as elaboration, explicitly subordinate ("where the
elaboration conflicts with it, the verbatim wins"). Add this to the DECISION_LOG recording
conventions in `docs/CONVENTIONS.md` so future D-entries stop letting ceremony outrank the
ruling.

### F5 — Resume-preamble for stalled sessions (operational habit)

When a session dies mid-thread and resumes, its first act is a recall pass: grep SETTLED.md
for every pending prompt's topics before answering. The §1 paste-preamble is the immediate
instance for `da5b5108`.

## 5. Sequencing

1. **Now:** F1 register seeded + F4 convention line (both are doc-only, this repo).
2. **Owner sign-off:** F2 hook (touches `.claude` settings — not implemented without it).
3. **Next doc pass:** F3 test added beside the recall rule.
4. **Immediate:** F5 preamble pasted into the resumed Opus session before it answers the
   19:41 prompt.