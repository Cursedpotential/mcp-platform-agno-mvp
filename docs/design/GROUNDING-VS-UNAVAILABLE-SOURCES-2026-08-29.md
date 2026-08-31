# Grounding vs. unavailable sources — harvesting prior analysis

> _Byline: Claude · Opus 5 · 2026-08-29._
>
> A consequence of ADR-0062 §7 that will surface on the first harvest attempt. Recorded
> before it does.

## The conflict

ADR-0062 requires every generation-1 assertion to cite at least one `claim_candidate`, and
every claim to cite a `chat_message_id`. One hop to something a person actually said.

Three prior analysis documents exist — high-quality, produced by a frontier model over the
chat corpus. They are the reason the assertion layer was designed at all. But:

- They derive from `SRC-CHAT-5e625c3d` and `SRC-CHAT-6b19dce6`.
- The second is documented as **returning fully redacted** through the provider's
  conversation-read path; its content was recovered only in fragments through search.
- The first was read fully for turns 0–26; turns 27–76 were covered by targeted retrieval
  only.

If those conversations cannot be ingested as sources, their claims cannot be created, so
their assertions cannot be grounded, so under the rule just adopted **they can never be
accepted.** The best analysis in the corpus would be permanently stuck at `ungrounded`.

## What not to do

**Do not weaken the grounding rule.** It is the single thing preventing an assertion chain
that never reaches a human statement. An exception carved for "important analysis we can't
ground" is exactly the exception that makes the rule meaningless — the important ones are
the ones that end up in a filing.

## Options

**A — Treat the analysis document as its own source.**
Ingest `case-extract-01/02/03` as context sources in their own right. Extract claims *from
the document*, where the human-attributed passages it quotes verbatim become
`claim_candidate` rows with `claim_class='SELF_ACCOUNT'` and the document's own message as
provenance. The panels then ground to those claims.

*Cost:* provenance is one hop longer than it looks — the claim's `verbatim` is a quotation
inside an analysis document, not the original utterance. That must be visible on the row,
not inferred. Requires a marker distinguishing "quoted from an analysis document" from
"read from the original conversation," or the corpus silently mixes first-hand and
second-hand spans.

**B — Park until the source lands.**
Assertions are created with `owner_disposition='parked'` and a reason. If the source
conversation is ever exported by other means, claims get created and the assertions ground
normally at that point.

*Cost:* the analysis sits unusable for an unknown period, possibly forever if the export
never happens.

**C — Both, sequenced.**
Harvest under A now so the reasoning is addressable and searchable immediately, and mark
every claim sourced from an analysis document with its second-hand provenance. If the
original conversation is later ingested, the first-hand claims supersede the second-hand
ones and the assertions re-point. Nothing is lost either way, and supersession is already
how every other correction works in this schema.

## Recommendation

**C**, with one schema requirement that must be decided before any harvest runs:

> A claim must record whether its `verbatim` was read from the original conversation or
> quoted inside a derived document.

This is not the same thing as `claim_class`. A `SELF_ACCOUNT` quoted inside an analysis
document is still a self-account — but it is a self-account whose surrounding context was
chosen by a model, and it inherits whatever that model included or omitted. That is a
material difference in evidentiary weight and it must be a column, not a convention.

Candidate shape: `provenance_depth` ∈ `original` | `quoted_in_derived`, plus
`derived_source_ref` naming the document. Cheap now; unrecoverable later, since claims are
append-only and cannot be retro-annotated.

## Status

Undecided. Blocks the first harvest, not the first extraction run — R1 over ingestible
conversations is unaffected and can proceed.
