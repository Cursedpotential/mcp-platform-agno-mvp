# Dual graph paths — node identity, version stamping, and governed write-back

> _Byline: Claude · Opus 5 · 2026-08-29 · owner design session._
>
> Captures three open concerns raised while designing `sql/0052` (ADR-0062). None of them
> block ingestion; all three are cheap now and expensive to retrofit. Recorded so they are
> not rediscovered.

## Standing shape (owner, 2026-08-29)

Two graph extraction paths run **in parallel** and write to **separate graphs**:

| Path | Writes to |
|---|---|
| Semantica | its own graph |
| SAT RAG | its own graph |

**They are not merged.** Two independent readings you can diff is worth more than one
averaged graph — the disagreement is the finding. This is the same rule that governs claims
(accumulate, never merge) and generation-2 syntheses in ADR-0062 §8 (preserve variance,
record divergence, adjudicate as an owner act).

Both are fed from PostgreSQL by change detection. Neither is an authoring home.

---

## 1 · Shared node identity — invert the dependency

**The concern:** if each graph keys entities its own way, a diff between them becomes an
entity-resolution problem instead of a finding.

**The resolution, and it unblocks this now:** do not resolve identity in order to diff.
**Diff on provenance, and let identity resolution be an output of the diff.**

The requirement is not that both graphs agree on what to call a node. It is that both anchor
every node and edge to the **same PG source coordinate** it was derived from — chunk id,
message id, claim id. Then a comparison reads:

> For chunk X: Semantica says `A —relates_to→ B`. SAT says `A′ —relates_to→ C`.

That is comparable without ever deciding whether `A` and `A′` are the same entity. Agreement
on `B` vs `C` is visible immediately; the `A`/`A′` question becomes a *candidate alias*
produced by the comparison rather than a prerequisite for it.

**What must be true now** (cheap, and unrecoverable if skipped): every node and edge in
either graph carries the PG source coordinate. Nothing else.

**What can be iterative** (owner: "figure that'll get resolved later"): the alias table.
When it lands it should be an **alias *candidate* table with evidence and review state** —
which mentions/nodes support the alias, confidence, who approved it — not a hand-maintained
address book. A hand-maintained one drifts silently and there is no way to tell a stale
alias from a wrong one. Same candidate-plus-review shape as everything else in `working.*`.

**Hazard if the coordinate is skipped:** a graph whose nodes cannot be traced back to a PG
row cannot be diffed, cannot be rebuilt with confidence, and cannot be audited. It becomes
an opinion with no provenance. This is the one item on this page that is genuinely
load-bearing before either extractor runs.

---

## 2 · Version stamping

**The concern:** without it, a disagreement between the two graphs is ambiguous between
*"they read the same material differently"* and *"one of them is stale."* Those require
opposite responses, and telling them apart after the fact is not possible.

Every projected node/edge carries, at minimum:

| Field | Why |
|---|---|
| `extractor_name` | which path produced it |
| `extractor_version` | code version |
| `model_id` | when a model is in the loop |
| `prompt_version` | prompt changes are extractor changes |
| `run_id` | ties a batch together for replay/rollback |
| `source_generation` | **the PG generation the input was read at** |
| `projected_at` | wall clock |

`source_generation` is the one that does the real work. A disagreement between two nodes
computed against the *same* source generation is a genuine divergence worth adjudicating. A
disagreement across *different* generations is staleness and requires a re-run, not a
decision. Without this field every diff has to be manually investigated.

---

## 3 · Governed write-back

**Correction to an earlier framing in this session.** "Neither writes back" was too blunt.
Several things legitimately need to influence canon. Owner, 2026-08-29:

> "There's several things that need to write back while not writing back, and the solution
> thus far has been a candidate table or a resolution table or a human-in-the-loop process
> where it's not allowed to technically write back but it kicks back potential changes, and
> then those changes get reviewed and they canonicalized, and then it projects — the change
> detection would then force a recalculation of projected data."

That is the correct pattern and it is already the platform's pattern everywhere else
(`working.*_candidate` → review → promotion → CDC fan-out). Stated as a loop:

```
projection / analysis observes something
        │
        ▼
proposal lands in a PG candidate or resolution table
   (never a direct write to a canonical row)
        │
        ▼
human review  →  rejected: retained, marked, never silently dropped
        │
        ▼ approved
canonical row changes in PG
        │
        ▼
change detection fires
        │
        ▼
projections recalculate; affected subgraphs rebuild
```

The invariant is not "projections never influence canon." It is **projections never
*author* canon.** They propose; a human canonicalizes; PG remains the single writer of
truth. A projection is still fully rebuildable from PG at any point in that loop.

### The one hazard worth guarding

This loop can oscillate: a graph's output changes canon → canon re-projects → the graph's
input changes → it proposes again. Left unguarded, two extractors proposing against each
other can ping-pong indefinitely without anyone noticing, because each individual step looks
legitimate.

**Guard:** every proposal records the `source_generation` it was computed against. On
review, a proposal whose source generation has since been superseded is **stale** — it
requeues for recomputation rather than applying. An approval can only be applied against the
generation it was reasoned about.

This is the same field from §2 doing double duty, which is a good sign it is the right field.

---

## Status

- §1 source coordinate — **required before either extractor runs.** Cheap.
- §1 alias candidate table — deferred, iterative, owner-acknowledged.
- §2 version stamping — **required at first projection.** Cheap.
- §3 write-back loop — already the platform pattern; the staleness guard is new and
  belongs in whichever ADR governs the proposal tables when they are built.

None of this affects `sql/0052`. Claims, temporal edges, and assertions live in PG and
neither graph extractor authors them.
