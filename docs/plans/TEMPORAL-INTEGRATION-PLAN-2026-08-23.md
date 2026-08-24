# Temporal integration plan — durable execution under the evidence pipelines

> _Byline: Claude Code · Opus 5 · 2026-08-23_

- **Status:** ADR-precursor (not an ADR; no decision recorded yet)
- **Owner input 2026-08-23:** "pretty confident we need to move forward with the temporal
  integration as laid out roughly in this document — there's other features and shapes that
  need to be adhered to so don't take this as a letter-for-letter guide."
- **Source doc:** `C:/Users/matts/Downloads/temporal.md` (obataka/temporal-demo analysis)
- **Relates:** ADR-0045 (walk derivation), ADR-0054 (structured terminal reasons), ADR-0057,
  ADR-0058, sql/0005 (run ledger), sql/0026 (projection outbox), sql/0027 (walk ledger)

## 0. The finding that drives everything below

**The platform already built a poor-man's Temporal, by hand, and it works.**
`server/evidence/run_ledger.py` is a durable-execution ledger: `create_run` (:60),
`seed_stages` (:101), `stage_start` (:114), `stage_finish` (:128), `set_gate` (:174),
`read_gate` (:205), `skip_remaining_stages` (:219), `set_trace_id` (:250),
`record_review_action` (:259), `finish_run` (:354) — persisted to `ops.workflow_run` /
`workflow_run_stage` / `workflow_run_review_action` (origin `sql/0005_workflow_run_ledger.sql`).
`server/evidence/workflows.py:160` wraps every agno `Step` to write those rows as stages execute,
and `:232` wraps them again for gate/abort control.

That is event history, search attributes, signals and queries — reimplemented in SQL, by us,
without the replay guarantee. Temporal's value here is **not new capability**; it is *deleting
hand-rolled reliability code we now maintain*, and getting crash/deploy survival that the current
design cannot provide (a process restart mid-run leaves `status='running'` rows with no runner).

Feature-by-feature equivalence:

| Hand-rolled today | Temporal equivalent |
|---|---|
| `ops.workflow_run_stage` rows written per stage (`workflows.py:160-214`) | Workflow **event history** (automatic, replay-safe) |
| `gate_state` column + 2s poll (`run_ledger.py:174/205`, `workflows.py:297-312`) | **Signal** + `workflow.wait_condition` (push, no poll, no ceiling) |
| `GET /v1/runs/{id}` / `/report` reading DB state (`server/api/run_routes.py:529/539`) | **Query** handlers (plus keep the DB report — see §3) |
| `workflow`, `domain`, `custody_tier`, `sha256` columns for run filtering | **Search Attributes** |
| `store.py:167 _retry_async` / `:206 _retry_sync` bounded backoff, per-call | Activity **RetryPolicy** (declared once, runtime-enforced) |
| `working.evidence_vector_projection_job` claim/fail/backoff (`vector_projection.py:126/253`) | Activity retry + Temporal **Schedule** for the drain |
| `run_knowledge_from_store()` partial rerun (`workflows.py:1024`) | Workflow **Reset** to a stage, or a child workflow |
| Nothing (no versioning of in-flight runs) | `workflow.patched()` |

---

## 1. What Temporal replaces vs what it must NOT touch

