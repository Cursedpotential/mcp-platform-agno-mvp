# Knowledge Workbench — web (C1 Operator Console)

> _Byline: Claude Code · Sonnet (agent) · 2026-07-20 (C1 rebuild: Runs/Tools/Intake replaces Upload/Files-promote)_
> _Current-product repair: Codex · GPT-5 · 2026-08-15._

> **Current role:** this custom Next.js Workbench—not AgentOS Studio—is the accepted
> operator product. It consumes neutral platform/Workbench APIs so the browser does not
> depend on whether Agno or a future adapter coordinates a run.

## Current working-tree surfaces — held, not deployed

The original C1 description below is historical foundation, not the complete current route
map. The dirty working tree also contains Knowledge browsing and a Matter workspace with
Knowledge-to-Evidence actions. These additions have local build/test evidence but are
committed locally and not verified against deployed services. Horizon execution remains held.

- `/knowledge`: canonical, case-prefiltered Knowledge browsing plus separately labeled
  read-only Graphiti memory.
- `/matter`: Matter/CourtCase scope plus a bound canonical Knowledge pane. It
  prebinds the Matter partition and primary CourtCase, resolves one exact
  custody-backed record, creates a default-unsafe draft, records human review,
  and reads the append-only review history through the Workbench BFF.
- Existing operational routes remain the current Workbench foundation; provider routing,
  persistent OpenCode workspace control, and the full horizon/delta experience are targets.

The C1 Operator Console: drive the evidence spine instead of feeding a blind
upload->promote box (owner rejection, `docs/planning/operator-console-requirements.md`).
The first C1 rebuild emphasized three pages: **Runs** (default landing — start/watch spine runs stage-by-stage:
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
  citations, session sidebar) were removed. The current product does query
  canonical Knowledge through `/knowledge` and the Matter-bound Knowledge
  pane; those are governed operator surfaces, not the donor chat experience.
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
- **Donor `e2e/` + Playwright setup**: skipped for the original sprint. The
  current app instead has a zero-dependency Edge/Chrome CDP smoke at
  `smoke/matter-flow.smoke.test.mjs` for the complete Matter-bound operator
  journey.
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
npm run smoke:matter-flow  # build + strict mocked browser journey
```

The Matter smoke starts a same-origin fixture server and a quarantined headless
browser profile, then proves search → exact-source resolution → unsafe draft →
review → persisted history. It fails on unscoped Matter discovery, cross-Matter
requests, or Graphiti calls. Browser profiles are retained under the repository
`to_be_deleted/` directory for owner-only cleanup, per the no-delete policy.

## Requirements

Node.js >= 20 (see `package.json` `engines`). No `packageManager` field is set
here — the donor kit's root `package.json` and this package both omit one; pnpm
is assumed per the donor kit's `engines.pnpm >= 9` (root only) and
`pnpm-workspace.yaml`, though this app itself is no longer part of that
workspace and can be built with npm/pnpm/yarn.
