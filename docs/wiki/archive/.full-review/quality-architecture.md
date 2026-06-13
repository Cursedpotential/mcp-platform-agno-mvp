# Phase 1: Code Quality & Architecture Review

## Code Quality Findings

### Critical (3)

1. **SQL injection via `postgres_raw_query`** — `ts-mcp-server/src/tools/PostgresWriter.ts:45-57` exposes `client.unsafe(sql)` directly. Any caller can execute DROP TABLE, DELETE, etc. on the forensic evidence database. Chain-of-custody violation.

2. **Arbitrary table injection via `postgres_write_record`** — `PostgresWriter.ts:24-39` allows writing to ANY table including system/keycloak/audit tables. No allowlist enforced.

3. **No automated parse-to-store pipeline** — `ts-mcp-server/src/index.ts:278-332`. Parsers return JSON, vault accepts file-level records, PostgreSQL accepts arbitrary data. Nothing connects them. The stack CANNOT process a message end-to-end without manual LLM orchestration — a forensic chain-of-custody violation for deterministic processing.

### High (7)

4. **Neo4j missing from docker-compose.yml** — All 8+ Semantica/Neo4j tools in py-mcp-server will fail with connection errors. `server.py:26-29` defaults to `bolt://neo4j:7687` but no service exists.

5. **WhatsApp parser falsely marked "Built"** — `docs/TOOL_CATALOG.md:16` lists it as Built. No WhatsApp code exists anywhere in ts-mcp-server.

6. **DuckDB hashes file PATH not content** — `DuckDbService.ts:205-207`. When only binaryPath is provided, SHA-256 is computed on the path string. Moving the file changes the hash, breaking chain of custody.

7. **No authentication on MCP server endpoints** — `ts-mcp-server/src/index.ts:399-407`. Both `/mcp` and `/health` have zero auth, zero rate limiting. Anyone with network access can call `postgres_raw_query`.

8. **Hardcoded secrets throughout** — `docker-compose.yml:22-24,62-63,175-181`. `NEXTAUTH_SECRET: "secret"`, `DIAL_API_KEY: "dial_api_key"`, `INFLUXDB_ADMIN_TOKEN=my-super-secret-auth-token`, default passwords everywhere.

9. **Parser output as massive JSON will exceed MCP limits** — `index.ts:281-282`. `parse_sms_xml` returns `JSON.stringify(messages)` for multi-GB XML files. Will OOM or exceed message size limits.

10. **Eager NER loading crashes all Python tools** — `server.py:611-614`. `_get_ner().extract` called at import time defeats lazy initialization. If spaCy model missing, all 30+ Python tools become unavailable.

### Medium (14)

11. **Tool name mismatch: docs vs code** — Catalog says `sms_xml_parser`, code registers `parse_sms_xml`. Agents will call wrong names.
12. **JS MCP Server is scaffolding only** — Only has `ping_js_server`. All documented tools are fiction. But config.json references it.
13. **Standard response format documented but never implemented** — `TOOL_CATALOG.md:169-182` describes `{success, data, metadata}` format. No tool uses it.
14. **Placeholder tools silently pass in workflows** — `user_detection.py` returns zeros. Workflow reports zero severity for all behavioral patterns regardless of input.
15. **voice_tools.py doesn't actually use faststylometry** — Claims Burrows' Delta but uses hand-rolled basic statistics. Library imported but never called.
16. **HAP scoring reaches into model internals** — `dpk_tools.py:155-170` accesses `hap.tokenizer` and `hap.model` bypassing public API.
17. **Language ID downloads 131MB model at runtime** — `dpk_tools.py:88-95`. No hash verification, no timeout, will fail air-gapped.
18. **Workflow engine uses brittle string-prefix dispatch** — `workflow_tools.py:166-185`. `if tool_name.startswith("dpk_")` violates Open/Closed Principle.
19. **Facebook parser loads entire file into memory** — `FacebookExportParser.ts:105`. No streaming like SmsXmlParser. OOM on large exports.
20. **Duplicate PostgreSQL connection pools** — PostgresWriter (max 10) and ReviewQueue (max 5) create separate pools to same DB.
21. **PII data exposed in redaction response** — `dpk_tools.py:249-260`. Original PII text returned alongside redacted version.
22. **Python tools return errors as successful responses** — `{"error": str(e)}` returned as success. Callers can't distinguish errors.
23. **Global mutable singletons not thread-safe** — All Python lazy singletons use `global _var` without locking.
24. **Workflow config writable at runtime without auth** — `workflow_tools.py:218-360`. Any caller can modify analysis pipeline.

