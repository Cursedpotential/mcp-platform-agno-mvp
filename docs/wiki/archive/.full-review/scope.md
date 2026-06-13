# Review Scope

## Target

Full dial-stack codebase review with emphasis on:
1. Documentation vs code alignment (do docs/planning/TODOs match what the code actually does?)
2. New features added by other agents (DPK tools, voice fingerprinting, workflow engine, user detection)
3. Message processing capability — can the stack actually parse and process SMS/Facebook/iMessage messages end-to-end?

## Files

### Core Infrastructure
- `docker-compose.yml` — 14 services (core, chat, themes, keycloak, auth-helper, dragonfly, postgres, ollama, ts-mcp-server, py-mcp-server, audit-logger, influxdb, analytics-realtime, caddy)
- `core/config.json` — DIAL Core routing config (3 models, 4 apps, 1 interceptor, 3 API key roles)
- `settings/settings.json` — DIAL settings including Keycloak identity provider
- `Caddyfile` — Reverse proxy config

### TS MCP Server (port 8081) — Parsers & Storage
- `ts-mcp-server/src/index.ts` — Main server, 20 tool definitions, Express + StreamableHTTPServerTransport
- `ts-mcp-server/src/tools/SmsXmlParser.ts` — SMS/MMS/Call XML parser (stream processing)
- `ts-mcp-server/src/tools/FacebookExportParser.ts` — Facebook Messenger HTML parser (cheerio)
- `ts-mcp-server/src/tools/ImessagePdfParser.ts` — iMessage PDF parser
- `ts-mcp-server/src/tools/DuckDbVault.ts` — DuckDB forensic vault (SHA-256, UUIDv7, dedup)
- `ts-mcp-server/src/tools/PostgresWriter.ts` — PostgreSQL evidence writer
- `ts-mcp-server/src/tools/AdminTools.ts` — LLM provider/system prompt management
- `ts-mcp-server/src/tools/ReviewQueue.ts` — HITL review queue
- `ts-mcp-server/src/services/DuckDbService.ts` — DuckDB service layer

### Py MCP Server (port 8082) — NLP & Knowledge Graph
- `py-mcp-server/src/server.py` — FastMCP server, 30+ tools (Semantica, DPK, voice, user detection, workflows)
- `py-mcp-server/src/tools/dpk_tools.py` — HAP scoring, PII redaction, language ID, doc quality, readability
- `py-mcp-server/src/tools/voice_tools.py` — Voice fingerprinting (Burrows' Delta)
- `py-mcp-server/src/tools/user_detection.py` — Behavioral/DARVO/coercive control detection (placeholders)
- `py-mcp-server/src/tools/workflow_tools.py` — Config-driven workflow engine
- `py-mcp-server/src/tools/audit_hooks.py` — Audit hooks
- `py-mcp-server/config/workflows.json` — Workflow definitions

### Client (React + CopilotKit)
- `client/src/App.tsx` — Main React app
- `client/src/main.tsx` — Entry point
- `client/src/components/ui/*.tsx` — 50+ Radix UI components (shadcn/ui)

### Documentation
- `CLAUDE.md` — Agent instructions
- `README.md` — Project README
- `docs/ARCHITECTURE.md` — System architecture
- `docs/ROADMAP.md` — Development roadmap (Phases A-I)
- `docs/TOOL_CATALOG.md` — Tool inventory (22 built, 22 planned)
- `docs/SPEC_DRIVEN_DEVELOPMENT.md` — Dev process
- `docs/DATA_SOURCES.md` — External data sources

### Planning
- `.planning/PROJECT.md` — Project overview
- `.planning/BACKLOG_LEGACY.md`
- `.planning/REQUIREMENTS_LEGACY.md`
- `.planning/SPRINT_HANDOFF_LEGACY.md`
- `.planning/codebase/CONCERNS_LEGACY.md`
- `.planning/codebase/CONVENTIONS.md`
- `.planning/codebase/INTEGRATIONS_LEGACY.md`

### Other
- `interceptors/audit_logger/app.py` — Audit logging interceptor
- `core/prompts/INGESTION_AGENT_PROMPT.md` — Agent system prompt
- `utilities/` — 40+ standalone Python scripts (legacy tools)
- `tools/` — Forensic tools (exiftool, etc.)

## Flags

- Security Focus: yes
- Performance Critical: no
- Strict Mode: no
- Framework: TypeScript (TS MCP Server) + Python (Py MCP Server) + React (Client)

## Review Phases

1. Code Quality & Architecture
2. Security & Performance
3. Testing & Documentation
4. Best Practices & Standards
5. Consolidated Report
