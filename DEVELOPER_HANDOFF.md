# Developer Handoff: Agno MCP Platform MVP

## Your Mission

Get this platform running end-to-end, then start porting tools from the alpha repository. You are the primary builder — the human (Matt) will approve your plans but you drive the implementation.

## What Has Been Built

This is an Agno-based control layer sitting on top of modular MCP servers. It was just security-audited and fixed. The infrastructure is sound. The gap is tool porting from the alpha repo.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Agno Control Layer (this repo) — FastAPI + AgentOS         │
│  7 agents: 4 platform + 3 builder                           │
│  PostgreSQL + pgvector for state, embeddings, insights      │
└──────────────┬────────────────────────────────┬──────────────┘
               │ MCPTools(command=...)          │ MCPTools(command=...)
               ▼                                ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│  TS MCP Server (Node.js) │    │  Py MCP Server (Python)      │
│  Port: 3001              │    │  Port: 3002                  │
│  • SMS XML parser ✅     │    │  • Semantica NLP ✅          │
│  • Facebook parser ⚠️    │    │  • Entity extraction ✅      │
│  • iMessage stub ❌      │    │  • Vector embeddings ✅      │
│  • DuckDB vault ✅       │    │  • LanceDB search ✅         │
│  • Review queue ✅       │    │  • Neo4j queries ✅          │
│  • Pass1Runner ⚠️       │    │  • Forensic analysis ✅      │
└──────────────────────────┘    │  • Pattern detection ❌      │
                                │  • HurtLex ❌                │
                                └──────────────────────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │  n8n Workflow Automation       │
                              │  Port: 5678                    │
                              │  • Bidirectional MCP           │
                              │  • 400+ app integrations       │
                              │  • Visual workflow builder     │
                              └────────────────────────────────┘
```

Legend: ✅ Working | ⚠️ Partial/Blocked | ❌ Missing

### What Was Fixed in the Security Audit

| Issue | Severity | Fix Location |
|-------|----------|-------------|
| Path traversal in `/v1/transcripts/mine` | CRITICAL | `app/main.py:579` — `fp.relative_to(base_path)` |
| Per-request DB engine creation | CRITICAL | `app/main.py:349` — single `AsyncEngine` in lifespan |
| No authentication | CRITICAL | `app/main.py:40` — `X-API-Key` header auth |
| MCP subprocess leak | CRITICAL | `app/main.py:358-371` — store refs, cleanup in shutdown |
| Hardcoded DB password | CRITICAL | `config/settings.py:33` — removed default |
| Health check DB leak | HIGH | Uses shared engine |
| `reload=True` in production | HIGH | Gated behind `UVICORN_RELOAD` |
| `agent_run` never populated | MEDIUM | `create_agent_run()` helper added |
| Transcript truncation | CRITICAL | `lib/chunking.py` + multi-chunk loop |
| Docker no Node.js/root | HIGH | Multi-stage build, non-root user, health checks |

## Step 1: Get It Running Locally

### 1.1 Clone All Three Repos

```bash
mkdir -p ~/projects && cd ~/projects

# This repo (control layer)
git clone https://github.com/Cursedpotential/mcp-platform-agno-mvp.git

# Modular MCP servers
git clone https://github.com/Cursedpotential/MCP_PLATFORM.git

# Alpha (legacy, for porting reference)
git clone https://github.com/Cursedpotential/mcp-tool-platform.git
```

### 1.2 Build the MCP Servers

**TypeScript MCP server:**
```bash
cd ~/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server
npm install
npm run build
# Verify dist/ exists with compiled JS
ls dist/
```

**Python MCP server:**
```bash
cd ~/projects/MCP_PLATFORM/mcp-servers/py-mcp-server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Verify it starts (will fail on DB connection outside Docker, but should show tools)
python main.py --help 2>/dev/null || echo "Expected to fail outside Docker — that's OK"
```

### 1.3 Configure Environment

```bash
cd ~/projects/mcp-platform-agno-mvp
cp .env.example .env
```

Edit `.env`:
```bash
# Required
OPENAI_API_KEY=sk-your-key-here
PLATFORM_DB_URL=postgresql+psycopg://postgres:changeme@postgres:5432/agno_platform

# Point to MCP servers (adjust paths for your system)
TS_MCP_COMMAND=node /home/$USER/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server/dist/index.js
PY_MCP_COMMAND=python /home/$USER/projects/MCP_PLATFORM/mcp-servers/py-mcp-server/main.py

# n8n encryption (generate with: openssl rand -hex 32)
N8N_ENCRYPTION_KEY=<generate>
N8N_USER_MANAGEMENT_JWT_SECRET=<generate>
```

### 1.4 Create Storage Directories

```bash
cd ~/projects/mcp-platform-agno-mvp
mkdir -p data/postgres_data data/n8n_data data/r2_share
mkdir -p knowledge/platform/{conversations,docs,notes}
sudo chown -R $USER:$USER data/
chmod -R 775 data/
```

### 1.5 Start the Stack

```bash
cd ~/projects/mcp-platform-agno-mvp
docker compose up -d

