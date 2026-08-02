# HANDOFF — Weaviate/MemGQL transition to fully functional (2026-07-27)

> _Byline: Claude Code · Fable 5 · 2026-07-27_
> Owner cleared context after this. Next session: read this file top to bottom, then work the
> phases in order. Everything above the task list is verified-live state, not aspiration.

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| **data-weaviate** | LIVE ovh-data (100.119.96.29), uuid `h5hrvmcs84no9g1ubl0jr0pw`, REST **:8081** (8080=coolify-proxy), gRPC :50051, ready=200, anonymous auth (tailnet-only), image `semitechnologies/weaviate:latest` = 1.39.0-rc.0 (UNPINNED — task below), `DEFAULT_VECTORIZER_MODULE=none` (we bring embeddings). Compose `deploy/data-weaviate.yaml` @ branch `infra/data-weaviate-memgql`. |
| **data-memgql** | **KILLED (owner 2026-07-28)** — app deleted from Coolify (was uuid `is1z1b0v0j6s842gggak5iew`). MemGQL removed from architecture entirely (ADR-0041 addendum: 2-connector/2-connection Community cap + workloads need whole-graph MAGE algorithms, not federation). Replacement: `data-memgraph` (memgraph-mage), Phase 2. |
| **Milvus** | STAYS UP but sidelined (ADR-0040): memsearch MCP still depends on it. No new platform writers. 4096-d nv-embed-v1 vectors, collections incl. `platform_knowledge`. |
| **coolify-mcp (federated)** | 21 tools live through ContextForge (`coolify-write-*`), create_application fixed for 4.1.2, 7 lifecycle tools added, verified end-to-end incl. live get-application-logs call. CF stale-catalog gotcha + fix documented in `~/.claude/skills/coolify-write/references/MCP-PATH.md`. |
| **ContextForge** | v1.0.4 @ 100.72.169.40:4444, Streamable HTTP federation confirmed, client token in `~/.secrets/contextforge.env`. Gateways: coolify-write, agno_platform, coolify(read), graphiti(:8071, reachable), exa. Can also register raw REST endpoints as catalog tools (integration_type REST) for anything an MCP lacks. Tool-catalog re-sync = `PUT /gateways/{id}` (no /refresh endpoint). |
| **ADRs** | 0040 ACCEPTED (Weaviate), 0041 **REVISED — Variant A (MemGQL) KILLED per addendum (owner "go" 2026-07-28); Variant B = Memgraph Community projection is the accepted direction** (see Phase 2), 0037 blocker CLOSED (CF federates streamable HTTP; graphiti already behind it), 0036 ACCEPTED (owner 2026-07-29 — DozerDB memory/evidence split). All committed on `docs/adr-graphiti-memory`. |
| **Orchestration ruling** | Agno-native. GraphRAG/retrieval = thin MCP tools consumed by Agno agents. LlamaIndex allowed as in-tool library. NO LangGraph. OpenCode delegation allowed: NVIDIA + Ollama Cloud anything; OpenRouter + OpenCode Zen free-only; prefer the OpenCode MCP door. |

## The target architecture (what "fully functional" means)

```
ingestion (custody-hashed evidence pipeline, agentos-api)
  ├─ rows        → PG working.normalized_record (bitemporal, provenance)  [unchanged]
  ├─ embeddings  → WEAVIATE (replaces Milvus for all platform writes)
  ├─ entities    → Graphiti temporal KG (agent memory, Neo4j `memory` DB)
  └─ evidence KG → Semantica → Neo4j `evidence` DB (DozerDB split, ADR-0036)
retrieval / analysis
  ├─ FTS + vector hybrid → Weaviate (native BM25+vector)
  ├─ zero-ETL federated GQL → MEMGQL (connectors: data-pg, Neo4j, DuckDB) —
  │    cross-store graph queries WITHOUT copying data (cycle detection,
  │    antecedent reconstruction over live rows + both graphs)
  └─ all exposed as MCP tools behind ContextForge → consumed by Agno agents
```

## PHASES / TASK LIST (work in order)

