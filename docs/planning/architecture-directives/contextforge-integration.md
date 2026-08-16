# ContextForge MCP Gateway — Integration Design (EXEC tier / OVH-1)

> _Byline: Claude Code · Opus 4.8 · 2026-06-14_
>
> **Status: DESIGN / DRAFT — not deployed.** This is a copy-paste-ready design artifact for
> wiring IBM ContextForge (MCP Gateway) into `compose.exec.yaml`. It does **not** modify any
> live compose file or touch infra. Coolify deploys the real thing once this is reviewed.

> **2026-08-16 correction — Codex · GPT-5:** this historical draft is superseded for storage
> and publication topology. ContextForge remains the authored registry but must use a dedicated
> PostgreSQL database on ovh-files; SQLite is migration/rollback input only. Approved tools are
> published one-way from an exact ContextForge `/servers/<uuid>/mcp` endpoint into Portkey MCP
> Gateway for downstream auth/audit. The current OSS Portkey LLM container does not itself prove
> MCP control-plane availability. See `docs/plans/MCP-GATEWAY-CHAIN-PHASE1-2026-08-16.md`.

---

## 0. What this is and why

**ContextForge** = IBM's open-source MCP Gateway / registry (`github.com/IBM/mcp-context-forge`,
docs `ibm.github.io/mcp-context-forge`). It is the **single controlled gateway** through which
ALL external MCP access flows. The actual MCP servers (graphiti-mcp, and any future ones) stay
**internal/tailnet-only** and are registered *behind* ContextForge as federated peer "Gateways".
Clients (Agno's `MultiMCPTools` / external callers) connect to ONE unified, JWT-gated endpoint;
nothing else MCP is exposed directly.

Topology (locked decisions):

```
                  public twin (gated)         private name
                  mcp.mitechconsult.com        mcp.int.mitechconsult.com
                          │                         │
                          ▼  (Traefik, DOMAIN PHASE)▼
   ┌──────────────────────────────────────────────────────────┐
   │ OVH-1  EXEC tier   tailnet 100.72.169.40 / salem 10.1.1.122 │
   │                                                            │
   │   contextforge  ──(salem/tailnet)──►  graphiti-mcp         │
   │   :4444 (BIND_IP)                     OVH-3 10.1.2.101:8071 │
   │      ▲                                (SSE / streamable)    │
   │      │ JWT                                                  │
   │   agentos-api ───────────────────────┘ (points at gateway, │
   │                                          NOT graphiti direct)│
   └──────────────────────────────────────────────────────────┘
```

> **Addressing note / discrepancy to confirm:** the task brief places graphiti-mcp on **OVH-3**
> (tailnet `100.119.96.29`, salem `10.1.2.101:8071`). The current `compose.data.yaml` header
> comments describe the data box as **OVH-2** (`vps-ff65b4ab…`). They refer to the same DATA-tier
> graphiti service; this doc uses the brief's explicit `salem` address `http://10.1.2.101:8071`
> for the gateway→graphiti link and exposes it as `${GRAPHITI_MCP_URL}` so the actual host can be
> set once in env without editing the registration call. Reconcile OVH-2 vs OVH-3 naming before deploy.

---

## a) Compose service block for `compose.exec.yaml`

Append the following to the `services:` map in `compose.exec.yaml`. It follows the existing house
conventions: `${BIND_IP}` port binding (never `0.0.0.0`), `linux/amd64` pin, bind-mount volumes
under `/data/agno/volumes/<svc>`, official pulled image with a **pinned tag**, healthcheck, and a
COMMENTED-OUT "DOMAIN PHASE" Traefik scaffold for the `mcp.*` names (off by default).

```yaml
  # ---------------------------------------------------------------------------
  # ContextForge — IBM MCP Gateway (ADR-0025). The ONE controlled MCP front door.
  # All external MCP flows through here; graphiti-mcp (DATA tier, OVH-3) and any
  # future MCP servers register BEHIND it as federated peer "Gateways" and are
  # never exposed directly. Public face: mcp.int.mitechconsult.com (private) +
  # gated mcp.mitechconsult.com (public twin) — Traefik scaffold below, OFF by default.
  #
  # Backing store: SQLite on a bind mount (single-node, no external Postgres/Redis
  # needed for this footprint — see "Footprint / gotchas"). Listen port 4444.
  #
  # HOST-PREP on OVH-1 BEFORE first deploy:
  #   sudo mkdir -p /data/agno/volumes/contextforge
  #   sudo chown -R 1000:1000 /data/agno/volumes/contextforge   # SQLite db + state
  # ---------------------------------------------------------------------------
  contextforge:
    image: ghcr.io/ibm/mcp-context-forge:1.0.3   # pin; do NOT use :latest
    platform: linux/amd64
    container_name: contextforge
    restart: unless-stopped
    ports:
      # Tailnet-only (BIND_IP=ovh1 tailnet IP). Public exposure happens ONLY via the
      # Traefik DOMAIN PHASE labels below — never bind 0.0.0.0, never publish elsewhere.
      - "${BIND_IP:-127.0.0.1}:4444:4444"   # unified MCP + admin API/UI surface
    env_file:
      - path: .env
        required: false
    environment:
      HOST: "0.0.0.0"            # inside the container; the host bind is gated by BIND_IP above
      PORT: "4444"
      # --- persistence: SQLite on the bind mount (no external DB) ---
      DATABASE_URL: "sqlite:////data/mcp.db"
      CACHE_TYPE: "database"     # use the DB for cache/sessions — no Redis dependency
      # --- auth / admin ---
      AUTH_REQUIRED: "true"
      JWT_SECRET_KEY: ${CF_JWT_SECRET_KEY:?set CF_JWT_SECRET_KEY}            # openssl rand -hex 32
      AUTH_ENCRYPTION_SECRET: ${CF_AUTH_ENCRYPTION_SECRET:?set CF_AUTH_ENCRYPTION_SECRET}  # encrypts stored peer creds
      BASIC_AUTH_USER: ${CF_BASIC_AUTH_USER:-admin}
      BASIC_AUTH_PASSWORD: ${CF_BASIC_AUTH_PASSWORD:?set CF_BASIC_AUTH_PASSWORD}
      PLATFORM_ADMIN_EMAIL: ${CF_ADMIN_EMAIL:-admin@mitechconsult.com}
      PLATFORM_ADMIN_PASSWORD: ${CF_ADMIN_PASSWORD:?set CF_ADMIN_PASSWORD}
      PLATFORM_ADMIN_FULL_NAME: "Platform Admin"
      MCPGATEWAY_UI_ENABLED: "true"          # admin dashboard (only reachable via tailnet/proxy)
      MCPGATEWAY_ADMIN_API_ENABLED: "true"   # admin REST API (POST /gateways, /servers)
      SECURE_COOKIES: "false"                # HTTP on the tailnet; flip true once behind TLS proxy
      # --- keep the worker count low: OVH-1 is a tight 7.6GB box ---
      GUNICORN_WORKERS: "1"                   # 1–2 max; each worker is a full python process
    volumes:
      # SQLite db + gateway state on a host bind (owner backs up via host dirs).
      - /data/agno/volumes/contextforge:/data
    healthcheck:
      # /health is unauthenticated and returns 200 when the gateway is up.
      test: ["CMD-SHELL", "python3 -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4444/health').status==200 else 1)\""]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 40s
    networks:
      - agentos
    extra_hosts:
      - "host.docker.internal:host-gateway"
    # DOMAIN PHASE — the ONE MCP-layer service that gets a public face.
    # Private name now (mcp.int.*), gated public twin (mcp.*) when opened.
    # Re-enable + set MCP_DOMAIN / MCP_INT_DOMAIN to expose:
    # labels:
    #   - traefik.enable=true
    #   # private internal name
    #   - traefik.http.routers.contextforge-int.rule=Host(`${MCP_INT_DOMAIN}`)
    #   - traefik.http.routers.contextforge-int.entryPoints=https
    #   - traefik.http.routers.contextforge-int.tls=true
    #   - traefik.http.routers.contextforge-int.tls.certresolver=letsencrypt
    #   - traefik.http.routers.contextforge-int.service=contextforge
    #   # gated public twin (add a forwardauth/IP-allowlist middleware before opening)
    #   - traefik.http.routers.contextforge-pub.rule=Host(`${MCP_DOMAIN}`)
    #   - traefik.http.routers.contextforge-pub.entryPoints=https
    #   - traefik.http.routers.contextforge-pub.tls=true
    #   - traefik.http.routers.contextforge-pub.tls.certresolver=letsencrypt
    #   - traefik.http.routers.contextforge-pub.service=contextforge
    #   # - traefik.http.routers.contextforge-pub.middlewares=mcp-gate@file
    #   - traefik.http.services.contextforge.loadbalancer.server.port=4444
```

**No sidecar DB/Redis service block is required for this deployment.** SQLite-on-bind-mount +
`CACHE_TYPE=database` covers a single-node gateway. (If you later scale to multiple replicas or
want federation-grade caching, add Postgres + Redis service blocks and switch `DATABASE_URL` to
`postgresql+psycopg://…` and `CACHE_TYPE=redis` / `REDIS_URL` — see gotchas.)

---

## b) Registering graphiti-mcp (DATA tier) behind the gateway

graphiti-mcp (`zepai/knowledge-graph-mcp`) publishes container port `8000` as host `8071`,
tailnet-bound, speaking **SSE / streamable-http**. Over salem it is reachable at
`http://10.1.2.101:8071`. ContextForge introspects the peer on registration and imports its
tools/resources/prompts into the central registry; we then optionally bundle them into a named
**virtual server** that gives clients one clean MCP endpoint.

This is a **bootstrap step run once after the gateway is up** (from any host on the tailnet, or via
`docker exec contextforge …`). Nothing here goes in compose.

### Step 1 — mint an admin bearer/JWT (must match `JWT_SECRET_KEY`)

```bash
export CF_BEARER=$(docker exec contextforge python3 -m mcpgateway.utils.create_jwt_token \
  --username "$CF_ADMIN_EMAIL" \
  --exp 10080 \
  --secret "$CF_JWT_SECRET_KEY")     # --exp in minutes; 10080 = 7 days
```

### Step 2 — register graphiti as a federated peer Gateway (`POST /gateways`)

graphiti speaks SSE; the SSE peer URL is the `/sse` path. (If you front it as streamable-http the
peer URL ends `/mcp` and `transport` is `STREAMABLEHTTP`.)

```bash
curl -s -X POST http://${BIND_IP}:4444/gateways \
  -H "Authorization: Bearer $CF_BEARER" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "graphiti",
        "description": "Temporal knowledge-graph memory (Graphiti + Neo4j), DATA tier OVH-3",
        "url": "'"${GRAPHITI_MCP_URL:-http://10.1.2.101:8071}"'/sse",
        "transport": "SSE"
      }'
```

`transport` enum (UPPERCASE): `SSE` | `STREAMABLEHTTP` | `STDIO` | `WEBSOCKET`.

### Step 3 (optional but recommended) — bundle into a virtual server (`POST /servers`)

After Step 2, list the imported tool IDs (`GET /tools` with the bearer) and bundle the graphiti
ones into a single named virtual server so clients get a stable, curated endpoint:

```bash
curl -s -X POST http://${BIND_IP}:4444/servers \
  -H "Authorization: Bearer $CF_BEARER" \
  -H "Content-Type: application/json" \
  -d '{"server":{
        "name":"graphiti",
        "description":"Graphiti memory tools, fronted by ContextForge",
        "associated_tools":["<TOOL_ID_1>","<TOOL_ID_2>"]
      }}'
# → returns the virtual server UUID used in the client endpoint below.
```

> If you skip Step 3, the imported graphiti tools are still callable through the gateway; a virtual
> server just gives a clean per-bundle endpoint and lets you curate/scope which tools are exposed.

---

## c) Required env / secrets (`${VARS}`)

Add to `.env` (and the Coolify app env). All `CF_*` so they don't collide with existing vars:

```dotenv
# --- ContextForge gateway (EXEC tier, OVH-1) ---
CF_JWT_SECRET_KEY=          # openssl rand -hex 32  (signing secret, MUST match token mint)
CF_AUTH_ENCRYPTION_SECRET=  # openssl rand -hex 32  (encrypts stored peer credentials)
CF_BASIC_AUTH_USER=admin
CF_BASIC_AUTH_PASSWORD=     # admin basic-auth password (change from default)
CF_ADMIN_EMAIL=admin@mitechconsult.com
CF_ADMIN_PASSWORD=          # platform admin password (change from default)

# Upstream MCP peer (DATA tier graphiti, salem address). Brief: OVH-3 10.1.2.101.
GRAPHITI_MCP_URL=http://10.1.2.101:8071

# Already present in the exec env, reused here:
# BIND_IP=100.72.169.40     # ovh1 tailnet IP — the gateway's host port bind

# DOMAIN PHASE (only when Traefik labels are enabled):
# MCP_INT_DOMAIN=mcp.int.mitechconsult.com
# MCP_DOMAIN=mcp.mitechconsult.com

# Only if you later add Postgres/Redis sidecars (NOT needed for SQLite single-node):
# DATABASE_URL=postgresql+psycopg://ai:ai@<host>:5432/mcp
# REDIS_URL=redis://<host>:6379/0
```

Generate the two secrets:

```bash
echo "CF_JWT_SECRET_KEY=$(openssl rand -hex 32)"
echo "CF_AUTH_ENCRYPTION_SECRET=$(openssl rand -hex 32)"
```

---

## d) Pointing Agno (`agentos-api`) at the gateway instead of graphiti directly

Today `agentos-api` would reach graphiti directly. After this change it connects to the **gateway's
unified MCP endpoint** (JWT-gated) and never addresses graphiti's `8071` itself.

**Unified endpoint shape** (streamable-http, per virtual server UUID from step b/3):

```
http://${BIND_IP}:4444/servers/<SERVER_UUID>/mcp
```

(SSE variant: `…/servers/<SERVER_UUID>/sse`. Both require `Authorization: Bearer <JWT>`.)

In Agno, use `MCPTools` / `MultiMCPTools` with the streamable-http transport and the bearer header:

```python
from agno.tools.mcp import MCPTools

mcp = MCPTools(
    url=f"{os.environ['CF_GATEWAY_URL']}/servers/{os.environ['CF_GRAPHITI_SERVER_ID']}/mcp",
    transport="streamable-http",
    # ContextForge auths clients with a bearer JWT in the Authorization header:
    headers={"Authorization": f"Bearer {os.environ['CF_GATEWAY_TOKEN']}"},
)
```

Add to `agentos-api`'s `environment:` in `compose.exec.yaml` (gateway is on the same box/network):

```yaml
      # Reach MCP servers ONLY through ContextForge, never graphiti's 8071 directly.
      CF_GATEWAY_URL: http://contextforge:4444          # internal docker network name
      CF_GRAPHITI_SERVER_ID: ${CF_GRAPHITI_SERVER_ID:-} # virtual server UUID from POST /servers
      CF_GATEWAY_TOKEN: ${CF_GATEWAY_TOKEN:-}           # long-lived client JWT (mint w/ create_jwt_token)
```

> Mint a dedicated long-lived **client** token for Agno (same `create_jwt_token` command, longer
> `--exp` or a scoped service identity) and store it as `CF_GATEWAY_TOKEN`. Internal traffic uses
> the docker network name `contextforge:4444`; external clients use `mcp.int/mcp.*` once the
> DOMAIN PHASE Traefik labels are enabled.

---

## e) Footprint estimate + gotchas / open questions

### RAM footprint (OVH-1 is a tight 7.6 GB box)

- ContextForge is FastAPI + Uvicorn/Gunicorn (ASGI). RAM scales ~linearly with worker count —
  each worker is a separate Python process.
- **No official IBM RAM benchmark is published.** Inferred: a **single-worker** instance idles
  around **~150–250 MB**; the *default* multi-worker Gunicorn config (`cpu*2+1`) could climb to
  several hundred MB–1 GB+. The FAQ notes it runs on a Raspberry Pi if you reduce workers.
- **Mitigation already baked in above:** `GUNICORN_WORKERS=1` and SQLite (no extra Postgres/Redis
  containers). Budget **~256–400 MB** for the gateway on OVH-1. If you add Postgres+Redis sidecars
  later, add roughly **+300–500 MB**.

### Gotchas / open questions

1. **Does it need its own Postgres/Redis?** — *No, not for this single-node footprint.* SQLite on
   a bind mount + `CACHE_TYPE=database` is sufficient and is what's specified here. Redis/Postgres
   only become necessary for multi-replica HA or heavy federation caching. **Open decision:** is a
   single gateway instance acceptable for the EXEC tier, or do we want HA later? (If HA → Postgres
   is mandatory; SQLite won't share across replicas.)
2. **Version pin:** `1.0.3` is the current GA tag on `ghcr.io/ibm/mcp-context-forge` (GA line:
   1.0.0 → 1.0.3). The `main` README still shows `1.0.0-RC-3` in some examples — **ignore that,
   pin 1.0.3**, and re-verify the latest patch tag at deploy time.
3. **Listen port:** `4444` is the documented Gunicorn default (some Uvicorn dev examples show
   `8000`). We set `PORT=4444` explicitly to remove ambiguity. Note the house rule "NEVER publish
   host 8080" is respected — we publish `4444` only, tailnet-bound.
4. **`JWT_SECRET_KEY` must match the token-mint `--secret`** or every API/MCP call 401s. Keep the
   value identical between the compose env and any `create_jwt_token` invocation.
5. **`transport` casing:** prefer UPPERCASE (`SSE`, `STREAMABLEHTTP`). Lowercase is tolerated in
   some examples but UPPERCASE is the documented enum.
6. **graphiti peer URL path:** SSE peer = `…:8071/sse`; if graphiti is fronted as streamable-http
   instead, use `…:8071/mcp` and `transport: STREAMABLEHTTP`. Confirm which path
   `zepai/knowledge-graph-mcp` actually serves before registering (it advertises both SSE and
   streamable-http on `8000`).
7. **OVH-2 vs OVH-3 naming** for the data/graphiti box (see §0 note) — reconcile before deploy. The
   `${GRAPHITI_MCP_URL}` indirection means only the env value changes, not the registration call.
8. **Registration is stateful, not declarative.** Peer Gateways/virtual servers live in the
   gateway's DB, created via the bootstrap API calls in §b — they are NOT in compose. Persist them
   by keeping the SQLite db on the bind mount, and script the bootstrap (idempotent re-`POST`s) so a
   fresh volume can be re-seeded. **Open task:** write a small `scripts/contextforge-bootstrap.sh`.
9. **Healthcheck** uses `/health` (unauthenticated). Confirm that path on `1.0.3` (some builds
   expose `/healthz`); adjust the healthcheck test if it 404s.
10. **Public twin gating:** the `mcp.*` public router MUST sit behind an auth/IP-allowlist
    middleware before it's enabled — the gateway's own JWT is the only guard otherwise. Left
    commented (`mcp-gate@file`) as a TODO in the Traefik scaffold.

---

### Source references

- IBM/mcp-context-forge — README, Releases, ghcr.io package
- ibm.github.io/mcp-context-forge — Quick Start, API Usage Guide, Architecture, FAQ
- repo `docker-compose.yml` (Postgres+Redis+replicas reference), perf-baseline issue #432
- local: `compose.exec.yaml` (conventions), `compose.data.yaml` (graphiti `8071:8000`, ADR-0025 routing note)

> _Byline: Claude Code · Opus 4.8 · 2026-06-14_
