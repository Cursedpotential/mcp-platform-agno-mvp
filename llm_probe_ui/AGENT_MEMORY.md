---
scope: llm_probe_ui
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - llm_probe/AGENT_MEMORY.md
watches:
  - "llm_probe_ui/**/*.ts"
  - "llm_probe_ui/**/*.tsx"
  - "llm_probe_ui/**/*.json"
contains_secrets: false
---

# LLM Probe UI Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- This UI visualizes evaluation runs; it does not turn model output into canonical facts.
- Display provider/model/prompt identity, progress, errors, and the exact validation boundary.
- Keep credentials server-side and out of browser bundles, logs, and screenshots.

<!-- freshness
watches_hash: 7dcb36e
last_verified: 2026-08-27
watches:
  - llm_probe_ui/**/*.ts
  - llm_probe_ui/**/*.tsx
  - llm_probe_ui/**/*.json
-->
