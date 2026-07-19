# Knowledge Workbench — web

> _Byline: Claude Code · Sonnet (agent) · 2026-07-19_

Staging + promote surface for the platform knowledge base. Two pages: **Upload**
(drag-drop staging) and **Files** (staged-file browser, metadata editor, promote).

## Donor origin

This app was bootstrapped from the `apps/web` package of
[backblaze-b2-samples/agentic-rag-vector-starter-kit](https://github.com/backblaze-b2-samples/agentic-rag-vector-starter-kit)
(MIT licensed), stripped down to a self-contained, non-workspace Next.js app and
re-pointed at this platform's staging/promote API instead of the donor kit's
chat + B2 + LanceDB backend. Attribution kept here per the donor's license terms;
no Backblaze/B2 branding or copy remains in the UI.

### What was removed from the donor kit

- **Chat + RAG**: `src/app/chat/`, `src/components/chat/` (streaming chat UI,
  citations, session sidebar) — this app never queries the knowledge base, it
  only stages and promotes files into it.
- **Dashboard**: `src/app/page.tsx` (the donor's session-analytics dashboard),
  `src/components/dashboard/` (stats cards, query/ingestion tables, retrieval
  quality, agent behavior, session drill-down, the recharts-based upload chart).
- **`packages/shared` workspace dependency**: types are now inlined at
  `src/lib/shared/types.ts` and rewritten around this app's `StagedFile` record
  (see `workbench/api/app/types/documents.py` for the backend source of truth)
  instead of the donor's B2/document-chunk/chat/dashboard types.
- **SSE streaming upload pipeline**: the donor kit uploaded via
  `POST /upload/stream` with live pipeline-step events (chunking, embedding,
  etc. shown in real time). This backend uploads via a single
  `POST /api/upload` call and returns the finished `StagedFile` (or a
  `duplicate: true` flag) — no streaming, no pipeline visualization.
- **B2-style file browser**: the donor's `file-browser.tsx` rendered a
  folder/key tree (`lib/file-tree.ts`) with download/delete actions against
  Backblaze B2 keys. Staged files have no folder concept, so `Files` is now a
  flat table (name, size, detected_type, domain, status, updated_at) with
  Promote + detail actions — no download/delete (out of scope for staging).
- **`e2e/`, `playwright.config.ts`**: skipped for this sprint per the build brief.
- **Unused shadcn/ui primitives**: `avatar.tsx`, `chart.tsx` (recharts),
  `scroll-area.tsx`, `tabs.tsx`, `toggle.tsx`, `alert-dialog.tsx`,
  `dropdown-menu.tsx` — not imported by anything in the Upload/Files/layout
  surface (the donor's tree file-browser used alert-dialog for a delete
  confirmation and dropdown-menu for row actions; the flat table + dialog
  rewrite here doesn't need either).
- **Dependencies dropped**: `recharts`, `react-markdown`, `remark-gfm` (chat +
  dashboard only). `shadcn` stays as a devDependency even though its CLI is
  never invoked in this build — `globals.css` does `@import "shadcn/tailwind.css"`,
  so the package itself is a real (if unusual) build-time dependency, not just
  a CLI tool.

### What was kept + adapted

- `src/components/upload/` — dropzone, progress list, and a new
  `upload-result.tsx` (replaces the donor's pipeline-progress/processing-status
  components) that shows the staged result per file, including a duplicate
  banner when the backend reports `duplicate: true`.
- `src/components/files/` — `file-browser.tsx` (rewritten as a table) and a
  new `file-detail-dialog.tsx` (replaces `file-preview.tsx` +
  `file-metadata-panel.tsx`) with a text preview pane and a metadata editor
  (domain select — exactly `timeline_relationship`, `personal_history`,
  `platform_design`, `legal_strategy` — plus category and source-platform
  inputs) and a Promote button.
- `src/components/layout/` — sidebar trimmed to Upload + Files only, header
  breadcrumbs simplified, Backblaze footer link replaced with a plain caption.
- All other `components/ui/*` primitives, `lib/utils.ts`,
  `lib/refresh-context.tsx`, and `hooks/use-mobile.ts` are unchanged from the
  donor kit.

## Static export

`next.config.ts` sets `output: "export"` and `images.unoptimized: true`. There
are no server actions, no route handlers (`src/app/api/**` does not exist in
this app — that's the sibling FastAPI service under `workbench/api/`), and no
`next/headers` usage. The built `out/` directory is meant to be served
same-origin by that FastAPI service, which is also why `src/lib/api-client.ts`
defaults its base URL to `""` (same origin) rather than
`http://localhost:8000`.

## Scripts

```
pnpm dev     # next dev
pnpm build   # next build -> out/
pnpm start   # next start (dev convenience only; static export doesn't need a server)
pnpm lint    # eslint
```

## Requirements

Node.js >= 20 (see `package.json` `engines`). No `packageManager` field is set
here — the donor kit's root `package.json` and this package both omit one; pnpm
is assumed per the donor kit's `engines.pnpm >= 9` (root only) and
`pnpm-workspace.yaml`, though this app itself is no longer part of that
workspace and can be built with npm/pnpm/yarn.
