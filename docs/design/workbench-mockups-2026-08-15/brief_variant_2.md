# Workbench Mockup Variant 2 — Temporal Case Atlas

> _Byline: Codex · GPT-5 · 2026-08-15_

> **Superseding addendum — ADR-0059 (2026-08-18; Codex · GPT-5):** Preserve this
> historical brief, but interpret the mockup with three clocks: first-party source
> availability at occurrence, acquired-third-party source availability at conversation
> acquisition, and zero-to-many later realization atoms. Acquired-third-party threads
> show their actual sender/recipients with the owner absent. Healthy Pause/Resume keeps
> one walk identity; a terminal failure is sealed and non-resumable before a separately
> identified, explicitly linked Re-walk is allowed. These remain local prototype states,
> not authorization to deploy or execute a backend walk.
>
> **Active debt/change-order gate:** Human projection-review API/UI and approved
> vector reprojection are not implemented by this artifact. Do not present either
> as active until its implementation and live proof land separately.

## Objective

Create a self-contained HTML mockup that makes the platform's defining knowledge-horizon mechanism visually primary: the operator must understand what was known as-lived, what hindsight reveals, and the delta between them.

## Audience

The owner/operator reconstructing realization, manipulation, and gaslighting across a large evidence corpus while preserving strict temporal and provenance boundaries.

## Aesthetic direction

A temporal investigation atlas rather than a dashboard. Use layered chronology, a wide central canvas, fine cartographic lines, and deliberate editorial typography. The interface should feel like navigating an evidence map through time—not a kanban board or analytics template.

## Content structure

- Matter/CourtCase identity remains visible but separate from Knowledge partition/horizon controls.
- Central dual-track temporal canvas: As-Lived walk versus Hindsight view.
- A high-clarity Delta lane between them surfacing contradictions, newly realizable facts, and belief changes.
- Horizon controls for pace, schedule, batch, re-walk, checkpoint, and disclosure tier; visibly disabled/held because execution is not yet proven.
- Timeline events link to canonical evidence and exact provenance.
- Separate belief-memory layer for Graphiti with current/invalidated fact status.
- Semantica VIP extraction status and candidate output appear as an upstream provenance layer, never as agent belief.
- Side drawer for People, Claims, Issues, Evidence, and generated Work Products.
- Provider/model indicator showing requested route and actual model, with next-turn switching semantics.

## Typography

Use a confident editorial serif for temporal headings paired with a highly legible sans and mono annotations. Dates and horizon boundaries must scan instantly.

## Color direction

Parchment-neutral canvas, near-black type, cobalt as-lived track, violet hindsight track, and a luminous but restrained coral/gold delta. Never imply correctness solely through green/red.

## Memorable element

The central delta ribbon should visually widen where hindsight diverges most sharply from the as-lived belief state, with provenance threads connecting each divergence to evidence and realization events.

## Image needs

No photography. Use CSS/SVG only for the temporal schematic, simple icons, and subtle map-like background grid.

## Technical/output constraints

- Self-contained responsive `index.html`; no external network dependencies or build step.
- Desktop-first at 1440px with a credible compressed tablet state.
- Use fictional sample data only.
- Minimal inline JS may change horizons/checkpoints, but execution controls must be marked prototype/held.
- Output: `workbench/design-mockups/temporal-case-atlas/index.html`.
- Include a short `README.md` explaining how this direction protects the Knowledge/agent-horizon separation.
