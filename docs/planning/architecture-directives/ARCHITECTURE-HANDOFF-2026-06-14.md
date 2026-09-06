# Architecture Brainstorming Handoff — 2026-06-14
> _Byline: Claude Code · Opus 4.8 · 2026-06-14_
> Written to survive a context clear. Resume here + the memory resume-pointer [[platform-redeploy-plan]].
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## 0. WHERE WE ARE (one line)
Deploy of the Agno platform is **paused right before Coolify app-creation** because a new
**target architecture** (Portkey edge → ContextForge → Windmill → SurrealDB-central + Milvus/Neo4j)
arrived and we're adapting to it first. Nothing is deployed in the old shape yet, so no rework.

---

## 1. DONE THIS SESSION (verified)
- **OVH-3 = new data box ("ovh3-data")** provisioned: public `147.135.79.183`, tailnet `100.119.96.29`,
  salem private `10.1.2.101`, **100 GB volume → /data** (ext4), Docker 29.5.3 + Compose v5.1.4,
  Tailscale joined. **Registered + VALIDATED in Coolify** (server uuid `nt9v3z24ts9fqr3pn703llv5`).
  - Fix that unblocked Coolify validation: **disabled Tailscale SSH** (`tailscale set --ssh=false`) — `--ssh`
    hijacks port 22 over the tailnet and broke Coolify's root SSH (instant exit 255, no packet hit sshd).
  - Also stripped the OVH cloud-image **forced-command guard** from `/root/.ssh/authorized_keys` (backup `.bak`).
- **Salem private link ovh1↔ovh3 LIVE** (~1 ms). ovh1's `ens7` was down; fixed via `/etc/netplan/60-salem-private.yaml`
  (dhcp4 + use-routes:false) on both boxes.
- **Composes rewired** for the new topology (committed+pushed): data→OVH-3, exec→OVH-1; Milvus **relocated**
  to the data tier; SurrealDB + ContextForge + agent-ui added; cross-box via `${OVH1_HOST}/${OVH3_HOST}` (default
  tailnet, salem documented as swap); BIND_IP per box; no host 8080; MCPs internal-only (ContextForge-gated).
- **SurrealDB wired as Agno operational store**: `db/session.py get_agno_db()` → `SurrealDb` for
  session/memory/metrics/eval/knowledge-content/traces/spans; `get_postgres_db()` kept for Knowledge contents +
  evidence; Milvus vectors untouched. `surrealdb>=1.0.4,<2` added.
- **agent-ui** (native Agno chat) added to exec stack (docker/agent-ui/Dockerfile).
- **Host-prep DONE**: OVH-3 dirs+chown (pgdata 999, neo4j 7474, milvus 999, surrealdb 0) + staged
  sql/graphiti/milvus configs; OVH-1 contextforge dir.
- **DNS scheme designed** (.planning/build/create-dns.mjs, dry-run): `<svc>.int.mitechconsult.com` → tailnet IP
  (private); gated public twins `api/chat/mcp.mitechconsult.com`. milvus/attu records still → OVH-2, must repoint.
- **Secrets**: Unstructured API key + endpoint saved to `Secrets/api-keys.md`; `docs/INFRASTRUCTURE.md` sanitized
  → `docs/INFRASTRUCTURE.template.md` (committed), real one gitignored.
- **Windmill LIVE on OVH-2** (ADR-0028, replaces FileFlows) — per memory [[windmill-casebible-deployment]].

## 2. REPO / IDS (don't re-derive)
- Repo: `github.com/Cursedpotential/mcp-platform-agno-mvp` (PRIVATE), branch `main` @ **`ddf020e`**. Old unrelated
  history archived at branch `archive/v0.1.1-pre-reset`.
