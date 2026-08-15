# Evaluation — Attempt 1

> _Byline: Codex · GPT-5 · 2026-08-15_

## Overall Verdict: PASS

## Overall Assessment

The mockup convincingly behaves like a temporal investigation atlas rather than a conventional dashboard. Its widening delta ribbon, editorial cartographic styling, and explicit separation of as-lived belief from hindsight evidence make the project’s defining mechanism immediately legible; however, provenance detail and secondary interactions are still less complete than the primary visualization.

The page was rendered and inspected at 1440 × 900, 768 × 900, and 375 × 812. Desktop is polished and coherent. The tablet state remains operable through horizontal panning, but it is compressed rather than truly recomposed; the 375px view is substantially clipped, though a mobile layout was not required by the brief.

## Scores

| Criterion | Score | Status | Weight | Notes |
|-----------|-------|--------|--------|-------|
| Design Quality | 3/3 | PASS | HIGH | The parchment field, editorial serif hierarchy, fine map grid, distinct cobalt/violet tracks, and restrained coral/gold delta form one unmistakable investigation-atlas identity. The data semantics and visual semantics reinforce each other. |
| Originality | 3/3 | PASS | HIGH | The variable-width delta ribbon with provenance threads is a custom, memorable response to this specific product concept. The result does not resemble a generic admin dashboard, card grid, or analytics template. |
| Craft | 2/3 | PASS | MEDIUM | Desktop typography, alignment, contrast, spacing, SVG labeling, focus treatment, and color discipline are clean. Craft falls short of 3 because the tablet composition depends on a wide fixed canvas, some small annotations approach the lower edge of comfortable legibility, and the event readout can obscure map content. |
| Functionality | 1/3 | PASS | MEDIUM | Horizon preview, checkpoint selection, keyboard-accessible event selection, disabled execution controls, and next-turn route semantics are understandable. Several navigation and drawer controls appear interactive but have no behavior, and exact evidence provenance is not available from selected events. |

## What's Working Well

- The central delta ribbon is the correct visual protagonist. Its width changes materially over time, and the increasing coral saturation communicates divergence without relying on green/red correctness semantics.
- The three lanes are unmistakable. “As-Lived,” “Delta,” and “Hindsight” have distinct editorial labels, stable positions, and a useful layer key without becoming three separate authored stores.
- Matter/CourtCase identity and Knowledge partition/horizon are adjacent but clearly separated into different header blocks, matching the domain boundary in the brief.
- The left rail handles prototype honesty well. Pace, schedule, batch, disclosure tier, re-walk, and checkpoint controls are visible, while execution controls are visibly disabled and repeatedly marked held/not proven.
- Graphiti beliefs are correctly presented as a separate memory layer with current and invalidated states, not as evidence or Semantica output.
- Semantica is explicitly first-class and upstream. Its candidate counts are separated from belief formation, and the copy states that it forms no beliefs.
- The requested route, policy path, actual model, fallback, and next-turn switching semantics are unusually clear in both the masthead and persistent footer.
- Keyboard focus styling, reduced-motion handling, SVG title/description, and Enter/Space activation for events show meaningful accessibility attention.

## Issues Found

### Issue 1: Exact provenance is promised visually but not exposed operationally

- **What**: Dashed provenance threads connect events across lanes, but selecting an event shows only a narrative title and explanation. It does not reveal a canonical evidence identifier, normalized-record identifier, custody hash, source pointer, or acquisition/realization timestamp.
- **Where**: Central temporal map event groups and the lower-right selected-divergence readout.
- **Why it matters**: The brief explicitly requires timeline events to link to canonical evidence and exact provenance. In an evidence product, a visual line alone cannot support verification or distinguish a sourced event from an illustrative relationship.
- **Suggested fix**: Extend the selected-event readout with a compact provenance block such as `evidence_item`, `normalized_record`, H1 hash prefix, source acquisition time, and realization event. Add a clear “Open evidence” affordance while retaining fictional identifiers.

### Issue 2: Drawer and section controls over-promise interaction

- **What**: People, Claims, Issues, Evidence, Works, and the upper navigation tabs all use button styling and hover/focus behavior, but only checkpoint and event controls have implemented behavior. The visible drawer also mixes a person, beliefs, and a work product while “People” remains selected.
- **Where**: Top atlas navigation and right-side linked-layers drawer.
- **Why it matters**: The controls look actionable, so their inert behavior creates false affordance. Mixing layer types under the People tab weakens the otherwise excellent information architecture.
- **Suggested fix**: Implement minimal tab switching with realistic sample content for each drawer layer, or render non-demonstrated tabs as static labels/disabled prototype controls. Keep Graphiti beliefs in a Memory layer or clearly label the panel as a cross-layer selection rather than People.

### Issue 3: Tablet compression is dominated by horizontal panning

- **What**: At 768px, the controls consume a fixed 170px while the map retains a 650px minimum width, forcing the primary canvas and footer route to extend beyond the viewport. The event readout is partially offscreen until the operator pans. At 375px, almost all of the delta visualization begins outside the initial viewport.
- **Where**: The `max-width: 920px` stage, canvas, and footer composition.
- **Why it matters**: A temporal atlas can legitimately pan, but the brief asks for a credible compressed tablet state. The current initial tablet view hides part of the memorable element and makes the selected divergence difficult to inspect alongside its horizon controls.
- **Suggested fix**: At tablet width, collapse Horizon Controls into a horizontal summary/expandable sheet above the map, allow the central SVG to use nearly the full viewport width, and move the selected-event readout below the map. Keep deliberate horizontal panning inside the map only, with a visible pan cue or minimap.

### Issue 4: Small annotations lose hierarchy at compressed widths

- **What**: Several SVG event notes, provenance labels, route details, drawer types, and Semantica telemetry render around 8–9px. They are crisp on desktop but become difficult to scan once the page is compressed or panned.
- **Where**: SVG map annotations, persistent provider footer, drawer metadata, and Semantica upstream card.
- **Why it matters**: Dates and horizon boundaries scan well, but supporting evidence metadata—the information an operator uses to verify the map—should not require close visual effort.
- **Suggested fix**: Raise essential annotation text to a rendered minimum near 10–11px, reduce the number of simultaneously visible notes, and reveal secondary details in the selected-event readout rather than placing every label on the map.

## Priority Fixes for Next Attempt

1. Add exact, fictional provenance fields and an “Open evidence” affordance to the selected-event readout so every divergence can be verified against canonical evidence and custody.
2. Implement the linked-layer tabs—or visibly mark them as held—and separate People, Graphiti belief memory, Evidence, and generated Work Products into honest panel states.
3. Recompose the 768px state so the delta ribbon and selected event are visible without page-level horizontal panning; confine any intentional panning to the atlas canvas.

## Should the next attempt REFINE or PIVOT?

**REFINE.** The fundamental direction is exceptionally well matched to the brief, and the central visual metaphor should be preserved. The next attempt should concentrate on verification detail, truthful interaction states, and a more intentional tablet composition rather than changing the aesthetic or information model.
