# Platform completion orchestration recovery — Unified Surface convergence

> _Byline: Codex · GPT-5 · 2026-08-28._

STATUS: RECOVERED_FOR_CONTINUATION
BUILD_STATUS: UNKNOWN
LIVE_STATUS: PARTIAL_AND_NOT_RELEASE_CERTIFIED

## Outcome

The resumed Platform lane is the coordinated completion of the approved Unified Operator Surface and
the backend capabilities that make its first intake workflow real. The prior working pattern was:

- the owner and root agent work on the approved Unified Surface frontend;
- bounded backend agents continue non-overlapping implementation and verification lanes;
- the root agent reviews and integrates exact allowlists into production vertical slices;
- no local implementation, preview, process, or static receipt is upgraded into deployment or live
  proof.

The first convergence point is one governed intake slice:

`select source -> acquire/seal -> parse/preview -> reject or confirm -> durable receipt -> live progress`

The committed browser-local surface is an approved visual and interaction baseline. Its simulated
receipt is not a canonical write. The safe frontend continuation is to preserve its anatomy while
wiring the governed intake API and real receipt.

## Verified repository state

| Area | Verified state on 2026-08-28 | Disposition |
|---|---|---|
| Branch | `main` at `38fb97b`, equal to `origin/main`; no staged files | Preserve the dirty shared checkout; stage only explicit allowlists |
| Unified Surface | Approved prototype committed in `468d05e`; tailnet HTTP hashing fix committed in `3e213c5` | Reserve its source files for owner/root frontend work |
| Fresh database lane | Integrated on `main`; fresh `platform` exists and migrations 0036-0038 are active per current indexed status | Do not restart or merge the stale lane |
| Raw/normalized pipeline lane | Integrated on `main` in `6e1bffd` | Do not restart or merge the stale lane |
| n8n/UIW live ingest | The original two blockers were cleared live; a third H1 trigger defect was reproduced and repaired through migration 0042; five workflows are inactive pending matching worker deployment | Deploy the Go query fix, resume the preserved run, then repeat reject/approve/idempotency proof |
| Migrations 0039 and 0042 | Applied to `platform`, independently reconnected, and recorded with rich-ledger hashes | Commit/push their exact source and receipts; verify the intended worker revision live |
| R2/B2/upload acquisition | Untracked `engine/acquisition/**` implementation exists; current integration/test/deploy status is not yet certified | Recover provenance and tests before assigning or integrating |
| Storage browser research | Prior session recommended SFTPGo Community with Workbench command authority and optional rclone transfer support | Research result needs a durable, current source-backed artifact before product adoption |
| Run-event SSE | Complete local read path and Workbench panel; 12 new files plus three narrow wiring diffs; migration 0041 unapplied; no real producers | Useful first-slice dependency, but not independently production-complete |
| API coverage | Static census complete; backend-to-Workbench coverage is not complete | Close only the endpoints required by each current vertical slice |
| SATemporal/Semantica A/B | D-093 accepted; extraction-only Slice 1 exists locally; deployment/live proof pending | Keep separate from intake integration until ownership is reconciled |
| Timesketch | Deployment scaffold and contract tests exist; no live deployment or round-trip proof | Second Unified Surface slice, after intake is live |
| Workbench auth | Tailscale-bound authentication rotation has a live receipt | Preserve server-side credentials and tailnet gating |

## Current collision boundaries

- Unified Surface frontend: `workbench/design-mockups/unified-operator-surface/**` is reserved for the
  owner/root frontend collaboration.
- UIW/n8n: migration 0039, its apply/validate scripts and tests, five workflow JSON files, their README,
  and the focused workflow tests remain one coordinated delivery boundary.
- Run events: migration 0041, Platform ledger/SSE files, the Workbench proxy/client/panel, and the three
  registration/mount diffs form one exact integration allowlist.
- Acquisition: `engine/acquisition/**` plus any required import-light contract or registration change
  must be recovered before ownership is assigned; `engine/go.mod` and `engine/go.sum` are shared
  collision points.
- SATemporal/Semantica, Timesketch, broad canon/ADR/TODO edits, and existing Workbench run/promote edits
  remain separate dirty lanes until individually reconciled.

## Backend work order while frontend continues

1. Recover the exact provenance, diffs, tests, and missing integration points of
   `engine/acquisition/**` and migration 0039/UIW. Do not edit during recovery.
