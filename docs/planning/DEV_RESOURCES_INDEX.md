# dev-resources Index (scanned map — read this before re-crawling)

> **Purpose:** a static index of everything scanned under
> `the-platform-workspace/dev-resources/`, so future sessions reference this file
> instead of re-running `find`/`ls` (saves tool usage). `dev-resources` is
> **reference + a parts bin to port good code/tools from** — never code to revive.
> The active build lives in the sibling `agno-mvp/` (this project). The old
> `Agno-MCP-Platform/` repo is **abandoned**.
> **Noise note:** `Archives/` contains thousands of `Projects (N).xxh3` checksum
> files — ignore them all. **`OTHER_RESOURCES_TO_SORT/Secrets/` was NOT opened and
> must never be ingested.**
> Scanned: 2026-06-01.

---

## Top level: `dev-resources/`
```
Agno MCP Platform MVP Handoff Guide.txt
HANDOFF_INSTRUCTIONS.md
Archives/                  ← all the iterations (below)
upstream-resources/        ← the clean Agno skeleton (the build base)
(loose .txt notes, table-1779745754350.csv)
```

---

## ⭐ `upstream-resources/agno-agent-platform/`  — THE BUILD BASE (copied into agno-mvp)
Canonical Agno AgentOS docker-template, already customized with all 7 agents. **This
is what `agno-mvp/` was seeded from.**
```
agents/   ingestion_orchestrator.py  analysis_orchestrator.py  review_gatekeeper.py
          transcript_miner.py  dev_copilot.py  project_pal.py  forensic_data_agent.py
          instructions.py  __init__.py
app/      main.py  settings.py  config.yaml  __init__.py
db/       __init__.py  session.py  url.py            (get_postgres_db pattern)
evals/    __main__.py  cases.py  dotenv.py  __init__.py   (runnable: python -m evals)
docs/     create-new-agent.md  extend-agent.md  improve-agent.md
          eval-and-improve.md  review-and-improve.md
scripts/  generate_requirements.sh  entrypoint.sh  build_image.sh  validate.sh
          venv_setup.sh  format.sh  railway/{env-sync,redeploy,up}.sh
root:     compose.yaml  Dockerfile  pyproject.toml  requirements.txt  example.env
          README.md  AGENTS.md  CLAUDE.md  .mcp.json  railway.json  LICENSE
          .github/workflows/validate.yml  .dockerignore  .gitignore
note:     ships a real .env (secrets) — NOT copied into agno-mvp.
```

---

## `Archives/` — the iterations

### ⭐ `MCP_PLATFORM/`  — CANONICAL modular MCP servers (vendor these)
The "current repo" per the handoff. **Source of the live tools the agents orchestrate.**
```
mcp-servers/
  ts-mcp-server/   (TypeScript — ingest/parse/custody)
    src/tools/  AdminTools.ts  constants.ts  DuckDbVault.ts  EvidenceIngestor.ts
                FacebookExportParser.ts  ImessagePdfParser.ts  MessageChunker.ts
                Pass1Runner.ts  PostgresWriter.ts  ReviewQueue.ts  SbvClient.ts
                SbvIngestor.ts  SmsEvidenceIngestor.ts  SmsXmlParser.ts  SmsXmlReader.js
    src/services/ DuckDbService.ts
    src/index.ts  package.json  tsconfig.json  README.md  AGENTS.md  INDEX.md  TODO.md  memory/
  py-mcp-server/   (Python — analysis/doc-intelligence/forensic crypto)
    src/document_intelligence/  base.py  engine_registry.py  models.py  router.py  mcp_tools.py
      engines/  aws_textract  docling  doctr  glm_ocr  google_docai  ibm_watsonx
                llamaparse  ocropus  pandoc  tesseract  unstructured
    src/tools/  audit_hooks.py  dpk_tools.py  evidence_signing.py  hash_verification.py
                sqlite_wal_parser.py  user_detection.py  voice_tools.py  workflow_tools.py
    src/server.py  src/utils/timezone_utils.py  requirements.txt  README.md  INDEX.md  TODO.md  memory/
  js-mcp-server/   (minimal — optional "ping")  src/index.js  package.json
other dirs: client/ docs/ infrastructure/ migrations/ scripts/ memory/ dial-stack/
            _DEPRECATED/ _local_archive/  + AGENTS.md INDEX.md TODO.md
```

### `dial-stack/`  — OLDER SUBSET of the modular servers (not canonical; diff/history only)
```
mcp-servers/ts-mcp-server/src/tools/  AdminTools  DuckDbVault  FacebookExportParser
   ImessagePdfParser  PostgresWriter  ReviewQueue  SmsEvidenceIngestor  SmsXmlParser
   (MISSING vs MCP_PLATFORM: EvidenceIngestor, MessageChunker, Pass1Runner, Sbv*, DuckDbService)
mcp-servers/py-mcp-server/src/tools/  (same 8 as MCP_PLATFORM)
also: client/ docs/ infrastructure/ migrations/ tools/ utilities/ memory/ core-logs/
      + .claude/ .planning/ .codex/ .cursor/ etc.
```

