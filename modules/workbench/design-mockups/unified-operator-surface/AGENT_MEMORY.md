---
scope: workbench/design-mockups/unified-operator-surface
status: current
verified_at: 2026-08-27
superseded_by: null
authority:
  - workbench/design-mockups/unified-operator-surface/AGENTS.md
  - docs/design/0061-unified-operator-surface/spec.md
watches:
  - workbench/design-mockups/unified-operator-surface/**
contains_secrets: false
---

# Approved Unified Surface Memory

> _Byline: Codex · GPT-5 · 2026-08-27._

- **Owner directive:** graphite shell, warm light workspace, compact operations density,
  plain-language labels, and a light/dark theme control are the approved visual direction.
- The first complete slice is intake: choose data, perform local extraction, show hash/metadata and
  parser details, preview the normalized conversation, reject or confirm, and show an honest receipt.
- A browser-local simulation must label itself as such. Confirmation does not make chat evidence and
  does not claim a production write unless the governed backend returns a production receipt.
- Preserve the approved layout while wiring real APIs. Do not replace it with the legacy Workbench.
- Run `npm run build` and `npm run test:sites` after UI changes; live deployment verification remains
  a separate requirement.

Exact `src/App.jsx` rationale:
`src/.agent-memory/App.jsx.md`.

<!-- freshness
watches_hash: 9408e93
last_verified: 2026-08-27
watches:
  - workbench/design-mockups/unified-operator-surface/src/**/*.jsx
  - workbench/design-mockups/unified-operator-surface/src/**/*.css
  - workbench/design-mockups/unified-operator-surface/AGENTS.md
  - workbench/design-mockups/unified-operator-surface/package.json
-->
