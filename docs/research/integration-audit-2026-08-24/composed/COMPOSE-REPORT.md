# Stage 4 — Compose: five importable n8n workflows

> _Byline: stage-4 compose agent · Opus · 2026-08-24_
> Method per `docs/plans/N8N-BUILDER-AGENT-GUIDE.md` (Stage 4). **Files only** — nothing was
> imported into the live n8n instance, nothing was installed, nothing was committed. Target:
> **n8n 2.36.6** self-hosted (lane-6 audit). All five JSONs validated with a Python parser +
> connection-integrity check (`validate-composed.py`, shipped next to them).

---

## 0. The governing principle applied

> **THE WRAP IS THE ACTIVITY BOUNDARY** (owner, 2026-08-24, Stage-5 governing principle):
> every execution wrap maps 1:1 to a Temporal activity.

So this is **not** one big workflow. It is five separate workflow bodies, each one activity:

| File | Activity name carried in every payload | Trigger | Nodes |
|---|---|---|---|
| `wf-intake-dropdir.json` | `n8n.intake.dropdir` | Local File Trigger | 9 (4 sticky) |
| `wf-classify-batch.json` | `n8n.classify.batch` | Webhook (JSON batch) | 18 (5 sticky) |
| `wf-judge-gate.json` | `n8n.judge.gate` | Webhook (JSON batch) | 18 (4 sticky) |
| `wf-persist-results.json` | `n8n.persist.results` | Webhook (JSON batch) | 8 (3 sticky) |
| `wf-error-handler.json` | `n8n.error.handler` | Error Trigger | 7 (3 sticky) |

Each body is small, fast-completing, and **stateless between runs** — no Wait node holds state,
no workflow keeps a queue, no n8n-side counter table. Sequence and state belong to the durable
spine, not to n8n.

**Validation result (re-runnable: `python validate-composed.py`):**

```
OK   wf-classify-batch.json     nodes=18 (sticky=5) conns=15
OK   wf-error-handler.json      nodes= 7 (sticky=3) conns= 3
OK   wf-intake-dropdir.json     nodes= 9 (sticky=4) conns= 4
OK   wf-judge-gate.json         nodes=18 (sticky=4) conns=14
OK   wf-persist-results.json    nodes= 8 (sticky=3) conns= 4
ALL STRUCTURALLY VALID
```

Checks performed: JSON parses; `nodes[]`/`connections{}`/`meta`/`name` present; node **ids unique
within and across all five files**; node names unique; every node has `typeVersion`, `position`,
`parameters`; **every connection source and target resolves to a real node name**; every
connection entry carries `type`+`index`; a trigger exists; sticky notes exist; and a regex sweep
for `apiKey`/`password`/`secret`/`token`-shaped **values** found none (only `REPLACE_ME` and
`{{PLACEHOLDER}}` strings). No orphan nodes except the deliberately disabled TOP-JUDGE slot.

---

## 1. `wf-intake-dropdir.json` — drop-dir → custody door

**Node list (execution order)**

1. `Watch /data/ingest (add events, recursive)` — `n8n-nodes-base.localFileTrigger` v1
   (`triggerOn: folder`, `events: ["add"]`, `depth: -1` = recursive, ignore patterns for
   `*.partial` / `*.crdownload` / `.DS_Store`, `usePolling: true`).
2. `Read File From Disk` — `n8n-nodes-base.readWriteFile` v1 (`operation: read`, binary → `data`).
3. `Idempotency Key + In-Run Dedupe Guard` — `n8n-nodes-base.code` v2.
4. `POST -> Platform Custody Door` — `n8n-nodes-base.httpRequest` v4.4, multipart body with
   `formBinaryData` field `file` ← binary property `data`, plus form fields
   `idempotency_key` / `source_path` / `observed_at_epoch_ms` / `observed_at_iso` / `origin`;
   headers `X-Idempotency-Key`, `X-Observed-At-Epoch-Ms`; batching 5 items / 1000 ms;
   `retryOnFail` 3× / 2 s; `neverError` **off** so a non-2xx becomes a real failure that reaches
   the Error Trigger.
5. `Emit Record IDs` — `n8n-nodes-base.set` v3.4 → `run_id`, `workflow`, `mode`, `status`,
   `idempotency_key`, `source_path`, `observed_at_epoch_ms`, `handed_off_at_epoch_ms/_iso`,
   `activity_name`. (Shape matches `POST /v1/ingest`'s documented 202
   `{run_id, workflow, mode, status}` from lane-2.)
