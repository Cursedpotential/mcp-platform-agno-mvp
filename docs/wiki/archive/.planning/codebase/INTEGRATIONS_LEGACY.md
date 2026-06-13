# External Integrations

**Analysis Date:** 2026-02-25

## APIs & External Services

### Cloud AI — AWS

- **AWS Rekognition** - Face detection, object recognition, text-in-image OCR
  - SDK: `@aws-sdk/client-rekognition` ^3.972.0
  - Auth: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/aws-ai.ts`

- **AWS Comprehend** - Sentiment analysis, entity extraction, PII detection
  - SDK: `@aws-sdk/client-comprehend` ^3.972.0
  - Auth: Same AWS credentials
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/aws-ai.ts`

- **AWS Textract** - Document OCR, form field extraction
  - SDK: `@aws-sdk/client-textract` ^3.972.0
  - Auth: Same AWS credentials
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/aws-ai.ts`

- **AWS S3 / Cloudflare R2** - Object storage (S3-compatible)
  - SDK: `@aws-sdk/client-s3` ^3.693.0, `@aws-sdk/s3-request-presigner` ^3.693.0
  - Auth: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ENDPOINT`
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/storage.ts`

### Cloud AI — GCP

- **Google Document AI** - Complex document parsing, form extraction, invoice/receipt parsing
  - SDK: `@google-cloud/documentai` ^9.5.0
  - Auth: `GCP_PROJECT_ID`, `GCP_SERVICE_ACCOUNT_KEY_PATH`, `GCP_DOCUMENT_AI_PROCESSOR_ID`
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/gcp-ai.ts`

- **Google Vertex AI** - Model training, AutoML, custom prediction endpoints
  - SDK: `@google-cloud/aiplatform` ^6.1.0, `@google-cloud/vertexai` ^1.10.0
  - Auth: GCP service account
  - Config: `GCP_VERTEX_AI_ENDPOINT`
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/gcp-ai.ts`

- **Google Cloud Natural Language** - Text analysis
  - SDK: `@google-cloud/language` ^7.2.1
  - Auth: GCP service account

- **Google Cloud Speech-to-Text** - Audio transcription
  - SDK: `@google-cloud/speech` ^7.2.1
  - Auth: GCP service account
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/voiceTranscription.ts`

- **Google Cloud Video Intelligence** - Video content analysis
  - SDK: `@google-cloud/video-intelligence` ^6.2.1
  - Auth: GCP service account

- **Google Cloud Vision** - Image analysis
  - SDK: `@google-cloud/vision` ^5.3.4
  - Auth: GCP service account

- **Google Cloud Storage** - File storage
  - SDK: `@google-cloud/storage` ^7.18.0
  - Auth: GCP service account

- **Google Generative AI (Gemini)** - LLM for location-admin and Chronicle Voice
  - SDK: `@google/generative-ai` ^0.24.1 (location-admin), `@google/genai` latest (Chronicle Voice)
  - Auth: `GOOGLE_API_KEY`

### LLM Providers (via LiteLLM Proxy + Provider Hub)

The platform routes LLM requests through LiteLLM (unified proxy) and a custom Provider Hub.

- **OpenAI** - GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo, text-embedding-ada-002
  - Auth: `OPENAI_API_KEY`
- **Anthropic** - Claude Sonnet 4, Claude Opus 4, Claude Haiku 3
  - Auth: `ANTHROPIC_API_KEY`
- **Google Gemini** - Gemini Pro, Gemini 1.5 Pro
  - Auth: `GEMINI_API_KEY`
- **Groq** - Llama 3.1 70B/8B, Mixtral 8x7B (fast inference)
  - Auth: `GROQ_API_KEY`
- **Azure OpenAI** - GPT-4o, GPT-3.5-turbo
  - Auth: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`
- **OpenRouter** - Multi-model routing
  - Auth: `OPENROUTER_API_KEY`
- **Cohere** - Text models
  - Auth: `COHERE_API_KEY`
- **Together AI** - Open-source model hosting
  - Auth: `TOGETHER_API_KEY`
- **Replicate** - Model hosting
  - Auth: `REPLICATE_API_KEY`
- **Hugging Face** - Model hosting
  - Auth: `HUGGINGFACE_API_KEY`
- **Ollama** - Local LLM runtime (Llama 3.2, Qwen 2.5, nomic-embed-text)
  - Config: `OLLAMA_URL` / `OLLAMA_BASE_URL` (default: `http://localhost:11434`)

