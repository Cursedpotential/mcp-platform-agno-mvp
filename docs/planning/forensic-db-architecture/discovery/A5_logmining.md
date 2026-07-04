# A5 — Conversation-Log Mining: Prior Tools / Schemas / Ontologies

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Sources: 7 memsearch daily digests (2026-05-25 → 06-11), `opencode-turns.db`,
> Claude session transcripts under `…/.claude/projects/E--AI-Workspace-Projects-the-platform-workspace`.
> NOTE: `opencode-turns.db` stores only turn **metadata** (session_id, turn_id, timestamps,
> message counts) — NO message content — so it yielded no minable text. All content came from
> the digests + transcript greps.

---

## 1. Timeline of relevant prior tool-calls / work (last ~30–40 days)

**2026-05-25** — Forensic platform discovery & GSD init. "TheBigOne" identified as a container, not a
project; real projects = **MCP Tool Platform (TraceIQ)** + **TraceIQ** (location pipeline). System =
"Salem Forensic Trinity": Timeline Forensics, Voice Analysis, Evidence Analysis, MCP Tool Platform.
Original stack: Node/TS, Express, tRPC, React, Drizzle ORM, Neo4j, ChromaDB, 4-tier memory.
Read the Perplexity blueprint (`[https___github.com_Hawksight-AI_semantica](https_.md`, 1777 lines) →
architectural pivot decided: **DuckDB (master clock/ETL) + LanceDB (Arrow zero-copy) + dual Neo4j
(`semantic_facts` via Semantica / `temporal_memory` via Graphiti) + Semantica (FastAPI: NER, PROV-O
provenance, conflict engine) + Docling (PDFs)**. Custom parsers (SMS XML, Facebook HTML) survive;
ChromaDB/pgvector/Supabase to be replaced. Phased roadmap (Storage → ETL → Verticals → Patterns →
Scale). Heavy doc-consolidation pass (GAP_REPORT, SCHEMA_PARSER_INVENTORY, TIMELINE_SCHEMA).

**2026-05-26** — Sprint 1 "Front Door" build (in `MCP_Tool_Platform`). Enforced **UUIDv7** (time-clustered)
+ **SHA-256** chain-of-custody in `duckdb.ts`; created `server/mcp/ingest/index.ts`. Mined legacy
`xml-sms-parser.ts` + `enhanced-xml-chunker.py` → merged into a LlamaIndex `SmsXmlReader`
(streaming, SMS-vs-calls detection, SMS-Backup-&-Restore attr mapping). Decision: no rigid PG schemas
— dump raw XML into a `normalized_messages.raw_data` JSON column, query JSON natively in DuckDB.

**2026-06-01** — Architecture lock-in: LlamaIndex Property Graph as orchestrator; SHA-256/UUIDv7 first-class;
`normalized_messages` universal schema for platform-hop reconstruction; Neo4j for identity resolution
(alias merging). Stream-based SHA-256 hasher (64KB chunks) for 4GB XML; MinIO presigned uploads; VPS3
placement debate (`FULL_STACK_MAP.md`). Supabase references flagged for removal (`supabase-client.ts`).
Found behavioral library: `seed-patterns.ts` (~303 patterns) + `patterns-schema.ts` + `behaviors.yaml`.

**2026-06-02** — Ontology + dataset system built (NO STUBS): `mcl_722_23.ttl` (12 MCL factors),
`behavioral_patterns.ttl`; `dataset_loader.py` (528 ln), `hurtlex_loader.py` (368 ln, lazy, EN-only),
`semantica_pipeline.py` (997 ln: NER, relation extraction, 303 MySQL patterns, temporal KG, conflict
detection, PROV-O, embeddings, all linked via `source_hash`). GraphQL resolvers (`graphql/schema.ts`,
`plugins/schema-resolver.ts`). Decision: Semantica = primary workflow; extra NLP tools = atomic utilities.

**2026-06-09 → 06-11** — *Off-topic for forensic-db-arch*: legal-skills consolidation from Downloads,
and a Node/JS memory-leak hunt (culprit = `osgrep` worker children; uninstalled, removed from opencode +
Claude configs). No schema/ontology/parser work. (Note: by 06-10 the salvage had already been extracted —
see §2 `extracted-code/MANIFEST.md`, mined 2026-06-10.)

---

## 2. Deduped pointer list — tool/resource → location → last-referenced

> CRITICAL: The original project tree (`C:\Users\matts\Projects\TheBigOne`,
> `D:\AI_Workspace\Projects\TheBigOne`, `E:\…\TheBigOne`) is **GONE from disk** (all three roots
> missing — see §3). Everything below now lives ONLY inside the current workspace under
> `dev-resources/Archives/` and the curated `extracted-code/` salvage. **Prefer `extracted-code/`** —
> it is the deliberate, deduped, provenance-tracked staging copy (manifest mined 2026-06-10).

**★ Master pointer doc:** `E:/AI_Workspace/Projects/the-platform-workspace/extracted-code/MANIFEST.md`
— the canonical, provenance-tracked index of every salvaged parser/schema/ontology/tool. Read this first.