+ 4 sticky notes: deploy prerequisites, custody boundary, placeholders, source attribution.

**Owner rules encoded here**
- **Custody path is never n8n-side** — the raw file goes to the door; the workflow consumes IDs.
  The sticky says explicitly: "if this workflow ever grows a hashing node, that is a defect."
- **Idempotency from object keys** — key = FNV-1a over `path|fileSize` (+ a second hash of the
  path). Pure JS, **no `require()`**, so it does not depend on `NODE_FUNCTION_ALLOW_BUILTIN`.
- **Temporal-awareness** — `observed_at_epoch_ms` + ISO on every item, forwarded in the POST body
  *and* as a header.

**Cannibalization — source-attribution table**

| Shape | Chosen candidate | Shelf | URL | What was taken / dropped |
|---|---|---|---|---|
| Drop-dir trigger wiring | "Organise your local file directories with AI" (template **2334**) | template | https://n8n.io/workflows/2334 | Trigger→downstream-handoff shape. **Caveat:** 2334's JSON was *not* pulled in Stage 3, so the trigger's actual parameters come from the native docs snapshot in `extracted/native-node-notes.md`, not from the template file. Recorded, not hidden. |
| Diff / dedupe guard | "Monitor Dropbox folders for new files with DB comparison" (template **3297**) | template | https://n8n.io/workflows/3297 | Kept: the list→diff→dedupe→hand-off skeleton and its "do the heavy work elsewhere" boundary (`executeWorkflow` nodes). Dropped: Dropbox auth, the webhook challenge/ack pair, and the **NocoDB seen-table** — a cross-run state store contradicts the stateless-activity rule, so dedupe was reduced to in-run only + door-side idempotency. |
| Custody POST | Local File Trigger → HTTP Request (Shape-1 rank 1) | native | docs.n8n.io `n8n-nodes-base.localfiletrigger`, `…/httprequest` | typeVersions and the multipart/binary body form taken from `extracted/native-node-notes.md`. |

**Placeholders to fill at deploy**
- `{{PLATFORM_API}}` → base URL (final: `{{PLATFORM_API}}/v1/ingest`).
- Credential **`PLATFORM_API_BEARER (placeholder)`** (`httpBearerAuth`, id `REPLACE_ME`).
- `/data/ingest` → confirm the container bind-mount.
- `NODES_EXCLUDE` must be edited on the Coolify app (the trigger ships excluded by default from
  n8n 2.0) **and the app redeployed** — Coolify renders env values into the compose at deploy, so
  a restart alone does not reach the container.

---

## 2. `wf-classify-batch.json` — chunk batch → draft labels

**Node list**

1. `Webhook - classify batch` — `n8n-nodes-base.webhook` v2, `POST /d068/classify-batch`,
   `responseMode: responseNode`.
2. `Normalize Batch Items` — `code` v2. Body contract:
   `{ batch_id, classifier_version, items:[{record_id, chunk_id, chunk_text, occurred_at_epoch_ms}] }`.
   Hard-fails if an item lacks `record_id`/`chunk_id` — **IDs only, never raw evidence**.
3. `Sort Chronologically (occurred_at)` — `n8n-nodes-base.sort` v2, simple, `occurred_at_epoch_ms`
   ascending (temporal mandate applied *inside* the flow, per Interview B).
4. `Loop Over Items (small batches)` — `splitInBatches` v3, **batchSize 10**.
5. `Extract Classification (JSON Schema)` — `informationExtractor` v1.2, `schemaType: manual`,
   `inputSchema` = placeholder schema `{labels[], severity int 0–10, summary, sentiment enum}`,
   `systemPromptTemplate` carries the chunk timestamp and an explicit *under-call* instruction.
   `onError: continueErrorOutput`.
6. `Portkey Gateway - Cheap Tier` — `lmChatOpenAi` v1.2, temperature 0.
7. `Repair - Basic LLM Chain (auto-fix)` — `chainLlm` v1.5, `hasOutputParser: true`.
8. `Auto-fixing Output Parser` — `outputParserAutofixing` v1 → wraps →
9. `Structured Output Parser` — `outputParserStructured` v1.3 (same schema).
10. `Portkey Gateway - Fixer Tier (stronger)` — `lmChatOpenAi` v1.2, feeds **both** the repair
    chain and the auto-fixer's fix-up call.