2. Integrate and live-prove the UIW blocker fixes against fresh `platform`: configuration access,
   retain-original privilege, preview hold, reject, approve, and idempotent retry.
3. Integrate provider-neutral R2, B2, and authenticated upload acquisition so each selected object is
   copied and sealed into the immutable source-object boundary before parsing.
4. Wire the existing Unified Surface intake interaction to the real acquisition/preview/decision APIs
   and replace the simulated receipt only when a canonical backend receipt is returned.
5. Integrate the run-event ledger and minimum real producers needed by the intake slice; apply 0041
   through a reviewed migration path and prove replay after disconnect/reconnect.
6. Run the applicable Python, Go, Workbench, and mandatory live integration checks; commit and push
   exact allowlists; verify Coolify built the intended commit; prove the owner-facing workflow live.
7. Only after the intake slice has a durable current-revision receipt, expose the Timesketch timeline
   review slice. Keep GraphRAG A/B work independent unless it becomes a direct dependency.

## Recovered acquisition lane detail

The 2026-08-28 read-only recovery established the following for `engine/acquisition/**`:

- The nine package source/test files are untracked and have no Git history. Their only external changes
  are the AWS SDK additions in `engine/go.mod` and `engine/go.sum`.
- The package implements strict `r2://`, `b2://`, and `upload://` acquisition references, a single
  content-addressed sealing primitive, post-publish hash verification, quarantine-on-failure, a
  fail-closed scheme router, S3-compatible R2/B2 retrieval, and a bounded bearer-authenticated upload
  handler.
- The result is contract-compatible with `platformpostgres.ImmutableAcquisition` and the existing
  retained-object opener. No changes were found in `engine/postgres/**`, `engine/runtimeapi/**`, or
  `engine/activities/**` for this lane.
- From `engine/`, `go build ./...`, `go vet ./acquisition/...`, and
  `go test ./acquisition/... -count=1` passed; all 24 acquisition tests passed in 4.334 seconds.
- The package is unreachable in production: `engine/uiwworker/worker.go` still registers only the
  filesystem resolver, `NewSchemeRouter` has no production caller, R2/B2/upload configuration fields
  are absent, and `NewUploadIngress` is not mounted on an API.

The smallest safe integration boundary is the nine acquisition files, `engine/go.mod`,
`engine/go.sum`, and a separately reviewed worker/config registration seam. The upload network surface
requires an explicit mount/auth decision and must not be smuggled into the resolver-only change.

## Recovered UIW/n8n blocker detail

The two 2026-08-27 live blockers remain separate:

1. Checked-in n8n workflows cannot use `$env` under the deployed n8n security policy. The current five
   JSON exports correctly contain fail-closed `.example.invalid` endpoint placeholders and credential
   placeholders, and the focused tests explicitly forbid `$env`/`process.env`. The remaining operation
   is deployment-time endpoint and header-credential binding in n8n; the global security setting must
   not be weakened.
2. PostgreSQL `FOR UPDATE` on the retain-original locking join requires update privilege on both joined
   tables. Migration 0039 supplies the narrow `UPDATE (id)` privilege on `context.source` through the
   lifecycle role while the append-only trigger continues to reject actual source mutation.

Current focused validation on 2026-08-28:

- `uv run pytest -q tests/test_0039_context_source_retention_lock.py tests/test_n8n_parser_activity_workflows.py`
  passed: 20 tests.
- Ruff check passed for the two 0039 scripts and the two focused test files.
- Ruff format check passed for the same four Python files.
- The rollback-only live validator was rerun against `platform` and passed:
  `PASS: migration 0039 rolled back; retain-original locking join succeeded and source stayed
  immutable`.

This validation does not prove a committed apply, n8n endpoint binding, workflow reactivation, or
end-to-end live ingest.

## Current deployed revision and workflow state

Read-only Coolify and n8n inspection on 2026-08-28 established:

- Unified Operator Surface, Universal Import starter, and Universal Import worker each have a
  successful deployment of commit `fdc6f93`; repository `main` is currently `38fb97b`, equal to
  `origin/main`, so these live applications are behind source.
- The Unified Surface and starter report `running:healthy`; the worker reports `running:unknown` even
  though its latest deployment finished successfully. Worker readiness still requires queue/activity
  proof because it intentionally exposes no HTTP port.
