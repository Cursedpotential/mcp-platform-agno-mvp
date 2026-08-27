---
scope: server/tools
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - server/tools/AGENTS.md
  - docs/CONVENTIONS.md
watches:
  - "server/tools/**/*.py"
  - server/tools/AGENTS.md
contains_secrets: false
---

# Tool and Parser Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- One tool performs one atomic capability and registers by stable capability, not implementation
  language or function name.
- Parsers parse only. Engine routing is decoder-coverage based, never file-size based.
- Every parser emits the same contract and accounting shape. No parser receives a private
  destination, hashing recipe, or special promotion path.
- Off-the-shelf tools are preferred when observed output proves they work; otherwise implement a
  compatible wrapper without changing downstream contracts.
- Keep exact donor provenance and never expose secrets or evidence bodies through logs/tool catalogs.

<!-- freshness
watches_hash: 101a047
last_verified: 2026-08-27
watches:
  - server/tools/**/*.py
  - server/tools/AGENTS.md
-->
