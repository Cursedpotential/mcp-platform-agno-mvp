# Tool Sources Inventory — `dev-resources/` crawl

> **Why this exists:** `dev-resources/` is **where all the final tools are sourced from**. The Agno MVP
> is the **builder/control layer whose job is to finish consolidating the iterations already started
> here** — port the alpha monolith's tools into the modular MCP servers, unify the duplicated
> chunkers/extractors into ChatMiner, and orchestrate the whole evidence pipeline. This file maps every
> tool source, marks the **canonical** one per family, and points each at the MVP agent that will drive it.
> **Crawl method:** directory + source-file listing (the thousands of `.xxh3` files are checksum noise,
> excluded). `osgrep` is available for semantic follow-ups. `Secrets/` was **not** opened.

---

## 0. The one-line shape

```
upstream-resources/agno-agent-platform   = the MVP SKELETON to build on (already has the 7 agents)
Archives/MCP_PLATFORM/mcp-servers        = CANONICAL modular tool servers (ts + py + js)  ← orchestrate these
Archives/MCP_Tool_Platform-REF-READ-ONLY = the ALPHA monolith = the big pool of tools still to PORT
Archives/dial-stack/mcp-servers          = older SUBSET of the modular servers (not canonical)
OTHER_RESOURCES_TO_SORT/{Chunker,ConversationExtractor,Tools} = ChatMiner's ancestors (parsers/chunkers)
Archives/TheBigOne + Evidence_Analysis + Voice_Analysis + TraceIQ = the wider platform's domain apps
```

---

## 1. THE BUILD SKELETON — `upstream-resources/agno-agent-platform/`

This is the canonical Agno **agentos-docker-template**, already customized to this project. It is almost
certainly the source the reference `agents_factory.py` / `agents_instructions.py` were derived from, and
it is the **strongest base to build the MVP on** (stronger than the current repo).

Already present:
- `agents/`: `ingestion_orchestrator.py`, `analysis_orchestrator.py`, `review_gatekeeper.py`,
  **`transcript_miner.py`**, `dev_copilot.py`, `project_pal.py`, `forensic_data_agent.py`, `instructions.py`
  → **answers the earlier gap: `transcript_miner` exists here as its own module.**
- `app/`: `main.py`, `settings.py`, `config.yaml`
- `db/`: `__init__.py`, `session.py`, `url.py`  (the `get_postgres_db()` pattern)
- `evals/`: `__main__.py`, `cases.py`, `dotenv.py`  (the dash-style eval harness, runnable)
- `compose.yaml`, `Dockerfile`, `pyproject.toml`, `requirements.txt`, `example.env`
- `scripts/`: `generate_requirements.sh`, `entrypoint.sh`, `build_image.sh`, `validate.sh`, `venv_setup.sh`, `railway/*`
- `docs/`: `create-new-agent.md`, `extend-agent.md`, `improve-agent.md`, `eval-and-improve.md`, `review-and-improve.md`
- `.mcp.json`, `AGENTS.md`, `CLAUDE.md`, `.github/workflows/validate.yml`, `railway.json`

> **Migration impact:** this likely **replaces "scaffold from scratch"** in MIGRATION_PLAN_v8.md §2/§4.
> Decision for the owner: **build the MVP by copying this skeleton in** (then port ChatMiner + wire the
> real MCP servers + add cloud), rather than hand-rebuilding the scaffold. Big time saver. Confirm whether
> the reference `factory.py`/`instructions.py` supersede this dir's per-agent modules or complement them.

---

## 2. CANONICAL MODULAR TOOL SERVERS — `Archives/MCP_PLATFORM/mcp-servers/`

The "current repo" the handoff's Dev Copilot references. **These are the tools the platform agents
orchestrate today.** Recommend **vendoring this iteration** into the MVP repo under `mcp-servers/`.

### `ts-mcp-server` (TypeScript) — ingestion/parsing/custody  → **Ingestion Orchestrator**
| Tool file | Capability |
|---|---|
| `SmsXmlParser` / `SmsXmlReader` / `SmsEvidenceIngestor` | Android SMS Backup XML parse + ingest |
| `FacebookExportParser` | Facebook Messenger HTML export parse |
| `ImessagePdfParser` | iMessage PDF parse |
| `MessageChunker` | message chunking |
| `EvidenceIngestor` | generic evidence ingestion |
| `DuckDbVault` / `DuckDbService` | forensic vault (SHA-256 custody) on DuckDB |
| `PostgresWriter` | normalized record writes to Postgres |
| `ReviewQueue` | HITL review queue |
| `Pass1Runner` | first-pass processing |
| `SbvClient` / `SbvIngestor` | SBV (sub-band/voice?) client + ingest |
| `AdminTools` / `constants` | admin/util |