- All five Universal Import workflows exist in n8n and remain inactive.
- Their deployed bodies are the older `$env` versions. Each outbound node still falls back to an
  `.example.invalid` endpoint, while the repository working copies have already moved to explicit
  fail-closed literal placeholders.
- The official n8n MCP connection can list the workflows but full workflow inspection is disabled for
  them. The existing authenticated n8n Public API was therefore used read-only, with output restricted
  to workflow state, node types, credential types, and endpoint expressions. No credential value was
  printed.

The reviewed production order is therefore:

1. apply migration 0039 to `platform` through the guarded apply script;
2. change only the five deployed outbound URL fields to the two stable live endpoints, preserving the
   already-bound credentials and the dynamic workflow-ID suffixes;
3. re-read the workflow bodies and credential bindings, then activate all five;
4. prove unauthenticated webhooks fail closed;
5. run the synthetic start -> preview -> reject path and prove `execute_parser_activity` never ran;
6. separately prove approve-to-publication and same-request idempotency.

After owner confirmation, migrations 0039 and 0042 were applied and independently verified, the five
deployed workflows received URL-only endpoint updates, and a synthetic run proved retention before
exposing the H1 BYTEA/BIGINT defect. The workflows were returned inactive and the worker was paused
before deployment of the matching Go fix. See `2026-08-28-uiw-live-repair-progress.md`.

## Control-plane safety incident

During read-only Coolify discovery, a tool documented as returning application summaries returned
full application records, including sensitive fields. No exposed value is reproduced here or sent to
an external model. The affected control-plane and webhook/sentinel credentials must be treated as
transcript-exposed and rotated through a separately scoped, reviewed operation. Further Coolify reads
in this session were parsed internally and emitted only allowlisted non-sensitive fields.

## Recovered first-slice API detail

The existing Workbench already has real paths for upload/staging, text preview, analysis, dry-run parse,
starting an ingest, polling run status, run reports, continue/abort/retry, and review actions. The local
run-event SSE slice supplies a not-yet-deployed live-progress path.

The first-slice gaps are narrower but authority-critical:

- the approved prototype's reject action is browser-local only;
- no implemented `PreviewDecisionV1` command binds the exact source, parser/version, configuration,
  preview hash, actor decision, and idempotency key;
- the existing confirm/start path does not prove that the confirmed preview is the exact input started;
- current Workbench upload is the older staging path, not the recovered R2/B2/upload sealing boundary;
- the approved prototype is not yet wired into the real Workbench intake/run components.

Do not invent a second decision API before reconciling the existing Temporal UIW approval signal and
n8n preview-decision workflow. The production command must use the durable workflow's approval state
rather than create a competing authority path.

## Model/workforce routing

- GLM 5.3 Cloud through Ollama/OpenCode: primary long-context repository implementation and review.
- Nemotron 3 Ultra Cloud through Ollama/OpenCode: independent architecture, authority, and release-risk
  review.
- DeepSeek V4 Flash Cloud through Ollama/OpenCode: fast bounded reconnaissance and test enumeration.
- Claude usage is conserved for tasks that the Cloud routes cannot complete reliably.

No evidence bodies, case PII, credentials, privileged legal content, or secret-bearing configuration
may be sent to external workers. Cloud worker output is proposal input until root review and tests.

## UNRESOLVED

- The Unified Surface spec and ADR still contain a stale proposed/owner-acceptance gate even though the
  approved prototype was subsequently committed and the owner has now explicitly resumed this lane.
  Reconcile the historical decision text without erasing the original gate.
- Acquisition provenance, tests, and missing production registration are recovered; integration
  ownership and the upload ingress mount/auth decision remain unresolved.
- The n8n replacement contract is selected and deployed: literal endpoint binding in the five
  deployed workflow bodies. The workflows remain inactive until the matching worker code deploys and
  the preserved run advances safely.
- Coolify application metadata exposed sensitive fields through a summary tool response; targeted
  credential-rotation scope and execution remain unresolved.
- Migrations 0039 and 0042 are applied live but their source is not yet committed/pushed; migration
  0041, run-event producers, and the local GraphRAG/Timesketch slices remain uncommitted or undeployed.
- No current full validation, Coolify release receipt, or live end-to-end intake proof exists for this
  combined checkout.