- Coolify: control plane tailnet API `http://100.98.98.38:8000/api/v1`; token in `~/.claude.json` →
  `mcpServers.coolify.headers.Authorization` (`2|TGaq…`). **CLI at `C:/Users/matts/.agents/skills/coolify/coolify-cli.cjs`
  is BUGGY on create/update ("Validation failed") — use raw REST (`curl`) for writes.**
  Servers: ovh1-agno `fmuao9enq3nxk8qw5hqjzzce`, ovh3-data `nt9v3z24ts9fqr3pn703llv5`, ovh2-worker `cn89l8801u8gsginw1rxq5qt` (LEAVING — now runs Windmill).
  Project `agno-platform` **NOT created yet** (a separate empty project "Agni" `xygcwltqe3z18x6dbcw9wlbr` exists — leave alone).
  GitHub App `cursedpotential` `r4mhpblr8cnxk3481r07xxz0` (private-repo source). ovh-fleet SSH key uuid `ysezpww898o2v6dxqvgucc6p`.
- Cloudflare: zone `mitechconsult.com` id `d543c96e4bb7fad63e5f1925dce79640`; API via the cloudflare MCP plugin
  (OAuth'd) or token at `C:\Users\matts\.secrets\cloudflare.env`.
- Fleet: OVH-1 exec (tailnet 100.72.169.40 / salem 10.1.1.122 / public 40.160.5.19), OVH-3 data (above),
  OVH-2 vps-ff65b4ab (100.91.190.107) = user's Windmill/other, Ionos control 100.98.98.38.
- Build artifacts: `.planning/build/{surrealdb-integration,contextforge-integration,dns-and-domains,topology-rewire-notes}.md`, `create-dns.mjs`.

## 3. THE NEW TARGET ARCHITECTURE (owner blueprint 2026-06-14 — "guide not bible, adapt")
Tiered boundary + clean division of concerns:

```
3 surfaces (internal chat / admin UI / external) → [ PORTKEY edge ] → [ ContextForge (MCP router) ] → [ Windmill jobs ] → DBs
                                                          │ model routing+auth                │ schema/creds map            │ TS(Zod)+Py(Pydantic)
                                                          ▼                                                                  ▼
                                                   providers (NVIDIA/Ollama/…)                            [ SurrealDB CENTRAL ] + Milvus + Neo4j
```

**Division of concerns (adopt):**
1. **Portkey** = model routing + client auth ONLY (OpenAI-compatible edge; loadbalance; built-in MCP gateway → ContextForge). Never touches DBs.
2. **ContextForge** = unified MCP interface + schema mapping + credential handling ONLY. Routes tool calls to swappable Windmill scripts. No app logic, no heavy files.
3. **Windmill + Agno** = execute scripts/workflows. Zod (TS) / Pydantic (Agno) enforce schemas. Tools = Windmill jobs.
4. **SurrealDB = central hub.** Native multi-model records + **pgwire (:5432)** for legacy PG traffic + **FerretDB (:27017)** for Mongo→pgwire. Native GIS (geometry + MTREE) replaces PostGIS.
5. **Milvus (:19530)** vectors / RAG and **Neo4j (:7687)** graph = auxiliary, queried directly by runtimes.

**Ports (blueprint):** SurrealDB native 8000 (WS/HTTP), SurrealDB-pgwire 5432, FerretDB 27017, Milvus 19530, Neo4j 7687, ContextForge 8081 (our earlier draft used 4444 — reconcile), Portkey edge (OpenAI-compat).

## 4. OPEN DECISIONS / FORKS (resolve, then adapt composes)
1. **Gateway: RESOLVED (owner 2026-06-14) — Portkey REPLACES LiteLLM. LiteLLM goes away entirely** (not kept as a target). The `gateway` container's LiteLLM role is removed; Portkey becomes the OpenAI-compatible edge. (OpenCode sandbox piece, if still wanted, is separate from LiteLLM — confirm its fate.)
2. **Central DB (the big one) — OWNER DIRECTION 2026-06-14:** consolidate on **SurrealDB-central**. SurrealDB native GIS replaces PostGIS. **Integrate DuckDB via pgwire** — i.e. DuckDB's `postgres` ATTACH extension reads SurrealDB-pgwire as a source, so we keep DuckDB analytics WITHOUT pg_duckdb. ⇒ **Drop the dedicated pg_duckdb Postgres (`agentos-db`)** if validated.
   - **MUST VALIDATE FIRST:** SurrealDB pgwire is young — confirm it speaks enough Postgres for (a) DuckDB's postgres_scanner ATTACH and (b) any legacy PG clients. If it can't, fallback = keep a thin Postgres or coexist. Don't drop agentos-db until proven.
   - Knowledge contents currently on Postgres → would move to SurrealDB (or stay until pgwire proven).
   - **GUARANTEED FALLBACK (owner 2026-06-14):** if dropping Postgres is too risky, **keep Postgres underneath and put SurrealDB ON TOP** as the unifying multi-model layer — SurrealDB absorbs/consumes all the data and presents one clean centralized "package," Postgres stays as the durable store beneath. So there's a floor: SurrealDB becomes the centralizer either way; the only open question is Postgres-replaced-beside vs Postgres-survives-underneath. (Validate the exact mechanism: SurrealDB Postgres storage-backend vs ingest/sync vs pgwire-front — pick per spike results.)
   - **Portkey edge is now a hard guarantee (locked); the data-layer choice is the only thing pending the spike.**
3. **Tools → Windmill jobs** (ContextForge routes to Windmill `/api/w/main/jobs/run/f/<script>`). **Semantica (SBV) stays VIP / standalone — do NOT dissolve it into generic Windmill tooling.**
4. ContextForge port 8081 vs 4444; Windmill lives on OVH-2 (off-salem) — ContextForge→Windmill crosses tailnet; confirm reachability + which box ContextForge sits on (exec OVH-1).

> **⛔ UPDATE 2026-06-14 — §4.2 / §5.2 RESOLVED. DO NOT run the pgwire spike.**
> Validated against SurrealDB primary sources: pgwire is **not GA** ("In development", Q2 2026)
> AND carries **SurrealQL, not Postgres SQL** (ANSI SQL also in-dev) — so DuckDB ATTACH /
> FerretDB / legacy PG clients **cannot** work over it, now or at GA. The "drop Postgres" path
> is dead; the §4.2 **guaranteed fallback is now the only path** (keep Postgres + pg_duckdb;
> SurrealDB via native WS/RPC = consolidation/analysis projection; Postgres = live federation
> hub via FDWs). Full verdict + locked decisions + ID scheme + image/types work:
> **[[architecture-validation-2026-06-14]]**. Portkey-at-edge (§4.1) still stands.

## 5. NEXT ACTIONS (post-clear)
1. **Architect-agent reconciliation pass:** feed this handoff + the current composes + the 4 build artifacts → produce a revised target (composes for Portkey/SurrealDB-central/Windmill-tools), the DuckDB-over-pgwire validation plan, and a crisp decision list. (Keeps main context clean.)
2. ~~**Validate SurrealDB-pgwire ↔ DuckDB ATTACH** (spike) before dropping pg_duckdb.~~ **DONE 2026-06-14 — answered NO, see banner above + [[architecture-validation-2026-06-14]]. Spike cancelled.**
3. Resolve forks §4 with owner.
4. Adapt composes → create Coolify `agno-platform` project + apps (raw REST) → set env from secrets → deploy data→exec.
5. Post-deploy: run create-dns.mjs --apply, Milvus re-index, register graphiti behind ContextForge, repoint milvus/attu DNS, then OVH-2 fully free.

## 6. CARVE-OUTS / STANDING RULES (don't lose)
- **Semantica (SBV) = VIP**, stays standalone.
- Mongo→**FerretDB**, Redis→**Dragonfly** everywhere ([[db-substitution-rules]]).
- Bind-mount volumes only; BIND_IP=tailnet IP; **host 8080 stays free**; MCPs never directly exposed (ContextForge-gated); Tailscale `--ssh` OFF on Coolify-managed nodes; deploy via Coolify raw REST.
- Personal/internal use → license fine-print is a non-issue ([[project-usage-scope-personal]]); CPU-only, no GPU ([[hardware-cpu-only-model-constraint]]).