11. `Stamp Version + Timestamps` — `set` v3.4 (`classifier_version`, `classified_at_*`,
    `is_draft: true`), then loops back to node 4.
12. `Collect Batch Results` — `code` v2 (loop output 0 = *done*).
13. `Respond - classification batch` — `respondToWebhook` v1.1.
+ 5 sticky notes.

**Deviation from the brief — recorded, not hidden (also stated in a sticky inside the file)**

The brief asked for Information Extractor **with** an Auto-fixing Output Parser wrapped over a
Structured Output Parser. In n8n 2.36.6 that is **not wireable**: the Information Extractor node
accepts only an `ai_languageModel` sub-node — no `ai_outputParser` input and no "Enable
Auto-Fixing" toggle (re-verified against docs.n8n.io on 2026-08-24; the node uses a structured
parser internally, which is why v1.2 exists). Forcing the connection would produce a JSON that
does not import cleanly.

Both instructions were therefore honoured by splitting them: the Information Extractor **is** the
primary JSON-Schema pass (native-first rule), and its **error output** routes to a Basic LLM Chain
that **does** carry `Auto-fixing Output Parser → Structured Output Parser` on a *stronger* model —
which is precisely the "one LLM-corrected retry before failing" Interview B required for free-tier
schema-constrained output, and it follows the extract report's warning to point the fix-up model at
a stronger tier than the one that failed.

**Owner rules encoded here**
- **Small batches, always** — batchSize 10, described in a sticky as a start-small tunable, not a
  throughput target.
- **Every output is a draft** — `classifier_version` on every row, `is_draft: true`, sticky stating
  nothing auto-promotes and re-classification supersedes rather than overwrites.
- **Anti-over-flagging** — the schema description and system prompt tell the model that uncertainty
  means *fewer* labels and *lower* severity. No flagging decision is made in this workflow at all.
- **Portkey is THE gateway** — one call per task; rotation across NIM / Gemini ×4 / OpenRouter /
  Ollama is the gateway's `loadbalance` config, not workflow logic.
- **Sub-node first-item-only gotcha** documented in a sticky; no per-item expressions live inside
  any parser sub-node.

**Cannibalization — source-attribution table**

| Shape | Chosen candidate | Shelf | URL | What was taken / dropped |
|---|---|---|---|---|
| Batched AI loop | "Smart Gmail Labeling Automation with Text Classifier and GPT-5" (template **7633**) | template | https://n8n.io/workflows/7633 | Kept: the exact `Loop Over Items` wiring — output **1** = loop → AI node → action → **back into the loop's input**, output **0** = done → collector. Dropped: all three Gmail action nodes and the schedule trigger. |
| Schema-enforced extraction | Information Extractor v1.2 (+ Structured Output Parser v1.3) | native | docs.n8n.io cluster-nodes | Shape-3 rank-1 pick; JSON-Schema mode, flat schema (no `$ref` support). |
| Malformed-JSON retry | Auto-fixing Output Parser | native | docs.n8n.io | Interview B addition; wrapped over the structured parser on a stronger model. |
| Chronological ordering | Sort node v2 | native | docs.n8n.io | Interview B addition; epoch-numeric field, ascending. |
| Model routing | Native OpenAI Chat Model → self-hosted Portkey base URL | native + vendor doc | portkey.ai/docs/integrations/libraries/n8n | Shape-5 rank-1 pick. **No** `n8n-nodes-portkey` exists; `n8n-nodes-nvidia-nim` was ruled out in Stage 3 (plain action node, cannot fill the `ai_languageModel` slot). |

**Placeholders to fill at deploy**
`{{PORTKEY_BASE_URL}}`, `{{PORTKEY_CONFIG_ID}}`, `{{PORTKEY_CLASSIFY_MODEL}}`,
`{{PORTKEY_FIXER_MODEL}}`, `{{CLASSIFIER_VERSION}}` (also overridable per request via
`body.classifier_version`), credential **`PORTKEY_GATEWAY (placeholder)`** (`openAiApi` type: API
key + Base URL). The label taxonomy inside `inputSchema` is itself a placeholder.

---

## 3. `wf-judge-gate.json` — verification gate (accepted / needs_review)

**Node list**

1. `Webhook - judge gate` — v2, `POST /d068/judge-gate`, respond-node mode.
2. `Normalize Classification Batch` — `code` v2; body `{batch_id, threshold, items:[…]}`;
   `threshold` defaults to **0.7**.
