---
scope: llm_probe
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/PROJECT_CANON.md
watches:
  - "llm_probe/**/*.py"
  - AGENTS.md
contains_secrets: false
---

# LLM Probe Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Probe output is evaluation data, not evidence or established fact.
- Remote providers only on this machine; do not restore local ONNX/model inference.
- Record provider, model, prompt/version, timestamps, and failure boundaries for comparable runs.
- Never print, persist, or expose provider credentials.

<!-- freshness
watches_hash: 909a201
last_verified: 2026-08-27
watches:
  - llm_probe/**/*.py
  - AGENTS.md
-->
