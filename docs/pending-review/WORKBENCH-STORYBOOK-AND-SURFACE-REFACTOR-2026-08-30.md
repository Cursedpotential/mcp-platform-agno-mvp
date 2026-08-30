# Workbench Storybook and two-surface refactor

> _Byline: Codex · GPT-5.6-Sol · 2026-08-30._

STATUS: FOUNDATION IMPLEMENTED / DEPLOYED / LIVE ROUTES VERIFIED

## Owner direction captured

- The Workbench remains two related product surfaces, expressed as separate source directories:
  - `workbench/web/src/surfaces/primary/` — the everyday **Evidence Operations Desk**.
  - `workbench/web/src/surfaces/advanced/` — the **Modular Service Cockpit**.
- Shared visual and behavioral contracts live under `workbench/web/src/platform-ui/` rather than
  inside either surface.
- Storybook is the shared component workshop and visual contract. It is not a canonical data,
  workflow, or authority layer.
- The separate agent's Storybook/Glide document sorting work belongs to the primary surface when
  its implementation is ready for integration. This slice deliberately does not duplicate it.
- `react-calendar-timeline` and `vis-timeline` remain available as development-only visualization
  options. There is no artificial bake-off and no ruling that one must replace the other.
- Timesketch moves to the advanced surface. It remains a standalone governed projection and is not
  replaced by a lightweight primary-surface timeline.

## Implemented locally

- Added Storybook 10.5 on the React/Vite adapter, with Docs and accessibility addons.
- Added `storybook` and `build-storybook` package scripts.
- Added Storybook light/dark rendering based on the approved warm-paper/graphite palette.
- Added first-class stories for:
  - the approved Platform palette;
  - the primary Evidence Operations Desk boundary;
  - the advanced Modular Service Cockpit boundary.
- Added a typed two-surface registry and moved the live navigation definition into
  `src/surfaces/primary/navigation.ts`.
- Kept advanced navigation empty and fail-closed. No Timesketch, graph, map, workflow, or legal
  destination is exposed before its live-proof gate passes.
- Replaced the Storybook Next-specific adapter with the React/Vite adapter after the former
  introduced a no-fix high-severity advisory through a development-only image parser dependency.
  The resulting dependency audit is clean.
- Storybook's generated `storybook-static/` output is ignored by Git and ESLint.

## Timesketch sharing boundary

The local fork audit found that Timesketch's default frontend is Vue 2/Vuetify 2, with an optional
Vue 3/Vuetify 3 frontend, while Workbench is React. Therefore:

- share generated CSS variables/design-token JSON, vocabulary, and launch/deep-link schemas;
- do not import Workbench React components into the Timesketch fork;
- reserve web components for small framework-neutral leaf controls if later justified;
- do not make an iframe the target architecture;
- enter the advanced Timesketch surface through a future short-lived, scoped server-side launch
  exchange, not by exposing an internal sketch identifier as the Workbench contract.

No launch exchange or Timesketch UI route was implemented in this slice.

## Verification

| Check | Result |
|---|---|
| `npm run build` | PASS — Next production build, 17 static routes |
| `npm run build-storybook` | PASS — palette plus primary and advanced surface stories |
| `npm run lint` | PASS with zero errors; two pre-existing warnings in untouched `uiw-preview-client.tsx` |
| `npm audit --audit-level=high` | PASS — zero vulnerabilities after moving to React/Vite Storybook |
| `git diff --check -- workbench/web` | PASS |
| Workbench smoke files | 16 PASS / 3 FAIL in untouched matter/intake tests |

The three smoke failures are outside this refactor's files:

1. `matter-flow.smoke.test.mjs` does not expect the current fixed-case request to
   `GET /api/matters?limit=50&offset=0`.
2. `unified-intake-anatomy.contract.test.mjs` still expects `preview.select_ref`, while the current
   UI renders the parser identity/version/config digest returned by the preview state.
3. The same contract test expects older receipt copy referring to a Temporal identity; current UI
   says "Server-returned preview identity and latest durable workflow phase."

These failures were recorded, not repaired, because neither the affected tests nor their production
components belong to this Storybook/surface-boundary slice.

## Production deployment receipt

- Implementation commit: `2952250dfe8eab94a2fa861658302236ac452e5e`.
- Coolify application: `knowledge-workbench` (`xjbuo6drbwjfby75lalk8bk7`).
- Coolify deployment: `vis21loq504r6spk6krpwyg9`, terminal status `finished`.
- The production image built the Next.js application successfully and generated all 17 static
  routes before Coolify replaced the prior container.
- Stable Tailscale Service live proof after replacement:
  - `GET https://workbench.tilapia-skilift.ts.net/health` returned HTTP `200` and JSON.
  - `GET https://workbench.tilapia-skilift.ts.net/` returned HTTP `200` and the Platform HTML title.
  - `GET https://workbench.tilapia-skilift.ts.net/evidence/preview` returned HTTP `200` and the
    Platform HTML title.

This proves deployment and live reachability of the current Workbench build. Storybook remains a
development workshop built and verified separately; it was not added as a public production route.

## Still open

- Integrate the other agent's Glide sorter without duplicating its component or query contract.
- Add stories for real primary-surface components as they are refactored; do not create feature
  inventory mockups disconnected from production behavior.
- Select a lightweight timeline engine per concrete visualization. Both retained engines may be
  used when their interaction models serve different jobs.
- Add the Timesketch advanced launch/deep-link contract only after its deployment, authority, and
  PostgreSQL round-trip gates pass.
- TanStack Query/Router/Form adoption and removal of the static Next shell are separate follow-on
  slices, not implied complete by this Storybook foundation.
