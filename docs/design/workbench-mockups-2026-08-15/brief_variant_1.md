# Workbench Mockup Variant 1 — Evidence Operations Desk

> _Byline: Codex · GPT-5 · 2026-08-15_

## Objective

Create a self-contained HTML mockup for a desktop-first, single-operator family-law evidence Workbench. This variant should make daily evidence operations fast, legible, and court-safe. It is a visual prototype, not production code.

## Audience

The owner/operator managing large personal evidence collections, provenance review, case preparation, and agent-assisted analysis. Assume long work sessions, high information density, and attention-switching costs.

## Aesthetic direction

An intentional forensic operations desk: compact, calm, authoritative, and materially different from a generic SaaS dashboard. Use graphite, warm paper, restrained indigo, and amber status accents. Prefer crisp rules, tabular rhythm, and a few tactile paper/evidence details over rounded-card sprawl.

## Content structure

- Persistent Matter/CourtCase switcher and current custody/horizon status.
- Left navigation grouped by Case Work, Intelligence, and Platform Operations.
- Main workspace showing an evidence review queue with provenance, custody state, source type, review status, and next action.
- Right inspector showing exact source pointer, normalized-record preview, H1 hash/custody chain, review gates, and agent notes.
- Visible service health strip for Semantica VIP, Knowledge ingestion, Postgres, Weaviate, Graphiti, Portkey, OpenCode, and the orchestration adapter.
- Quick entry points for Knowledge, People, Timeline, Issues, Work Product, Horizon Replay, Agents, Providers, and Code Sandbox.
- Clearly distinguish canonical evidence, Knowledge search results, Graphiti belief memory, and generated work products.
- Show unsafe/unreviewed/HITL-required states prominently and accessibly.

## Typography

Use a serious humanist sans for navigation/body and a restrained mono for hashes, dates, IDs, and system provenance. Strong numeric alignment matters more than oversized headings.

## Color direction

Warm off-white and charcoal base; indigo for primary navigation/action; amber for needs-review; red only for custody/safety failure; muted green for verified. Maintain WCAG-friendly contrast.

## Memorable element

The evidence inspector should feel like opening a custody jacket: one continuous vertical provenance rail connecting source, normalized record, evidence draft, review gate, and court-safe status.

## Image needs

No photography. Use only simple inline schematic icons or CSS textures; do not use external assets or services.

## Technical/output constraints

- Self-contained responsive `index.html`; no build step and no external network dependencies.
- Desktop-first at 1440px, still coherent at tablet width.
- Include realistic sample data but no real names or sensitive data.
- Include interactive affordances sufficient to communicate layout (tabs, selected rows, expandable inspector) using minimal inline JavaScript if useful.
- Output: `workbench/design-mockups/evidence-operations-desk/index.html`.
- Include a short `README.md` in the same folder describing the direction and tradeoffs.
