---
scope: vendored
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/REPO_STRUCTURE.md
watches:
  - "vendored/sbv/**/*.go"
  - vendored/sbv/DEVELOPMENT.md
contains_secrets: false
---

# Vendored Code Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Preserve upstream provenance and licenses. Do not reformat third-party code merely to satisfy
  platform lint rules.
- Wrap reusable capability behind platform-owned contracts instead of letting donor architecture
  become canonical by accident.
- `server/vendored/` is import-oriented third-party Python. Root `vendored/` contains non-Python
  projects that may be actively developed under their own development instructions.
- Upstream behavior and platform-specific changes must remain distinguishable for future merges.

<!-- freshness
watches_hash: 76ad554
last_verified: 2026-08-27
watches:
  - vendored/sbv/**/*.go
  - vendored/sbv/DEVELOPMENT.md
-->
