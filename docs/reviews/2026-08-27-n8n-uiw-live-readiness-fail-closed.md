# n8n / Universal Import live-readiness receipt — fail closed

> _Byline: Codex · GPT-5 · 2026-08-27_

STATUS: **BLOCKED / FAIL CLOSED**
LIVE_PROOF: **PARTIAL** — the Coolify-managed services are running and the starter can create a
real Temporal run, but the run cannot reach the preview hold. No approve-to-publication or
same-request idempotency claim is authorized by this receipt.

## Outcome first

Two independent live blockers were observed:

1. n8n 2.36.6 rejected the `$env.REFERENCE_IMPORT_STARTER_URL` expression with
   `ExpressionError: access to env vars denied`.
2. A direct starter/Temporal isolation run passed `register_source_activity` and then failed in
   `retain_original_activity` with `permission denied for table source (SQLSTATE 42501)`.

All five Universal Import n8n workflows were returned to **inactive** after the first production
execution failed. The global n8n environment-access security setting was not weakened, live URLs
were not hardcoded into the workflows, no approval signal was sent, and no secrets were printed.

## Live readiness observations

| Component | Live observation | Result |
|---|---|---|
| Parser Activity runtime | Coolify `o11nxvzqwskxrqmtbvup7iet`; `running:healthy`; `/healthz` returned `{"status":"ok"}` | PASS |
| Parser readiness | `/readyz` returned `{"parser_count":11,"status":"ready"}` | PASS |
| Reference Import starter | Coolify `r1084s1lsm80fsv4ol9ocij0`; `running:healthy`; `/healthz` returned `{"status":"ok"}` | PASS |
| Universal Import worker | Coolify `d24bb9eoo47qtw9eq1xc6u64`; running; log showed queue `universal-import-v1`, namespace `default`, and `activity_count=23` | PASS |
| n8n service | Coolify service `ddjgrmys36d9n8xwcwj0mml2`; restarted through Coolify and returned to `running:unknown` | PASS for process state |
| n8n endpoint configuration | Stored service compose contained both `PLATFORM_IMPORT_RUNTIME_URL` and `REFERENCE_IMPORT_STARTER_URL` keys; values were not printed | PASS for presence only |
| n8n node use of configuration | First production start execution failed because node expressions cannot access `$env` | FAIL |
| Runtime role at retention boundary | `retain_original_activity` could not read `context.source` | FAIL |

## n8n activation attempt

Pre-activation inspection of all five imported workflows verified:

- exactly five nodes per workflow;
- authenticated Webhook nodes;
- bound Webhook and downstream HTTP credentials;
- expected UIW runtime-variable expressions;
- inactive state before activation.

The workflows were activated only after parser, starter, and worker readiness checks passed:

| Workflow | ID | Activated version |
|---|---|---|
| Universal Import - select_parser_activity | `fvKS2gcsRUdEKUun` | `14425317-8ef4-4695-9b89-4584f417a5f3` |
| Universal Import - execute_parser_activity | `YQoFBykpZoDrU0n6` | `c90bf33f-5457-43a9-8a2a-487cdd4a8e0f` |
| Universal Import - start | `7HDcx0GPDELB56J0` | `d3bf11a2-356f-46ef-b91a-7e398de6ef21` |
| Universal Import - preview | `nobMh2uO8eIBuH2p` | `65ca4148-65df-47f2-8d8c-536742a373de` |
| Universal Import - decision | `abOE3dzoZo3yw26x` | `e4489e6d-4855-406c-b6f0-47531f99c241` |

The authenticated production start webhook created n8n execution `1`, which terminated at node
`HTTP - reference import starter start` with status `error` and exact message
`ExpressionError: access to env vars denied`. It produced no workflow ID or run ID. All five
workflows were then deactivated and their inactive state was re-read from the Public API.

## Direct starter / Temporal isolation proof

A repository-owned synthetic fixture was copied to the UIW intake mount without using real case
material:

- repository source: `vendored/sbv/backend/testdata/sample_backup.xml`;
- live acquisition path:
  `/data/uiw/source-objects/test-fixtures/live-proof-20260827-sample_backup.xml`;
- SHA-256 on both sides:
  `72640c6c2995d7dd89ce01e5757f7ee5ccc5af2945f1faadefc60339b77c9a55`.

The direct authenticated starter request returned HTTP `201`:

- workflow ID: `uiw-live-reject-direct-20260827-001`;
- run ID: `01a0446a-12fc-7afe-8c5d-f263a7fdb850`;
- declared format: `smsbackuprestore_xml`.

Worker logs then proved this sequence:

1. `register_source_activity` executed.
2. `retain_original_activity` executed.
3. Retention failed with
   `retain original: resolve source version ownership: ERROR: permission denied for table source (SQLSTATE 42501)`.

The workflow therefore never reached `awaiting_decision`. A rejection signal was not sent because
there was no preview hold to adjudicate, and querying the terminal run returned HTTP `422`.

## Residual live state

- All five UIW n8n workflows are **inactive**.
- The synthetic fixture remains under the clearly labeled `test-fixtures` intake directory; it was
  not hard-deleted.
- The failed workflow and its successful source-registration receipt remain durable Temporal /
  PostgreSQL audit state. This receipt makes no claim that test-state cleanup has occurred.
- Parser, starter, worker, and n8n processes remain running.

## Required follow-up gates

1. Choose an n8n-safe endpoint configuration contract. Do not silently set
   `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`: that is a service-wide security relaxation. A governed n8n
   variable/configuration mechanism or another explicit non-secret endpoint contract should be
   selected and kept consistent with the checked-in workflow exports.
2. Run a least-privilege query/permission census for `retain_original_activity` and add the missing
   `platform_runtime` grants through a new numbered migration. Do not patch live grants ad hoc.
3. Redeploy/restart only through Coolify, reactivate the workflows, and rerun start -> preview ->
   reject. Prove from receipts that `execute_parser_activity` did not run.
4. Only after reject passes, run a separate approve-to-publication fixture and the same-request
   idempotency proof, followed by the project-approved disposable-test-state reconciliation.