> **Note vs handoff §3.1 "no DuckDB anywhere":** that rule is about the *Agno* stack. The **TS MCP
> server uses DuckDB internally** for the forensic vault — the Agno layer just calls it as a black-box
> tool, so there's no contradiction. Flag for the owner only if you intend to migrate the vault to PG.

### `py-mcp-server` (Python) — analysis/document-intelligence/forensic crypto  → **Analysis Orchestrator + Forensic Data Agent**
| Tool group | Files |
|---|---|
| **Document Intelligence** (10 engines + router) | `aws_textract`, `docling`, `doctr`, `glm_ocr`, `google_docai`, `ibm_watsonx`, `llamaparse`, `ocropus`, `pandoc`, `tesseract`, `unstructured`; `router.py`, `mcp_tools.py`, `models.py`, `engine_registry.py` |
| **Forensic crypto / custody** | `hash_verification`, `evidence_signing`, `audit_hooks` |
| **Parsers / data** | `sqlite_wal_parser`, `dpk_tools`, `user_detection` |
| **Voice** | `voice_tools` |
| **Workflow** | `workflow_tools` |

### `js-mcp-server` (JavaScript) — minimal
Just `src/index.js` (the optional "ping"-class server; connect only if it grows useful tools, per handoff).

### `Archives/dial-stack/mcp-servers/` — **older subset** (NOT canonical)
Has the same py 8-tool set and a *reduced* ts set (no EvidenceIngestor / MessageChunker / Pass1Runner /
Sbv* / DuckDbService). Use **MCP_PLATFORM** instead; keep dial-stack only for diff/history.

---

## 3. THE ALPHA MONOLITH (the big port-from pool) — `Archives/MCP_Tool_Platform-REF-READ-ONLY/server/mcp/`

This is the **alpha repo** the Dev Copilot is meant to help port into the modular servers. It's a
monolithic MCP with far more capability than the modular ts/py servers yet expose — **this is the
"finish building it out" backlog**. Capability domains and their tool files:

| Domain (`server/mcp/<dir>`) | Notable tools |
|---|---|
| `forensics/` | `behavior-service`, `chain-custody`, `forensics-router`, `hurtlex-fetcher`, `hurtlex-stream`, `identity-service`, `pattern-analyzer`, `timeline-generator` |
| `analysis/` | `classifier`, `conversation-segmentation`, `multi-pass-classifier`, `priority-screener` |
| `ingest/` | `archive-handler`, `coordinator`, `forensicHasher`, `format-detection`, `validation`, `watcher` |
| `orchestration/` | `forensic-workflow`, `langchain-memory`, `langgraph-adapter`, `sub-agents` |
| `pipelines/` | `document-pipeline`, `end-to-end-pipeline`, `production-pipeline` |
| `hitl/` | `approval` |
| `export/` | `pipeline` |
| `tools/` | `sbv-mcp-tools` |
| others (dirs) | `auth`, `chroma` (vector), `config`, `graphql`, `llm`, `loaders`, `observability`, `prompts`, `proxy`, `queue`, `realtime`, `schemas`, `stats`, `storage`, `store`, `utils`, `wiki`, `workers`, `plugins`, `plugins-pending`, `forking`, `realtime` |

Sibling snapshots of the same alpha lineage (for diff/history, not canonical):
`Archives/MCP_Tool_Platform/`, `Archives/mcp-tool-platform/` (each: `server/`, `client/`, `drizzle/`,
`n8n-workflows/`, `salem-trinity-deployment/`, `Docker/`).

> **Builder mission, concretely:** Dev Copilot's recurring job = take a capability from this monolith
> (e.g. `forensics/pattern-analyzer`, `analysis/multi-pass-classifier`, `ingest/format-detection`) and
> port it into the modular `ts-mcp-server` / `py-mcp-server`, then register it for the Agno agents. The
> alpha already has an `hitl/approval` and `forensics/chain-custody` — useful references for the MVP's
> own approval + custody guarantees.

---

## 4. CHATMINER'S ANCESTORS — `Archives/OTHER_RESOURCES_TO_SORT/`

The current repo's `chatminer/` + `lib/chunking.py` descend from these. Useful for filling parser/chunker
gaps and for the dedupe (multiple copies of the same code):
- **Chunkers:** `Chunker_from_External_Utils_Lib/chunkers/{base,smart}.py` + `exporters/{json,txt,zip}.py`;
  `Chunker_from_Satellite_Tools/...` (same); `Tools/Chunker/main.py`. → ancestors of `lib/chunking.py`.