3. `Loop Over Items (small batches)` — `splitInBatches` v3, batchSize 10.
4. `Judge - Second Model` — `chainLlm` v1.5, `hasOutputParser: true`. System message states the
   judge did **not** write the draft, must judge on chunk text alone, must not weigh anything
   after the chunk timestamp, and that **low confidence is a safe, correct answer**.
5. `Portkey Gateway - Judge Tier` — `lmChatOpenAi` v1.2 (`{{PORTKEY_JUDGE_MODEL}}` — must differ
   from the classifier model).
6. `Auto-fixing Output Parser` v1 → 7. `Structured Output Parser (verdict)` v1.3, schema
   `{verdict: pass|fail, confidence 0–1, reasons[]}`.
8. `Portkey Gateway - Fixer Tier (stronger)` — fix-up model for the auto-fixer.
9. `TOP-JUDGE SLOT (Claude SDK - pending ToS ruling)` — `noOp` v1, **disabled**, unconnected,
   with node-level notes. A concrete marker for the insertion point.
10. `IF - confidence >= threshold AND verdict = pass` — `if` v2.3, combinator **and**,
    `{{ $json.output.confidence }} >= threshold` **and** `{{ $json.output.verdict }} == "pass"`.
11. `Mark accepted` / 12. `Mark needs_review (UNREVIEWED - not a flag)` — `set` v3.4; both loop
    back into node 3.
13. `Split accepted / needs_review` — `code` v2 on loop output 0 (done).
14. `Respond - gate result` — v1.1, returns `{counts, accepted[], needs_review[]}`.
+ 4 sticky notes.

**Owner rules encoded here**
- **Anti-over-flagging is structural, not advisory**: there are exactly two outcomes and neither is
  a flag. `needs_review` rows carry `review_state: "unreviewed"`. The sticky states that nothing
  downstream may render them as an alert, a hit, or evidence of anything.
- **Two-model review**: the judge is a *second* model, per the Interview-A added shape.
- **Threshold is a parameter**, not a constant — default 0.7, per-batch override.
- **Top-judge tier is pluggable and explicitly NOT wired** — sticky records the three blockers
  from the Stage-3 extract: `n8n-nodes-claude-cli` needs the `claude` binary inside the container
  (a **custom n8n image via Coolify**, same shape as the existing custom graphiti-mcp image), a
  long-lived `claude setup-token` in Coolify env storage (never git), and an **explicit owner ToS
  ruling** — the package's own author warns that driving a Pro/Max subscription through recurring
  automation may conflict with Anthropic's subscription terms.

**Cannibalization — source-attribution table**

| Shape | Chosen candidate | Shelf | URL | What was taken / dropped |
|---|---|---|---|---|
| Confidence gate | "Classify documents and score confidence…" (template **15229**) | template | https://n8n.io/workflows/15229 | Kept: the IF-gate wiring — one confidence/empty check branching to a needs-review path vs a silent continue, re-pointed at our own parser's `confidence` field. Dropped: the `@easybits/n8n-nodes-extractor` node (third-party hosted service, not in our pick list) and its form-upload trigger. |
| Judge mechanics | Basic LLM Chain + Structured Output Parser (Shape-4 composite top pick) | native | docs.n8n.io | The Guardrails node's Custom-threshold primitive was considered and **not** used: it emits a pass/fail branch, not a `{verdict, confidence, reasons}` record, and this gate must persist the judge's reasons. Guardrails remains the right tool for PII/secret sweeps later. |
| Council (reference only, NOT built) | "OpenRouter council" (template **12316**) | template | https://n8n.io/workflows/12316 | Documented in a sticky as the reserved high-stakes path: N independent answers → **anonymized** cross-ranking → chairman synthesis. Its raw `httpRequest`-per-model calls and `emailSend` output are explicitly rejected (calls go through Portkey; results go to Postgres). |
| Cheap pre-filter (parked) | `awesome-hallucination-detection.json` (`bespoke-minicheck` via Ollama) | github | enescingoz/awesome-n8n-templates | Noted in the same sticky as a candidate pre-filter. **Not adopted** — Stage 3 flagged it for owner discussion, and Stage 4 does not adopt unilaterally. |

**Placeholders to fill at deploy**
`{{PORTKEY_BASE_URL}}`, `{{PORTKEY_CONFIG_ID}}`, `{{PORTKEY_JUDGE_MODEL}}`,
`{{PORTKEY_FIXER_MODEL}}`, `{{THRESHOLD}}` (default 0.7), credential
**`PORTKEY_GATEWAY (placeholder)`**.

