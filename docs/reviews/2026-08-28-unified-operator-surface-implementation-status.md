# Unified operator surface implementation status — 2026-08-28

> _Byline: Codex · GPT-5 · 2026-08-28._

STATUS: PARTIAL — production deployment and live acceptance remain open.

## Integrated and pushed

- `3e06271` — UIW authenticated upload ingress plus authoritative
  `Matter`/`CourtCase` binding on `context.source_version` through migration 0043.
- `b1f3df5` — real Workbench unified intake shell/BFF, UIW upload/start/preview/decision
  client, and the previously completed durable run-event stream work.
- The Workbench deployment definition no longer mounts the retired LanceDB intake
  volume. The released intake route uses only the authenticated UIW acquisition
  ingress and reference-only Temporal start contract.
- The visible shell is graphite/warm-paper and exposes only the intake vertical
  slice. Legacy flat navigation is not the product entry surface.

## Validation evidence

- `go test -tags fts5 ./uiw ./activities ./temporal ./postgres ./temporal/cmd/starter ./acquisition` — passed.
- `uv run pytest -q tests/test_0043_context_source_matter_binding.py` — 2 passed.
- Workbench API UIW + run/runtime/event focused suite — 20 passed, one upstream
  Starlette deprecation warning.
- `npm run lint -- --max-warnings=0` — passed.
- `npm run build` — passed; `/intake` emitted as a static Next route.
- Scoped `git diff --check` — passed before both commits.

## Deployment boundary

- Commit `bda0db8` built successfully on parser-activity-runtime,
  universal-import-starter, and universal-import-worker. Parser and starter were
  healthy; the worker was running with unknown health because that deployment has
  no decisive health proof.
- Migration 0043 and the later commits still require current-revision Coolify
  deployment and live schema/behavior proof.
- Coolify currently has a deployed `unified-operator-surface` mockup on port 8020
  but no deployed production Workbench app. A safe cutover must replace that
  resource without losing its rollback path, provision Workbench/UIW credentials,
  and verify the real application on its VPS origin. Localhost is not acceptance.

## SBV preview boundary

- SBV is currently bundled inside `exec-platform-tools`; there is no standalone
  SBV Coolify application or same-origin Workbench `/evidence/preview` route.
- The SBV React client is a donor for the custody ledger, reconciliation summary,
  accepted/rejected record views, attachment manifest, and bounded error excerpts.
  Its Axios/Bootstrap client and synchronous `/api/imports` upload must not be
  copied into Workbench because that would create a second intake authority.
- ADR-0061 requires the bounded SBV preview surface behind Workbench with a
  short-lived, audience/scope-bound, single-use launch exchange. The ticket
  issuer, nonce store, SBV exchange endpoint, scoped session, and same-origin proxy
  are not implemented yet. The current local text preview is not a substitute.

## Deferred infrastructure census

The read-only VPS application/deployment census is retained as a later cleanup
TODO. No resource was stopped, moved, deleted, or reconfigured as part of that
census. Every retirement candidate still requires caller/volume reconciliation,
an observation window, and explicit owner confirmation; nothing is approved for
deletion.

## Next release actions

1. Apply and prove migration 0043 against database `platform` only.
2. Confirm current-revision UIW deployments, configure the shared upload mount and
   credentials, and live-prove upload, reject-without-parse, resume, approval, and
   idempotency.
3. Cut over port 8020 from the mockup to the real Workbench through Coolify and
   live-prove the VPS-hosted intake surface.
4. Implement the U0/U1 launch-context foundation, then expose SBV as the bounded
   `/evidence/preview` client without bypassing UIW.
5. Start the Timesketch round-trip slice only after the first slice has live proof.
