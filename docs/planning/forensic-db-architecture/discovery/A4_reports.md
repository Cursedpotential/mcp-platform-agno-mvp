# A4 — Existing-Reports Harvest (forensic DB architecture discovery)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Mandate: lean into prior scan reports/indexes instead of re-scanning blind; verify freshness; flag blind spots.
> Today = 2026-06-30. "Date" below = content/compiled date; "mtime" = file last-modified (when it differs, file was just copied/moved, not re-authored).

---

## 1. What each prior report documents + freshness verdict

| # | Report (path) | Content date / mtime | Documents (tools / schemas / parsers / gaps) | Freshness |
|---|---|---|---|---|
| R1 | `Agno-MCP-Platform/docs/planning/DEV_RESOURCES_INDEX.md` | scanned 2026-06-01 / mtime 06-10 | Static map of ALL of `dev-resources/`: upstream Agno skeleton (7 agents), canonical modular MCP servers (`MCP_PLATFORM/mcp-servers` ts+py+js), alpha monolith (`MCP_Tool_Platform-REF-READ-ONLY`), dial-stack subset, TheBigOne, ChatMiner ancestors. Canonical-source map. | **CURRENT** (most recent, authored for this workspace). Note: header calls `Agno-MCP-Platform/` "abandoned" and points to a sibling `agno-mvp/` — that naming is **stale vs current canon** (active repo is `Agno-MCP-Platform/`). Treat layout as accurate, repo-status line as outdated. |
| R2 | `Agno-MCP-Platform/docs/planning/TOOL_SOURCES_INVENTORY.md` | 2026-06-01 / 06-10 | Per-family tool source inventory w/ canonical pick + which Agno agent drives it. ts-mcp tools (SMS/FB/iMessage parsers, DuckDbVault, PostgresWriter, ReviewQueue, Pass1Runner, Sbv*). py-mcp 10 doc-intel engines + forensic crypto (hash_verification, evidence_signing, sqlite_wal_parser). Alpha monolith capability domains. | **CURRENT.** Best single map of tool→source→canonical. Same `agno-mvp` naming caveat as R1. |
| R3 | `Agno-MCP-Platform/docs/wiki/INDEX.md` | 2026-03-12 / 06-10 | dial-stack architecture reference: 4-tier DB stack (**DuckDB→PostgreSQL/pgvector→Neo4j→LanceDB**), Dragonfly cache, Semantica NLP, FastMCP, Cosmo GraphQL fed, Keycloak, IBM ContextForge gateway, 6 parsers + doc-processing utils, MCP tool counts (ts=18, py=22, js=1+4). | **AGING.** Architecture intent still largely valid but predates infra reconciliation (Milvus-over-Lance ADR-0026, FerretDB/Dragonfly substitution mandate, live OVH/Coolify topology). Use for component intent, verify each DB against current ADRs. |
| R4 | `Agno-MCP-Platform/docs/wiki/tools/INDEX.md` | 2026-03-15 / 06-10 | 13-tool wiki: MCP servers (Document-Analyser, LangExtract, Stirling-PDF, UNS-MCP, MCP-NLTK), forensic tools (ExifTool 12.69, Snaparser, Epoch 2.2), AI-workspace tools (Smart Chunker, Conversation Extractor, Directory Scanner Pro, Manipulative Expression Recognition, NLP Toxicity Analyzer). By language/framework. | **AGING.** External/3rd-party tool catalog; tools stable, but "production ready" status is aspirational. Good for tool discovery, not current wiring state. |
| R5 | `dev-resources/.../Case/COMPLETE_SCHEMA_PARSER_INVENTORY.md` **≡ DUP of** `.../Workbench/COMPLETE_SCHEMA_PARSER_INVENTORY.md` | compiled 2026-01-06 / mtime 02-19 | **THE schema/parser SSOT.** 8 messaging platforms (SMS/MMS, FB, WhatsApp, Snapchat, Instagram, iMessage, Email, Photos-OCR) w/ field schemas + parser regex + gotchas. Full Supabase messaging schema (messaging_documents/conversations/messages/attachments/behaviors + evidence/factor_citation/timeline tables). Google Timeline schema (timeline_events/waypoints). detection_patterns.py (256-pattern classifier, MCL A–L, 18 behavior categories). | **AGING but authoritative on data model.** Compiled from chat scan Jan 6; richest forensic-DB reference. Caveats: targets **Supabase/pgvector/PostGIS** (project since moved to self-hosted PG + Milvus + R2/DuckDB); some parsers "DEFINED NOT BUILT". Two copies byte-identical → dedupe to one. |
| R6 | `dev-resources/.../Workbench/STATUS_REPORT_2026-01-29.md` | 2026-01-29 | Alpha "MCP Tool Platform" status: 85% complete, 46k LOC server + 28 plugins. Gateway API, plugin ecosystem (doc/NLP/vector/graph/forensics), storage (Chroma/Graphiti/Directus/PG/Neo4j), HITL approval backend, multi-agent orchestration, LLM provider hub, Python bridge. Gaps = mostly frontend/viz. | **STALE (status), USEFUL (inventory).** Completion % and "production ready" claims 5 mo old; describes the *alpha monolith* now slated for porting (per R2), not the live stack. Use for "what exists to port." |
| R7 | `dev-resources/.../_project_dirs_loose/AUDIT_REPORT.md` | 2026-01 (Manus AI) / mtime 01-29 | Codebase audit of "MCP Tool Shop": **critical placeholders** (smart-router returns "Placeholder response"; ML embeddings fall back to TF-IDF; config in-memory only). Missing forensic DB tables (behavioralPatterns, hurtlexTerms, mclFactors, forensicResults...). Forensics pipeline 0% at that time. | **STALE.** Early alpha snapshot (checkpoint c41e4bb3) contradicted by R6 (which says forensics done). Value: checklist of known-bad placeholders & missing tables to verify fixed. |
| R8 | `dev-resources/.../_project_dirs_loose/COMPREHENSIVE_GAP_REPORT.md` | 2026-01 / mtime 01-29 | Tool-executor gap matrix: ~40% implemented / 60% registered-not-wired. 20 working executors vs 50+ unwired (vector.*, graph.*, mem0.*, n8n.*, browser.*, forensics.*, py/js libs). Missing doc-intelligence tables (sections/chunks/spans/entities/findings/approvals). | **STALE** (same alpha era as R7). Useful as "registered-but-not-wired" backlog checklist. |
| R9 | `dev-resources/.../_project_dirs_loose/MCP_TOOL_CATALOG.md` | 2026-01 / mtime 01-29 | Designed tool catalog (intended API surface): ocr.*, screenshot.*, content.*, image.*, forensics.*, llm.*, document.*, schema.*, workflow.* with standard response envelope. | **AGING (design spec).** Aspirational tool contract, not as-built. Good for naming/contract conventions. |
| R10 | `dev-resources/.../TheBigOne/02_TraceIQ_Repo/FORENSIC_ANALYSIS_REPORT.md` | 2026-01-06 / mtime 05-25 | TraceIQ codebase forensics: 3 mixed versions (Python/Flask+SQLite [mature, 1,770 segments tested], Python/Flask+PostgreSQL, React evidence-processors v4/v7) + location-admin. Multi-pass ETL (pass1–4.5), geocode resolvers, recursive dup chaos. | **STALE (cleanup state), USEFUL (timeline-DB design).** Dir-chaos findings obsolete (since reorganized). Timeline schema + ETL pass design + forensic geo rules are durable. |
| R11 | `dev-resources/.../TheBigOne/02_TraceIQ_Repo/FINAL_RECOVERY_REPORT.md` | 2026-01-06 / mtime 05-25 | Recovery of 344 unique files (from 1,331, 74% dup, 1.02GB). 2 Streamlit timeline apps + React processor recovered; Flask backends NOT recovered. Key data assets (Timeline.json 13MB, timeline_radar_enriched.sqlite 45MB, 127 geocode CSVs). | **STALE.** One-time recovery event log. Value: which timeline artifacts physically exist + Flask backends gone (don't hunt). |
| R12 | `dev-resources/.../TheBigOne/02_TraceIQ_Repo/INDEX.md` | 2026-01-03 / mtime 05-25 | TraceIQ project index: TraceIQ_Main (Flask/SQLite→PG, ijson streaming, WAL, chain-of-custody, multi-device detection, geocode cache strategy) + full timeline DB schema (timeline_enriched/visits/activities/waypoints/places/api_cache) + location-admin (React/MUI/Supabase, UNS-MCP connectors). | **AGING (best timeline-DB doc).** Richest single description of Google-Timeline forensic DB + geocoding architecture. Schema/design durable; deployment (Supabase, local launch) outdated. |
| — | `E:/AI_Workspace/Workspace_Manifest_*.json` (78 files) | 2026-02..03 | NOT parsed (per instructions). Bulk inventory snapshots. | **STALE** — Feb–Mar, superseded by R1/R2 workspace map; historical noise unless a specific file-existence lookup is needed. |

**Dedup result:** R5 Case-copy and R5 Workbench-copy are **byte-identical** → one logical report. All other reports are distinct.

---

## 2. Deduped master list of prior TOOLS & RESOURCES (+ locations)

### A. Canonical build sources (current — R1/R2)
- **Agno app skeleton (7 agents)** → `dev-resources/upstream-resources/agno-agent-platform/` (seeded into active `Agno-MCP-Platform/`). Agents: ingestion_orchestrator, analysis_orchestrator, review_gatekeeper, transcript_miner, dev_copilot, project_pal, forensic_data_agent.
- **Canonical modular MCP servers** → `dev-resources/Archives/MCP_PLATFORM/mcp-servers/` (`ts-mcp-server`, `py-mcp-server`, `js-mcp-server`).
- **Alpha monolith (port-from backlog)** → `dev-resources/Archives/MCP_Tool_Platform-REF-READ-ONLY/server/mcp/`.
- **Older subset (diff/history only)** → `dev-resources/Archives/dial-stack/mcp-servers/`.
- **Alpha sibling snapshots** → `dev-resources/Archives/{MCP_Tool_Platform, mcp-tool-platform}/`.

### B. Parsers / ingestion (R2, R5, R3)
- **ts-mcp-server/src/tools/**: `SmsXmlParser`/`SmsXmlReader`/`SmsEvidenceIngestor` (Android SMS XML), `FacebookExportParser` (FB HTML), `ImessagePdfParser` (iMessage PDF), `MessageChunker`, `EvidenceIngestor`, `Pass1Runner`, `SbvClient`/`SbvIngestor`, `AdminTools`.
- **ChatMiner ancestors** → `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/{Chunker_from_External_Utils_Lib, Chunker_from_Satellite_Tools, ConversationExtractor_from_Gemini_Debris, ConversationExtractor_from_Satellite_Tools, Tools/}` (base/smart chunkers, AndroidMsgParser, FacebookParser, json/txt/zip exporters).
- **Parser specs (R5)**: SMS/MMS streaming iterparse, FB modern+legacy regex, WhatsApp txt regex, Snapchat/Instagram (defined), Email (TBD), Photos-OCR pipeline.
- **Document-intelligence engines (py-mcp, R2)**: aws_textract, docling, doctr, glm_ocr, google_docai, ibm_watsonx, llamaparse, ocropus, pandoc, tesseract, unstructured (+ router/registry/models).

### C. Forensic / analysis tools
- **py-mcp forensic crypto** (R2): `hash_verification`, `evidence_signing`, `audit_hooks`, `sqlite_wal_parser`, `dpk_tools`, `user_detection`, `voice_tools`, `workflow_tools`.
- **Alpha forensics** (R2/R6): `behavior-service`, `chain-custody`, `forensics-router`, `hurtlex-fetcher`/`-stream`, `identity-service`, `pattern-analyzer`, `timeline-generator`; analysis: classifier, conversation-segmentation, multi-pass-classifier, priority-screener.
- **detection_patterns.py** (R5): 256-pattern MessageClassifier, MCL 722.23 A–L mapping, 18 behavior categories, child-name patterns, DARVO sequence.
- **3rd-party forensic tools** (R4): ExifTool 12.69, Snaparser, Epoch 2.2 (timeline), Smart Chunker, Conversation Extractor (Autopsy plugin), Directory Scanner Pro, Manipulative Expression Recognition, NLP Toxicity Analyzer.
- **3rd-party MCP servers** (R4): Document-Analyser-MCP, LangExtract-MCP, Stirling-PDF-MCP, UNS-MCP, MCP-NLTK (dupes also at `OTHER_RESOURCES_TO_SORT/MCP_*_dupe`).

### D. Database schemas (R5, R12, R10, legacy CLAUDE.md)
- **Messaging DB (R5, Supabase/PG)**: messaging_documents, messaging_conversations, messaging_messages, messaging_attachments, messaging_behaviors, messaging_evidence_items, messaging_factor_citations, messaging_timeline_events; ref tables mcl_factors, behavior_categories. Extensions: uuid-ossp, pg_trgm, postgis.
- **Timeline DB (R5/R12)**: timeline_events, waypoints, processing_metadata; (R12 TraceIQ) timeline_enriched, visits, activities, places, google_api_cache/radar_api_cache, multi_device_splits, processing_log. Schema files: `schema_complete.sql`, `normalized_geo_schema_v5.sql`.
- **Alpha Drizzle/PG schema (R6/R7/R8)**: users, apiKeys, systemPrompts, workflowTemplates + (missing-then) behavioralPatterns, patternCategories, hurtlexTerms/Categories, bertConfigs, severityWeights, mclFactors, schemaResolvers, forensicResults, sections/chunks/spans/summaries/entities/keywords/findings/approvals.

### E. DB engines / storage (R3, R6, legacy CLAUDE.md)
- Layered tier (R3): **DuckDB → PostgreSQL/pgvector → Neo4j → LanceDB**, Dragonfly cache.
- Alpha storage clients (R6): Chroma (dual-collection 72hr TTL + persistent), Graphiti, Directus, content-addressed store (SHA-256), FAISS.
- TraceIQ (R12): SQLite (WAL) ↔ PostgreSQL/PostGIS migration path; Supabase backend.
- DuckDbVault/DuckDbService in ts-mcp (R2) — DuckDB forensic vault.

### F. Domain apps (R1, R10–R12)
- TraceIQ (Flask/SQLite + Flask/PG + React processors + location-admin) → `Archives/TheBigOne/02_TraceIQ_Repo/`; Streamlit timeline apps in `Timeline Tools/`.
- Evidence_Analysis (ConflictAnalysisApp, forensic-data-refinery), Voice_Analysis (Chronicle_Voice_App, story-voice-backend).

---

## 3. Blind spots — what these reports do NOT cover

1. **Current live infra is absent.** No report reflects the present stack: OVH/Ionos boxes, Coolify deploys, self-hosted **Milvus 3.0** (replaces LanceDB/Zilliz per ADR-0026), **FerretDB/Dragonfly** substitutions, **R2 buckets + Iceberg Data Catalog**, Neo4j-backed Graphiti memory, Windmill on OVH-2. Reports still assume **Supabase + Chroma + LanceDB**. DB-architecture work must reconcile against current ADRs/MEMORY, not these docs.
2. **No as-built / runtime verification.** All are design-intent, status-claim, or static scans. None confirm what is actually deployed and working today (R6 "85% done" vs R7/R8 "40%, placeholders" directly conflict). The master-prompt's "current forensic DB architecture" is NOT directly answered by any report.
3. **Stale Supabase/pgvector data model.** R5's authoritative schema targets Supabase + PostGIS; no mapping to current PG-on-Coolify / DuckDB / R2 layout; no pg_duckdb integration (a known owner decision) covered.
4. **Migration/consolidation state untracked.** The port "alpha monolith → modular ts/py servers" (R2's core mission) has no progress report — reports define the backlog, none say what's been ported.
5. **Embeddings/reranker reality.** No report covers the OpenRouter/`bge-m3` embedding decision, the NIM asymmetric-model gotcha, or the CPU-only ≤4B model constraint — all relevant to forensic-DB vector design.
6. **Case Bible / R2 sorting lane.** None cover the casebible-raw/-sorted/-quarantine bucket flow or the R2 catalog (DuckDB) — a parallel data-architecture domain outside this report set.
7. **In-source schema gaps acknowledged**: Email parser (format TBD), Snapchat/Instagram parsers "defined not built", iMessage two-pass, OCR pipeline — still open per R5.
8. **78 Workspace_Manifest_*.json (Feb–Mar) not parsed** — file-level inventory exists but unread; last-resort lookup, likely superseded by R1/R2.
9. **No security/secrets/PII-governance coverage** beyond "don't ingest Secrets/" — no audit of chain-of-custody guarantees as-deployed.
10. **Legacy `_project_dirs_loose/CLAUDE.md`** (rich 6-pass NLP + dual-Chroma + R2-SSOT design, "Jan 2025", Supabase-centric) is a strong forensic-pipeline reference but design-intent only.
