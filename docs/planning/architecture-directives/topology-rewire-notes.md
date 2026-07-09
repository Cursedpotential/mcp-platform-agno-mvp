# Topology Rewire Notes — compose.data.yaml + compose.exec.yaml

> _Byline: Claude Code · Opus 4.8 · 2026-06-14_
>
> **Status: authoring only.** No deploy, no infra, no docker run. Changes are live
> in the two committed compose files (reviewable via `git diff 99fd637`).

## New topology (source of truth)

| Tier | File | Box | tailnet | salem | public |
|------|------|-----|---------|-------|--------|
| DATA | compose.data.yaml | OVH-3 "ovh3-data" | 100.119.96.29 | 10.1.2.101 | 147.135.79.183 |
| EXEC | compose.exec.yaml | OVH-1 "ovh1-agno" | 100.72.169.40 | 10.1.1.122 | 40.160.5.19 |

- **OVH-2 decommissioned** — removed from all headers/comments.
- DATA services: agentos-db (PG18), neo4j, graphiti-mcp, **Milvus (relocated from OVH-2)** + **Attu (optional)**, **SurrealDB (new)**.
- EXEC services: agentos-api, gateway, sandbox, platform-tools, desktop, agent-ui, **ContextForge (new)**.
- Cross-box default = **TAILNET** (owner: "at the moment, everything communicates through Tailscale"); salem is the swap-later fast path. Switch by changing the `OVHx_HOST` env value only.

## BIND_IP per box (set in Coolify app env)

- DATA (OVH-3): `BIND_IP=100.119.96.29`  (salem alt 10.1.2.101)
- EXEC (OVH-1): `BIND_IP=100.72.169.40`  (salem alt 10.1.1.122)

All published ports bind `${BIND_IP:-127.0.0.1}:...` — never 0.0.0.0. Host port 8080 never published (ContextForge uses 4444).

## Env vars — new / changed (default = tailnet; salem = swap-later alt)

### Cross-box host vars
| Var | Default (tailnet) | Salem alt | Notes |
|-----|-------------------|-----------|-------|
| `OVH1_HOST` | `100.72.169.40` | `10.1.1.122` | exec box; graphiti-mcp → gateway. Already present, unchanged. |
| `OVH3_HOST` | `100.119.96.29` | `10.1.2.101` | data box. **RENAMED from `OVH2_HOST`.** |

### agentos-api (EXEC) — points at DATA tier
| Var | Default in compose | Notes |
|-----|--------------------|-------|
| `DB_HOST` | `${OVH3_HOST}` | was `${OVH2_HOST}` |
| `MILVUS_ADDRESS` | `http://${OVH3_HOST}:19530` | was empty default; now defaults to data-box gRPC over tailnet |
| `MILVUS_TOKEN` | (empty) | unchanged |
| `SURREALDB_URL` | `ws://${OVH3_HOST}:8000/rpc` | **NEW** — WS transport, /rpc path |
| `SURREALDB_USER` | `root` | **NEW** |
| `SURREALDB_PASS` | `root` | **NEW** — MUST equal data-tier SURREALDB_PASS |
| `SURREALDB_NS` | `agno` | **NEW** |
| `SURREALDB_DB` | `platform` | **NEW** |
| `CF_GATEWAY_URL` | `http://contextforge:4444` | **NEW** — internal docker network name (same box) |
| `CF_GRAPHITI_SERVER_ID` | (empty) | **NEW** — virtual server UUID from POST /servers (bootstrap) |
| `CF_GATEWAY_TOKEN` | (empty) | **NEW** — long-lived client JWT |

### ContextForge (EXEC) — new service
| Var | Default | Notes |
|-----|---------|-------|
| `GRAPHITI_MCP_URL` | `http://${OVH3_HOST}:8071` | **NEW** — upstream graphiti peer (salem alt 10.1.2.101:8071); used at bootstrap registration |
| `CF_JWT_SECRET_KEY` | **required** (`:?`) | `openssl rand -hex 32`; MUST match token-mint --secret |
| `CF_AUTH_ENCRYPTION_SECRET` | **required** (`:?`) | `openssl rand -hex 32`; encrypts stored peer creds |
| `CF_BASIC_AUTH_USER` | `admin` | |
| `CF_BASIC_AUTH_PASSWORD` | **required** (`:?`) | |
| `CF_ADMIN_EMAIL` | `admin@mitechconsult.com` | |
| `CF_ADMIN_PASSWORD` | **required** (`:?`) | |
| (DOMAIN PHASE) `MCP_INT_DOMAIN` / `MCP_DOMAIN` | — | only when Traefik labels enabled |