| Replaced by Temporal | Stays platform-side (Temporal only schedules/invokes it) |
|---|---|
| **Polling HITL gate.** `workflows.py:222-223` (`_GATE_POLL_INTERVAL_S = 2`, `_GATE_POLL_CEILING_S = 24h`) and the loop at `:297-312` → Signal + `wait_condition`. Deletes the poll, the ceiling, and the `gate_timeout` fail-closed branch. | **Custody hashing.** `custody.py:133 _sha256_file`, `:173 ingest_artifact`, `:345 verify_artifact`, `:429 record_evidence_hash`. Owner rule: custody is mandatory at capture and hashing is a callable process. It stays exactly that — a callable **invoked from inside** an Activity, never reimplemented as workflow code. |
| **Per-stage retry.** `store.py:167/206` bounded backoff wrappers, and the `attempts` lists threaded through `_ledger_stage_output` (`workflows.py:143-156`) → declared `RetryPolicy` per Activity. Keep the attempt lists as *reporting*, stop hand-rolling the loop. | **Walk derivation.** `derivation.py:220 derive_walk` — `_compute_base_version` (:141), `_genesis_hash` (:155), `_step_corpus_hash` (:181), `verify_reproducibility` (:375), under the `working.walk_ledger` advisory lock (:77). **RULING: stays platform-side, unchanged.** It is evidentiary and must reproduce byte-for-byte from `base_version` alone. Temporal must never become an input to that hash chain. |
| **Abort-at-boundary.** `workflows.py:316-317` reads `gate_state` at every stage boundary; an abort mid-stage is non-preemptive (documented at `:246-253`). Temporal cancellation is delivered to the workflow immediately. | **The run report.** `run_report.py:53 build_run_report` and `ops.workflow_run*` remain the **authoritative durable report** (`run_report.py:115` says so explicitly). Temporal history is operational telemetry, same status the code already assigns traces: `"authority": "diagnostic_only"` (`run_report.py:154`). |
| **Outbox retry queue.** `vector_projection.py:126 _claim` (`FOR UPDATE SKIP LOCKED`, `attempts+1`) and `:253 _fail` (`LEAST(attempts,10) * interval '1 minute'`) → Activity retry + a Temporal Schedule driving `NativeEvidenceProjector.drain` (:98). | **Projection authority.** The outbox *table* and `working.source_available_from` re-evaluation (`vector_projection.py:3-5`) stay. Postgres remains projection authority; Temporal replaces the *retry mechanic*, not the authority model. |
| **Crash/deploy survival** — currently absent. A killed `agentos-api` orphans `status='running'` rows. | **Evidence schema.** No column changes to `evidence.*` or `working.*` in P0-P2. Additive only, and only in P3 (§2). |
| **In-flight versioning** — currently absent; a deploy mid-run is undefined behavior. `workflow.patched()`. | **Agent reasoning.** Agno agents/teams/knowledge stay as they are, called from inside Activities. Temporal defines no reasoning. |

---

## 2. Phased adoption

### P0 — Stand up Temporal on the fleet (infra only, no pipeline change)

- **Host: `ovh-files` (100.91.190.107).** Reason: Temporal's server is extremely chatty with its
  persistence store, and `data-pg-files` (PG18) already lives there
  (`docs/PROJECT_CANON.md:209`). Co-locating puts them on the same **local** `agno` bridge
  (service-name DNS, no tailnet hairpin — the bridge is not a cross-host overlay). Putting the
  server on `ovh-app` or `ovh-data` would route every event-history write over tailnet.
- **Persistence: two new databases in the existing PG18 (`temporal`, `temporal_visibility`),
  dedicated `temporal` role.** NOT a new Postgres container. This is the direct lesson from
  `data-vector`: Milvus's bundled embedded etcd corrupted **six times** and the app is down
  deliberately since 2026-08-10 (`PROJECT_CANON.md:208`). Every new self-managed stateful
  service is a new corruption surface; `data-pg-files` is already operated and backed up.
  Guardrails: separate role, connection-pool cap, and a bounded workflow retention (e.g. 30d)
  so history cannot grow unbounded against the evidence system-of-record's disk.
- **Apps (Coolify, separate-everything-separable):** `temporal-server`, `temporal-ui`,
  `temporal-worker`, plus a one-shot search-attribute init. **Tailnet-only — no Traefik route,
  no new public surface.** UI reachable at the tailnet IP + Coolify's *published* port (note
  `coolify-proxy` owns host 8080 on every node, so expect a bumped port).
- **Do NOT ship the demo's Prometheus + Grafana pair.** Grafana already exists on `ovh-app`
  (`PROJECT_CANON.md:212`). Point it at Temporal's metrics endpoint over tailnet. A second
  Prometheus/Grafana is a parallel stack and violates the no-parallel-stacks rule.
- **Exit test (live, per policy):** start a trivial workflow, `docker restart` the worker
  mid-run, confirm it resumes from history. That is the one thing today's ledger cannot do.

