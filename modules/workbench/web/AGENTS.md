# AGENTS.md — Workbench browser application

> _Byline: Codex · GPT-5.6-Sol · 2026-08-30._

- This subtree is React + Vite + TypeScript. Do not restore Next.js conventions, imports, runtime
  environment access, server components, or server actions.
- Browser build-time variables use `import.meta.env.VITE_*`. The production default is same-origin;
  do not bake a private service address into the client bundle.
- TanStack Router owns browser navigation. Preserve deep-link behavior through the FastAPI SPA
  fallback and keep unknown `/api`, health, docs, and asset paths as real 404 responses.
- Storybook uses the React/Vite builder. A Storybook build proves component compilation, not the
  deployed application or live API wiring.
- Finish and smoke-test one functional operator path before exposing another navigation
  destination. Do not advertise disconnected advanced surfaces.
- PostgreSQL and durable backend receipts remain authoritative. Browser state cannot promote,
  approve, or rewrite evidence by implication.
- Glide Data Grid is the target for data-heavy operator tables; migrate one complete table at a
  time and preserve its API/custody contract.
- Desktop/Tauri packaging is deferred until the browser application is complete. Keep desktop
  filesystem, IPC, and SQLite adapters outside browser-only modules.
- Run `npm run lint`, `npm run build`, `npm run smoke`, and `npm run build-storybook` for product
  changes. Coolify revision and live browser proof are separate required gates.

> _Sprint-mode policy REMOVED 2026-08-25 on owner order ("you're grounded — remove it entirely"). Confirm-and-discuss-before-changing is back in force._
