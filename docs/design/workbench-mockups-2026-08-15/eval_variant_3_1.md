# Evaluation — Attempt 1

> _Byline: Codex · GPT-5 · 2026-08-15_

## Overall Verdict: NEEDS REVISION

## Overall Assessment

The mockup establishes a convincing dark professional workstation, and its
Matter → CourtCase → partition → horizon → run → route spine is the strongest
scope-control treatment in the three concepts. However, the main workspace is
still a preset-filtered card grid rather than a credibly dockable cockpit, and
several brief-mandated module details are missing. Local renders at 1440, 768,
and 375 pixels also show that the disciplined desktop density degrades into
clipping and overly small telemetry at narrower widths.

## Scores

| Criterion | Score | Status | Weight | Notes |
|---|---:|---|---|---|
| Design Quality | 2/3 | PASS | HIGH | The mineral palette, restrained service accents, exact micro-label language, and persistent context spine form a coherent workstation identity. Semantica has appropriate visual priority without becoming garish. |
| Originality | 1/3 | FAIL | HIGH | The context spine is custom and memorable, but the workspace beneath it is a conventional repeated-card dashboard. Panels cannot be moved, resized, collapsed, pinned, or reordered, so the advertised docking/customization is mostly a visual metaphor. |
| Craft | 1/3 | PASS | MEDIUM | Desktop alignment and color discipline are solid, but much of the operational text is only 8–9px and the faint color is used at that size. Tablet/mobile renders show horizontal clipping and truncated module content rather than a controlled compressed state. |
| Functionality | 1/3 | PASS | MEDIUM | Preset switching, filtering, selects, and the command-palette overlay are present and the JavaScript parses cleanly. Scope blocks look clickable but are not controls, “Change scope” opens a workspace command palette, and the palette lacks robust keyboard navigation/focus containment. |

## What’s Working Well

- The context spine is excellent information architecture. It exposes every
  action-affecting scope in the requested order and gives each one both a human
  label and technical identifier.
- Service colors identify families while the small status squares separately
  carry ready/review/paused state. This respects the brief’s requirement not to
  conflate service identity with health.
- Semantica is unmistakably first-class: “VIP service” and “Privileged
  extraction plane” are prominent, while only its extracted claims are labeled
  candidate.
- The data-state vocabulary—canonical, projected, candidate, belief, and
  generated—is repeated consistently and reinforced by the operator-queue
  legend.
- Graphiti is correctly framed as non-canonical agent-lived belief memory, and
  the OpenCode panel clearly communicates network denial and restricted tools.
- The provider module explicitly separates provider, exact model, service tier,
  and apply timing; “next turn” is visible rather than hidden in configuration.
- Static verification passed: the HTML parses, inline JavaScript passes
  `node --check`, and the document contains no external URLs.

## Issues Found

### Issue 1: The “dockable cockpit” is a filtered card grid

- **What**: Presets only hide/show modules and occasionally make one span two
  columns. There are no docking handles, panel controls, resize states, collapse,
  pinning, reordering, or a visible saved-layout interaction.
- **Where**: `.module-grid`, every `.module-head`, and `setPreset()`.
- **Why it matters**: Custom arrangement is the objective and the main source of
  potential originality. Without a credible arrangement interaction, this
  becomes the exact repeated-card dashboard pattern the design instructions warn
  against.
- **Suggested fix**: Add a restrained panel control cluster to every module
  (drag handle, collapse, focus, pin), implement at least reorder plus
  collapse/focus in minimal JavaScript, and make the active layout manifest
  visibly update. Presets should rearrange modules, not merely remove them.

### Issue 2: Modules do not consistently satisfy their information contract

- **What**: The brief requires every service module to show ownership boundary,
  current status, last verified action, pending work, and data class. Several
  panels omit an explicit pending item or verified-action label. The OpenCode
  module shows workspace, session, tools, and network boundary but no active
  model. Provider routing shows requested selections but not a clearly separated
  effective/actual route inside the module.
- **Where**: Especially Canonical Knowledge, Graphiti, Provider routing,
  OpenCode, and Observability modules.
- **Why it matters**: Operators must compare services without inferring whether
  blank space means “none,” “unknown,” or “not implemented.” OpenCode’s model and
  effective provider are specifically required for execution accountability.
