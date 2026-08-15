# Evaluation — Attempt 2

> _Byline: Codex · GPT-5 · 2026-08-15_

## Overall Verdict: PASS

## Overall Assessment

The revision now behaves like a configurable operator cockpit rather than a
preset-filtered card dashboard. The persistent context spine remains its
strongest product-specific idea, while reorder, collapse, focus, pin, saved
layout state, normalized audit footers, and explicit execution routing give the
workspace a credible operational model. Fresh local renders at 1440, 768, and
375 pixels confirm that desktop and tablet are substantially improved; mobile
still has horizontal overflow in several dense module internals.

## Scores

| Criterion | Score | Status | Weight | Notes |
|-----------|------:|:------:|:------:|-------|
| Design Quality | 2/3 | PASS | HIGH | The mineral workstation language is coherent across the context spine, service accents, dock controls, audit footers, manifest, and operator queue. Semantica remains appropriately first-class without conflating VIP identity with health. |
| Originality | 2/3 | PASS | HIGH | The scope spine plus a reorderable, collapsible, focusable, persistable service layout is now a custom response to this platform rather than a conventional filtered card grid. Repeated rectangular modules keep it below a genuinely novel 3. |
| Craft | 1/3 | PASS | MEDIUM | The 980px single-column breakpoint fixes the tablet clipping, critical telemetry has been raised to a 10–11px floor, and wrapping rules are much stronger. At 375px, however, the page still overflows horizontally and clips scope values, workspace copy, ownership text, metrics, and route details. |
| Functionality | 2/3 | PASS | MEDIUM | Presets visibly reorder and focus modules; keyboard move buttons, collapse, focus, pin, layout save/restore, compact preset selection, and palette arrows/Enter/Escape/focus return form a credible prototype. Pinning is still mostly visual, and programmatic preset/restore changes do not synchronize every panel-control `aria-pressed` state. |

## What’s Working Well

- The prior originality failure is resolved. Every module now has a restrained
  control rail, modules can be reordered by drag or keyboard-accessible move
  controls, and collapse/focus states visibly alter the composition.
- Workspace presets now carry explicit ordered manifests. Switching between
  Case Review, Ingestion, Agent Lab, Horizon Analysis, and Platform Ops changes
  module order and focus instead of merely hiding panels.
- The layout manifest distinguishes preset, unsaved custom, saved custom, and
  restored custom states. This makes customization legible rather than a hidden
  browser behavior.
- The audit contract is consistent across all nine modules: owner boundary,
  status, last verified action, pending work, and data class are all present.
  Explicit “No refresh pending” and “No active alerts” values avoid ambiguous
  blanks.
- Provider routing now separates requested, effective-now, and pending state,
  with next-turn semantics and a clear no-mid-turn-mutation warning.
- OpenCode now exposes active model, session pin, isolated workspace, network
  denial, restricted tools, staged output, and generated/non-canonical status.
- The 768px render is a credible compressed workstation: a compact preset
  selector replaces the masthead preset strip, the context spine wraps into two
  rows, and modules become a readable single column without page-level clipping.
- The `DEMO FIXTURE` marker resolves the detached-screenshot ambiguity from
  Attempt 1.
- The command palette adds Up/Down selection, Enter activation, Escape, focus
  containment, and return-focus behavior. “Change scope” no longer opens the
  unrelated workspace palette.
- Static verification passed: the HTML parses, the inline JavaScript compiles,
  `git diff --check` is clean, and the document has no external assets or URLs.

## Issues Found

### Issue 1: Mobile still has page-level horizontal overflow

- **What**: At 375px, several right edges remain outside the viewport. The
  CourtCase and Route scope values are clipped; the workspace description runs
  past the edge; and Semantica ownership, the third metric, activity copy, and
  later provider/OpenCode rows are only partially visible.
- **Where**: The two-column mobile context spine, `.workspace-head`,
  `.boundary`, `.metric-row`, route-state rows, and module audit content.
- **Why it matters**: The mobile state hides exactly the ownership, status, and
  route semantics the cockpit exists to expose. The page is still usable as a
  desktop-first prototype, but the 375px composition is not release-grade.
- **Suggested fix**: At the 760px breakpoint, use a one-column scope list or
  permit each value to wrap instead of ellipsizing; force `max-width: 100%` and
  `min-width: 0` through workspace and module children; stack three-part metrics
  below roughly 460px; and add `overflow-wrap: anywhere` to route and ownership
  values. Verify `document.documentElement.scrollWidth <= innerWidth` at 375px.

### Issue 2: Pin and restored control states are not fully truthful

- **What**: Pinning adds a visual border and persists a boolean, but it does not
  protect placement when a preset is applied. `setPreset()` and saved-layout
  restoration also change focus/collapse/pin classes without synchronizing the
  corresponding control labels, symbols, and `aria-pressed` values.
- **Where**: Panel-control click handling, `setPreset()`, and the saved-layout
  restore block.
- **Why it matters**: A pin conventionally promises stable placement, and stale
  accessibility state can tell a keyboard or screen-reader user the opposite of
  the visible panel state.
- **Suggested fix**: Either define pin honestly as a visual favorite, or keep
  pinned modules anchored across presets. Centralize panel-state application in
  one function that updates class, button text, title, and `aria-pressed` for
  direct actions, presets, and restoration.

### Issue 3: The scope editor remains an initially actionable held control

- **What**: “Change scope” is a live-looking button whose only action is to
  rename itself “Scope editor · demo held”; it cannot inspect or change any
  scope field.
- **Where**: The right end of the persistent context spine and
  `#changeScope` handler.
- **Why it matters**: This is much safer than opening the wrong palette, but the
  first label still promises an operation the prototype intentionally withholds
  on the product’s safety-critical scope surface.
- **Suggested fix**: Label it `Scope editor · held` from the outset and disable
  it with an explanatory description, or implement a read-only scope summary
  dialog that makes the held state explicit before offering any mutation.

## Priority Fixes for Next Attempt

1. Eliminate 375px page-level horizontal overflow so Matter/CourtCase scope,
   ownership, status, pending work, and provider/OpenCode routing remain visible.
2. Give pinning an honest behavioral definition and synchronize every visual and
   ARIA panel-control state after presets and saved-layout restoration.
3. Present the unavailable scope editor as held from the outset, or provide a
   truthful read-only scope dialog.

## Should the next attempt REFINE or PIVOT?

**REFINE, if another attempt is desired.** The design now passes and the core
direction should not change. A further pass would be responsive and semantic
polish: repair the 375px overflow, make pin behavior exact, and remove the last
scope-control over-promise.