### Low (4)

25. **CLAUDE.md lists WunderGraph/CopilotKit as active** — Neither exists in docker-compose.
26. **Facebook date parsing fallback is a no-op** — `FacebookExportParser.ts:63-81`. Regex matches but retries same `new Date()` call.
27. **dpk_doc_quality is basic heuristics, not DPK** — Only 5 possible scores. Misleadingly named.
28. **No graceful shutdown for DB connections** — `index.ts:414-417`. SIGINT exits without closing DuckDB/PostgreSQL.

---

## Architecture Findings

### Critical (3)

1. **Ingestion pipeline completely disconnected** — The documented flow (parse → DuckDB → PostgreSQL → Semantica → Neo4j → LanceDB) does not exist in code. Each tool is atomic with no orchestration. ROADMAP.md acknowledges this as unchecked task.

2. **Neo4j not in docker-compose** — All graph tools will fail. Impacts 8+ tools across Semantica, timeline queries, and conflict detection.

3. **`postgres_raw_query` is a chain-of-custody violation** — Unrestricted SQL on forensic evidence database. No query logging, no allowlisting, no read-only enforcement.

### High (5)

4. **JS MCP Server is empty** — Only `ping_js_server` tool. But `core/config.json` registers it as a full application. Architecture diagram claims "Text utilities, Format handlers, API adapters."

5. **WunderGraph Cosmo does not exist** — ARCHITECTURE.md dedicates pages to "Dual Retrieval Architecture" as if it's current. It's entirely aspirational (Phase F Planned).

6. **No PostgreSQL init scripts** — `init/postgres/` is mounted but empty. Database starts empty. All write operations will fail with "relation does not exist."

7. **Architecture diagram is ~40% aspirational** — Diagram shows capabilities that don't exist: WhatsApp parser, format detector, JS server tools, WunderGraph, React HITL UI.

8. **Eager NER initialization crashes py-mcp-server** — `server.py:611-614` defeats the lazy pattern used everywhere else.

### Medium (5)

9. **Missing depends_on in docker-compose** — ts-mcp-server depends on PostgreSQL but no `depends_on`. py-mcp-server depends on Neo4j (nonexistent).
10. **Port mapping ambiguity for py-mcp-server** — `8082:8000` mapping but no explicit PORT env var. FastMCP default port behavior unverified.
11. **TS MCP uses 19-case switch dispatch** — ROADMAP acknowledges this tech debt. Python server uses @mcp.tool() decorators — much better.
12. **Workflow engine has hardcoded tool dispatch** — Violates its own "Nothing is hardcoded" claim.
13. **No cross-tier consistency mechanism** — 4 storage tiers with no distributed transaction, saga pattern, or outbox pattern.

### Low (3)

14. **React client is default Vite template** — `client/src/App.tsx` is a counter button. No HITL UI despite docs describing it.
15. **Client not in docker-compose** — Described in architecture but not deployable.
16. **Inconsistent singleton pattern** — Parsers instantiated per-request, services are singletons.

---

## Critical Issues for Phase 2 Context

The following findings should inform the Security & Performance review:

1. **SQL injection surface** — `postgres_raw_query` and `postgres_write_record` need security-focused deep dive
2. **No auth on MCP endpoints** — Both servers exposed without authentication
3. **Hardcoded secrets** — 6+ instances across docker-compose and settings
4. **PII exposure in tool responses** — Redacted PII still returned in metadata
5. **Runtime config modification without auth** — Workflow engine is fully writable
6. **Chain-of-custody gaps** — DuckDB hash computation on paths, no deterministic pipeline
7. **Memory/scaling risks** — Parsers returning unbounded JSON, Facebook parser loading full files
8. **Thread safety** — Python singletons use unsynchronized global state
