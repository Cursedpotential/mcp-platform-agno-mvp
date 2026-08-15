# Workbench Mockup Variant 3 — Modular Service Cockpit

> _Byline: Codex · GPT-5 · 2026-08-15_

## Objective

Create a self-contained HTML mockup for a customizable operator cockpit where each major platform service has a clear, honest surface and can be arranged into task-specific workspaces.

## Audience

The technical owner/operator who needs to move rapidly between case work, ingestion, agents, provider routing, memory, extraction, and code execution without losing Matter or provenance context.

## Aesthetic direction

A modular professional workstation: dockable panels, command palette, strong hierarchy, and clear service identities. Avoid gamer aesthetics and generic glowing AI cards. Use a dark mineral base with low-saturation service colors and precise typographic density.

## Content structure

- Workspace presets: Case Review, Ingestion, Agent Lab, Horizon Analysis, and Platform Ops.
- Persistent context bar for Matter, CourtCase, Knowledge partition, active horizon/pass, run, and provider route.
- Docked service modules for Semantica VIP, Go/Python ingestion routing, canonical Knowledge, Evidence/Custody, Graphiti belief memory, Agents/AG2 candidate adapter, Portkey/direct providers, OpenCode workspace/sandbox, and observability.
- Each module must show ownership boundary, current status, last verified action, pending work, and whether its data is canonical, projected, candidate, belief, or generated work.
- Provider/model selector supports presets plus authorized exact provider/model/tier selection and makes next-turn/next-stage semantics explicit.
- OpenCode module shows isolated workspace, session, model, tool activity, and sandbox boundary.
- Semantica is visually first-class/VIP, never labeled candidate; its extracted claims may remain candidates.
- Include a command palette or workspace switcher interaction.

## Typography

Use a compact grotesk or humanist sans for controls, a technical mono for service telemetry, and disciplined uppercase micro-labels. Density should remain readable rather than miniature.

## Color direction

Dark graphite/mineral surfaces with distinct restrained accents per service family: Semantica gold, custody red/amber, Knowledge blue, memory violet, agents teal, OpenCode green, providers cyan. State color and service color must not be conflated.

## Memorable element

A persistent context spine across the top should show every scope currently affecting an action—Matter → CourtCase → partition → horizon → run → route—so a user can see and change scope without hidden state.

## Image needs

No photography. Use simple schematic service glyphs and CSS-only ambient texture; no external assets.

## Technical/output constraints

- Self-contained responsive `index.html`; no external network dependencies or build step.
- Desktop-first at 1440px; demonstrate at least one alternate workspace preset through minimal inline JS.
- Fictional sample data only.
- Output: `workbench/design-mockups/modular-service-cockpit/index.html`.
- Include a short `README.md` describing module boundaries and the cost of this more configurable approach.