# Wait 30s for initialization
sleep 30

# Verify all services
docker compose ps

# Verify health
curl http://localhost:8000/health
# Expected: {"status":"healthy","agents_ready":true,"db_connected":true}

# List agents
curl http://localhost:8000/v1/agents

# Test an agent
curl -X POST http://localhost:8000/v1/agents/project_pal/run \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the current status of the platform?"}'
```

### 1.6 Verify n8n

```bash
# n8n should be at http://localhost:5678
# First-time setup: create owner account
# Then: Settings → Community nodes → Enable (already set in compose)
```

## Step 2: Understand the Codebase

### Key Files You Will Work With

| File | Purpose | When You Modify It |
|------|---------|-------------------|
| `app/main.py` | FastAPI routes, DB helpers, auth | Adding API endpoints, fixing DB operations |
| `agents/factory.py` | Agent constructors, MCP tool wiring | Adding agents, changing tool connections |
| `agents/instructions.py` | Agent role instructions | Changing what agents can/cannot do |
| `config/settings.py` | Environment config, model factory | Adding config options |
| `sql/schema.sql` | Database schema | Adding tables/columns |
| `lib/chunking.py` | Transcript chunking logic | Improving chunking strategy |
| `scripts/ingest_knowledge.py` | Knowledge indexing | Loading new document types |
| `scripts/mine_transcripts.py` | Batch transcript mining | Processing transcript formats |
| `prompts/platform_context/*.md` | Agent starter knowledge | Updating project context |

### How Agents Are Built

```python
# agents/factory.py
# Each agent gets: model + tools + instructions + knowledge + memory config

ingestion_orchestrator = Agent(
    name="ingestion_orchestrator",
    agent_id="ingestion_orchestrator",
    model=model,                          # From settings.get_model()
    tools=platform_tools,                # MCPTools from TS + Py MCP servers
    instructions=get_instructions("..."), # From instructions.py
    knowledge=knowledge,                 # pgvector knowledge base
    search_knowledge=True,
    add_history_to_messages=True,
    num_history_responses=5,
    markdown=True,
)
```

### How MCP Tools Connect

```python
# agents/factory.py:build_mcp_tools()
ts_tools = MCPTools(command=settings.ts_mcp_command, timeout=30)
# Spawns: node mcp-servers/ts-mcp-server/dist/index.js
# Communicates via stdio (JSON-RPC over stdin/stdout)
```

The Docker compose also exposes MCP servers via HTTP:
- TS MCP: `http://ts-mcp-server:3001` (SSE transport)
- Py MCP: `http://py-mcp-server:3002` (SSE transport)

For HTTP transport (more reliable in containers):
```python
n8n_mcp_tools = MCPTools(
    transport="streamable-http",
    url="http://ts-mcp-server:3001",
)
```

### How the Database Works

```python
# config/settings.py
# One shared AsyncEngine created in lifespan
app.state.engine = create_async_engine(
    settings.platform_db_url,
    pool_size=settings.db_pool_size,      # 10
    max_overflow=settings.db_max_overflow, # 20
    pool_recycle=settings.db_pool_recycle, # 3600
    pool_pre_ping=True,
)

# All DB helpers use app.state.engine
async def create_approval_request(engine: AsyncEngine, ...):
    async with engine.begin() as conn:
        await conn.execute(text("INSERT ..."))
```

Tables:
- `agent_run` — tracks every agent execution
- `approval_request` — HITL approval checkpoints
- `learned_knowledge` — reusable patterns with pgvector embeddings
- `transcript_insight` — structured insights from mined transcripts

## Step 3: First Porting Task — Wire Facebook Parser (P0-1)

This is the highest impact, lowest effort task. The parser code exists. It's just not connected.

### 3.1 Read the Current Code

```bash
# Facebook parser implementation
cat ~/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server/src/tools/FacebookExportParser.ts
# ~250 lines, dual HTML structure support

# Evidence ingestor that blocks it
cat ~/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server/src/tools/EvidenceIngestor.ts
# Lines 103-108: hardcoded rejection of .html files
```

### 3.2 Read the Alpha Reference

```bash
cat ~/projects/mcp-tool-platform/server/mcp/loaders/facebook-parser.ts
# Compare approaches, check for missing features
```

### 3.3 Make the Change

In `EvidenceIngestor.ts`:
```typescript
// BEFORE (line ~103):
if (ext === '.html' || ext === '.htm') {
  return { status: 'unsupported_format', message: 'planned addition — requires owner approval' };
}

// AFTER:
if (ext === '.html' || ext === '.htm') {
  const facebookParser = new FacebookExportParser();
  const parsed = await facebookParser.parse(filePath, fileBuffer);
  // Compute SHA-256 hash FIRST
  const hash = await computeSha256(fileBuffer);
  // Log to DuckDB vault
  await vault.logIngestion(filePath, hash, 'facebook_html', parsed.messages.length);
  return { status: 'parsed', data: parsed, hash };
}
```

### 3.4 Test

```bash
cd ~/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server
npm run build

# Get a Facebook HTML export and test
# (Ask Matt for a sanitized test file, or use the test fixtures if they exist)
```

### 3.5 Update Documentation

```bash
# Update PARITY_MATRIX.md — mark Facebook parser as working
# Update GROUND_TRUTH.md — reflect the change
# Update TODO.md — mark TS-003 as complete
```

## Step 4: Second Porting Task — iMessage PDF Parser (P0-2)

### 4.1 Read the Alpha Implementation

```bash
cat ~/projects/mcp-tool-platform/server/mcp/loaders/pdf-imessage-parser.ts
# Understand: PDF library used, regex patterns for iMessage format,
# how it extracts timestamps, sender names, message direction
```

### 4.2 Check Current Dependencies

```bash
cd ~/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server
cat package.json | grep -i pdf
# If no PDF library, add: npm install pdf-parse
```

### 4.3 Implement in Current

```bash
cat ~/projects/MCP_PLATFORM/mcp-servers/ts-mcp-server/src/tools/ImessagePdfParser.ts
# Currently 28 lines of stub. Replace with full implementation following
# the same pattern as SmsXmlParser.ts and FacebookExportParser.ts
```

### 4.4 Wire into EvidenceIngestor

Add `.pdf` handling alongside the Facebook parser code you just added.

### 4.5 Add Test Fixture

Create a minimal PDF that looks like an iMessage export for testing.

## Step 5: n8n Integration

### 5.1 Verify n8n MCP Support

```bash
# n8n should be running at http://localhost:5678
# Go to Settings → Community nodes
# Verify N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true took effect
```

### 5.2 Create First Workflow: Agno Calls n8n

In n8n:
1. Create new workflow
2. Add **Webhook** trigger node
3. Set method to POST, path to `/evidence-ingested`
4. Add **Slack** node (or email/notification)
5. Connect webhook → Slack
6. Save workflow, copy webhook URL

In Agno (test):
```bash
curl -X POST http://localhost:8000/v1/agents/dev_copilot/run \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need to trigger an n8n webhook when evidence is ingested. The webhook URL is http://mcp-n8n:5678/webhook/evidence-ingested. Show me how to add this as a tool to the ingestion_orchestrator agent."
  }'
```

### 5.3 Create Second Workflow: n8n Calls Agno

In n8n:
1. Create new workflow
2. Add **Schedule Trigger** (every Monday 9am)
3. Add **HTTP Request** node
4. Set URL to `http://agentos:8000/v1/agents/analysis_orchestrator/run`
5. Set method to POST, body to `{"message": "Run weekly pattern analysis"}`
6. Add **Email** node for results
7. Save and activate

### 5.4 Bidirectional MCP (Future)

For true bidirectional MCP (not just HTTP webhooks):

**Agno as MCP client to n8n:**
```python
# In agents/factory.py, add:
n8n_mcp_tools = MCPTools(
    transport="streamable-http",
    url="http://mcp-n8n:5678/mcp",
    headers={"Authorization": "Bearer N8N_API_KEY"}
)
# Add n8n_mcp_tools to platform_tools list
```

**n8n as MCP client to Agno:**
In n8n, use the **MCP Client Tool** node pointing to `http://agentos:8000/mcp`

## Step 6: Cloudflare R2 Integration (Optional)

### 6.1 Configure rclone

```bash
rclone config
# New remote: cloudflare_r2
# Type: S3
# Provider: Cloudflare
# Access Key: from Cloudflare dashboard
# Secret Key: from Cloudflare dashboard
# Endpoint: https://ACCOUNT_ID.r2.cloudflarestorage.com
```

### 6.2 Mount R2

```bash
cd ~/projects/mcp-platform-agno-mvp
rclone mount cloudflare_r2:bucket-name ./data/r2_share \
  --vfs-cache-mode writes \
  --allow-other \
  --daemon
```

### 6.3 Add R2 Tool to Agno

```python
# New tool: r2_upload, r2_download, r2_list
# Use boto3 with S3-compatible API
# Add to dev_copilot's task list
```

## Step 7: Testing Strategy

The platform currently has **zero test coverage**. This needs to change.

### Priority 1: Parser Integration Tests

```python
# tests/integration/test_parsers.py
# For each parser (SMS, Facebook, iMessage):
# 1. Load test fixture file
# 2. Run parser
# 3. Verify SHA-256 hash computed
# 4. Verify DuckDB vault entry created
# 5. Verify PostgreSQL records written
# 6. Verify LanceDB embeddings generated
```

### Priority 2: API Endpoint Tests

The existing tests in `tests/` are stubs. Make them real:

```bash
# tests/integration/test_approval_flow.py
# - Test approval creation → decision → agent_run status update
# - Test auth required on POST endpoints
# - Test path traversal protection

# tests/e2e/test_full_pipeline.py
# - End-to-end: ingest evidence → analyze → approve → export
```

### Priority 3: Agent Behavior Tests

```python
# tests/unit/test_agents.py
# Mock MCP tools, verify agent produces correct tool plans
# Verify approval requests created for write operations
```

## Open Technical Decisions

| Decision | Options | Context | Default if not decided |
|----------|---------|---------|----------------------|
| Embedding model | all-MiniLM-L6-v2 / mpnet / BGE | Blocks PY-001 | all-MiniLM-L6-v2 |
| MCP transport | stdio / HTTP-SSE / both | Affects reliability | Both with fallback |
| Testing framework | pytest-only / pytest+Playwright | E2E needs browser | pytest only for now |
| n8n MCP mode | Webhooks / native MCP / both | Native MCP is newer | Both |
| R2 sync | rclone mount / boto3 API / both | Mount is simpler | rclone mount |

## Quick Reference: Common Tasks

### Add a New Agent
```bash
# 1. Add instructions to agents/instructions.py
# 2. Add constructor to agents/factory.py
# 3. Add to return dict in build_agent_team()
# 4. Add API route in app/main.py if needed
# 5. Update prompts/platform_context/06_agent_starters.md
```

### Add a New MCP Tool
```bash
# TS server: add to mcp-servers/ts-mcp-server/src/tools/
# Py server: add to mcp-servers/py-mcp-server/ (check existing structure)
# Register in server's main file
# Rebuild TS: npm run build
# Restart: docker compose restart ts-mcp-server
```

### Run a Single Agent
```bash
curl -X POST http://localhost:8000/v1/agents/{agent_name}/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "your prompt here"}'
```

### Check Agent Knowledge
```bash
# Query transcript insights
curl "http://localhost:8000/v1/transcripts/insights?insight_type=decision&limit=10"

# Query learned knowledge directly from DB
docker compose exec postgres psql -U postgres -d agno_platform \
  -c "SELECT title, namespace FROM learned_knowledge ORDER BY created_at DESC LIMIT 10;"
```

### Reset One Service
```bash
docker compose restart agentos   # Agno control layer
docker compose restart ts-mcp-server  # TypeScript MCP
docker compose restart py-mcp-server  # Python MCP
docker compose restart postgres  # Database (resets data!)
docker compose restart n8n       # n8n workflows
```

### View Agent Logs
```bash
# Real-time logs
docker compose logs -f agentos

# Last 100 lines
docker compose logs --tail=100 agentos

# Since last restart
docker compose logs --since=10m agentos
```

## Files to Read Before Starting Work

1. `prompts/platform_context/03_porting_playbook.md` — Your task list
2. `prompts/platform_context/02_alpha_inventory.md` — What exists in old platform
3. `MCP_PLATFORM/GROUND_TRUTH.md` — Current platform specification
4. `MCP_PLATFORM/PARITY_MATRIX.md` — What's ported vs not
5. `MCP_PLATFORM/mcp-servers/*/TODO.md` — Per-server task lists

## Communication Protocol

You are working for Matt. He is non-technical but deeply knowledgeable about the litigation and the platform goals.

**When proposing work:**
1. State the problem in one sentence
2. State the solution in one sentence
3. List files you'll modify
4. Estimate effort
5. Flag any risks or blockers
6. Ask for approval before making changes

**When something is blocked:**
1. State what's blocked and why
2. Reference the open question ID (OQ-5, etc.)
3. Suggest what Matt needs to decide
4. Offer to work on something else while waiting

**When you discover something:**
1. Store it as learned_knowledge if it's a durable pattern
2. Store it as transcript_insight if it came from a chat
3. Update the project_pal with new context

## Your First Day Checklist

- [ ] All three repos cloned
- [ ] MCP servers build successfully
- [ ] Docker compose starts all services
- [ ] Health check returns healthy
- [ ] Can list agents via API
- [ ] Can run project_pal agent
- [ ] Read P0-1 porting task (Facebook parser)
- [ ] Read P0-2 porting task (iMessage parser)
- [ ] Read alpha inventory
- [ ] Propose P0-1 implementation plan to Matt
- [ ] Get approval
- [ ] Implement P0-1
- [ ] Test with sample data
- [ ] Commit and push