**LiteLLM Configuration:**
- Config file: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/config/litellm_config.yaml`
- Model aliases: `cheap`→gpt-4o-mini, `fast`→llama-3.1-8b, `smart`→claude-opus, `analysis`→claude-opus, `coding`→claude-sonnet
- Redis caching enabled
- Auth: `LITELLM_MASTER_KEY`

**Provider Hub:**
- Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/llm/provider-hub.ts` (1725 lines)
- Smart routing: routes by task complexity (simple/medium/complex)
- Supports 20+ provider types including CLI tools (claude-cli, gemini-cli, aider)
- Fallback chains and cost tracking
- Remote CLI bridge via Tailscale/Cloudflare

### Supabase

- **Supabase** - Managed PostgreSQL (alternative to self-hosted)
  - SDK: `@supabase/supabase-js` ^2.89.0 (platform), ^2.38.4 (location-admin), 2.39.3 (Chronicle Voice)
  - Auth: `SUPABASE_URL`, `SUPABASE_KEY`
  - Used by: Directus CMS backend, PhotoPrism database, LiteLLM cost tracking, location-admin, Chronicle Voice
  - Evidence: `deploy/docker-compose.yml` (Directus, PhotoPrism, LiteLLM all reference `SUPABASE_HOST`)

### Graphiti (Temporal Knowledge Graph)

- **Graphiti-core** - Python-based temporal knowledge graph over Neo4j
  - Package: graphiti-core >=0.3.0 (Python)
  - Bridge: TypeScript→Python via `child_process.spawn`
  - Runner: `server/python-tools/graphiti_runner.py`
  - Client: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/mcp/storage/graphiti-client.ts` (752 lines)
  - Deployment: `deploy/gcp/graphiti/` (FastAPI + uvicorn Docker container)
  - Auth: `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `OPENAI_API_KEY` (for embeddings)

### Manus Platform

- **Manus OAuth** - Authentication provider
  - Config: `OAUTH_SERVER_URL` (default: `https://oauth.manus.im`)
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/oauth.ts`, `server/core/sdk.ts`
- **Manus Forge API** - Built-in storage/services
  - Config: `BUILT_IN_FORGE_API_URL` (default: `https://forge.manus.im`), `BUILT_IN_FORGE_API_KEY`
  - Implementation: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/core/storage.ts`
- **Manus Runtime** - Vite plugin for Manus platform integration
  - Package: `vite-plugin-manus-runtime` ^0.0.57
  - Evidence: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/vite.config.ts`

### Unstructured API

- **Unstructured** - Document parsing and processing (MCP server)
  - SDK: `unstructured-client` >=0.32.1
  - MCP server: `uns_mcp` (Python package in `TraceIQ/location-admin/UNS-MCP-main/`)
  - Also: `firecrawl-py` >=1.14.1 (web scraping integration)
  - Auth: Unstructured API key (via env)

## Data Storage

### Databases

**PostgreSQL 16 + PGVector + PostGIS (VPS1 - Primary):**
- Connection: `DATABASE_URL` (Drizzle), or individual `POSTGRES_HOST/PORT/DB/USER/PASSWORD`
- Client: Drizzle ORM via `postgres` package
- Docker: `pgvector/pgvector:pg16`
- Schema: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/drizzle/schema.ts`
- Migrations: `MCP_Tool_Platform/MCP_Tool_Platform_Repo/drizzle/` (3 SQL migrations)
- Extensions: pgvector (1536-dim embeddings), PostGIS (geospatial)
- Vector client: `server/mcp/storage/pgvector-client.ts` (LangChain PGVectorStore + Ollama embeddings)
- Evidence: `server/core/db.postgres.ts`, `drizzle.config.ts`

**MySQL (VPS3 - Application):**
- Connection: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`
- Client: Drizzle ORM via mysql2/promise
- Role: Internal site processes (settings, users, API keys)
- Evidence: `server/core/db.mysql.ts`