- **Conversation extractors:** `ConversationExtractor_from_{Gemini_Debris,Satellite_Tools}/`
  (`AndroidMsgParser.py`, `FacebookParser.py`, `ConversationExtractorModule.py`, bundled `fpdf/`);
  `Tools/ConversationExtractor/`. → parser ancestors (SMS/Facebook).
- **Chat parser docs/inventory:** `Tools/Chat_Parsers/` (chatgpt_parser, JSON_SPLITTER, PARSER_QUICK_REFERENCE);
  `Workbench/COMPLETE_SCHEMA_PARSER_INVENTORY.md` (an existing parser inventory — read before re-inventorying),
  `Workbench/COMPLETE_SALEM_v_KINZEL_FULL_EXTRACTION.md` (case extraction output).
- **MCP dupes (reference only):** `MCP_langextract-mcp-main_dupe`, `MCP_NLP_Document-Analyser-MCP_dupe`,
  `MCP_notebooklm-skill-master_junk`, `MCP_pandoc_wizard_dupe`, `MCP_UNS-MCP-main_dupe`.
- **Apps:** `Context analysis extraction apps/` (`chronicle_-empathetic-timeline-investigator`,
  `forensic-video-analyzer`), `TraceIQ/`, `Workbench/` (many case + planning docs incl. CopilotKit plans).
- ⚠️ **`Secrets/`** — present; **not opened**. Treat as out-of-bounds; never ingest into Knowledge or logs.

---

## 5. THE WIDER PLATFORM (the "finish building" target) — domain apps

- **`Archives/TheBigOne/`** — mega-monorepo bundling everything: `01_MCP_Tool_Platform_Repo` (alpha),
  `02_TraceIQ_Repo` (`forensic_tools`, `location-admin`, `TraceIQ_Main`, `TraceIQ_Snippets`),
  `02_Voice_Analysis`, `03_Evidence_Analysis`, `ai-dial`, and `00_Documentation`
  (`AI_Firm_Strategy`, `STACK_Deployment`, `System_Guides`, `Context_Files`, `Deployment_Artifacts`).
- **`Archives/Evidence_Analysis/`** — `ConflictAnalysisApp`, `forensic-data-refinery`.
- **`Archives/Voice_Analysis/`** — `Chronicle_Voice_App` (has `package.json`), `Context_Analysis_Suite`,
  `story-voice-backend` (has `SETUP.md`).
- **TraceIQ** — location/forensic tooling (forensic_tools, location-admin).

These are the larger evidence platform's pieces the MVP ultimately helps assemble (Semantica bootstrap,
handoff §17). For the MVP they are **Knowledge/Workspace sources to navigate**, not things to run yet.

---

## 6. Canonical-source decisions (so "the final tools" have one home)

| Tool family | Canonical source | Action |
|---|---|---|
| MVP app skeleton | `upstream-resources/agno-agent-platform` | Build the MVP from this (copy in) |
| Modular MCP servers (ts/py/js) | `Archives/MCP_PLATFORM/mcp-servers` | **Vendor** into MVP `mcp-servers/` |
| Tools still to port | `Archives/MCP_Tool_Platform-REF-READ-ONLY/server/mcp` | Dev Copilot ports → modular servers, one capability at a time |
| Chat parsers/chunkers | current repo `chatminer/` (+ ancestors in OTHER_RESOURCES) | Keep ChatMiner; backfill gaps from ancestors; dedupe |
| Domain apps (TraceIQ/Evidence/Voice) | `Archives/TheBigOne` (most complete bundle) | Knowledge/Workspace navigation sources only (for now) |

---

## 7. Recommended updates to MIGRATION_PLAN_v8.md (pending owner OK)
1. **Reframe the build base:** start from `agno-agent-platform` (copy-in) instead of scaffolding from
   scratch; the current repo's custom assets (ChatMiner, prompts, approval routes) port *onto* it.
2. **Add a standing "porting backlog" workstream** (the Dev Copilot mission): alpha monolith → modular
   ts/py servers, capability by capability, each behind the approval gate. This is the MVP's reason to exist.
3. **Vendor `MCP_PLATFORM/mcp-servers`**; keep `dial-stack` only for diff.
4. **Mark `Secrets/` and case-data dirs as never-ingest** in the ingestion allowlist (privacy).
5. **Confirm reference `factory.py`/`instructions.py` vs `agno-agent-platform/agents/*` precedence.**
```
