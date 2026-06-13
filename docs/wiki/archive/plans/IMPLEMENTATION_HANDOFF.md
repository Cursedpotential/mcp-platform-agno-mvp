# AI DIAL Stack — Implementation Handoff

> This document lists every identified gap, required refactor, and implementation task.
> Priority: P0 (blocks everything) → P1 (blocks next phase) → P2 (quality/correctness) → P3 (nice-to-have)

## Critical Rules (Read First)
- `MCP_Tool_Platform` is READ-ONLY. Extract patterns only.
- No local LLM hosting (limited GPU)
- No file deletions
- Every new dependency gets a skill doc in `docs/wiki/skills/`

---

## P0: Transport Mismatch (Blocks All MCP Communication)

**Problem**: All 3 MCP servers (TS, Py, JS) use `StdioServerTransport` but DIAL Core's `config.json` references HTTP endpoints (`http://ts-mcp-server:8081/mcp/chat/completions`). Stdio transport can't serve HTTP requests.

**Fix Options** (pick one):
1. Add HTTP adapter layer to each MCP server (recommended — keeps MCP purity, adds thin HTTP wrapper)
2. Switch MCP servers to use HTTP transport directly (simpler but loses stdio composability)
3. Use an MCP-to-HTTP bridge sidecar

**Files to modify**:
- `ts-mcp-server/src/index.ts` — lines that create `StdioServerTransport`
- `py-mcp-server/src/server.py` — `mcp.run()` call at bottom
- `js-mcp-server/src/index.js` — `StdioServerTransport` usage
- `core/config.json` — application endpoint URLs (may need adjustment depending on approach)

**Acceptance**: Each MCP server responds to HTTP requests from DIAL Core and tools are discoverable.

---

## P0: TS MCP Server — Registry Pattern Refactor

**Problem**: `ts-mcp-server/src/index.ts` uses a massive if/else-if chain (18+ branches) for tool dispatch. This is unmaintainable and error-prone.

**Fix**: Refactor to a registry pattern:
```typescript
const toolRegistry = new Map<string, ToolHandler>();
toolRegistry.set('parse_sms_xml', handleParseSmsXml);
toolRegistry.set('parse_facebook_export', handleParseFacebook);
// ... etc

// Dispatch
const handler = toolRegistry.get(toolName);
if (!handler) throw new Error(`Unknown tool: ${toolName}`);
return handler(args);
```

**Files**: `ts-mcp-server/src/index.ts`
**Acceptance**: All 18 tools work identically but dispatch via registry map.

---

## P0: TS MCP Server — Lazy Singletons

**Problem**: `DuckDbVault` and `PostgresWriter` are instantiated fresh on every tool call. This wastes connections and may cause concurrency issues.

**Fix**: Implement lazy singleton pattern (Python server already does this correctly — use as reference):
```typescript
let _duckdb: DuckDbVault | null = null;
async function getDuckDb(): Promise<DuckDbVault> {
  if (!_duckdb) {
    _duckdb = new DuckDbVault();
    await _duckdb.initialize();
  }
  return _duckdb;
}
```

**Files**: `ts-mcp-server/src/index.ts`
**Reference**: `py-mcp-server/src/server.py` (lines with `_get_neo4j`, `_get_lancedb`, etc.)
**Acceptance**: Only one instance of each service exists per server lifetime.

---

## P1: Remove Ollama from Docker Compose

**Problem**: `docker-compose.yml` includes an `ollama` service, but Rule 3 prohibits local LLM hosting.

**Fix**: Remove or comment out the ollama service block. Remove `ollama-local` model from `core/config.json`.

**Files**: `docker-compose.yml`, `core/config.json`
**Acceptance**: No local LLM containers. All inference goes through OpenRouter or other external APIs.

---

## P1: Add Keycloak to Docker Compose

**Problem**: `settings/settings.json` references Keycloak but no Keycloak container exists in `docker-compose.yml`.

**Fix**: Add Keycloak service:
```yaml
keycloak:
  image: quay.io/keycloak/keycloak:24.0
  command: start-dev
  environment:
    KEYCLOAK_ADMIN: admin
    KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
    KC_HTTP_PORT: 8080
  ports:
    - "8180:8080"
  volumes:
    - keycloak_data:/opt/keycloak/data
  networks:
    - dial-network
```

Create realm `dial` with roles: `admin`, `default`, `readonly`.

**Files**: `docker-compose.yml`
**Acceptance**: Keycloak starts, realm exists, DIAL Core validates JWTs.

---

## P1: Add WunderGraph Cosmo to Docker Compose

**Problem**: Architecture specifies WunderGraph Cosmo for GraphQL federation but it's not in docker-compose.

**Fix**: Add WunderGraph Cosmo containers (router + controlplane) to docker-compose. Create initial subgraph schemas for PostgreSQL and Neo4j.

**Files**: `docker-compose.yml`, new `wundergraph/` directory for schema files
**Acceptance**: WunderGraph router serves federated GraphQL on port 4000.

---

## P1: JS MCP Server — Decide Keep or Remove

**Problem**: `js-mcp-server/src/index.js` is an empty placeholder with only a `ping_js_server` tool. It consumes container resources for nothing.

