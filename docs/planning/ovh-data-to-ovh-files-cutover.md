# ovh-data → ovh-files cutover — definition of done

> _Byline: Claude Code · Opus 5 (1M) · 2026-08-01_

**A datastore migration is not done when the bytes land. It is done when every
consumer talks to the new host and that has been proven by a real query.**

This doc exists because the host re-point was written down as a follow-up task
instead of as part of the migration (owner correction, 2026-08-01). Re-pointing
and re-verifying are **exit criteria below**, not a separate ticket. The migration
stays open until every box in section 3 is checked.

## 1. What is moving

| From | To |
|---|---|
| `ovh-data` — tailnet `100.119.96.29` | `ovh-files` — tailnet TBC at cutover |

Payload measured earlier this session: **1,914 MB**. Five independent Coolify
apps on the shared `agno` docker network: pg, neo4j, graphiti, surreal, vector.

## 2. Every place the old host is configured

Good news from the inventory (2026-08-01): **the repo is almost entirely
variable-driven**. The work is env values and defaults, not scattered literals.

| Where | What to change | Kind |
|---|---|---|
| Coolify env — each of the 5 data apps | `BIND_IP` → new tailnet IP | **live env, needs redeploy** |
| Coolify env — exec tier (`compose.exec.yaml`) | `OVH3_HOST` → new tailnet IP; `DB_HOST` follows it | **live env, needs redeploy** |
| `compose.data-*.yaml` (pg, neo4j, graphiti, surreal, vector) | header comments naming `100.119.96.29` | doc-in-code |
| `compose.data-graphiti-case.yaml:68` | `NEO4J_URI` default `bolt://100.119.96.29:7687` | **default literal** |
| `compose.exec.yaml:30,68` | `${OVH3_HOST}` default comment | doc-in-code |
| `compose.data.yaml:38,40` | cross-box default IP comment | doc-in-code |
| `compose.contextforge.yaml:10` | `OVH3_HOST` comment | doc-in-code |
| `AGENTS.md:101` | "Tailnet PG from the desktop needs `DB_HOST=100.119.96.29`" | **doc claim, will be false** |
| local desktop `.env` (`DB_HOST`) | new tailnet IP | not in git |
| scratchpad ingest scripts | host is read from `.env` — no change needed | — |
| `~/.secrets/infra-access.md` | any recorded host/port for the data tier | not in git |

**Coolify gotcha that will bite here:** env values are rendered as literals into
the materialized compose at deploy. Changing an env var does **not** reach running
containers until a redeploy. Every app whose `BIND_IP`/`OVH3_HOST` changes must be
redeployed, not restarted.

**Watch-paths gotcha:** any app created for this move must have watch paths set at
creation, or it redeploys on every push to its branch.

## 3. Exit criteria — the migration is open until ALL of these pass

Not "the config looks right". Each line is a command whose real output is read.

- [ ] **PG answers on the new host** — `SELECT count(*) FROM evidence.raw_sms;`
      over the tailnet returns **13,662** (the committed load, 2026-08-01).
- [ ] **Row counts match pre-move** — `evidence.vw_layer_map` (migration 0012)
      returns the same per-layer counts as the snapshot taken before the move.
- [ ] **`analysis.human_label_gold` = 1,918.** Non-negotiable; it is the
      hand-labelled gold set and it has no FKs to protect it.
- [ ] **Neo4j bolt reachable** on the new host and the graph is non-empty.
- [ ] **Graphiti writes AND reads** — add one episode, search it back.
- [ ] **SurrealDB answers** and agno sessions persist across a container restart.
- [ ] **Weaviate REST :8081 + gRPC :50051** reachable, collection count matches.
- [ ] **agentos-api `/config` returns 200** and lists the expected `db_id`s —
      the API is the consumer that proves `DB_HOST` actually re-pointed.
- [ ] **A real agent run completes end to end** and its memory row lands.
- [ ] **Desktop ingest works** — re-run the e2e script against the new host and
      confirm it reports `RE-RUN ... topping up`, i.e. it found the existing data.
- [ ] **Old host is unreachable or drained** — prove nothing is silently still
      talking to `100.119.96.29`. A passing test against the old box is a failure.
- [ ] **Every row of section 2 applied**, including `AGENTS.md:101` and the compose
      comments — a stale doc claim is how the next agent re-breaks this.

## 4. Order of operations

1. Snapshot counts from the OLD host (`vw_layer_map`, `vw_pipeline_funnel`, gold set).
2. Move the data.
3. Change env in Coolify, **redeploy** each app (not restart).
4. Update repo defaults + docs in one commit.
5. Run section 3 top to bottom, reading real output.
6. Only then: drain the old box.

Do not skip step 1. Without a before-snapshot, "the counts look fine" is unfalsifiable.

## 5. Related

- Verified load this snapshot is taken from: `docs/reports/` (evidence pipeline report)
- Coolify env-literal behaviour and watch-paths: `AGENTS.md` → Deploy & Data-Tier Gotchas
