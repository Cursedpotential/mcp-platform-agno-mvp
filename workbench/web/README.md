# Knowledge Workbench — web (C1 Operator Console)

> _Byline: Claude Code · Sonnet (agent) · 2026-07-20 (C1 rebuild: Runs/Tools/Intake replaces Upload/Files-promote)_

The C1 Operator Console: drive the evidence spine instead of feeding a blind
upload->promote box (owner rejection, `docs/planning/operator-console-requirements.md`).
Three pages: **Runs** (default landing — start/watch spine runs stage-by-stage:
custody -> parse -> store -> knowledge), **Tools** (schema-generated forms over
every configured MCP server), **Intake** (the renamed Files page — upload folded
in, Promote buttons removed, each row's action is "Start run ->").

## C1 rebuild (2026-07-20)

- `POST /api/promote/{id}` still exists on the backend but nothing in this UI
  calls it anymore — `promoteFile`/`promoteAll`/`PromoteResult` were removed
  from `lib/api-client.ts` and `lib/shared/types.ts`.
- `/upload` route retired (folded into `/intake`) — the old route file is
  archived at `_stale/upload-page-pre-c1/page.tsx` (never deleted, per the
  project's no-delete convention), not part of the route tree.
- `/files` renamed to `/intake` (`src/app/files` -> `src/app/intake` via `git mv`);
  `src/components/files/` renamed to `src/components/intake/`,
  `file-browser.tsx` -> `intake-table.tsx`.
- New: `src/components/runs/` (RunsTable, NewRunDialog, RunDetailDialog,
  StageRail, StageDrawer, StageOutputView), `src/components/tools/`
  (ToolExplorer, ToolForm — hand-rolled JSON-Schema form, ToolResultPane),
  `src/lib/new-run-dialog-context.tsx` (lets the Runs page and the Intake
  table's row action both open the same New-run dialog), `src/components/ui/switch.tsx`
  and `textarea.tsx` (small primitives the donor kit didn't carry).
- Run/Stage/ToolServer/Tool types cross-checked against the actual spine
  implementation that landed in this same working tree mid-build
  (`server/evidence/run_ledger.py`, `server/api/run_routes.py`,
  `sql/0005_workflow_run_ledger.sql`) — notably, STAGE status uses
  `pending|running|success|failed|skipped` (not `completed`, which is only
  the RUN-level vocabulary), and the custody stage's blob-path field is
  named `blob_key`.

The sections below (donor origin, static-export constraints) describe the
original P0–P4 workbench build and still apply structurally.

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