**Neo4j 5.15 Community (VPS1 - Graph):**
- Connection: `NEO4J_URL` (bolt://), `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- Client: neo4j-driver (Node.js), neo4j (Python)
- Role: Temporal knowledge graph — entities, relationships, MCL 722.23 factor mapping
- Plugins: APOC
- Evidence: `server/mcp/storage/graphiti-client.ts`

**ChromaDB (VPS2 - Vector):**
- Connection: `CHROMA_URL` (default: `http://localhost:8000`), `CHROMA_AUTH_TOKEN`
- Client: chromadb npm package
- Role: Dual-collection system
  - Evidence Processing collection: 72hr TTL, preliminary classification
  - Project Context collection: Persistent preferences, workflows, case info
- Evidence: `server/mcp/storage/chroma-client.ts` (513 lines)

**SQLite (TraceIQ - Local):**
- Path: `TraceIQ/TraceIQ_Main/data/processed/timeline.db`
- Schema: `TraceIQ/schema.sql` (4 tables: timeline_events, waypoints, processing_metadata, parse_errors + 5 views)
- Role: Google Timeline data processing (visits, activities, waypoints, multi-device)

**PostgreSQL + PostGIS 15 (TraceIQ Docker):**
- Connection: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- Docker: `postgis/postgis:15-3.3`
- Role: TraceIQ timeline data with geospatial queries
- Evidence: `TraceIQ/TraceIQ_Main/docker-compose.yml`

**Redis 7 (VPS - Caching):**
- Connection: `redis://localhost:6379`, auth via `REDIS_PASSWORD`
- Client: ioredis (Node.js)
- Role: Caching (Directus, LiteLLM), rate limiting, job queues
- Evidence: `deploy/docker-compose.yml`

**MongoDB 7 (LibreChat):**
- Connection: `mongodb://mongo:27017/LibreChat` (Docker internal)
- Role: LibreChat conversation storage
- Evidence: `deploy/docker-compose.yml` line 315

### File Storage

**Cloudflare R2:**
- S3-compatible object storage
- Bucket: `salem-forensics` (configurable via `R2_BUCKET`)
- Access: Cloudflare Worker at `r2.mitechconsult.com`
- Sync: rclone container syncs PhotoPrism originals → R2
- Auth: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`
- Evidence: `deploy/cloudflare/wrangler.toml`, `deploy/docker-compose.yml` (r2-sync service)

**Directus CMS (VPS1 - File Vault):**
- Binary file management (PDF, images, exports)
- Chain-of-custody tracking with SHA-256 verification
- Storage backend: Cloudflare R2
- Auth: `DIRECTUS_ADMIN_EMAIL`, `DIRECTUS_ADMIN_PASSWORD`, `DIRECTUS_KEY`, `DIRECTUS_SECRET`
- Client: `server/mcp/storage/directus-client.ts` (539 lines)
- Docker: `directus/directus:latest`

**PhotoPrism (VPS1):**
- AI-powered evidence photo management
- NSFW detection enabled, TensorFlow-based analysis
- Database: PostgreSQL (Supabase)
- Auth: `PHOTOPRISM_ADMIN_USER`, `PHOTOPRISM_ADMIN_PASSWORD`
- Docker: `photoprism/photoprism:latest`

### Caching

**Redis 7 Alpine:**
- Docker: `redis:7-alpine`
- Uses: Directus cache, LiteLLM response cache, rate limiting, job queues
- Config: Append-only persistence (`--appendonly yes`)
- Auth: `REDIS_PASSWORD`

## Authentication & Identity

**OAuth (Manus Platform):**
- Provider: Manus OAuth server
- Flow: Authorization code → token exchange → user info → session cookie
- Token: JWT-based session tokens (1 year expiry)
- Cookie: `COOKIE_NAME` (from `@shared/const`)
- Auth middleware: tRPC `protectedProcedure` and `adminProcedure`
- Implementation: `server/core/oauth.ts`, `server/core/sdk.ts`, `server/core/cookies.ts`
- Config: `OAUTH_SERVER_URL`, `JWT_SECRET`, `OWNER_OPEN_ID`

**API Key Authentication:**
- Custom API key system with hashed storage
- Schema: `drizzle/schema.ts` → `apiKeys` table (keyHash, keyPrefix, permissions, usage tracking)
- Per-key permissions and expiration
- Router: `server/routers/api-keys.ts`

**Encryption:**
- AES encryption for API key storage
- Config: `ENCRYPTION_KEY` (32-byte hex key)
- Implementation: `server/core/encryption.ts`

**Role-Based Access:**
- User roles: `user`, `admin`
- tRPC middleware: `requireUser` (authenticated), `adminProcedure` (admin only)
- Evidence: `server/core/trpc.ts`

**Cloudflare Workers Auth:**
- API key authentication per worker
- JWT secrets for auth proxy
- Config: `API_KEY` (per worker), `JWT_SECRET` (auth proxy), `API_KEYS` (JSON object)
- Evidence: `deploy/cloudflare/wrangler.toml`

## MCP Server Infrastructure

### MCP Gateway (Platform Core)

The platform itself IS an MCP server aggregator/gateway.

- **Gateway API** - 4 core endpoints via tRPC:
  - `search_tools` - Discover tools with minimal token overhead
  - `describe_tool` - Get full tool specification on demand
  - `invoke_tool` - Execute tools with reference-based returns
  - `get_ref` - Retrieve content-addressed artifacts with paging
- Implementation: `server/mcp/gateway.ts` (1431 lines)
- Supports: HTTP, WebSocket, stdio transports
- Features: Tool registry, plugin system, task execution queue, LLM routing

### MCP Server Proxy

- Consolidates multiple MCP servers into unified interface
- Register/proxy/aggregate remote MCP servers
- Health monitoring and load balancing
- Config import from standard MCP JSON configs
- Implementation: `server/mcp/proxy/mcp-proxy.ts` (707 lines)
- Config import: `server/mcp/proxy/mcp-config-import.ts`

### MetaMCP (MCP Registry)

- Docker service for MCP server registry and discovery
- Internal (port 4001) + External (port 4002)
- Auth: API key required for external
- Config: `MCP_REGISTRY_URL` (default: `https://mcp.run/registry`)
- Evidence: `deploy/docker-compose.yml`, `Docker/Dockerfile.metamcp`

### UNS-MCP (Unstructured API)

- MCP server for Unstructured API interactions
- Manages sources, destinations, workflows, jobs
- Package: `uns_mcp` (Python, pyproject.toml)
- Location: `TraceIQ/location-admin/UNS-MCP-main/`
- Dependencies: anthropic, boto3, firecrawl-py, mcp[cli], unstructured-client

### Python Bridge

- TypeScript↔Python communication for NLP/ML tools
- Uses `child_process.spawn` to invoke Python scripts
- Implementation: `server/mcp/python-bridge.ts`
- Python tools directory: `server/python-tools/`

## Monitoring & Observability

**Logging:**
- Server: `console.log`/`console.warn`/`console.error` throughout
- Structured logging in MCP subsystem: `server/mcp/realtime/log-stream.ts`
- Python: Python `logging` module (file + stdout handlers)
- Config: `LOG_LEVEL` env var

**Analytics/BI:**
- Metabase - Business intelligence dashboard
  - Docker: `metabase/metabase:latest` (port 3001)
  - Connects to PostgreSQL (Supabase)
  - Evidence: `deploy/docker-compose.yml`

**Health Checks:**
- Database health check interval: `DATABASE_HEALTH_CHECK_INTERVAL` (default: 30s)
- PostgreSQL: `pg_isready` Docker healthcheck
- MCP Server proxy: Per-server health monitoring with latency tracking
- `initAllDatabases()` function tests all 4 database connections
- Evidence: `server/core/db.ts` lines 188-206

**Error Tracking:**
- No external service (Sentry, Datadog, etc.) detected
- Error tracking via database: `parse_errors` table (TraceIQ SQLite schema)
- MCP gateway returns structured `ApiResponse` with error codes

## CI/CD & Deployment

**Hosting:**
- Self-hosted VPS (3-node Salem Trinity architecture)
- Cloudflare (R2 storage, Workers, DNS for mitechconsult.com)
- Supabase (managed PostgreSQL option)
- GCP (Graphiti FastAPI deployment)

**CI Pipeline:**
- GitHub repository detected (`.github/` directory exists)
- No CI workflow files found in active directories (may be in `.github/workflows/`)

**Docker Images Used:**
- `node:22-alpine` (MCP Platform)
- `python:3.11-slim` (TraceIQ)
- `pgvector/pgvector:pg16` (PostgreSQL)
- `postgis/postgis:15-3.3` (TraceIQ PostgreSQL)
- `neo4j:5.15-community` (Graph DB)
- `chromadb/chroma:latest` (Vector DB)
- `redis:7-alpine` (Cache)
- `directus/directus:latest` (CMS)
- `photoprism/photoprism:latest` (Photo management)
- `ollama/ollama:latest` (Local LLM)
- `ghcr.io/berriai/litellm:main-latest` (LLM proxy)
- `ghcr.io/danny-avila/librechat:latest` (Chat UI)
- `ghcr.io/open-webui/open-webui:main` (Chat UI)
- `mongo:7` (MongoDB)
- `getmeili/meilisearch:latest` (Search)
- `n8nio/n8n:latest` (Workflow automation)
- `metabase/metabase:latest` (BI)
- `browserless/chrome:latest` (Headless browser)
- `rclone/rclone:latest` (R2 sync)
- `tailscale/tailscale:latest` (VPN)
- `jupyter/scipy-notebook:latest` (Notebooks)
- `kasmweb/debian-bookworm-desktop:1.15.0` (VNC desktop)

**Deployment Docs:**
- `deploy/salem-trinity/MASTER_DEPLOYMENT_GUIDE.md`
- `deploy/salem-trinity/FULL_STACK_MAP.md`
- Phase-based deployment: phase1 (VPS1 fix), phase2 (VPS2 deploy), phase3 (VPS3 platform), phase4 (system router)

## Workflow Automation

**n8n:**
- Docker: `n8nio/n8n:latest` (port 5678)
- Workflow file: `n8n-workflows/service-control.json`
- Auth: `N8N_USER`, `N8N_PASSWORD`
- Feature flag: `N8N_ENABLED`, `ENABLE_N8N`
- Config: `N8N_URL`, `N8N_API_KEY`, `N8N_WEBHOOK_BASE_URL`

**Browserless + Playwright:**
- Headless Chrome for web scraping, PDF generation, screenshots
- Browserless: port 3004, auth via `BROWSERLESS_TOKEN`
- Playwright: port 3005, custom Dockerfile
- Evidence: `deploy/docker-compose.yml`, `Docker/Dockerfile.playwright`

## Environment Configuration

### Required Environment Variables (Critical)

**Database:**
- `DATABASE_URL` — PostgreSQL connection string (Drizzle primary)
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- `CHROMA_URL`, `CHROMA_AUTH_TOKEN`
- `REDIS_PASSWORD`
- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`

**Security:**
- `ENCRYPTION_KEY` — 32-byte hex for API key encryption
- `JWT_SECRET` — JWT signing secret

**Auth:**
- `OAUTH_SERVER_URL` — Manus OAuth endpoint
- `OWNER_OPEN_ID` — Platform owner identity

**Storage:**
- `SUPABASE_URL`, `SUPABASE_KEY`
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ENDPOINT`

**AI Services:**
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY` / `GEMINI_API_KEY`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- `GCP_PROJECT_ID`, `GCP_SERVICE_ACCOUNT_KEY_PATH`

**Platform:**
- `PORT` (default: 3000)
- `NODE_ENV` (development/production)
- `VITE_APP_URL`
- `VITE_APP_ID`

**Feature Flags:**
- `ENABLE_VECTOR_DB` (default: true)
- `ENABLE_GRAPH_DB` (default: true)
- `ENABLE_MEM0` (default: false)
- `ENABLE_N8N` (default: false)

### Env File Locations

- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env` — Active platform config
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env.example` — Full template (138 lines)
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env.postgres.example` — PostgreSQL-specific
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/.env.docker.example` — Docker Compose vars (145 lines)
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/python-tools/.env` — Python tools config
- `MCP_Tool_Platform/MCP_Tool_Platform_Repo/server/python-tools/.env.graphiti` — Graphiti-specific
- `TraceIQ/timeline-explorer-pro/.env.local` — Timeline explorer config
- `deploy/salem-trinity/phase3-vps3-platform/.env` — VPS3 production config

## Webhooks & Callbacks

**Incoming:**
- OAuth callback: `GET /api/oauth/callback` (code + state params)
  - Evidence: `server/core/oauth.ts`
- Cloudflare Webhook Receiver: `webhooks.mitechconsult.com/*`
  - Forwards to: `https://api.mitechconsult.com`
  - Evidence: `deploy/cloudflare/wrangler.toml`
- n8n webhooks: `http://localhost:5678/`
  - Config: `WEBHOOK_URL`, `N8N_WEBHOOK_BASE_URL`

**Outgoing:**
- MCP tool invocations to registered external MCP servers
- LLM API calls via LiteLLM proxy and Provider Hub
- Graphiti Python runner subprocess calls
- R2 sync (rclone) to Cloudflare R2

## Inter-Component Communication

### Sub-Project Relationships

```
MCP_Tool_Platform (Core Platform)
├── tRPC API (/api/trpc) — All client↔server communication
├── MCP Gateway — Tool search/invoke/describe for AI agents
├── Python Bridge — Node.js ↔ Python NLP/ML tools (child_process)
├── Graphiti Client — Node.js → Python graphiti_runner.py → Neo4j
├── Database Router — Routes queries to PostgreSQL/MySQL/Neo4j/ChromaDB/Directus
├── LLM Provider Hub — Routes to 20+ LLM providers
├── MCP Proxy — Aggregates external MCP servers (HTTP/WS/stdio)
└── Cloudflare Workers — Edge functions (auth, cache, rate limit, evidence hashing)

TraceIQ (Timeline Forensics)
├── TraceIQ_Main — Flask + SQLite/PostgreSQL (standalone, Docker-based)
├── timeline-explorer-pro — React SPA (standalone Vite app, no server deps)
├── location-admin — React + Express + MUI + Supabase + Gemini AI
├── Chat_Parser_App — Flask + PostgreSQL (shares TraceIQ DB config)
└── TimelineExtractor — Python CLI tool (Docker, standalone)

Voice_Analysis
├── Chronicle_Voice_App — React + Supabase + Google GenAI (standalone)
├── story-voice-backend — Gradio Python backend (standalone)
└── Video_Analyzer_App — React SPA (client-side only)

Evidence_Analysis
├── ConflictAnalysisApp — PySide6 desktop app (standalone, local files)
└── forensic-data-refinery — React SPA (client-side only, IndexedDB)
```

### Communication Patterns

1. **MCP Platform ↔ Databases:** Multi-database router in `server/core/db.ts` dispatches to PostgreSQL (primary), MySQL (app), Neo4j (graph), ChromaDB (vector), Directus (files)

2. **MCP Platform ↔ Python Tools:** `server/mcp/python-bridge.ts` spawns Python processes. Graphiti client spawns `graphiti_runner.py` for Neo4j graph operations.

3. **MCP Platform ↔ External MCP Servers:** Proxy in `server/mcp/proxy/mcp-proxy.ts` connects to remote MCP servers via HTTP/WebSocket/stdio, aggregates their tools.

4. **MCP Platform ↔ LLM Providers:** Provider Hub (`server/mcp/llm/provider-hub.ts`) routes requests based on task complexity. LiteLLM Docker service provides unified API gateway.

5. **TraceIQ sub-projects** operate mostly independently. `location-admin` and `Chat_Parser_App` share the same PostgreSQL database config (host: `postgres`, DB: `traceiq`).

6. **No direct communication** detected between MCP_Tool_Platform and TraceIQ/Voice_Analysis/Evidence_Analysis sub-projects. They are separate applications that could be integrated through the MCP gateway in the future.

7. **Edge layer:** Cloudflare Workers handle auth proxy, R2 storage access, evidence hashing, caching, rate limiting, and webhook receiving — all on `*.mitechconsult.com` subdomains.

---

*Integration audit: 2026-02-25*
