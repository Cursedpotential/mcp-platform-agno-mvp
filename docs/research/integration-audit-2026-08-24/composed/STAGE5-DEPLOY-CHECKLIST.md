# Stage 5 — platform injection: what's code-complete vs. what deploy still needs

> _Byline: Claude Code · Fable 5 · 2026-08-24_

## Code-complete tonight (committed; inert until worker redeploy)

- `server/temporal/n8n_activities.py` — the generic n8n-webhook activity (the wrap=activity
  invoker; Temporal RetryPolicy replaces n8n's missing durable retry).
- `server/temporal/classification_workflow.py` — `ClassificationBatchPipeline`: per small
  batch classify→judge→[Signal gate iff needs_review]→persist; anti-over-flagging,
  classifier_version stamped, notify-forever gate doctrine; abort supported.
- Worker registration updated (queue `evidence-pipeline`). 38/38 skeleton tests pass.

## Deploy checklist (small steps, live-verify each)

1. **Redeploy temporal-worker** (picks up the new workflow/activity; image cached — fast).
   Env to add on the worker app: `N8N_BASE_URL=https://n8n.mitechconsult.com`,
   `N8N_WEBHOOK_TOKEN` (optional shared secret; if set, add the same check in the webhooks).
2. **Import the 5 composed JSONs** into n8n (owner action or API import on approval) and fill
   the 17 documented placeholders — key ones:
   - `{{PLATFORM_API}}` = `http://100.72.169.40:8000` + bearer credential (OS key, Coolify env)
   - `{{PORTKEY_BASE_URL}}` = the self-hosted gateway URL (portkey app on ovh-app)
   - Top-judge slot = **direct Anthropic API** (owner ruling) — HTTP Request to the Messages
     API, key in a named n8n credential from Coolify env
   - Persist table: create `analysis.chunk_classification` (draft labels + classifier_version)
     via a numbered migration BEFORE first persist run
3. **Drop-dir trigger prerequisites on the n8n app** (lane-6 findings): the container has NO
   host mounts — add a bind mount for the intake dir; enable Local File Trigger (it is
   disabled by default since 2.0); then wf-intake-dropdir watches `/data/ingest`.
4. **First live run, small:** ONE batch of ~10 chunks through
   `ClassificationBatchPipeline` (start via a tiny client script, same pattern as the P0
   exit test), watch it in the Temporal UI (100.91.190.107:8233), review output together,
   purge test rows, iterate — per the small-batches + expect-it-to-suck rules.

## Custody conventions check (Stage-5 gate)

- Intake wf hands RAW files to `POST /v1/ingest` (the custody door) and only ever passes
  record IDs onward — no n8n node touches raw evidence content. ✔ (composed as specified)
- Chunking source: platform chunker (chonkie endpoint when built; today the chunks come from
  the platform's stored chunk tables). n8n never chunks conversations. ✔
- Persist writes DRAFT analysis rows only — nothing touches evidence status; promotion stays
  behind its PG gate. ✔