---

## 4. `wf-persist-results.json` — accepted rows → Postgres

**Node list**

1. `Webhook - persist results` — v2, `POST /d068/persist-results`, respond-node mode.
2. `Normalize + Validate Accepted Rows` — `code` v2. Requires `record_id`, `chunk_id`,
   `classifier_version`; **hard-fails** if any row's `gate_outcome` is not `accepted`
   ("needs_review rows do NOT persist here").
3. `Postgres - Insert Classification (parameterized)` — `n8n-nodes-base.postgres` v2.6,
   `operation: executeQuery`, `options.queryBatching: "transaction"`,
   `options.outputLargeFormatNumbers: "text"`, `retryOnFail` 3×.
4. `Build Confirmation` — `code` v2 → `{submitted_count, inserted_count, skipped_existing_count,
   classifier_version, persisted_at_*}`.
5. `Respond - persist confirmation` — v1.1.
+ 3 sticky notes.

**The SQL (verbatim from the file)**

```sql
INSERT INTO analysis.chunk_classification (
    record_id, chunk_id, classifier_version,
    labels, severity, summary, sentiment,
    judge_verdict, judge_confidence,
    occurred_at, classified_at, persisted_at, batch_id
) VALUES (
    $1, $2, $3,
    $4::jsonb, $5::int, $6, $7,
    $8, $9::numeric,
    to_timestamp($10::bigint / 1000.0),
    to_timestamp($11::bigint / 1000.0),
    to_timestamp($12::bigint / 1000.0),
    $13
)
ON CONFLICT (record_id, chunk_id, classifier_version) DO NOTHING
RETURNING record_id, chunk_id, classifier_version, persisted_at;
```

