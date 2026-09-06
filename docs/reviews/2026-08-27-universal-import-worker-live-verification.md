# Universal Import worker live-verification receipt — 2026-08-27

> _Byline: Codex · GPT-5 · 2026-08-27. Live evidence collected by Russell._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

- Status: **PASS**
- Verified at: `2026-08-27T17:46:36Z`
- Coolify application: `universal-import-worker` (`d24bb9eoo47qtw9eq1xc6u64`)
- Deployment: `nhp06clxpiilzl8ro6bmnqg3`
- Deployed revision: `6a2a5df543a188a5805c0cfb9afcccdfda99a3d7`
- Task queue: `universal-import-v1`
- Temporal namespace: `default`

## Verified live

1. The Coolify deployment finished successfully at `2026-08-27T17:40:20Z`.
2. Application state was `running:unknown`. The `unknown` portion is Coolify health metadata because
   `health_check_enabled=false`; it is not an unhealthy result.
3. The sanitized runtime log contained three nonblank lines and no matches for
   `fatal`, `panic`, `permission denied`, `failed`, or `error`.
4. Worker startup reported task queue `universal-import-v1`, namespace `default`, and
   `activity_count=23`.
5. The Temporal SDK reported the worker started on `universal-import-v1`.
6. Temporal's live task-queue description showed one workflow poller and one activity poller with the
   same worker identity and current access times.
7. Temporal Web returned HTTP 200 and the Temporal gRPC endpoint was reachable.

## Exact registration proof

At the exact deployed revision, `TestRegisterAllRegistersOneWorkflowAndAllExact23Stages` passed in
`engine/uiwworker`. The test asserts:

- one `UniversalImportWorkflow` registration;
- exactly 23 activity registrations;
- every canonical stage-graph activity name exactly once.

Together, the live startup/poller evidence and the exact-revision registration test establish that the
deployed worker is running and polling both queue types with the one workflow and all 23 canonical
activities registered.

## Validation boundary

Temporal's task-queue API exposes live pollers, not the individual registered activity-name list.
Therefore live state proves the exact deployed worker is running and polling both workflow and activity
queues, while name-by-name coverage is proven by the registration test at that same deployed revision.

No service, deployment, database, workflow, or repository state was changed during this verification.

## Remaining live path

1. Restart and verify the n8n service after its environment/compose change.
2. Activate the five imported UIW workflows only while parser, starter, and worker readiness remain
   verified.
3. Prove preview rejection produces no import, then separately prove approve-to-completion across all
   23 stages.
4. Retry the same request/idempotency identity and reconcile receipts, raw/normalized lineage, and
   current deployed revisions.