### SurrealDB + Milvus (DATA) — service-side
| Var | Default | Notes |
|-----|---------|-------|
| `SURREALDB_USER` | `root` | data-tier root signin; must match exec `SURREALDB_USER` |
| `SURREALDB_PASS` | `root` | must match exec `SURREALDB_PASS` |
| (DOMAIN PHASE) `MILVUS_DOMAIN` / `ATTU_DOMAIN` | — | only when Traefik labels enabled |

## Host-prep commands — OVH-3 (DATA) before first deploy

```bash
sudo mkdir -p /data/agno/volumes/{pgdata,neo4j_data,milvus,surrealdb} \
              /data/agno/config/{sql,graphiti,milvus}
sudo chown -R 999:999   /data/agno/volumes/pgdata       # postgres uid
sudo chown -R 7474:7474 /data/agno/volumes/neo4j_data   # neo4j uid
sudo chown -R 999:999   /data/agno/volumes/milvus       # milvus uid
sudo chown -R 0:0       /data/agno/volumes/surrealdb    # surrealdb runs as root
# stage real config/SQL files at the absolute bind paths:
scp sql/000*.sql                ovh3:/data/agno/config/sql/
scp docker/graphiti/config.yaml ovh3:/data/agno/config/graphiti/
scp configs/embedEtcd.yaml configs/user.yaml ovh3:/data/agno/config/milvus/
# (Attu, if used, auto-creates /data/agno/volumes/attu — no chown needed; it
#  runs as its image default. Add `sudo mkdir -p /data/agno/volumes/attu` if you
#  want the dir pre-created.)
```

## Host-prep additions — OVH-1 (EXEC)

```bash
sudo mkdir -p /data/agno/volumes/contextforge
sudo chown -R 1000:1000 /data/agno/volumes/contextforge   # ContextForge SQLite db + state
```

## Port map (tailnet-bound via BIND_IP)

- DATA: 5432 (pg), 7474/7687 (neo4j), 8071→8000 (graphiti-mcp), 19530/9091 (milvus), 3001→3000 (attu), 8000 (surrealdb).
- EXEC: 8000 (api), 4000/4096 (gateway), 8085/8090 (platform-tools), 6901 (desktop), 3000 (agent-ui), 4444 (contextforge).
- **Port collision avoided:** Milvus's Attu wants host 3000, but agent-ui (EXEC) and the convention reserve 3000. Attu is on the DATA box (no agent-ui there) so 3000 would be free, but it was mapped to **host 3001** to keep 3000 semantically the "chat UI" port platform-wide and avoid surprise. Internal Attu→Milvus stays `milvus:19530`.

## Open questions / assumptions

1. **Milvus relocation = fresh start.** Compose points at `/data/agno/volumes/milvus` on OVH-3, not the old OVH-2 data dir. If existing Milvus collections on OVH-2 must be carried over, copy `/data/milvus/volumes/milvus` (old path on OVH-2) → `/data/agno/volumes/milvus` (new path on OVH-3) before first start. **No migration is scripted here.**
2. **Milvus config path moved** from `/data/milvus/configs/*` (milvus-coolify) to `/data/agno/config/milvus/*` to fit the unified `/data/agno` tree. Stage `embedEtcd.yaml` + `user.yaml` there.
3. **SurrealDB starts empty** — no migration of existing Postgres-resident agno operational data. Decide whether historical sessions/memory must be carried over (see surrealdb-integration.md §e/7).
4. **SurrealDB `rocksdb:` arg form** (`rocksdb:/data/surreal.db`) — verify exact CLI prefix syntax for v3.1.4 before deploy (prefix syntax shifted across majors).
5. **`surrealdb` pip client not yet installed** — install + re-pin; verify 1.x client speaks v3.1.4 server RPC.
6. **ContextForge healthcheck** uses `/health` (some builds expose `/healthz`) — confirm on 1.0.3, adjust if it 404s.
7. **ContextForge registration is stateful** (peer gateways/virtual servers live in SQLite, created via bootstrap API calls — NOT in compose). Persist via the bind mount; an idempotent `scripts/contextforge-bootstrap.sh` is still an open task (registers graphiti at `${GRAPHITI_MCP_URL}/sse`).
8. **agentos-api now points at ContextForge, not graphiti directly** (`CF_GATEWAY_URL=http://contextforge:4444`). `CF_GRAPHITI_SERVER_ID` + `CF_GATEWAY_TOKEN` are empty until the bootstrap mints them — agno MCP wiring to the gateway is a follow-up code change (see contextforge-integration.md §d).
9. **graphiti peer transport** — registered as SSE (`/sse`) per artifact; `zepai/knowledge-graph-mcp` also serves streamable-http (`/mcp`). Confirm before bootstrap.
10. **Salem swap** — to move any cross-box link off tailnet, set `OVH1_HOST=10.1.1.122` / `OVH3_HOST=10.1.2.101` in the relevant Coolify app env; no compose edits needed.
```