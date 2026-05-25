# MCP Forensic Evidence Platform

## What This Is

A forensic evidence platform for litigation (Salem v. Kinzel). It ingests digital evidence — text messages, Facebook chats, iMessage exports — analyzes them with AI, and produces court-admissible output with full chain of custody.

**Three software projects work together:**

| Project | What It Does | Repository |
|---------|-------------|------------|
| **This project** (Agno Control Layer) | The brain — AI agents that orchestrate everything | `mcp-platform-agno-mvp` |
| **MCP_PLATFORM** (Modular Servers) | The hands — tools that parse, analyze, and store evidence | `MCP_PLATFORM` |
| **mcp-tool-platform** (Alpha) | The legacy — older working tools being moved to MCP_PLATFORM | `mcp-tool-platform` |

## The Big Picture

```
You (Matt) talk to AI agents --> Agents use tools --> Tools process evidence --> Evidence goes to court
```

### 7 AI Agents

**Platform Agents (run the evidence pipeline):**
- **Ingestion Orchestrator** — Takes your evidence files, figures out what parser to use, hashes everything with SHA-256, normalizes data, logs chain of custody
- **Analysis Orchestrator** — Runs NLP analysis on ingested evidence, finds patterns, builds knowledge graphs, detects behavioral anomalies
- **Review Gatekeeper** — Every time an agent wants to change something, this agent asks you for approval first
- **Transcript Miner** — Reads through your AI chat transcripts, extracts decisions, code, goals, blockers — so other agents don't waste context on raw chat logs

**Builder Agents (help build the platform):**
- **Dev Copilot** — Reads both old and new code, proposes how to move tools from alpha to current, generates implementation plans
- **Project PAL** — Your personal assistant, remembers goals, blockers, what we decided, what's next
- **Forensic Data Agent** — Explains database schemas, helps write safe queries, remembers which queries work

### Integration with n8n (Workflow Automation)

This platform connects bidirectionally with n8n — a visual workflow automation tool with 400+ app integrations.

**What n8n adds:**
- Connect evidence pipeline to external services (Slack notifications, email alerts, calendar triggers)
- Visual workflow builder for non-technical evidence processing steps
- Webhook triggers — external systems can trigger evidence ingestion
- Schedule automation — run analysis jobs on a timer

**How they connect:**
- **Direction 1: Agno calls n8n** — When evidence is ingested, Agno agents trigger n8n workflows to send notifications or update external systems
- **Direction 2: n8n calls Agno** — n8n workflows trigger Agno agents to start ingestion, run analysis, or check status
- **Protocol: MCP (Model Context Protocol)** — Both platforms speak the same language, no custom glue code needed

### Storage Architecture

```
Local (Docker):
  PostgreSQL + pgvector — all operational data, embeddings, approvals
  DuckDB — forensic vault with SHA-256 chain of custody
  LanceDB — vector embeddings for semantic search
  Neo4j — knowledge graphs (entities, relationships)

Cloud (Cloudflare R2):
  Evidence file archive — original exports stored securely
  Analysis output archive — reports, timelines, exports
  Cross-platform sync — accessible from any location
```

## Quick Start (If Someone Else Set This Up For You)

```bash
# 1. Copy the environment template
cp .env.example .env

# 2. Edit .env with your API keys
nano .env   # or any text editor

# 3. Start everything
docker compose up -d

# 4. Check it's working
curl http://localhost:8000/health

# 5. Open the web interface
# http://localhost:8000/docs  (API documentation)
# http://localhost:5678       (n8n workflow builder)
```

## File Structure

```
mcp-platform-agno-mvp/
│
├── README.md                           # This file
├── DEPLOYMENT_GUIDE.md                 # Detailed deployment instructions
├── DEVELOPER_HANDOFF.md                # Instructions for the developer agent
├── HANDOFF_INSTRUCTIONS.md             # Original architecture specification
├── docker-compose.yml                  # All services (Postgres, Agno, MCP servers, n8n)
├── Dockerfile                          # How the Agno container is built
├── .env.example                        # Template for environment variables
├── .gitignore                          # Files Git should ignore
├── requirements.txt                    # Python dependencies
│
├── app/
│   ├── __init__.py
│   └── main.py                         # FastAPI web server, API routes, authentication
│
├── agents/
│   ├── __init__.py
│   ├── factory.py                      # Creates all 7 agents with their tools
│   └── instructions.py                 # What each agent can and cannot do
│
├── config/
│   ├── __init__.py
│   └── settings.py                     # Database URLs, API keys, model selection
│
├── lib/
│   ├── __init__.py
│   └── chunking.py                     # Smart transcript splitting logic
│
├── prompts/
│   ├── system_prompts.yaml             # System prompt templates for all agents
│   └── platform_context/               # Agent starter pack — pre-loaded knowledge
│       ├── 01_architecture_overview.md
│       ├── 02_alpha_inventory.md       # 67 tools from old platform
│       ├── 03_porting_playbook.md      # What to port, in what order
│       ├── 04_open_questions.md        # Decisions that need to be made
│       ├── 05_decision_log.md          # What's already been decided
│       └── 06_agent_starters.md        # Each agent's first tasks
│
├── scripts/
│   ├── ingest_knowledge.py             # Load documents into the knowledge base
│   └── mine_transcripts.py             # Batch-process chat transcripts
│
├── sql/
│   └── schema.sql                      # Database tables (runs automatically on startup)
│
├── tests/                              # Test suite (not yet running)
│   ├── e2e/
│   ├── integration/
│   └── unit/
│
└── ui/
    └── review_schema.ts                # TypeScript types for the review UI
```