### ⭐ `MCP_Tool_Platform-REF-READ-ONLY/`  — THE ALPHA MONOLITH (port-from backlog)
The alpha repo; far more capability than the modular servers yet expose. Dev Copilot
ports these into the modular ts/py servers, one capability at a time.
```
server/mcp/
  forensics/      behavior-service  chain-custody  forensics-router  hurtlex-fetcher
                  hurtlex-stream  identity-service  pattern-analyzer  timeline-generator
  analysis/       classifier  conversation-segmentation  multi-pass-classifier  priority-screener
  ingest/         archive-handler  coordinator  forensicHasher  format-detection
                  validation  watcher  index  types
  orchestration/  forensic-workflow  langchain-memory  langgraph-adapter  sub-agents
  pipelines/      document-pipeline  end-to-end-pipeline  production-pipeline
  hitl/ approval     export/ pipeline     tools/ sbv-mcp-tools
  (dirs) auth chroma config graphql llm loaders observability prompts proxy queue
         realtime schemas stats storage store utils wiki workers plugins plugins-pending forking
server/  api/{copilotkit,routers}  core/types  database/migrations  drizzle/
also: client/ config/ cosmo/ data/ deploy/ Docker/ docs/ Evidence_Analysis/ init/ lib/
      memory/ n8n-workflows/ plans/ services/ shared/ utilities/ workflows/ _to_review/ archive/
```

### `MCP_Tool_Platform/` and `mcp-tool-platform/`  — alpha sibling snapshots (history)
Same lineage, different snapshots. Each: `server/ client/ drizzle/ n8n-workflows/
salem-trinity-deployment/ Docker/ config/ data/ deploy/ docs/ scripts/ shared/ utilities/`.
`mcp-tool-platform/` also has `.manus/ .github/ patches/`.

### `TheBigOne/`  — mega-monorepo bundling everything (most complete bundle)
```
00_Documentation/  AI_Firm_Strategy  Context_Files  Deployment_Artifacts
                   STACK_Deployment  System_Guides
01_MCP_Tool_Platform_Repo/   (alpha: analysis client config data deploy Docker docs
                              drizzle n8n-workflows patches scripts server shared utilities)
02_TraceIQ_Repo/   forensic_tools  location-admin  TraceIQ_Main  TraceIQ_Snippets  20260106033151884
02_Voice_Analysis/ Chronicle_Voice_App  Context_Analysis_Suite  story-voice-backend
03_Evidence_Analysis/ ConflictAnalysisApp  forensic-data-refinery
ai-dial/  graphql-eslint/  fefe/  archive/  memory/  TraceIQ/
+ .agents/skills  .claude/{plans,memories,evidence,traces,...}  .planning/codebase  .logs
```

### `Evidence_Analysis/`   ConflictAnalysisApp/ · forensic-data-refinery/
### `Voice_Analysis/`      Chronicle_Voice_App/ (package.json) · Context_Analysis_Suite/ · story-voice-backend/ (SETUP.md)

### `OTHER_RESOURCES_TO_SORT/`  — ChatMiner ancestors + misc (port good parsers/chunkers)
```
Chunker_from_External_Utils_Lib/  chunkers/{base,smart}.py  exporters/{json,txt,zip}.py  main.py
                                  Chat_Parsers_Tools/ (JSON_SPLITTER, PARSER_QUICK_REFERENCE, session_export)
Chunker_from_Satellite_Tools/     chunkers/{base,smart}.py  exporters/*  main.py   (dup of above)
ConversationExtractor_from_Gemini_Debris/    AndroidMsgParser.py  FacebookParser.py
                                             ConversationExtractorModule.py  fpdf/
ConversationExtractor_from_Satellite_Tools/  (same set)            Tools/ConversationExtractor/ (+util.py)
Tools/  Chat_Parsers/ (chatgpt_parser, chat_history_processor_plan, JSON_SPLITTER, ...)
        Chunker/main.py   ConversationExtractor/
Context analysis extraction apps/  chronicle_-empathetic-timeline-investigator/  forensic-video-analyzer/
TraceIQ/   Workbench/ (COMPLETE_SCHEMA_PARSER_INVENTORY.md, COMPLETE_SALEM_v_KINZEL_FULL_EXTRACTION.md,
           COPILOTKIT_IMPLEMENTATION_PLAN.md, many case + planning .md)
MCP dupes (reference): MCP_langextract-mcp-main_dupe  MCP_NLP_Document-Analyser-MCP_dupe
           MCP_notebooklm-skill-master_junk  MCP_pandoc_wizard_dupe  MCP_UNS-MCP-main_dupe
AI_Config/  Case/  Context_History/  _extracted_mineru/  _project_dirs_loose/
⚠ Secrets/  — DO NOT OPEN / DO NOT INGEST
```

---

## Canonical-source quick map (where "good code/tools" come from)
| Need | Take from |
|---|---|
| App skeleton | `upstream-resources/agno-agent-platform` (already copied → agno-mvp) |
| Modular MCP tool servers | `Archives/MCP_PLATFORM/mcp-servers` (vendor ts/py/js) |
| Tools still to port | `Archives/MCP_Tool_Platform-REF-READ-ONLY/server/mcp` (alpha monolith) |
| Chat parsers/chunkers | old repo `chatminer/` + ancestors in `OTHER_RESOURCES_TO_SORT` (review, then port) |
| Domain apps (TraceIQ/Evidence/Voice) | `Archives/TheBigOne` (Knowledge/Workspace nav only) |

## Re-scan only if needed
- Per-iteration deep dives: each MCP server has its own `INDEX.md` / `AGENTS.md` / `TODO.md` — read those first.
- Existing inventories already written by the owner: `OTHER_RESOURCES_TO_SORT/Workbench/COMPLETE_SCHEMA_PARSER_INVENTORY.md`.