Values arrive **only** through `options.queryReplacement` (n8n's sanitized Query Parameters), as an
expression-built array. **No value is concatenated into the SQL string anywhere.**

**Owner rules encoded here**
- **Never string-built SQL** — a direct reaction to the documented anti-example (template 14036:
  41 nodes, string-built SQL in all six Postgres nodes, zero error handling).
- **Versioned drafts** — `classifier_version` is part of the primary key, so a re-classified corpus
  writes *new* rows; old labels are superseded, never overwritten. `ON CONFLICT DO NOTHING` makes a
  Temporal retry a no-op rather than a duplicate.
- **Three timestamps per row** — `occurred_at` (when it happened), `classified_at` (when labelled),
  `persisted_at` (when it landed), all fed from epoch-numeric fields.
- **n8n stays read-only against evidence** — the sticky pins the credential to the `analysis`
  schema; nothing here writes `evidence.*`.

**Cannibalization — source-attribution table**

| Shape | Chosen candidate | Shelf | URL | What was taken / dropped |
|---|---|---|---|---|
| Injection-safe write | Postgres node — Execute Query + Query Parameters (Shape-7 rank 1) | native | docs.n8n.io `n8n-nodes-base.postgres` | `$1…$n` + `queryReplacement`, `queryBatching: transaction`, `outputLargeFormatNumbers: text` — all from `extracted/native-node-notes.md`. |
| What NOT to do | "Maintain RAG embeddings…auto drift rollback" (template **14036**) | template (anti-example) | https://n8n.io/workflows/14036 | Explicitly inverted: parameterized SQL, an error path, and a transaction. |

**Placeholders to fill at deploy**
Credential **`PLATFORM_PG (placeholder)`** (`postgres`, id `REPLACE_ME`); the table
`analysis.chunk_classification` and its columns are a **placeholder schema** — the DDL sketch is in
the sticky, and Stage 5 owns the real migration.

---

## 5. `wf-error-handler.json` — shared failure handler

**Node list**

1. `Error Trigger` — `n8n-nodes-base.errorTrigger` v1, `alwaysOutputData: true` (kept from 1326).
2. `Format Standard Failure Payload` — `code` v2. **Branches on payload shape**: a normal failure
   carries `execution{}`; a failure in the parent's own *trigger* carries `trigger{}` instead with
   `error.name`/`.cause`/`.timestamp` and **no** `execution.id`/`.url`. Emits a flat record
   (`failure_kind`, workflow id/name, execution id/url/mode, `retry_of`, `last_node_executed`,
   error name/message/cause/stack, `failed_at_epoch_ms`, `reported_at_epoch_ms/_iso`) plus a
   ready-made `title` and `text`.
3. `Notify (generic webhook placeholder)` — `httpRequest` v4.4 POST JSON to `{{ALERT_WEBHOOK_URL}}`,
   `onError: continueRegularOutput`, 2 tries — an unset URL can never turn the error handler into a
   second failure.
4. `Failure Recorded (no-op sink)` — `noOp` v1, so failures stay visible in the execution list even
   with no channel wired.
+ 3 sticky notes.

**Wiring**: this workflow is attached per-parent via **Settings → Error workflow**. The other four
files ship with `settings.errorWorkflow = "REPLACE_WITH_WF_ERROR_HANDLER_ID"`; swap in this
workflow's real ID after import. This handler deliberately has **no** `errorWorkflow` of its own.
It does not need to be activated to work.

**Cannibalization — source-attribution table**

| Shape | Chosen candidate | Shelf | URL | What was taken / dropped |
|---|---|---|---|---|
| Error alert skeleton | "Get a Slack alert when a workflow went wrong" (template **1326**) | template | https://n8n.io/workflows/1326 | Kept: the whole `errorTrigger → notify` skeleton and `alwaysOutputData: true`. **Dropped: the Slack node** — swapped for a generic webhook + no-op sink, with a sticky flagging the channel as an **open owner decision** (Slack / ntfy / email / platform inbox / Temporal-side alerting). |
| Payload shape | Error Trigger docs | native | docs.n8n.io `n8n-nodes-base.errortrigger` | The `execution{}` vs `trigger{}` branch is implemented, not assumed. |

**Placeholders to fill at deploy**
`{{ALERT_WEBHOOK_URL}}`; credential **`ALERT_WEBHOOK_AUTH (placeholder)`** (`httpHeaderAuth`) —
delete the auth block entirely if the chosen channel needs none.

---

## 6. Consolidated placeholder checklist (17 open items)

| # | Placeholder | Files | What it is |
|---|---|---|---|
| 1 | `{{PLATFORM_API}}` | intake | Platform API base URL |
| 2 | `{{PORTKEY_BASE_URL}}` | classify, judge | Self-hosted gateway base URL (never api.portkey.ai) |
| 3 | `{{PORTKEY_CONFIG_ID}}` | classify, judge | Portkey `loadbalance` config attached to the key |
| 4 | `{{PORTKEY_CLASSIFY_MODEL}}` | classify | Cheap-tier model id |
| 5 | `{{PORTKEY_FIXER_MODEL}}` | classify, judge | Stronger fix-up model id |
| 6 | `{{PORTKEY_JUDGE_MODEL}}` | judge | Second-model judge (≠ classifier) |
| 7 | `{{CLASSIFIER_VERSION}}` | classify | Default classifier version tag |
| 8 | `{{THRESHOLD}}` | judge | Gate threshold, default 0.7 |
| 9 | `{{ALERT_WEBHOOK_URL}}` | error | Notification endpoint (owner's channel choice) |
| 10 | cred `PLATFORM_API_BEARER (placeholder)` | intake | `httpBearerAuth` |
| 11 | cred `PORTKEY_GATEWAY (placeholder)` | classify, judge | `openAiApi` (key + base URL) |
| 12 | cred `PLATFORM_PG (placeholder)` | persist | `postgres`, `analysis` schema only |
| 13 | cred `ALERT_WEBHOOK_AUTH (placeholder)` | error | `httpHeaderAuth`, deletable |
| 14 | `REPLACE_WITH_N8N_INSTANCE_ID` | all 5 (`meta.instanceId`) | Cosmetic; n8n rewrites on import |
| 15 | `REPLACE_WITH_WF_ERROR_HANDLER_ID` | 4 (`settings.errorWorkflow`) | ID of `wf-error-handler` after import |
| 16 | `analysis.chunk_classification` + its label taxonomy | persist, classify | Placeholder schema — Stage 5 owns the DDL |
| 17 | `/data/ingest` + `NODES_EXCLUDE` | intake | Container mount + trigger enablement (Coolify env → **redeploy**, not restart) |

No credential **values** appear in any file. Every `credentials` block is `{"id": "REPLACE_ME",
"name": "<NAMED PLACEHOLDER>"}`.

---

## 7. What Stage 5 (platform injection) still has to do

These are deliberately **not** in the composed files. Each is an injection point, not an omission.

**A. Temporal wiring points (one activity per file)**
- Each workflow currently answers its caller synchronously (webhook respond node) or ends at
  `Emit Record IDs`. Stage 5 must decide the call shape: Temporal activity → n8n webhook →
  response, vs n8n → Temporal signal/callback. The payloads already carry `activity_name`,
  `batch_id`, and completion timestamps so either shape works without editing node logic.
- `wf-intake-dropdir` is the one **push** entry point (a file lands, nobody asked). Stage 5 must
  decide whether it starts a Temporal workflow directly or writes to a queue the spine polls.
- Retry granularity: node-level `retryOnFail` handles transient blips *inside* an activity; the
  activity-level retry belongs to Temporal. Do not add a second retry layer in n8n.
- **No n8n Wait node anywhere, by design** — n8n must never hold state between activity calls.

**B. HITL signal insertion**
- `wf-judge-gate`'s `needs_review` output is the **only** human-facing surface, and it is
  deliberately a *queue*, not a notification. Stage 5 inserts the **Temporal Signal gate** there:
  the spine parks the run; n8n (or the operator console) is the notify/approve surface; the signal
  resumes it. Never an n8n Wait holding state.
- The disabled `TOP-JUDGE SLOT` node is the second HITL-adjacent insertion point: routing
  high-stakes items to the Claude tier is gated on the **owner ToS ruling** plus the custom n8n
  image build. Both are Stage-5/deploy tasks.
- The example table (`analysis.human_label`) that feeds few-shot improvement is *not* written by
  any of these workflows — Stage 5 decides where owner labels enter.

**C. Custody conventions**
- `POST /v1/ingest` returns 202 with a `run_id` and processes in the background. Stage 5 must add
  the **completion/receipt** path: either poll `GET /v1/runs/{run_id}` from the spine, or have the
  door call back. `wf-intake-dropdir` deliberately stops at "handed off".
- Hash-chain verification (`POST /v1/verify/{sha256}`, H1/H2/H3) is never invoked from n8n. If a
  verification step is wanted, it is a separate platform-side activity.
- The `record_id`/`chunk_id` values the classify workflow consumes must come from the platform's
  canonical IDs (`working.normalized_record` / knowledge items), not from anything n8n invents.
- Conversation chunking stays platform-side (Stage-2 negative finding: no n8n-side chunker
  preserves timestamps/speaker/message boundaries). If n8n ever needs to chunk, it calls the thin
  platform `chunk` endpoint wrapping **chonkie** — the owner's ruled-on upgrade path — so chunk
  boundaries stay identical across n8n and the pipeline.
- Epoch-numeric timestamps are already on every payload; Stage 5 must confirm they match the
  evidence collections' range-filter fields exactly.

**D. Still-open items inherited from Stage 3 (unchanged by this compose)**
1. `NODES_EXCLUDE` edit + redeploy before `wf-intake-dropdir` can run at all.
2. Custom n8n image (claude CLI) + long-lived token, before the top-judge tier exists.
3. Owner ToS decision on driving a Pro/Max subscription through recurring automation.
4. `analysis.chunk_classification` DDL.
5. Notification channel choice for `wf-error-handler`.
6. Per-model JSON-schema conformance verification before any model joins the classification pool
   (standing lesson; `glm-5.1` is excluded).

---

## 8. Community check (standing rule — part of every stage's definition-of-done)

Re-run at Compose against the Stage-3 findings; **nothing new adopted**, and one adoption reversed:

- `n8n-nodes-roundrobin` — **not used.** Stage 3 proved the name is a false lead (multi-persona
  conversation state, not provider rotation). Portkey `loadbalance` remains the sole rotation
  mechanism.
- `n8n-nodes-nvidia-nim` — **not used.** Plain action node; cannot fill an `ai_languageModel` slot,
  and Portkey already fronts NIM.
- Semantic splitters (`…-with-context` dead upstream, `@bitovi/…` alive) — **not used here**: none
  of these five workflows chunks anything. Chunking is platform-side (chonkie).
- `bespoke-minicheck` hallucination pre-filter — **documented in a sticky, not adopted**; it needs
  an owner call.
- No new sweep surfaced a better fit for any of the five bodies than the native nodes chosen; the
  native-first preference order held throughout.

## 9. Not committed, not imported

No `git add`/`git commit` was run. Nothing was imported, published, activated, or executed on the
live n8n instance, and no package was installed. These are files on disk only.