**Options**:
1. **Remove it** from docker-compose until actually needed (recommended)
2. **Implement** Docling and Pandoc wrapping now if there's a near-term need
3. **Merge** any planned JS tools into the TS server instead

**Files**: `docker-compose.yml`, `core/config.json`
**Acceptance**: Either the JS server has real tools or it's removed from the running stack.

---

## P2: postgres_raw_query Security Risk

**Problem**: The `postgres_raw_query` tool in TS MCP server accepts arbitrary SQL. For a forensic evidence platform, this is a significant risk — it could allow accidental or intentional evidence tampering.

**Fix Options**:
1. Remove it entirely (safest)
2. Restrict to SELECT-only queries (validate query doesn't contain INSERT/UPDATE/DELETE/DROP/ALTER)
3. Add a role-based guard (only admin role can use it)
4. Rename to `postgres_admin_query` and add prominent warnings

**Files**: `ts-mcp-server/src/index.ts`
**Acceptance**: No unauthenticated arbitrary SQL execution against evidence database.

---

## P2: R2 Storage Integration

**Problem**: Architecture docs reference Cloudflare R2 for blob/file storage but no tools connect to it.

**Fix**: Create R2 storage tool in TS MCP server for archive uploads/downloads. Not blocking until Phase H.

**Files**: New `ts-mcp-server/src/tools/R2Storage.ts`
**Acceptance**: Files can be uploaded to and retrieved from R2 buckets.

---

## P2: DuckDB Query/Read Tool Missing

**Problem**: ROADMAP Phase A lists "Create DuckDB query/read tool for retrieval" as incomplete. Currently DuckDB is write-only (vault operations) with no read/query interface.

**Fix**: Add `duckdb_query` tool to TS MCP server that supports parameterized SELECT queries against the DuckDB vault.

**Files**: `ts-mcp-server/src/index.ts` or new tool file
**Acceptance**: Can query DuckDB vault for ingestion status, hash lookups, dedup checks.

---

## P2: DuckDB → PostgreSQL Pipeline

**Problem**: ROADMAP Phase A lists "Wire DuckDB → PostgreSQL ingestion pipeline as composable tools" as incomplete.

**Fix**: Create a tool that moves validated records from DuckDB holding tank to PostgreSQL evidence tables. Should be atomic and maintain chain of custody (hash verification on transfer).

**Files**: New tool in TS MCP server
**Acceptance**: Records flow from DuckDB to PG with hash verification.

---

## P2: Health Check Endpoints

**Problem**: No health checks for storage connections. Hard to diagnose what's down.

**Fix**: Add health check tools to each MCP server:
- TS: `health_check` → tests DuckDB + PostgreSQL connections
- Py: `health_check` → tests Neo4j + LanceDB connections
- JS: `health_check` → tests any configured services

**Files**: All three MCP server index files
**Acceptance**: Each server can report connection status for its storage tiers.

---

## P3: End-to-End Tests for Phase C

**Problem**: Semantica tools exist but have no end-to-end tests with real evidence data.

**Tests needed**:
1. Entity extraction on real SMS/Facebook evidence
2. Temporal graph building from extracted entities
3. Contradiction detection pipeline (requires both Pass 1 and Pass 2 data)

**Acceptance**: Tests pass with sample evidence from `MCP_Tool_Platform/Evidence_Analysis/` (read-only reference).

---

## P3: Encryption Config Hardcoded

**Problem**: `settings/settings.json` has `"secret": "salt"` and `"key": "password"` — clearly placeholder values.

**Fix**: Move to environment variables: `${DIAL_ENCRYPTION_SECRET}` and `${DIAL_ENCRYPTION_KEY}`. Add to `.env.example`.

**Files**: `settings/settings.json`, `.env.example`

---

## Implementation Order

1. **Transport mismatch** (P0) — nothing works without this
2. **TS registry refactor + lazy singletons** (P0) — code quality gate
3. **Remove Ollama** (P1) — contradicts rules
4. **Add Keycloak container** (P1) — auth infrastructure
5. **JS server decision** (P1) — reduce wasted resources
6. **DuckDB read tool + DuckDB→PG pipeline** (P2) — completes Phase A
7. **Health checks** (P2) — operational readiness
8. **postgres_raw_query security** (P2) — forensic integrity
9. **WunderGraph Cosmo** (P1) — federation layer (can be parallel with above)
10. **R2 integration** (P2) — Phase H dependency
11. **Encryption config** (P3) — pre-deployment
12. **E2E tests** (P3) — validation

---

## Reference Files

| What | Where |
|------|-------|
| Architecture | `docs/ARCHITECTURE.md` |
| Roadmap | `docs/ROADMAP.md` |
| Agent Rules | `CLAUDE.md` |
| DIAL Core Config | `core/config.json` |
| DIAL Settings | `settings/settings.json` |
| Docker Compose | `docker-compose.yml` |
| TS MCP Server | `ts-mcp-server/src/index.ts` |
| Py MCP Server | `py-mcp-server/src/server.py` |
| JS MCP Server | `js-mcp-server/src/index.js` |
| Legacy Reference | `../MCP_Tool_Platform/` (READ-ONLY) |
| Wiki/Skills | `docs/wiki/` |
