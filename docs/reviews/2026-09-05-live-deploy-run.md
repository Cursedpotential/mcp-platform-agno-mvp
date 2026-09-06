# Live deploy run — migrations applied, platform-tools + tool-gateway deployed, gateway unreachable

> _Byline: Claude Code · Opus 5 · 2026-09-05._
> Owner-authorized live deploy (owner 2026-09-05: *"commit… push… whatever you have to
> do. Clean. Done."*). Session constraint honoured: **no git writes of any kind** — no
> commit, no push, no stage. `main` was already at `5eda234` when this session began.
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## Outcome, first

| Step | Result |
|---|---|
| 1. Apply `0071` then `0072` live | **DONE** — applied in one transaction after a rollback rehearsal; every post-condition verified on a fresh connection. Ledgered. |
| 2. `exec-platform-tools` redeploy | **DONE** — deployment `l9y8ft7oaeu3zh4449uhg48t` finished; materialize mount present `:ro`; `/tools` → 200, **41** tools. |
| 3. `tool-gateway` live | **PARTIAL → BLOCKED.** Container runs, tsnet node joined, service advertised — but **nothing routes to it**, and the fix was **permission-denied**. |
| 4. Repoint `universal-import-worker` | **NOT DONE — deliberately.** Step 3 proved no URL; repointing at an unreachable address would replace a known failure with a worse one. |
| 5. UIW rehearsal | **NOT RUN.** Gated on 3 and 4. |
| 6. Weaviate `EvidenceChunkV1` | **DONE (create + validate)**; write probe **blocked on zero chunk rows**, as predicted. |

---

## Step 1 — migrations 0071 + 0072 · DONE

Target: `platform` on `100.91.190.107:5432`, connected through the repo's own
`server/core/url.py` resolution (`DB_HOST` overridden to the tailnet address because the
default `agentos-db` only resolves inside the compose network). No credential value was
read or printed.

**Pre-state (verified live, before any write):**

```
to_regclass working.cdc_sink                = None
to_regclass working.context_record_event    = None
to_regclass working.content_chunk_message   = None
to_regclass working.normalized_record_chunk = None      <- dropped by 0058, as documented
to_regclass working.content_chunk           = working.content_chunk
public.schema_version                       = 0 rows    <- ledger EMPTY
```

**Rehearsal (rollback):** both files applied in one transaction under
`pg_advisory_xact_lock(hashtext('apply-0071-0072-platform-cdc-bridge'))`,
`lock_timeout=10s`, `statement_timeout=300s`, then `ROLLBACK`. All post-conditions passed.

**Apply for real:** `2026-09-05T09:54:35Z` → `09:54:40Z`, one transaction, `COMMIT`.

```
0071_pg_cdc_outbox_spine.sql          sha256=18bafb658f209ba3c3e85dfe59fb36b2ef146ade291a86a0934e56f50e669816
0072_content_chunk_message_bridge.sql sha256=0beb825f819911de6523769a338bf0afdd98b9d52af28411d04f9f54e4894f60
```

**Post-commit verification, on a NEW connection (not the applying one):**

| Check | Result |
|---|---|
| `to_regclass` cdc_sink / cdc_source / context_record_event / content_chunk_message / cdc_cursor / cdc_dead_letter | all present |
| `to_regclass working.normalized_record_chunk` | still `None` — 0072 did not resurrect it |
| `pg_get_functiondef` of `working.enqueue_evidence_vector_projection(uuid[],text)` | **no** `normalized_record_chunk`; **does** name `content_chunk_message` |
| `SELECT working.cdc_lag()` | runs; **36 rows** (6 sinks × 6 outboxes) |
| `evidence_vector_projection_job` FK | `evidence_vector_projection_job_chunk_fk` present (was: none) |
| `working.cdc_sink` D-107 invariant | `surrealdb → (auto_drain=False, promotion_only=True)`; the other five `(True, False)` |
| outbox triggers | `chat_conversation_outbox`, `chat_message_outbox`, `content_chunk_outbox`, `context_asset_outbox`, `context_record_outbox`, `normalized_record_outbox` |

### Migration ledger — read this before trusting `public.schema_version`

Neither `0071` nor `0072` writes its own ledger row; in this repo the *apply script* does
(`scripts/apply_0054_live.py`). The live ledger was **empty (0 rows)** beforehand.

Two rows were appended, as `platform_admin`, at `2026-09-05T09:55:28Z` — and **nothing
else**. No prior migration history was reconstructed or invented. Each row's `notes` field
says so explicitly. The ledger therefore records exactly two of the many migrations this
database has actually seen; it is a starting point, not a history.

```
('0071', '0071_pg_cdc_outbox_spine',          'active', 'platform_admin', 2026-09-05 09:55:28+00)
('0072', '0072_content_chunk_message_bridge', 'active', 'platform_admin', 2026-09-05 09:55:28+00)
```

**Open item for the owner:** decide whether the ledger should be backfilled from `sql/`
for the migrations already live, or left as a going-forward-only record.

---

## Step 2 — `exec-platform-tools` · DONE

**Coolify did NOT auto-deploy from the push, and the reason is a live config defect.** The
app's watch paths are still the pre-restructure set:

```
compose.platform-tools.yaml
docker/tools/**
vendored/sbv/**
```

Commit `8ed3191` changed `deploy/platform-tools.yaml` and `deploy/docker/tools/Dockerfile`
— **neither matches any watch path**, so no deployment fired. Ground truth confirmed it:
before the manual trigger the container was still `platform-tools-…-232025273521`,
`StartedAt = 2026-08-29T23:26:12Z`, six days old, with no materialize mount.

> **FINDING — unfixed, config change, out of this session's scope.**
> `exec-platform-tools` watch paths must become `deploy/platform-tools.yaml`,
> `deploy/docker/tools/**`, `modules/forks/sbv/**`. Until then **every future
> platform-tools change requires a manual deploy** and will silently look deployed.

Manual trigger `2026-09-05T09:58:15Z`:

- deployment uuid **`l9y8ft7oaeu3zh4449uhg48t`** (id 1602), commit `5eda234`
- `status = finished`, `finished_at = 2026-09-05T10:01:53Z` (3m38s)

**Verified on ovh-app (100.72.169.40), not inferred:**

```
container   platform-tools-e1mshujml6bv8ldtoe8n7je0-095839059617
StartedAt   2026-09-05T10:01:52.070966386Z      (new; later than the 09:58:15Z trigger)
Status      running
Mounts      /data/agno/volumes/sbv_data                  -> /opt/sbv/data              RW=true
            <docker volume> r2-nexus                     -> /r2                        RW=true
            /data/agno/volumes/tool-gateway/materialize  -> /data/toolgw/materialize   RW=false   <- NEW, read-only
curl http://100.72.169.40:8090/tools  ->  HTTP 200
```

**Tool count: 41, not 39.** The 2026-09-05 review recorded 39 pre-redeploy; the rebuild
from `main` yields 41. Net **+2, nothing lost** — every tool that review named by hand is
still present (`transcripts.claude-ai-export`, `transcripts.chatgpt-official`,
`transcripts.perplexity-gdpr`, `transcripts.markdown`, `transcripts.generic-md`,
`documents.extract-docling`, `documents.extract-text`, `repair.pdf-inspect`, and the
`messages.*` family). The Dockerfile/context fixes in `8ed3191` did not cost coverage.
Reported as an honest discrepancy rather than filed as "matches".

---

## Step 3 — `tool-gateway` · the container is fine; the tailnet has no route to it

**No deploy needed — Coolify auto-deployed it from the push**, and this time it built. All
three blockers from the 2026-09-05 review are gone on `main`: `golang:1.26-bookworm` in all
four Go Dockerfiles, and the four `web-client-prebuilt/build/**` embed assets committed in
`8ed3191`.

**Container (ovh-app), verified:**

```
tool-gateway-ws67wgw1qxdgxo956p2k1jvi-095025287558
StartedAt    2026-09-05T09:54:40.228887685Z   Status running   RestartCount 0
image        platform-tool-gateway:latest
```

**Logs read with `--since $(docker inspect --format '{{.State.StartedAt}}' <c>)`, not a
time window:**

```
INFO tool gateway service token loaded token_length=96
tsnet running state path /data/toolgw/tsnet/tailscaled.state
tsnet starting with hostname "tool-gateway", varRoot "/data/toolgw/tsnet"
LocalBackend state is NeedsLogin; running StartLoginInteractive...
AuthLoop: state is Starting; done
INFO tool gateway listening address="https://tool-gateway.tilapia-skilift.ts.net (svc:tool-gateway)"
     platform_tools=http://100.72.169.40:8090 materialize_dir=/data/toolgw/materialize
     resolver_schemes=r2
```

tsnet **joined**. Tailscale API device record, live:

```
tool-gateway.tilapia-skilift.ts.net
  addresses ['100.126.220.36', 'fd7a:115c:a1e0::e329:dc25']
  tags      ['tag:docker']
  created   2026-09-05T09:54:41Z     lastSeen 2026-09-05T10:11:11Z
```

### Every URL form was probed from ovh-files, and every one failed

Token read into a shell variable from `/data/agno/secrets/tool-gateway/service-token` on
ovh-files (`token_len=96`; **the value was never echoed**).

| URL | Result |
|---|---|
| `https://tool-gateway.tilapia-skilift.ts.net/healthz` | `000` — TCP **connection refused** on :443 |
| `https://tool-gateway.tilapia-skilift.ts.net/tools` | `000` |
| `http://100.126.220.36:8099/healthz` | `000` — **connection refused** |
| `http://100.126.220.36:8099/tools` | `000` |
| `http://tool-gateway:8099/healthz` | `000` |

The node itself is up and routable — `tailscale ping` answers
`pong from tool-gateway (100.126.220.36) via 40.160.5.19:53445 in 1ms`, direct, not relay.
So this is not connectivity and not the bearer token.

### Root cause — `svc:tool-gateway` does not exist as a VIP service

`modules/engine/cmd/tool-gateway/main.go` calls
`srv.ListenService("svc:tool-gateway", tsnet.ServiceModeHTTP{HTTPS: true, Port: 443})`. A
Tailscale **Service** is reached at its own **VIP address**, not at the node's. Live from
the Tailscale API:

```
GET /tailnet/tilapia-skilift.ts.net/vip-services  -> 200
  svc:llm-probe     100.112.203.206   tcp:443   tag:docker
  svc:llm-probe-ui  100.75.17.185     tcp:443   tag:docker
  svc:n8n           100.70.243.34     tcp:443   tag:docker
  svc:workbench     100.105.91.39     tcp:443   tag:docker
```

**`svc:tool-gateway` is absent.** The four working services each have a VIP; the gateway
has none, so no address in the tailnet points at its listener. Worse, the *node* is also
named `tool-gateway`, so `tool-gateway.tilapia-skilift.ts.net` resolves to the **node IP**
`100.126.220.36` — a plausible-looking name that leads somewhere nothing listens. That is
why the failure reads as "connection refused" rather than "no such host", and it is why
this looked deployed.

`ListenService` succeeding inside the container is **not** evidence the service is
reachable. The container advertises; the tailnet must separately register the VIP.

### BLOCKED — permission denied, not worked around

The fix is one additive call, matching the four existing services exactly:

```
PUT https://api.tailscale.com/api/v2/tailnet/tilapia-skilift.ts.net/vip-services/svc:tool-gateway
{"name":"svc:tool-gateway","ports":["tcp:443"],"tags":["tag:docker"],"displayName":"Tool Gateway"}
```

**This call was attempted and refused by the permission system** (auto-mode classifier).
Per the session's hard rules it was **not** worked around — no alternate transport, no
admin-console automation, no fallback to a plain tsnet node listener, no ACL edit.
Recorded here and stopped.

**Owner decision needed:** approve the VIP-service creation, or create it in the Tailscale
admin console. Nothing else in step 3 is outstanding.

### Second finding — the gateway cannot resolve `upload://`

`resolver_schemes=r2`. `buildResolver()` registers `file` + `upload` **only when
`SOURCE_OBJECT_DIR` is set**; the `tool-gateway` app does not set it, so only the R2
resolver loaded. That is arguably correct — the gateway runs on ovh-app while the
`upload://` objects live on ovh-files, and cross-host bytes are supposed to travel via
object storage — but it means **the existing rehearsal fixture `upload://72640c6c…` cannot
be resolved by the gateway as deployed.** Either the fixture is published to R2 and
referenced as `r2://`, or this assumption is re-ruled. Flagged; not decided here.

---

## Step 4 — worker repoint · NOT DONE, deliberately

Step 4 is defined as setting `PLATFORM_TOOLS_BASE_URL` to *"the gateway URL proven in step
3."* **No URL was proven.** Pointing the worker at an address that refuses every connection
would convert a diagnosable 4xx into a connection failure on every repair Activity. No
`PATCH .../envs/bulk` was issued.

State of the worker as it stands, verified on ovh-files (read-only inspection):

```
container   universal-import-worker-d24bb9eoo47qtw9eq1xc6u64-095047602583
StartedAt   2026-09-05T09:52:55.646664753Z    Status running
env         PLATFORM_TOOLS_BASE_URL=http://100.72.169.40:8090   (still platform-tools direct)
            SOURCE_OBJECT_DIR=/data/uiw/source-objects
            TEMPORAL_HOST_PORT=100.91.190.107:7233  TEMPORAL_TASK_QUEUE=universal-import-v1
mount       /data/agno/secrets/tool-gateway/service-token -> /run/secrets/tool-gateway-service-token
```

`TOOL_GATEWAY_SERVICE_TOKEN_FILE` is unset in the environment, so `uiwworker/config.go`
falls back to its default `/run/secrets/tool-gateway-service-token` — which **is exactly
the mount path** (`fa51dde`). The two agree; no change required.

Logs since `StartedAt` show a **clean start with no fail-closed token error** — the worker
did read the token file, or `LoadConfig` would have aborted before Temporal polling began:

```
WARN UIW schema admission: PLATFORM_DEV_AUTH_BYPASS is set -- admitting the pre-launch DEV
     sentinel case-registry identity ... (D-125, D-126); remove this flag before go-live
DEBUG Worker heartbeating configured, but server version does not support it.
INFO  Started Worker Namespace default TaskQueue universal-import-v1 WorkerID 1@ovh-files@
INFO  universal import worker started task_queue=universal-import-v1 namespace=default activity_count=26
```

The worker is running the **new** gateway-shaped code (auto-deployed from the push; its
watch paths, unlike platform-tools', are correct). Because that code now sends
`{"source_ref","args"}` plus `Authorization: Bearer` while its env still addresses
**platform-tools directly**, the repair Activity would fail against a Python service that
speaks neither. That is the known consequence of steps 3–4 being blocked, not a new defect.

---

## Step 5 — UIW rehearsal · NOT RUN

Gated on steps 3 and 4, both blocked. Running it now would fail at
`assess_source_repair_activity` for an already-understood reason and would add no
information beyond what step 3 established. **The rehearsal state is unchanged from
2026-09-02: furthest stage reached remains `retain_original_activity` SUCCEEDED,
`assess_source_repair_activity` FAILED.** No fixture was modified. No workflow was started.

---

## Step 6 — Weaviate `EvidenceChunkV1` · created and validated

`server/core/evidence_vector_store.py:41` defines
`EVIDENCE_VECTOR_COLLECTION = f"EvidenceChunkV{EVIDENCE_VECTOR_COLLECTION_VERSION}"` →
**`EvidenceChunkV1`**, so the projection code does expect exactly that name. Created via
the repo's own `ensure_evidence_vector_collection()` — not hand-rolled schema JSON.

```
classes BEFORE: Evidence_knowledge, Legal_knowledge, Personal_history_knowledge,
                Platform_code_knowledge, Platform_context, Platform_knowledge,
                Relationship_timeline_knowledge                                (7)
created: True | name: EvidenceChunkV1 | dim: 2048 | model: nvidia/nemotron-3-embed-1b
validate_evidence_vector_collection: PASS
classes AFTER:  the same 7 + EvidenceChunkV1                                   (8)
added:   ['EvidenceChunkV1']
removed: []                          <- nothing deleted, nothing altered
objects in EvidenceChunkV1: 0
```

### The write probe is blocked on zero chunk rows — stated plainly

The rehearsal was not run, and it would not have produced chunks in any case. Live counts,
`platform`, after the migrations:

```
content_chunk                    0
content_chunk_message            0
content_chunk_generation         0
normalized_record                0
evidence_vector_projection_job   0
context_record                   0
cdc_cursor                       0      (no sink has claimed a batch yet)
cdc_dead_letter                  0
context_record_event             0
content_chunk_event              0
lanes with open dead letters     0
```

**No real projection was attempted, and none could be.** The only writer of
`content_chunk` + `content_chunk_message` is the Go message-window chunker Activity —
redesign-plan **Stage 3, not yet built**. Fabricating a chunk row to make a write probe
succeed would mean inventing a custody-derived digest, which is precisely what custody
exists to prevent. **The Weaviate feed remains correct-but-unproven; the 2048-d write path
has still never carried a single object.**

---

## Everything that changed, in one list

| Change | Where | Reversible |
|---|---|---|
| `0071` + `0072` applied | live `platform` DB | schema only; zero rows anywhere |
| 2 rows appended to `public.schema_version` | live `platform` DB | append-only rows |
| platform-tools redeployed → new container + materialize `:ro` mount | ovh-app | redeploy |
| `EvidenceChunkV1` created (0 objects) | Weaviate `100.91.190.107:8081` | additive; no existing class touched |
| **Nothing** committed, staged, pushed, or branched | repo | n/a |
| **No** file deleted or moved | anywhere | n/a |
| **No** worker env changed | Coolify | n/a |
| **No** Weaviate class deleted or altered | Weaviate | n/a |

## Blocked / stopped

1. **`svc:tool-gateway` VIP service creation — PERMISSION DENIED** by the auto-mode
   classifier. Not worked around. Steps 3, 4 and 5 stop here.
2. **`exec-platform-tools` watch paths are stale** — the app no longer auto-deploys on any
   change to its actual source files. Config fix; not attempted this session.
3. **Gateway resolves `r2` only**, not `upload` — the current rehearsal fixture is
   unreachable by the deployed gateway. Needs an owner ruling or an R2-published fixture.
4. **`public.schema_version` holds only these two rows.** No history was fabricated.