### P1 — Wrap ONE pipeline: `chat-transcript`

**Recommended pipeline: chat-transcript ingest** (`workflows.py:588 build_chat_transcript_workflow`,
`:940 run_chat_transcript`). Four Steps at `:673-676` map 1:1 to four Activities:

| Step (today) | Activity | RetryPolicy note |
|---|---|---|
| `custody` | `custody_activity` → calls `ingest_artifact` (`custody.py:173`) unchanged | Retries must be safe — dedupe already handled via `ArtifactRef.duplicate` |
| `parse` | `parse_activity` → registry tool resolution + fallback chain intact | Deterministic; retry on transient IO only |
| `store` | `store_activity` → `store_records` | Replaces `store.py:206 _retry_sync` |
| `knowledge` | `knowledge_activity` → `ingest_into_knowledge` (Weaviate) | Replaces `store.py:167 _retry_async`; this is the stage that actually fails in prod (`workflows.py:41-44`) |

Why this one and not `sms-xml`: identical four-step shape (`:819-822`), but chat-transcript is
"THE BOOTSTRAP VERTICAL" (`workflows.py:13`), has the documented real-world failure this fixes
(knowledge-stage failure → retry → custody dedupes → false-success `docs_ingested=0`,
`workflows.py:36-44`), and already carries the compensating `run_knowledge_from_store` path
(`:1024`) that Temporal's reset makes redundant.

**Cutover is a swap, not a shadow.** Per the no-parallel-stacks rule, the feature seam is a
single dispatch switch inside `run_chat_transcript` (Temporal client vs. the current agno
`Workflow.arun`) — one live path at a time, flipped for real traffic, flipped back only to
restore service. No side-by-side v2. The ledger writes stay on both sides of the seam during
P1, so `GET /v1/runs/{id}/report` is byte-comparable before and after.

### P2 — Move the HITL gate from polling to Signal

- Delete the poll loop (`workflows.py:297-312`). `supervised` mode becomes
  `await workflow.wait_condition(lambda: self._gate_decision is not None)`.
- Re-point the **existing** endpoints, do not build a new UI: `continue_run`
  (`run_routes.py:567`), `abort_run` (:587), `retry_run` (:617),
  `create_run_review_action` (:549) send Signals instead of writing `gate_state`.
- **Do NOT adopt temporal-demo's Bun/Hono approval web-ui.** The platform already has two HITL
  surfaces — the knowledge-workbench console on `:8020` and AgentOS `/approvals`
  (`PROJECT_CANON.md:504/207`). A third would be a new stack and a new surface for zero gain.
- Keep `record_review_action` writing to `ops.workflow_run_review_action`: the operator decision
  is evidentiary and belongs in Postgres, not only in Temporal history.
- Bonus the current design cannot give: a decision arriving **mid-Activity** is not lost.

### P3 — Observability

- **Honest correction to the brief:** there are **no existing token fields** to map onto.
  `run_report.py:53 build_run_report` has no token accounting, and `sql/0005` has no token
  columns (`ops.workflow_run` is `run_id/workflow/mode/source_name/source_path/sha256/
  artifact_id/domain/status/summary/error/…`). Token usage is captured only inside the vendored
  Semantica provenance layer (`server/vendored/semantica/semantica/llms/llms_provenance.py:158-175`).
- So P3 **creates** the mapping rather than aligning to one: add `total_tokens` (additive column
  on `ops.workflow_run`, plus `data.summary.tokens` in the report), populate it from the
  Semantica provenance numbers, and mirror the same value as the `Total_Tokens` Search
  Attribute. One number, two homes: Postgres = authority, Temporal = queryable operations.
