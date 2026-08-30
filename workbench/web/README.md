# Knowledge Workbench — web (C1 Operator Console)

> _Byline: Claude Code · Sonnet (agent) · 2026-07-20 (C1 rebuild: Runs/Tools/Intake replaces Upload/Files-promote)_
> _Current-product repair: Codex · GPT-5 · 2026-08-15._

> **Current role:** this custom Next.js Workbench—not AgentOS Studio—is the accepted
> operator product. It consumes neutral platform/Workbench APIs so the browser does not
> depend on whether Agno or a future adapter coordinates a run.

## Host-shell / application composition — OPEN, not decided (2026-08-26)

> _Byline: Claude Code · Sonnet 5 · 2026-08-26 (removal of the dead `@module-federation/nextjs-mf`
> integration — see below — created the risk that this direction reads as abandoned or resolved;
> this section exists so it doesn't)._

**Removing the module-federation adapter below is a dead-code cleanup, not a decision against
future host-shell/application composition.** Whether the Workbench should ever be composed into
a larger shell (single sign-on chrome, shared navigation, embedding as a remote module inside
another app, etc.) remains genuinely open and must be **reevaluated as its own scoped decision**,
not silently re-attempted with the next library that looks plausible, and not silently declared
unnecessary by omission. A future session picking this up must treat it as unresolved until an
ADR says otherwise.

**What was removed and why:** `@module-federation/nextjs-mf@^8.8.73` was wired into
`next.config.ts` (`withModuleFederation`, exposing `./Workbench` as a `agno` remote,
`remoteEntry.js`) by commit `9ef8311` (2026-08-23) as speculative host-shell scaffolding. It had
**zero consumers anywhere in this repository** — nothing imports the remote, nothing references
`remoteEntry.js`, no host shell exists. It also does not support this app's architecture: this
Workbench is Next 16 App Router with `output: "export"` (static export served by the FastAPI
sidecar — see "Static export" below), and `@module-federation/nextjs-mf`'s peer range
(`next@"^12 || ^13 || ^14 || ^15"`) neither supports Next 16 nor App Router's static-export mode.
It broke the `knowledge-workbench` Coolify build (`npm error ERESOLVE`) the first time a deploy
pulled in the commit that bumped `next` past what it supports, taking down the deploy pipeline for
an unrelated, unrated D-082 evidence-fence fix (see `WP-C01-IMPLEMENTATION-STATUS.md`,
GAP-032/D-082). It has been removed from `package.json`/`package-lock.json`/`next.config.ts`.

**What the reevaluation must cover, when someone picks this up:**

- **Whether a microfrontend/host-shell is needed at all** — reconfirm the actual product
  requirement (shared chrome across multiple apps? SSO handoff? embedding this Workbench inside
  something else?) before picking any integration mechanism. Don't default to module federation
  because it's the familiar name.
- **App Router / Next-16-compatible integration choices**, evaluated against what this app
  actually is (static export, no server component) — options include Module Federation successor
  tooling that supports Next 16 App Router (verify support explicitly, don't assume), iframe
  composition, a build-time/edge-side include of the static export, or a server-rendered host that
  fetches/mounts the exported HTML — each has different constraints against `output: "export"`.
- **Shell ownership and navigation/auth boundaries** — who owns top-level chrome/nav if a shell
  exists; how `WORKBENCH_API_KEY` Basic/Bearer auth (see `deploy/workbench.yaml`) composes with a
  shell's own auth instead of conflicting with it.
- **Artifact/static-export serving** — how the exported `out/` directory (currently served
  same-origin by `workbench/api`'s FastAPI, per "Static export" below) would be served/mounted
  inside a shell without breaking the same-origin assumption `src/lib/api-client.ts` depends on.
- **Branch/watch-path/Coolify topology** — whether composition changes the current
  one-Coolify-app-per-concern boundary (`deploy/workbench.yaml`, `workbench/sprint` branch,
  `workbench/** + deploy/workbench.yaml` watch paths) or requires a new topology.
- **Deterministic dependency/build policy** — any future integration package must be added with a
  committed lockfile change and built via `npm ci` (see `workbench/Dockerfile`, fixed 2026-08-26 to
  copy `package-lock.json` and use `npm ci` instead of an unconstrained `npm install`), and its
  peer-dependency range must be verified against this app's actual Next/React major version
  *before* it's added, not discovered via a broken production deploy.
- **Upgrade/security ownership** — who tracks security advisories and Next-version compatibility
  for whatever composition mechanism is chosen, so a future Next major bump doesn't silently
  re-break the build the way this one did.
- **Acceptance and rollback gates** — what proves a host-shell integration actually works
  (a real consumer, not speculative scaffolding) before it merges, and how to roll it back cleanly
  if it doesn't.
- **AgentOS retirement boundary** — the Workbench calls the framework-neutral Platform API through
  `PLATFORM_API_URL`; it does not call generic AgentOS agents, teams, workflows, sessions, or MCP.
  Tool discovery uses the ContextForge-authored, Portkey-published `platform-tools` surface.

## Current product surfaces — held, not deployed

The original C1 description below is historical foundation, not the complete current route
map. Knowledge browsing and the Matter workspace are committed and pushed to `main`,
with local build/test evidence but no deployed-service proof. Commit `be286a8`
adds exact evidence/custody inspection and makes successful inspection a prerequisite
for recording a review decision. Commit `7b6aaf6` adds a separate read-only
court-readiness dialog that distinguishes actual database export-view membership
from stricter supplemental checks and explicitly avoids admissibility/legal-advice
claims. Horizon execution remains held.

- `/knowledge`: canonical, case-prefiltered Knowledge browsing plus separately labeled
  read-only Graphiti memory.
- `/matter`: Matter/CourtCase scope plus a bound canonical Knowledge pane. It
  prebinds the Matter partition and primary CourtCase, resolves one exact
  custody-backed record, creates a default-unsafe draft, records human review,
  reads append-only review history, and exposes redacted canonical-record/H1/source
  custody inspection plus read-only court-export/readiness gates through the
  Workbench BFF.
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
  implementation that landed in the same implementation tranche
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
