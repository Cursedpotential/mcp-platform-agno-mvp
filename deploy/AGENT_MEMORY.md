---
scope: deploy
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - AGENTS.md
  - docs/REPO_STRUCTURE.md
  - docs/PROJECT_CANON.md
watches:
  - deploy/**
  - compose.yaml
contains_secrets: false
---

# Deployment Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- Source is edited and validated in this checkout, committed, and pushed; Coolify builds and
  deploys on the VPS. Do not create or present a duplicate local stack as production progress.
- One Coolify application uses one `deploy/<app>.yaml`; preserve correct watch paths so unrelated
  pushes do not bounce data services.
- Tailnet services bind the intended tailnet address, not assumed localhost.
- Do not manually start, stop, remove, or replace Coolify-owned containers behind Coolify.
- Never print or persist secrets in this hierarchy. Authentication configuration must remain
  rotatable without requiring application-code redeployment where the chosen identity layer allows.
- A successful build is not a live receipt. Verify health and the actual owner-facing interaction.

<!-- freshness
watches_hash: 8c62fb8
last_verified: 2026-08-27
watches:
  - deploy/**/*.yaml
  - compose.yaml
-->