| Resource | Canonical (current) location | Last ref |
|---|---|---|
| **DuckDB client** (Tier-1 master clock, SHA-256 + UUIDv7 chain-of-custody, `normalized_messages`) | `dev-resources/Archives/archive/MCP_BACKUP/platform_archive/mcp-tool-platform/server/mcp/storage/duckdb.ts` | 06-01 |
| **SMS XML parser** (streaming) | `extracted-code/parsers/messaging/xml-sms-parser.ts` | 05-26 |
| **enhanced-xml-chunker** (Python; tz handler, base64 image extract, call logs) | `dev-resources/Archives/TheBigOne/02_TraceIQ_Repo/20260106033151884/enhanced-xml-chunker.py` | 05-26 |
| **SMS Backup&Restore parser** (Python; blocked-call type 5/6 forensic indicators) | `extracted-code/parsers/messaging/sms_backup_parser.py` | 06-01 |
| **Facebook / iMessage / GVoice parsers** | `extracted-code/parsers/messaging/{facebook-parser.ts,pdf-imessage-parser.ts,gvoiceParser,sms-loader.ts}` | 05-25 |
| **Chat-export parsers** (ChatGPT/Claude JSONL, Takeout, output_schemas) | `extracted-code/parsers/chat-exports/` | 06-10 |
| **Location/Takeout parsers** (Google location-history, photos) | `extracted-code/parsers/location/` | 06-10 |
| **Snapchat parser** | *Skipped from salvage (112MB w/ exe)*; src under `dev-resources/Archives/dial-stack/utilities/parsers/snapchat/` | 05-25 |
| **schema-resolver plugin** (AI field-mapping for unknown formats) | `extracted-code/tools/schema-resolver.ts` (+ `.test.ts`) | 06-02 |
| **Drizzle schemas** (message, production-message, **patterns-schema (303)**, prompts, settings, relations) | `extracted-code/schemas/drizzle/` | 06-01 |
| **SQL schemas** (`agno-alpha-schema.sql`, `Salem_SMS_Tables_Complete_Deployment_2025-12-27.sql`) | `extracted-code/schemas/`, `extracted-code/sbv/` | 06-10 |
| **MCL 722.23 ontology** (RDF/Turtle, 12 best-interest factors) | `extracted-code/ontologies-datasets/ontologies/mcl_722_23.ttl` | 06-02 |
| **Behavioral / positive-behavior ontologies** | `extracted-code/ontologies-datasets/ontologies/{behavioral_patterns.ttl,positive_behaviors.ttl}` | 06-02 |
| **salem_v3 ontology** (Zep graph ontology builder, v3 final) | `extracted-code/ontologies-datasets/zep_salem_ontology_v3_final.py` | 06-02 |
| **Semantica pipeline** (997 ln: NER, PROV-O, conflict, temporal KG) | `dev-resources/Archives/dial-stack/utilities/python-tools/semantica_pipeline.py` | 06-02 |
| **dataset_loader / hurtlex_loader / GLiNER probe / unsloth dataset** | `extracted-code/ontologies-datasets/{dataset_loader.py,test_gliner.py,unsloth_dataset.jsonl}` | 06-02 |
| **Behavior rule library** (`seed-patterns.ts` ~303, `behaviors.yaml`) | `dev-resources/Archives/.../server/scripts/seed-patterns.ts`; `extracted-code/parsers/.../rules/behaviors.yaml` | 06-01 |
| **SBV (SMS Backup&Restore) viewer/extractor cluster** (Go upstream + TS client + ingestion + MCP) | `extracted-code/sbv/` | 06-10 |
| **PDF/unstructured extractors** | `extracted-code/extractors/{pdf_extractor.py,unstructured_parser.py}` | 06-10 |
| **Perplexity architecture blueprint** (Semantica/Docling/Agno/CopilotKit/memory tiers) | `dev-resources/Archives/.../[https___github.com_Hawksight-AI_semantica](https_.md` + `integrated-architecture-blueprint.md` | 05-25 |
| **Gap/inventory docs** (`COMPREHENSIVE_GAP_REPORT.md`, `COMPLETE_SCHEMA_PARSER_INVENTORY.md`, `TODO_TIMELINE_SCHEMA.md`) | `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/{Case,Workbench}/` + `…/docs/analysis/` | 05-25 |
| **Stack/deploy maps** (`FULL_STACK_MAP.md`, `docker-compose.vps1-storage.yml`, `test-graphiti.sh`) | `dev-resources/Archives/.../MCP_Tool_Platform_Repo/deploy/salem-trinity/` | 06-01 |

---

## 3. Stale pointers — referenced in logs but NOW MISSING from disk

Every original absolute path in the transcripts is dead. The whole `TheBigOne` tree was removed
(content migrated into `dev-resources/Archives/` + `extracted-code/`). Confirmed missing:

- `C:\Users\matts\Projects\TheBigOne\` **(entire root gone)** — incl. `MCP_Tool_Platform\server\mcp\storage\duckdb.ts`, `…\plugins\schema-resolver.ts`, `…\graphql\schema.ts`, `…\python-tools\{semantica_pipeline,dataset_loader}.py`, `…\data\ontologies\*.ttl`, and the Perplexity `…semantica](https_.md` blueprint.
- `D:\AI_Workspace\Projects\TheBigOne\` **(entire root gone)** — incl. `…\MCP_Tool_Platform_Repo\server\mcp\loaders\xml-sms-parser.ts`, `…\TraceIQ\Junkyard\Source_A_Root_Folder\20260106033151884\enhanced-xml-chunker.py`, `…\Evidence_Analysis\forensic-data-refinery\lib\ingestor.ts` (+`utils.ts`), `…\ConflictAnalysisApp\src\sms_backup_parser.py`.
- `E:\AI_Workspace\Projects\TheBigOne\` — not present.
- Active dev box note: `osgrep` MCP **uninstalled** 2026-06-11 (memory leak) and removed from opencode + Claude configs — any pointer to `osgrep`/`process-child.js` is stale.

**Mitigation:** all of the above survive (deduped, with provenance) in
`E:/AI_Workspace/Projects/the-platform-workspace/extracted-code/` (see MANIFEST.md) and, raw, in
`dev-resources/Archives/`. Known prior-iteration bugs to verify before porting (per MANIFEST):
chatminer `__init__` missing `core.pipeline`; root `parsers/` broken; `artifacts.EVIDENCE_REFERENCE` enum.
