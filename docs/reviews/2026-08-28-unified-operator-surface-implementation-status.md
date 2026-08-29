# Unified operator surface implementation status — 2026-08-28

> _Byline: Codex · GPT-5 · 2026-08-28; updated 2026-08-29._

STATUS: PARTIAL — the Workbench shell is live on the tailnet; end-to-end UIW
acceptance and the SBV bounded preview remain open.

## Integrated and pushed

- `3e06271` — UIW authenticated upload ingress plus authoritative
  `Matter`/`CourtCase` binding on `context.source_version` through migration 0043.
- `b1f3df5` — real Workbench unified intake shell/BFF, UIW upload/start/preview/decision
  client, and the previously completed durable run-event stream work.
- `657ca05` — removed Workbench/UIW bearer credentials and enforced the
  direct-tailnet socket-peer boundary in the Workbench and Go starter/upload
  handlers.
- `14392c3` — preserved the real tailnet peer through host networking while
  binding the starter only to `100.91.190.107:8091`.
- The Workbench deployment definition no longer mounts the retired LanceDB intake
  volume. The released intake route uses only the authenticated UIW acquisition
  ingress and reference-only Temporal start contract.
- The visible shell is graphite/warm-paper and exposes only the intake vertical
  slice. Legacy flat navigation is not the product entry surface.
- The intake surface now enforces the single-case product boundary: it
  automatically binds the only canonical Matter, presents that identity as fixed
  context, and exposes no Matter selector. Zero Matters blocks intake as an
  uninitialized baseline; more than one blocks intake as a split/duplicated-data
  integrity incident rather than offering the operator a choice.

## Validation evidence

- `go test -tags fts5 ./uiw ./activities ./temporal ./postgres ./temporal/cmd/starter ./acquisition` — passed.
- `uv run pytest -q tests/test_0043_context_source_matter_binding.py` — 2 passed.
- Workbench API UIW + run/runtime/event focused suite — 20 passed, one upstream
  Starlette deprecation warning.
- `npm run lint -- --max-warnings=0` — passed.
- `npm run build` — passed; `/intake` emitted as a static Next route.
- The 2026-08-29 single-case correction passed ESLint with zero warnings and a
  production Next.js build with all 16 static pages generated.
- Scoped `git diff --check` — passed before both commits.
- `uv run pytest -q tests/test_universal_import_deploy_contract.py` — 8 passed
  after the host-network correction.
- Workbench UIW/auth focused suite — 11 passed after token removal.

## Deployment boundary

- Commit `bda0db8` built successfully on parser-activity-runtime,
  universal-import-starter, and universal-import-worker. Parser and starter were
  healthy; the worker was running with unknown health because that deployment has
  no decisive health proof.
- Migration 0043 and the later commits still require current-revision Coolify
  deployment and live schema/behavior proof.
- The former `unified-operator-surface` Coolify resource was cut over in place to
  `/deploy/workbench.yaml` and renamed `knowledge-workbench`; no resource was
  deleted. Deployment `yswdcw4cjezm5xlk2jnfxfxe` finished for `0bc6f16`.
- Direct tailnet proof at `http://100.72.169.40:8020/intake` returned HTTP 200,
  the title `The Platform — Evidence & Legal Operations`, the unified Platform
  marker, and no legacy `Operator Console` marker.
- Workbench browser access uses the direct Tailscale socket peer as the existing
  security boundary. It does not use a Workbench password, Basic auth, forwarded
  identity headers, or a password environment variable.
- An incorrectly generated Workbench credential was disabled and its local file
  moved to `C:/Users/matts/.secrets/to_be_deleted/workbench-access-20260829.md`.
  It remains recoverable and only the owner deletes quarantined material.
- The UIW starter and upload boundary has now been rewritten for direct socket-peer
  tailnet authorization. The Workbench strips caller `Authorization` headers, and
  the starter ignores forwarded identity headers. Focused Go tests/build,
  deployment-contract tests, and Workbench UIW/auth tests pass locally.
- The existing `universal-import-starter` Coolify resource was corrected in place
  from a stale Dockerfile application to `/deploy/universal-import-starter.yaml`;
  no duplicate resource was created. Deployment `e46yekbynzl6ix7kgtubvwez`
  finished at `14392c3`.
- Direct tailnet `GET http://100.91.190.107:8091/healthz` returned 200. A synthetic
  raw upload through `http://100.72.169.40:8020/api/uiw/upload` returned 201 with
  a 64-character SHA-256 and no Basic challenge, proving the live
  Workbench-to-starter upload path.
- `GET http://100.72.169.40:8020/api/matters` still returns 500. The intake shell
  is previewable, but automatic fixed-case binding and an end-to-end UIW decision
  remain blocked by the incomplete fresh-`platform` database baseline.
- Workbench deployment `xozcknkg3biu0kvdx0w0n7w7` finished at `05bba3a`. A
  browser reload proved the rendered surface no longer advertises retired
  LanceDB or inactive Milvus and now explains the Matter-schema blocker instead
  of showing a generic internal-server error. The verified production capture is
  `2026-08-29-production-workbench-intake-final.png`.

## Security follow-up

- On 2026-08-29, a Workbench test was invoked from the repository root instead of
  `workbench/api`. Pydantic loaded the root `.env`, rejected unrelated keys, and
  emitted secret-bearing values into the agent tool transcript. No values are
  reproduced here. The root `.env` is ignored and untracked; it has no Git history
  and is absent from the `origin/main` tree. There is no evidence that the values
  reached GitHub. Per the owner ruling, transcript-only appearance does not require
  rotation; rotate only if GitHub exposure is proven. This incident does not
  change the settled no-password Workbench/UIW boundary.
- A bounded `nemotron-3-ultra:cloud` review confirmed the direct-peer and
  forwarded-header regression targets. It also identified the remaining
  infrastructure assumption: the application check recognizes any tailnet node,
  while Workbench-specific least privilege must be enforced by existing Tailscale
  ACLs/grants. See `2026-08-29-nemotron-tailnet-boundary-review.md`.

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

The three NocoDB duplicates were separately stopped after the owner confirmed
they contained no data. They were not deleted; exact UUIDs and verified stopped
states are recorded in `2026-08-29-nocodb-quarantine-receipt.md`.

## Next release actions

1. Apply and prove migration 0043 against database `platform` only.
2. Live-prove reject-without-parse, resume, approval, and idempotency after the
   fresh database baseline permits a bound Matter/CourtCase start.
3. Live-prove Matter listing, source upload, preview decision, and receipt from
   the VPS-hosted Workbench after the fresh `platform` baseline is reconciled.
4. Implement the U0/U1 launch-context foundation, then expose SBV as the bounded
   `/evidence/preview` client without bypassing UIW.
5. Start the Timesketch round-trip slice only after the first slice has live proof.
