# Temporal Case Atlas Mockup

> _Byline: Codex · GPT-5 · 2026-08-15 · ADR-0059 amendment 2026-08-18_

This standalone mockup explores the platform’s defining temporal experience:
comparing the belief state available during an as-lived walk with a full-corpus
hindsight view, then treating the difference as the primary product surface.
Open `index.html` directly; it contains no external assets, network calls,
production integration, or build step.

## Direction

- The interface is a cartographic chronology rather than a dashboard or review
  queue. A wide map canvas carries the product hierarchy.
- Cobalt identifies the as-lived belief track, violet the hindsight fact view,
  and a variable-width coral/gold ribbon shows where their meanings diverge.
- Dashed provenance threads connect changes in belief to exact evidence and
  realization boundaries.
- Matter/CourtCase identity stays separate from the text Knowledge partition
  and selected horizon checkpoint.
- Semantica VIP is visibly upstream and horizon-neutral: it extracts candidates
  but never forms agent beliefs.
- Graphiti current and invalidated beliefs occupy a clearly labeled memory
  layer, separate from canonical evidence and generated work product.
- Provider routing shows requested route versus actual model and makes clear
  that switching takes effect on the next turn.
- First-party messages become source-visible at occurrence. Separately projected
  acquired-third-party conversations become source-visible only at acquisition;
  their actual sender and recipients are shown and the owner is not a participant.
- Acquisition is not realization. A conversation can link to zero, one, or many
  later realization atoms without rewriting the message or its availability clock.

## Safety and interaction

The slider and checkpoint controls move only a visual boundary. The local-only
walk-state demonstrator can pause and resume a healthy checkpoint under the same
walk identity. A failed walk must first be sealed as terminal and non-resumable;
only then does its prototype Re-walk control become available under a new identity
with an explicit `rewalk_of` link. None of these controls execute a backend walk,
change evidence, or mutate memory. At tablet widths, the drawer moves below the
map while the chronology retains its scanning width.

## Active implementation hold

This mockup does not activate a human projection-review API/UI or approved vector
reprojection. Both remain implementation debt/change-order gates; the displayed
approval and projection states are fictional UI examples only.