- **Suggested fix**: Give every module the same compact audit footer:
  `last verified`, `pending`, and `authority/data state`. Add OpenCode model and
  session pin, and show provider `requested`, `effective now`, and `pending next
  turn/stage` as three explicit rows.

### Issue 3: Dense typography crosses into miniature telemetry

- **What**: Many meaningful labels, timestamps, source identifiers, state tags,
  and module metadata use 8–9px text. The faint color compounds the issue.
- **Where**: `.micro`, `.scope code`, `.module-title span`, `.status`,
  `.data-class`, `.metric span`, `.activity time`, `.stage small`, queue metadata,
  and the inspector verification block.
- **Why it matters**: These are not decorative captions; they carry provenance,
  safety, and routing semantics during long work sessions. The brief explicitly
  asks for readable density rather than miniature type.
- **Suggested fix**: Establish 10px as the absolute micro-label floor, 11px for
  telemetry, and 12px for operational body copy. Increase faint-text luminance
  and recover density through tighter spacing and shorter labels instead of
  shrinking type.

### Issue 4: Tablet and mobile states clip rather than compress

- **What**: The 768px render exposes only part of the second module column, and
  the 375px render clips long workspace copy and right-side module content. The
  preset strip also disappears progressively without a clear replacement.
- **Where**: The 1180px two-column `.module-grid`, the 760px masthead/preset
  rules, module flex/grid children, and long unbroken telemetry.
- **Why it matters**: Horizontal scanning hides custody, status, and pending-work
  data—the exact information this cockpit must keep visible. “Desktop-first”
  still requires a credible responsive state.
- **Suggested fix**: Switch to one module column before content reaches its
  min-content width (roughly 900px), apply `min-width: 0` and overflow wrapping
  to every flex/grid text child, stack metric/pipeline sections when needed, and
  replace the disappearing preset strip with one compact workspace selector.

### Issue 5: Scope affordances are misleading and not keyboard-complete

- **What**: Each `.scope` has `cursor: pointer` and hover styling but is a plain
  `div` with no keyboard semantics or click behavior. The “Change scope” button
  opens the workspace command palette rather than a scope editor. The dialog has
  no focus trap, arrow-key selection, Enter activation, or focus restoration.
- **Where**: `.scope`, `#changeScope`, `.palette-backdrop`, and palette JavaScript.
- **Why it matters**: The context spine is the product’s safety-critical control
  surface. False affordances and incomplete keyboard behavior undermine trust
  precisely where hidden scope must be eliminated.
- **Suggested fix**: Make each scope segment a real button with an explicit
  editor/popover, or remove pointer/hover affordances. Separate workspace commands
  from scope changes. Implement focus containment, Up/Down, Enter, Escape, and
  return-focus behavior for the command palette.

### Issue 6: Fictional docket presentation is overly realistic without a fixture cue

- **What**: “Rowan v. Rowan” and `2026-DM-1048` satisfy the fictional-data rule,
  but the interface does not visibly mark the page as sample/mock data.
- **Where**: Matter and CourtCase segments in the context spine.
- **Why it matters**: This is a minor prototype-safety concern: screenshots can
  be detached from their repository context and mistaken for an actual matter.
- **Suggested fix**: Add a quiet `DEMO FIXTURE` or `SAMPLE DATA` indicator in the
  masthead without weakening the professional aesthetic.

## Priority Fixes for Next Attempt

1. Turn the module grid into a believable dock system: add panel controls and
   implement reorder plus collapse/focus; make presets rearrange a visible
   layout manifest instead of only hiding modules.
2. Normalize every module to the complete audit contract—ownership, data class,
   status, last verified, pending—and add OpenCode’s active model plus explicit
   requested/effective/pending provider-route rows.
3. Repair responsive density: move to one column earlier, eliminate horizontal
   clipping, provide a compact workspace selector, and raise operational text to
   a readable 10–12px scale.

## Should the next attempt REFINE or PIVOT?

**REFINE.** The dark mineral direction, service-family accents, state semantics,
and persistent context spine are all appropriate and worth preserving. The next
attempt should deepen the cockpit metaphor through real arrangement behavior and
complete module contracts, not replace the visual language.
