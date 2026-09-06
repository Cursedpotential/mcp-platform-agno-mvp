# UIW opaque preview Go surface — implementation receipt

> _Byline: Codex · GPT-5.6 · 2026-08-29._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

STATUS: LOCAL CONTRACT + DURABLE PG18 STORE + STARTER MOUNT IMPLEMENTED; DEPLOYMENT/LIVE PROOF REMAIN

## Implemented

- Added `engine/runtimeapi/uiw_preview.go`, a UIW-native HTTP surface whose browser-visible
  correlation is a cryptographically random, opaque `preview_handle`. The server-side binding
  retains request, source, workflow, run, selection, options, source-version, and generation
  references without placing source or normalized bytes in Temporal payloads.
- Added bounded, handle-bound HMAC cursors; correlated snapshot and normalized-message pages;
  participants and all attachments with source locators; the six receipt types; replayable,
  monotonic SSE with `Last-Event-ID`; explicit unknown-handle, not-ready, malformed-cursor, and
  replay-gap failures; and decisions linked to the current Temporal selection/options refs.
- A decision cannot be submitted before a validated projection exists. The projection validator
  requires at least one normalized message, all six completed receipts, resolvable participants,
  and source locators for every message and attachment. Approval after rejection fails closed
  until the workflow exposes a changed selection or parser-options reference.
- Added a narrow `PreviewStore` contract and deterministic `MemoryPreviewStore` test double. The
  in-memory store is expressly not a deployment store.
- Extended starter route composition so an injected preview handler owns the new `/previews/*`
  routes and the UIW-native `/reference-import/start`, while acquisition upload, health, and the
  pre-existing Temporal routes remain reachable.
- Added forward-only migration `sql/0050_uiw_preview_projection_store.sql`: immutable opaque
  bindings, append-only snapshot generations, six typed receipts, participant/message/attachment
  projections, contiguous replay events, and idempotently keyed decision audit. Deferred database
  enforcement rejects a snapshot without all six completed receipts, at least one message, or a
  resolved participant projection. `platform_runtime` receives only inherited SELECT/INSERT;
  UPDATE, DELETE, TRUNCATE, and PUBLIC access remain forbidden.
- Added `engine/postgres/uiw_preview_store.go`. It idempotently reuses a request binding only when
  every workflow/source coordinate matches, publishes a validated projection atomically, pages the
  latest generation, detects replay gaps, serializes event allocation, and deduplicates identical
  decision audit rows.
- The starter now requires `PLATFORM_DATABASE_URL` to resolve specifically to database `platform`
  and reads the cursor-signing key from `UIW_PREVIEW_CURSOR_KEY_FILE`. Startup opens and pings the
  durable store before mounting the preview routes. There is no volatile memory fallback.
- Added `publish_uiw_preview_activity` after normalized-generation verification and before the
  operator decision/seal boundary. Its Temporal payload contains only request/source/generation,
  parser, and six receipt references. The PostgreSQL implementation resolves the actual normalized
  messages, every participant, and every raw-lineage attachment; validates lineage and successful
  receipts; and publishes the snapshot/pages/events in one transaction. Identical retries are a
  no-op, a changed digest for the same normalized generation fails closed, and event IDs are
  allocated contiguously while the binding is locked.
- Registered that activity on the production UIW worker and extended worker admission so it will
  not poll unless all eight 0050 projection tables exist.
- Made UIW/Workbench the sole source-repair decision authority. The opaque-handle repair endpoint
  derives the actor only from Traefik/Authentik response headers, requires a bounded idempotency
  key, persists the exact append-only 0051 decision through `RepairActivityStore`, and only then
  signals Temporal with its compact decision reference. The older workflow-id repair signal route
  is no longer mounted, so n8n cannot author or inject repair decisions.

## Remaining production boundary

Migration 0050 and the durable mount are local source changes only. They still require clean-branch
integration, deployment configuration for the existing platform libpq DSN and a file-mounted cursor
key, migration application through the governed deploy path, Coolify deployment, and live Authentik,
projection, SSE-resume, and decision proof. The `MemoryPreviewStore` remains test-only.

The normalized preview projection producer and repair decision authority are now wired locally.
Until migration/deployment/live proof completes, a deployed old revision remains unchanged; a new
handle on the new revision correctly remains `409 projection not ready` until its workflow reaches
the six-receipt publication activity.

## Verification

- `go test ./runtimeapi ./temporal/cmd/starter` — PASS.
- `gofmt` applied to every owned Go file.
- `go test ./...` from `engine/` — PASS across all packages.
- `go vet ./...` from `engine/` — PASS.
- `PLATFORM_0050_TEST_DSN=... go test ./postgres -run
  TestMigration0050RollbackOnlyOnPostgreSQL18 -count=1 -v` against the disposable PostgreSQL 18
  service — PASS; the migration transaction was rolled back. The same rollback-only test exercised
  durable binding creation/idempotent reuse, not-ready snapshot behavior, idempotent decision audit,
  and contiguous event replay against the migrated tables.
- After the durable-store extension, focused `go test ./runtimeapi ./postgres` — PASS.
- Repeated `go test ./...` and `go vet ./...` from `engine/` after concurrent integration settled —
  PASS.
- Focused activity/workflow/worker tests prove publication occurs only after normalized verification,
  rejection remains a resumable hold, stale post-publication parser repair refs fail closed, and UIW
  repair persistence occurs before the Temporal signal — PASS.
