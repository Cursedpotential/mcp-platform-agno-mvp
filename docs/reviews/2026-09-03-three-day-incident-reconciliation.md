# Three-day incident reconciliation + prevention plan — 2026-09-03

> _Byline: Claude Code · glm-5.3:cloud · 2026-09-03._
> Scope: owner messages 2026-08-31 → 2026-09-03 (122 real messages mined from session logs,
> transcript_miner noise excluded), `docs/DECISION_LOG.md` D-124…D-136, the prior analysis
> `docs/reviews/2026-09-02-relitigation-pattern-and-fix.md`, and the `.remember` daily digests.
> Owner ask: reconcile every issue in the past three days with the conversations where a build
> or task began without full understanding of what existed / what the problem was, plus the
> disagreements and conflicts, and produce a plan that makes them stop happening.

## 1. Incident register

| # | When | What happened | Failure mode | How it resolved |
|---|---|---|---|---|
| I-1 | 09-01 morning | Owner restructured the repo himself ("i made some structure chnages": `modules/engine`, `modules/workbench`, `deploy/docker/`, `contracts/` and `AGENT_MEMORY.md` deleted). Agents then hit broken tests (full pytest exit 2) and had to re-decide where contracts live. | Cold start after unannounced owner-side change; verify-before-done gap | 10 commits + PR #27; contracts ruled → `modules/contracts/` born-with-content (ADR-0054 amended); tests consolidated under `tests/` |
| I-2 | 09-01 07:57–08:01 | Owner resorted to hand-written "READ-ONLY / execution-sidecar" microprompts with exhaustive do-not-touch lists to keep agents scoped. | Trust cost of previous overreach: scoping had to be supplied manually by the owner | One-off; no standing fix landed |
| I-3 | 09-01 20:42 | SBV integration proposed with zero knowledge of prior SBV decisions, parsing, and workflows. Owner: "you clearly have no fucking clue about the decisions that have been made in regards to the… SBV". | **Build started without understanding what existed** — no inventory pass before proposing | Session corrected from owner's recall; D-131 later pinned donor-vs-fork |
| I-4 | 09-01 20:55 | Premature stop: "you found one document and stopped… like you struck fucking gold." | Shallow recall — first hit treated as complete | Verbal correction only |
| I-5 | 09-02 all day | 13 decisions logged (D-124…D-136); ≥7 are repairs of re-opened/mis-read/over-elaborated settled material (full table in the 09-02 review doc §2: D-128 misreads D-110; D-133 Authentik built end-to-end on the rejected forward-auth architecture; D-129 stack lapsed for lack of a record; D-131 SBV naming; D-134 false bind-bug; D-136 strips D-135's ceremony). | Re-litigation + elaboration drift + unrecorded standards | Analyzed 2026-09-02; fix plan F1–F5 written; **none implemented until today** |
| I-6 | 09-02 13:18–13:29 | Agent asked the owner to pick between two UUIDs without saying what either was; then feature flags were treated as license to skip building the guards. Owner livid. | Communication failure (unnamed references) + interpretation drift (flag ≠ skip work) | D-125/D-126/D-127/D-128 recorded |
| I-7 | 09-02 17:33 | Workbench frontend stack forgotten again ("you were gonna forget about it… not committed anywhere as a standard"). | Unrecorded standard → every session re-discovers by archaeology | D-129 recorded |
| I-8 | 09-03 08:57 | Owner re-stated, verbatim, the n8n→Temporal-activity rule that D-130 + the AGENTS.md ATOMICITY block had recorded the prior morning ("I don't know what the fuck the best way to do that is"). | Session answered a settled question as if undecided | Implemented correctly (commit d0b18f5), but the recall failed first |
| I-9 | 09-03 09:17–09:26 | Parser coverage discussed as if parsers were missing; owner: "Snapchat and Whatsapp also already have parsers… So have all these parsers been fucking ported and moved into the Tools Gateway" + "Super tired of rewriting parsers 14 times." | **Build proposed without inventorying what exists** — same mode as I-3, on the same platform, two days apart | Corrected from owner's memory mid-conversation |
| I-10 | 09-03 09:26–09:35 | Five "Try again" retries — glm-5.3:cloud backend timeouts (the same error this review session hit minutes later). | External model availability | Not a process defect; operational |
| I-11 | 09-03 08:55 | Black CMD.EXE window spawning from `claude.exe` → `npx @wonderwhy-er/desktop-commander@latest`. | Environment/tooling (open, separate lane) | Open — owner asked for diagnosis; launchMode suspected |
| I-12 | 09-03 09:29 | Cocoindex skill content re-injected repeatedly into the prompt stream; owner: "super annoying… it's also a necessary plugin. Can we patch it?" | Environment/tooling (open) | Open — patch question unanswered |
| I-13 | 09-03 09:03–09:12 | Today's rulings (AI-chats are context-only; sender/receiver normalization scope; fidelity-digest fields; raw contact question) are **not yet in DECISION_LOG** — no D-137+ exists. | Same-day recording lag | Open — owning session must record, then add register rows |

## 2. Root-cause taxonomy (consolidated)

The 09-02 review correctly located the defect on the **recall side**. Three days of logs show it
is actually **four distinct mechanical gaps, one of which is new since that analysis**:

1. **No lookup surface for prior rulings** (drives I-5, I-7, I-8). Rulings exist as dense prose
   walls; nothing lets a session with a proposal *find* the governing D-number.
2. **No inventory-before-build gate** (drives I-3, I-9 — the two angriest blowups of the three
   days, and the exact failure the owner named today). A session receives "normalize senders
   across sources" or "figure out parser coverage" and starts designing from the prompt alone,
   without enumerating what already exists — deployed parsers, prior decisions, SBV state.
3. **Elaboration masquerading as the ruling** (drives I-5's D-135→D-136, I-6's flag-as-skip-work,
   D-128's misread of D-110). Recording format lets ceremony outrank the owner's words.
4. **Cold/resumed sessions answering from scratch** (drives I-1, I-8) — a session that lost
   context answers a settled question as new.

Plus a communication defect the owner called out directly in I-6: presenting a choice between
two things without naming either. And a recording-lag defect (I-13): rulings made in the
morning are unindexed by afternoon.

## 3. Prevention plan — consolidated, with status

Carries the 09-02 plan (F1–F5) forward, adds what these three days exposed, and marks what is
DONE vs pending.

| Item | What | Status |
|---|---|---|
| P1 (was F1) | **Settled-question register** — `docs/registers/SETTLED.md`, one greppable line per settled question, appended at recording time. | ✅ **Seeded today** (16 rows: hashing, flags, atomicity, D-136 whole-rule, SBV, stacks, service identity, horizons, chunking, SurrealDB, geo, tests, parser coverage, chats-context-only). Register itself records the append-at-recording-time rule. |
| P2 (was F4) | **Owner-verbatim-first recording convention** in `docs/CONVENTIONS.md`: the owner's words are recorded first and labeled the ruling; elaboration is labeled elaboration and explicitly subordinate (D-136 is the template). | ⬜ Doc-only, one paragraph in CONVENTIONS — ready to apply on sign-off |
| P3 (new, highest value) | **Inventory-before-build gate** — before ANY build/normalize/coverage proposal, the first reply states what already exists (deployed services, existing parsers/tables/modules, governing D-numbers — grep + SETTLED.md + AGENTS.md), and design starts only after that inventory is on the table. Directly prevents I-3/I-9. | ⬜ Proposed — needs owner sign-off to add to root AGENTS.md next to the recall rule |
| P4 (was F3) | **Cite-before-propose test** — a proposal touching a register topic cites the ruling in its first line; contradicting it requires `RE-OPENING D-xxx` + owner sign-off before any build work. | ⬜ Proposed — one line in AGENTS.md (the register already carries the use-rule) |
| P5 (was F2) | **UserPromptSubmit hook** mechanically greps SETTLED.md for prompt keywords and injects matching rulings as `additionalContext` before the model answers — enforcement instead of exhortation, in every session. | ⬜ Needs owner sign-off (touches `.claude` settings; takes effect next session) |
| P6 (was F5) | **Resume-preamble habit** — any session resuming cold/stalled does a recall pass (grep SETTLED.md for pending-prompt topics) before answering. | ⬜ Habit; P5's hook largely automates it |
| P7 (new) | **Never present an unnamed choice** — any "pick A or B" put to the owner names the actual objects (IDs, paths, values) in the same message. | ⬜ Add one line to the structured-communication rule |
| P8 (new) | **Recording checklist, same turn** — the session that receives a ruling records the D-entry AND appends the SETTLED.md row in the same turn; I-13 shows half-day lag is already enough to lose it. | ⬜ Enforced socially by P1's header until P5 exists |
| O-1 | Black CMD window (desktop-commander spawn) — diagnose and fix. | ⬜ Open, separate lane |
| O-2 | Cocoindex skill re-injection — owner asked "can we patch it?"; answer pending. | ⬜ Open |
| O-3 | glm-5.3:cloud intermittent timeouts → "Try again" churn. | ⬜ External; nothing to fix in-repo |

## 4. Recommended order

1. **Now (doc-only, this turn):** P1 register seeded ✅.
2. **Next doc pass:** P2 (CONVENTIONS paragraph) + P3/P4/P7 lines in AGENTS.md — all text, one commit.
3. **Owner sign-off:** P5 hook — the only item that makes recall *mechanical* rather than
   voluntary; it is also the only item that protects the resumed-session case (I-8) without
   relying on the next model remembering to grep.
4. **This session's owners:** record today's 2026-09-03 rulings (I-13) as D-137+ and append the
   register rows; the chats-context-only row currently cites "D-number pending".

## 5. The one-line summary for future sessions

**Before proposing anything: grep `docs/registers/SETTLED.md`; before building anything: state the inventory of what already exists; cite the D-number; record rulings verbatim-first with a register row in the same turn.**