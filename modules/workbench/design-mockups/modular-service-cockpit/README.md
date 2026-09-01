# Modular Service Cockpit

> _Byline: Codex · GPT-5 · 2026-08-15_

This standalone mockup explores a customizable operator workstation organized around explicit service boundaries. Open `index.html` directly; it has no build step, external assets, or network dependencies.

The persistent context spine keeps Matter, CourtCase, knowledge partition, horizon/pass, run, and provider route visible while the operator changes workspaces. The five presets reorder the same service surfaces without changing that active scope. Each panel can be dragged or moved with keyboard-accessible controls, collapsed, focused, and pinned; **Save layout** persists the arrangement locally. The command palette opens from the header or `Ctrl/Cmd + K`.

## Module boundaries

- Semantica is the privileged extraction service. It owns structural extraction and proposed claims, but those claims remain candidates until reviewed.
- Ingestion owns coverage-based Go/Python routing and normalized writes.
- Canonical Knowledge owns authored, temporally filterable records.
- Evidence/Custody owns hashes, custody events, and controlled evidence promotion.
- Graphiti owns an agent's accumulated belief state, not canonical evidence.
- Agents/AG2 owns coordination and remains behind a framework-neutral adapter boundary.
- Provider routing owns the exact provider, model, tier, and when a change takes effect.
- OpenCode owns isolated generated work and restricted tool execution.
- Observability owns rebuildable telemetry and audit visibility.

## Configuration cost

This approach makes boundaries and hidden scope unusually visible, but configurability has a real cost: more layout state to persist, more permission combinations to test, additional responsive behavior, and a greater risk that operators create personally efficient but inconsistent workspaces. Production would need governed presets, reset-to-standard behavior, versioned workspace layouts, and validation that module visibility never bypasses authorization or horizon enforcement.