## What's Working Now

| Feature | Status | Notes |
|---------|--------|-------|
| SMS XML ingestion | Working | End-to-end: parse, hash, store, analyze |
| Semantica NLP (entity extraction) | Working | Python MCP server |
| Vector search (LanceDB) | Working | Semantic search on embeddings |
| HITL approval workflow | Working | Review queue with approve/reject |
| Knowledge graph (Neo4j) | Configured | Empty — needs data |
| Transcript mining | Working | Extracts structured insights from chat logs |
| Docker infrastructure | Working | Postgres, Agno, MCP servers, n8n |
| Facebook parser | Code exists | **Blocked — needs your approval to activate** |
| iMessage parser | Stub | **Needs porting from old platform** |
| Security audit | Fixed | Path traversal, auth, DB pooling all resolved |

## What's Coming Next

See `prompts/platform_context/03_porting_playbook.md` for the full task list.

**Immediate (P0):**
1. Activate Facebook parser (code exists, just needs a 6-line change)
2. Port iMessage PDF parser from old platform
3. Merge message schemas between old and new platforms

**Next (P1):**
4. Port behavioral pattern analyzer
5. Port HurtLex abusive language detection
6. Port timeline generator
7. Activate Pandoc document conversion
8. Activate Tesseract OCR

**After that (P2):**
9. Build test suite
10. Implement hybrid search
11. Connect n8n workflows

## 8 Decisions That Need You

See `prompts/platform_context/04_open_questions.md` for full details. Quick summary:

1. **Embedding model** — Which AI model for text embeddings? (Recommendation: start small, upgrade later)
2. **Internal API style** — REST, GraphQL, or gRPC? (Recommendation: HTTP/SSE for now)
3. **Cloud AI services** — Allow any cloud processing of evidence? (Recommendation: No — court evidence stays local)
4. **Multi-tenancy** — How to separate multiple cases? (Recommendation: schema-per-case)
5. **Evidence retention** — How long to keep data? (Recommendation: raw forever, derived case+2 years)
6. **Frontend** — Pure React or AI-native components? (Recommendation: Pure React first)
7. **Testing** — Integration tests, unit tests, or both? (Recommendation: Integration tests for parsers first)
8. **OpenCode integration** — Automated coding agent? (Recommendation: Yes, with mandatory approval)

## n8n Workflow Ideas

Once connected, you can build workflows like:

- **Evidence Alert** — New evidence ingested --> Slack notification --> Calendar event created
- **Weekly Analysis** — Every Monday --> Run pattern analysis --> Email summary
- **Approval Reminder** — Approval pending >1 hour --> Text message to you
- **Export Pipeline** — Case marked complete --> Generate court-ready export --> Upload to R2
- **Transcript Digest** — New chat transcript saved --> Mine for insights --> Update project status

## Important URLs

| URL | What It Is |
|-----|-----------|
| http://localhost:8000/docs | API documentation (Swagger UI) |
| http://localhost:8000/health | Health check — is everything running? |
| http://localhost:5678 | n8n workflow builder |
| https://github.com/Cursedpotential/mcp-platform-agno-mvp | This repo |
| https://github.com/Cursedpotential/MCP_PLATFORM | Modular MCP servers |
| https://github.com/Cursedpotential/mcp-tool-platform | Old platform (alpha) |

## Support

If something breaks:
1. Check `docker compose ps` — are all containers running?
2. Check `docker compose logs` — any error messages?
3. Check `http://localhost:8000/health` — is the API responding?
4. Read `DEVELOPER_HANDOFF.md` — technical troubleshooting
5. Ask the **Project PAL** agent — it knows the current state and blockers