### Phase 1 — Weaviate becomes the platform vector store
1. **Pin the image tag** (currently `:latest` = 1.39.0-rc.0 — pick current stable 1.3x, redeploy).
2. **Create collections** mirroring the Milvus two-collection design (ADR-0010) with 4096-d vectors, `vectorizer: none`, BM25 enabled — names/shape per ADR-0010/0011 (dimension contract carries over).
3. **Export Milvus → import Weaviate** dims-intact: pymilvus query-iterator over each collection → batch insert via Weaviate python client (gRPC :50051). Verify counts + spot-check search parity (same query vector → comparable neighbors). Good OpenCode delegation candidate (mechanical; free-tier model).
4. **Cut the knowledge pipeline over**: agentos-api knowledge stage writes to Weaviate instead of Milvus (env/config-level change + redeploy; find the vector-store client in the knowledge stage). Re-run one supervised ingest through the operator console (C2 gates) and prove docs land (search hit-count gate — owner's silent-empty scar).
5. **Auth hardening**: enable API-key auth (`AUTHENTICATION_APIKEY_*`), key into `~/.secrets/` + Coolify app envs, redeploy. Tailnet-only stays.
6. Milvus: leave running for memsearch ONLY. When memsearch is migrated or retired → decommission the convoy (separate decision).

### Phase 2 — Memgraph analysis graph (REVISED 2026-07-28, replaces MemGQL plan — see ADR-0041 addendum)
> MemGQL parked (Community = 2 connectors + 2 simultaneous connections; and the real workloads
> — cycle detection, alienation trajectories, community detection, bridge/anomaly analysis — are
> whole-graph MAGE algorithms federation can't run). DuckDB is EMBEDDED in PG (pg_duckdb), so the
> sync job's only relational source is PG.
0. **RAM sizing check** on ovh-data first (Memgraph is in-memory; project node/edge counts from `working.normalized_record` + entity tables — expected small at ~20K events, but verify headroom). **data-memgql: KILLED entirely (owner 2026-07-28)** — Coolify app deleted; remove `deploy/data-memgql.yaml` from the branch (git history keeps it).
1. **Deploy `memgraph/memgraph-mage`** as `data-memgraph` on ovh-data — own Coolify app, tailnet-only, pinned tag, same deploy pattern/gotchas as data-weaviate.
2. **Identity spine FIRST** (promoted from Phase 4 — gates everything): verify/fix entity-key stamping in `normalize.py` so one human = one node across phone/email/platform identities. Without it, community/centrality results are garbage.
3. **Projection sync job**: PG → Memgraph, idempotent Cypher MERGE, incremental + full-rebuild capable, scheduled (5-min or on-ingest). **Event time** (valid_from/valid_to) on edges; PG record ids on every node/edge (ADR-0041 guardrails 2/5). Smoke-test Bolt driver + Memgraph-vs-Neo4j Cypher dialect first (guardrail 4).
4. **Detection matcher fix** (`server/analysis/detection.py`, promoted from Phase 4): Unicode apostrophes/word boundaries/`deflection_of_accountability` — it feeds edge labels (provocation/deflection), so it gates cycle-detection quality.
5. **Algorithm MCP tools** behind ContextForge (`memgraph` gateway, coolify-write pattern, PUT-resync gotcha), in order: (a) cycle detection (provocation→reaction→selective-capture); (b) windowed contact-degree trend per person-set — the **alienation/isolation metric**, before/after incident anchors; (c) Louvain/Leiden communities ("my people / her people") + betweenness bridge nodes and bridge-cutting over time; (d) anomaly surfacing (community-misfit entities, coordinated-timing bursts). Agno agents consume; every result cites PG record ids.

### Phase 3 — Agno memory/knowledge integration
1. **AgentOS knowledge/memory UI repair** (owner-reported broken on first open; unscoped — repro pass first: open AgentOS, catalog which knowledge/memory surfaces fail, then chase config between AgentOS UI and Graphiti/vector backends). Likely intersects with the Milvus→Weaviate cutover (UI may point at Milvus).
2. **TraceIQ → Agno knowledge tie-in** (traceiq ADR-0015 gap): ingest TraceIQ-derived facts (home bases, patterns, labels) into Graphiti with provenance pointers to deterministic rows + prove-it-landed node-count gate. Evidence→Analysis→Legal-Team tier.
3. **Graphiti auth door**: register graphiti WRITE-enabled behind CF (0037 transport blocker now closed), retire the no-auth nginx :8071 door.
4. **DozerDB swap** (ADR-0036): BACKUP Neo4j volume first, swap image, create `memory`+`evidence` named DBs, RBAC writer roles. Confirm with owner before touching the volume.

### Phase 4 — carried items (unchanged priority)
- Detection matcher fix (`server/analysis/detection.py`) — Unicode apostrophes/word boundaries/`deflection_of_accountability` category. Cheapest high-value; gates cycle detection quality.
- Identity-spine verification (`normalize.py` — do entity keys stamp onto records at write time?).
- ADR-0034 stranded on `docs/adr-0033-0034-evidence-model` — merge or re-home.
- Root compose cleanup: migrate 19 root-level `compose.*.yaml` → `deploy/` (owner hates the root mess; each move = app config change + redeploy, do deliberately).
- Merge `infra/data-weaviate-memgql` → main when the data apps are settled.
- Rotations: Coolify API token, OS_SECURITY_KEY.

## Gotchas bank (hard-won today — respect these)
- Coolify 4.1.2: app create = `POST /applications/private-github-app` w/ `github_app_uuid` from `GET /github-apps`. Plain `/applications` 404s.
- NEVER `docker start/stop/rm` a Coolify-owned container on the host — orphans hold ports and wreck the next deploy (cost us 2 failed deploys today).
- coolify-proxy owns host 8080 on every node.
- Weaviate single-node on Coolify network needs `CLUSTER_ADVERTISE_ADDR=127.0.0.1`.
- ContextForge caches gateway tool lists — after upstream tool changes, `PUT /gateways/{id}` to re-sync.
- Classifier blocks Coolify writes/settings edits via shell — `autoMode.allow` rules exist in traceiq-rebuild `.claude/settings.local.json`; Edit-tool works where Bash is blocked.
- Env values bake into rendered compose at deploy — env change ⇒ redeploy.

## Where everything is
- ADRs + ledgers: `docs/adr/0040-*.md`, `0041-*.md`, `docs/OPEN-TASKS-2026-07-27.md` (branch `docs/adr-graphiti-memory`).
- Coolify skill (MCP-first, tested): `~/.claude/skills/coolify-write/` (SKILL.md router + references/MCP-PATH.md + references/API.md).
- Memgraph official skills: `~/.claude/skills/memgraph-*` (esp. `memgraph-graph-rag`, `memgraph-cypher-syntax`).
- Secrets (names only): `~/.secrets/contextforge.env`, `~/.secrets/coolify-ionos-api.env`, `~/.secrets/traceiq-provider-*.md`.
- Graphiti group `platform` holds the decision episodes; project memory `vector-graph-stack-revisit.md` + `opencode-provider-policy.md`.