- Grafana: reuse the existing instance; per-token pricing as a Gauge (the demo's trick) so
  vendor price changes need no PromQL edit.

---

## 3. Explicit non-goals

- **No CrewAI.** The demo's CrewAI wiring is incidental; the agent layer stays Agno, dropped
  into Activities. Temporal is the reliability substrate, not the reasoning layer.
- **No agent-reasoning changes.** Agents, teams, knowledge, routing: untouched.
- **No evidence-schema changes** in P0-P2. P3 adds one nullable column, nothing else.
- **Walk derivation and custody reproducibility untouched.** `derivation.py`'s hash chain and
  `custody.py`'s H1/H2/H3 lineage must produce identical bytes before and after this work.
  If a Temporal identifier ever appears inside a hashed payload, the change is wrong.
- **No multi-case abstraction.** It is one case; do not introduce namespacing/tenancy because
  Temporal makes it easy.
- **No new public surface.** Tailnet only. No Traefik route for the Temporal UI.
- **Postgres stays the system of record.** Temporal history is diagnostic, matching the status
  already assigned to traces (`run_report.py:154`).

---

## 4. Risks and mitigations

1. **New stateful infra on a fleet with a corruption history.**
   `data-vector`'s Milvus died to embedded etcd six times. *Mitigation:* zero new stateful
   containers — Temporal persists into the existing, operated PG18; bounded retention; the
   whole `temporal`/`temporal_visibility` pair is disposable and re-creatable, because
   authority stays in `ops.*` and `evidence.*`.

2. **Determinism constraints vs. import-time side effects.** Temporal workflow code must be
   replay-deterministic and cannot touch env/network at import. The codebase does exactly that
   in load-bearing places:
   - `server/core/url.py:27` — `db_url = build_db_url()` executes at **module import**, reading
     six env vars.
   - `server/core/session.py:94-98, 115-118, 214-233` — module-level `getenv` for SurrealDB,
     Weaviate, OpenRouter and NVIDIA endpoints/keys, several with hardcoded tailnet IP defaults.
   *Mitigation:* the pattern is already proven in-repo — `run_ledger.py:31` imports `db_url`
   *inside* `_get_engine()` specifically "to avoid import-time env coupling" (`:8-10`). Workflow
   modules import nothing but stdlib and the Activity **stubs**; all of `server.evidence.*` and
   `server.core.session` is imported inside Activity bodies. Enforce with the sandbox's
   passthrough allowlist plus a replay test in CI.

3. **The 24h gate ceiling.** Today a supervised gate fails closed at 24h with `gate_timeout`
   (`workflows.py:223`, `:309-312`) — a real hazard when the single operator is in a hearing for
   two days. Temporal waits indefinitely. *Mitigation:* keep an explicit, configurable timer
   (7d default) that **notifies** rather than aborts; removing the abort is the point, but a
   silently-forever-paused run is its own failure mode.

4. **Two ledgers during P1.** Both `ops.workflow_run_stage` and Temporal history record the same
   run. *Mitigation:* intentional and time-boxed — it is how the swap is verified (byte-compare
   the report). Postgres is authority throughout; nothing is deleted until P2 lands.

5. **Worker is a new single point of failure.** *Mitigation:* two worker replicas on the same
   task queue from day one; Temporal handles distribution.

6. **CPU-only local box.** The local machine cannot run the fleet's stack. *Mitigation:*
   consistent with LIVE-ONLY policy — Temporal runs on `ovh-files` and is exercised live.

---

## 5. Decision asks for the owner (3)

1. **Should Temporal's own bookkeeping live inside the same Postgres that holds the evidence?**
   Recommendation: yes — two extra databases in the PG18 already running on the files box,
   rather than standing up a second database server. It means no new piece of storage software
   to babysit (the thing that killed Milvus six times), at the cost of Temporal's write traffic
   sharing a disk with the evidence store. Say no and we run a dedicated Postgres container for
   it instead, and accept one more stateful thing to keep alive.

2. **When we flip the chat-transcript ingest onto Temporal, do we flip it for real traffic
   immediately?** House rule says replace in place, no shadow copies — so the switch happens
   once, on live ingests, and if it breaks we fix forward. Confirm that is what you want here,
   or say you'd rather run the old path for a set number of ingests first.

3. **Approvals stay in the workbench console you already use, correct?** The reference project
   ships its own separate approval web page; recommendation is to throw that away and have the
   existing continue / abort / retry buttons send the signal instead. Approving from a second,
   different web page is the alternative — worse, but it is a choice.
