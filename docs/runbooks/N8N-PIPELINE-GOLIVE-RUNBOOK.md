# n8n classification pipeline — GO-LIVE RUNBOOK (written for ANY model to execute safely)

> _Byline: Claude Code · Fable 5 · 2026-08-24_
> Purpose: a lesser/cheaper model (or a fresh session) can take the pipeline from
> "everything staged" to "first reviewed batch" WITHOUT design decisions. Every decision is
> already made and cited. If a step fails, STOP at that step, record what happened in
> docs/URGENT-TODO.md, and do not improvise around it.

## HARD GUARDRAILS (violating any of these is worse than stopping)

1. NEVER touch `evidence.*` tables, evidence Weaviate collections, or custody code. This
   pipeline writes ONLY to `analysis.chunk_classification` (drafts) — nothing else.
2. NEVER run schema changes except by a numbered migration file in `sql/`, and none are
   needed for this runbook (0033 is already applied).
3. SMALL BATCHES ONLY: ≤ 10 items per batch, ONE batch per run, review between runs
   (owner rule). The starter script enforces ≤ 25 and defaults to 10.
4. NEVER delete/stop/rm anything in Coolify or docker. Deploys happen only via the steps
   below. No `git add -A` — stage by explicit path.
5. Model calls: for now everything runs IN-NODE inside n8n pointed directly at NIM
   (owner ruling 2026-08-24: "do it all in code inside n8n — we'll copy that pattern over
   to Portkey later"). Do NOT build Portkey configs in this runbook.
6. Purge test rows after each reviewed run (`DELETE ... WHERE run_key = ...` — the script
   prints the exact statement). Test data never becomes canonical.
7. If ANYTHING here conflicts with what you find live, the live finding wins — record it,
   stop, don't force the runbook.

## Current state (verified 2026-08-24 late evening — do not re-derive)

- Temporal server+UI+worker LIVE on ovh-files; queue `evidence-pipeline`; UI http://100.91.190.107:8233
- Worker redeployed with `ClassificationBatchPipeline` + `n8n_webhook_activity` registered and
  `N8N_BASE_URL=https://n8n.mitechconsult.com` (deploy jso4q5vg… — verify it FINISHED before step 3:
  the container log line lists "ClassificationBatchPipeline" on boot).
- `analysis.chunk_classification` exists live (migration 0033, applied).
- 5 composed workflow JSONs at `docs/research/integration-audit-2026-08-24/composed/` with
  placeholder inventory in `COMPOSE-REPORT.md` (17 placeholders).
- n8n 2.36.6, greenfield, credentials already present: `NVIDIA NIM`, `Weaviate (ovh2 :8081)`.
- n8n Public API: URL+key in `C:/Users/matts/.secrets/n8n-ovh2.env` (`N8N_API_URL`,
  `N8N_API_KEY`). ⚠ key expires 2026-09-22. The MCP token in the same file is NOT the API key.

## Step 1 — import the three pipeline workflows via the n8n API

Import ONLY: `wf-classify-batch.json`, `wf-judge-gate.json`, `wf-persist-results.json`,
plus `wf-error-handler.json`. (Do NOT import `wf-intake-dropdir.json` yet — its Local File
Trigger needs container changes; separate task.)

For each file: read JSON → substitute placeholders (step 2 values) → `POST {N8N_API_URL}/workflows`
with header `X-N8N-API-KEY: {N8N_API_KEY}` and body `{"name": ..., "nodes": ..., "connections": ...,
"settings": ...}` (drop any `id`/`active`/`tags` top-level fields the file carries) → then
activate webhooks via `POST {N8N_API_URL}/workflows/{id}/activate`.

Webhook paths MUST end up exactly (the Temporal side calls these):
- classify → `classify-batch`   · judge → `judge-gate`   · persist → `persist-results`
(they are `webhook/<path>` URLs at runtime; check each Webhook node's `path` parameter after
substitution and fix if the composed value differs.)

## Step 2 — placeholder values (all decisions already made)

| Placeholder (see COMPOSE-REPORT.md) | Value |
|---|---|
| Chat-model endpoint (classify + judge) | OpenAI-compatible credential with base URL `https://integrate.api.nvidia.com/v1`, API key = the NVIDIA key (create credential type `openAiApi` named `NIM OpenAI-compat` via `POST /credentials` if the existing `NVIDIA NIM` credential's type doesn't fit the OpenAI Chat Model node) |
| Classify model | `mistralai/mistral-nemotron` (benchmarked choice) |
| Judge model | `ibm-granite/granite-4.1-8b` (different model than classifier — cheap, fast; June-run prior) |
| Top-judge (Claude) slot | LEAVE EMPTY/disabled — pending the owner adding an Anthropic API key; sticky note in wf-judge-gate marks it |
| `{{THRESHOLD}}` | `0.7` |
| `{{PLATFORM_API}}` + bearer | NOT needed for these three workflows (only intake uses it) — skip |
| Postgres credential (persist) | create n8n credential type `postgres`: host `100.91.190.107`, port `5432`, db `ai`, user `agno_app`, password from the Coolify exec-tier env `DB_PASS` (ask the owner to paste it into the n8n credential UI if you cannot read Coolify; NEVER write it into a file) |
| Persist target table | `analysis.chunk_classification` (exists; columns in sql/0033) |
| errorWorkflow setting | after importing wf-error-handler, set its workflow id as the Error Workflow of the other three (PATCH each workflow's `settings.errorWorkflow`) |

## Step 3 — first smoke run (ONE batch of 10, unsupervised)

```bash
cd E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform
uv run --no-sync python scripts/run_classification_batch.py --limit 10
```

- Pulls 10 messages from `analysis.human_label` (non-canonical EXAMPLE set — approved test corpus).
- Starts `ClassificationBatchPipeline` on Temporal; prints the run_key and the Temporal UI link.
- Expected: classify → judge → persist; result counts printed; rows visible via the printed
  SELECT. `needs_review` items simply land as drafts with `review_state='unreviewed'` (the
  Signal gate is OFF for smoke runs; `--supervised` turns it on later).

## Step 4 — review with the owner, then purge

Show the owner: the Temporal UI run, and the SELECT output (labels/sentiment/severity/
confidence per message). EXPECT IT TO BE MEDIOCRE — that is by design (iteration rule).
After review: run the printed DELETE (purge), record observations in
`docs/plans/N8N-BUILDER-AGENT-GUIDE.md` under a new "## Run log" heading (append-only).

## Step 5 — iterate (still small)

Adjust ONLY: prompts/schema inside wf-classify-batch, threshold, model choice per node.
Bump `--version` (e.g. clf-v1) on every change — versioned drafts rule. One batch, review,
purge, repeat. NOTHING here graduates to real corpus runs until the owner says so.

## Not in this runbook (do NOT attempt)

- Intake/drop-dir trigger (container mount + trigger enablement) — separate task, owner-gated.
- Portkey loadbalance configs — later, by explicit owner go.
- HITL Signal gate wiring to a notify surface — later.
- Any run against real corpus tables (chat model, context, evidence) — owner-gated.
- Anthropic top-judge — pending key.

## Troubleshooting quick refs

- Worker didn't pick up code: check deploy finished in Coolify; container boot log must list
  `ClassificationBatchPipeline`. SSH read-only: `ssh -i ~/.ssh/ovh root@100.91.190.107
  'docker logs --tail 5 $(docker ps --format "{{.Names}}" | grep e4dkqfshveu | head -1)'`
- Webhook 404 from the activity: workflow not ACTIVE or path mismatch (step 1 paths).
- n8n API 401: wrong token (use `N8N_API_KEY`, not the MCP token); or the key expired (2026-09-22).
- Workflow "running" forever at gate: you started with `--supervised` — send the Signal from
  Temporal UI (`gate_decision` = `approve`) or rerun unsupervised.
- Postgres errors in persist: check the credential user is `agno_app` and the table exists
  (`SELECT count(*) FROM analysis.chunk_classification`).
