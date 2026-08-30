# The Platform Workbench — browser application

> _Byline: Codex · GPT-5.6-Sol · 2026-08-30._

This is the browser-first operator surface for The Platform. It is a React + Vite application
served same-origin by `workbench/api` and deployed as the `knowledge-workbench` Coolify service.
It does not require Next.js, server components, server actions, or a separate JavaScript runtime in
production.

Desktop packaging is deliberately deferred. Once the browser product is complete, a Tauri host can
be added around the same client application with explicit adapters for local files, IPC, and SQLite.
The separate Case Bible desktop/sorting lane is not copied into this directory.

## Current stack

- React 19 + TypeScript
- Vite 8 for browser development and production bundling
- TanStack Router for code-split client routes
- Storybook 10 on the same Vite builder
- Tailwind CSS and the tracked Platform component primitives
- FastAPI for same-origin APIs and SPA fallback serving
- Indexed/browser state only where a feature explicitly needs it; PostgreSQL remains canonical

Glide Data Grid is the selected direction for data-heavy review tables, but table migration is not
claimed by the Vite shell release. It should be introduced one complete operational table at a time,
with its data contract and browser smoke coverage intact.

## Product boundary

The root route is the Evidence Operations Desk. The primary navigation exposes only the complete
daily path:

- `/` — live operational desk
- `/intake` — governed source selection and intake
- `/evidence/preview` — parser/message/provenance preview

Existing advanced routes remain directly addressable while they are reconciled, but they are not
advertised as finished navigation destinations. The browser must never infer a canonical write from
local state; durable API receipts remain authoritative.

## Local browser development

Use Node.js 22.13 or newer; the Vite and AI SDK dependency graph is intentionally built on the
same supported Node major used by the production image.

```powershell
npm ci
npm run dev
```

Vite listens on `127.0.0.1:5173` and proxies `/api` and `/health` to the Workbench API at
`127.0.0.1:8020`. Set `VITE_API_URL` only when a different browser API origin is intentionally
required. Classification-specific calls may use `VITE_API_BASE`; the default is `/api`.

## Verification

```powershell
npm run lint
npm run build
npm run smoke
npm run build-storybook
```

`npm run build` typechecks and writes the production bundle to `dist/`. The smoke suite serves that
actual SPA bundle through a same-origin fixture and exercises the governed Matter journey plus the
static contract tests. Browser profiles created by the journey are retained under the repository's
`to_be_deleted/` directory for owner-only cleanup.

The focused backend static-serving contract runs from the repository root:

```powershell
uv run pytest -q workbench/api/tests/test_vite_static_frontend.py
```

## Production serving

`workbench/Dockerfile` runs `npm ci`, builds `web/dist`, copies it into `/app/static`, and starts the
FastAPI service on port 8020. FastAPI routers are registered before the static mount. Extensionless
client routes fall back to `index.html`; reserved API/documentation/health paths and missing assets
remain real 404 responses.

The stable private browser address is `https://workbench.tilapia-skilift.ts.net`. A successful local
build or an old healthy container is not deployment proof; acceptance requires the exact Coolify
revision plus live root, health, and deep-link verification.

## Donor attribution

The original interface was bootstrapped from the MIT-licensed
`backblaze-b2-samples/agentic-rag-vector-starter-kit`. Its workspace, chat/RAG dashboard, B2 browser,
and Next.js runtime assumptions were removed. Shared primitive ancestry and this attribution are
retained.

The superseded Next-specific README is preserved, not deleted, at
`to_be_deleted/workbench-next-shell-20260830/workbench-web/README-next-architecture.md`.
