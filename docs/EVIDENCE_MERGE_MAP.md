# Evidence Spine — Cross-Archive Merge Map

> **Status:** DRAFT for owner sign-off. No code is to be written until this is approved.
> **Date:** 2026-06-13
> _Byline: Claude Code · Opus 4.8 · 2026-06-13_
> **Decisions locked this session:**
> 1. **Language strategy** — TS tools run as **MCP services behind Agno**; Agno agents call them as tools. No mass rewrite. (Matches the existing `ts-mcp-server` + `py-mcp-server` design and the spine's polyglot registry.)
> 2. **First target** — this **inventory + merge map**, approved, before any build.

This document inventories the three code corpora that feed the evidence spine, names the *most complete version of each capability*, flags what is **still missing**, and proposes the target architecture + build order.

---

## 0. The end goal — a multi-surface Platform Gateway

> **Owner vision (this session):** the real product is a **multi-surface tool platform / gateway** that **serves its own tools, consumes external tools, and routes/proxies between them**. Agno agents are *builders and consumers* of that platform — they help build it out and use it — but the gateway itself is the destination. The evidence spine is the **first domain application** running on the platform, not the platform itself.
>
> **⚠️ Critical correction:** **We are NOT using DIAL.** dial-stack was the *prior* attempt built on **AI DIAL Core**; the project **switched to Agno** as the orchestration core. So dial-stack is a **parts + pattern donor**, not the running platform. We harvest its *capabilities* (analysis, graph, parsers) and its *gateway design*, but we **drop the DIAL-specific runtime/transport** (AI DIAL Core routing, the `dial-ts-core` MCP server's DIAL coupling, `config.json` DIAL wiring).

The gateway **concept** is still the goal — it just gets **rebuilt on Agno**, not on DIAL. dial-stack already proved out each piece of that concept, and those pieces are the design reference (and, where transport-agnostic, the code) to carry forward:

| Vision capability | dial-stack reference (DIAL runtime stripped) | Carried forward as |
|---|---|---|
| **Serve** its own tools | `mcp/gateway.ts` — token-efficient `search_tools`/`describe_tool`/`invoke_tool`/`get_ref`; `plugins/registry.ts` | Pattern → re-host on Agno; spine's `registry.py` is the Python analogue already |
| **Consume** external tools | `mcp/proxy/mcp-proxy.ts` — federates remote MCP servers (http/ws/stdio) | Pattern → Agno-side MCP client / proxy |
| **Route / proxy** | proxy routing by tool→server map, latency selection, namespacing | Pattern |
| **Multi-surface** | `mcp/forking/tool-fork.ts` + `mcpConfig` generator — export any tool as **Claude MCP / Gemini ext / OpenAI fn** | Capability worth porting — the multi-surface export is the differentiator |
| Supporting | LLM provider hub, prompts/workflows, wiki, stats, API keys, HITL | Agno already provides most (HITL ✅ shipped); cherry-pick the rest |

**The layered picture (Agno-centric):**

- **Platform layer (gateway) — rebuilt on Agno:** serves/consumes/routes/proxies tools across surfaces (Claude / Gemini / OpenAI / Agno itself). The long-term product. **Not DIAL.**
- **Domain layer (evidence spine, Python):** custody + bitemporal records + forensic/relationship-history verticals — registered **as tools on the platform**.
- **dial-stack:** mined for the analysis/graph/parser tools and the gateway design; its DIAL host is **not** carried forward.

So "TS tools as MCP services behind Agno" (the locked decision) is the *tactical* shape; the *strategic* shape is: **spine tools + harvested dial-stack tools all become first-class registry entries**, and Agno is the orchestration core + one consumer surface among several.

**Gateway preference order (owner, this session):**

1. **Agno native** — if AgentOS can serve/consume/route/proxy tools across surfaces, use it. No extra gateway.
2. **IBM ContextForge MCP Gateway** (`IBM/mcp-context-forge`) — the **only** fallback, used **only if** Agno cannot cover the gateway role.
3. ~~DIAL~~ — **dropped.** Not a candidate. dial-stack's gateway code is design reference only.

**Open question for §5:** confirm we first prove out how far Agno's native tool-serving/proxying reaches before deciding whether IBM ContextForge is needed.

---

## 1. The three corpora

| Corpus | Path | Language | Role | State |
|---|---|---|---|---|
| **Agno spine (P2)** | `Agno-MCP-Platform/evidence/` | Python | The chassis: custody gate, capability registry, bitemporal record, workflows, CLI | Built, partially deployed; 4 parsers are shallow placeholders |
| **ChatMiner** | `dev-resources/Archives/Agno-MCP-Platform-alpha/chatminer/` | Python | AI-conversation parsing + segmentation + artifact extraction | Working library, clean architecture |
| **dial-stack** | `dev-resources/Archives/dial-stack/` | TypeScript (+ Python helpers) | Forensic parsers, behavioral/legal analysis, bi-temporal knowledge graph, chain-of-custody, MCP gateway | Rich + mostly working, but several architectures fused → not runnable as-is |

---

## 2. Most complete version of each capability

### 2.1 Parsing — **split across two corpora** (this is the "missing code" you sensed)

- **AI-chat exports → ChatMiner (Python).** `core/base.py` (BaseParser ABC: encoding fallbacks, 50MB cap, SHA-256, `can_parse()` confidence) + `parsers/` registry with `get_parser_for_file()` auto-detect (≥0.5 threshold). **10 parsers:** ChatGPT official + share, Gemini chrome + json, Claude md + code, Perplexity gdpr + plugin + md, generic-md fallback.
- **Forensic message exports → dial-stack (TypeScript).** `mcp-servers/ts-mcp-server/src/tools/`: `SmsXmlParser` (SMS Backup & Restore XML), `FacebookExportParser` (HTML/JSON), `ImessagePdfParser` (PDF), wrapped by `SmsEvidenceIngestor` (hash → DuckDB vault → parse → bucket conversations → Postgres `evidence.*` with multi-level provenance hashing).
- **The 4 parsers in `evidence/tools/` (chatgpt_export, claude_ai_export, claude_code_jsonl, markdown_transcript) are shallow placeholders → to be REPLACED by ChatMiner.**

> **Net:** ChatMiner covers AI chats; dial-stack covers SMS/FB/iMessage. Neither alone is complete. The spine needs both.

### 2.2 Canonical data model — Agno spine wins as the *target*, ChatMiner wins as the *source*

- **Agno `evidence/normalize.py`** — `NormalizedRecord` (pydantic) with the **bitemporal substrate**: `occurred_at` (valid time), `knowledge_time`, `disclosure_tier` ∈ {contemporaneous, hindsight, discovered}. This is the shape everything must land in.
- **ChatMiner `core/types.py`** — richer source model: `ParsedMessage` (verbatim content + per-message hash), `ParsedConversation`, `Artifact`, `TopicSegment`, `ParseResult`, and enums `ContentType`, `ArtifactType` (incl. `STRATEGY_DOC`, `TIMELINE_EVENT`, `ENTITY`, `EVIDENCE_REFERENCE`), `MessageRole`, `TopicTag`.
- **Merge:** ChatMiner parsers emit `ParsedMessage`/`ParsedConversation`; an adapter maps those into `NormalizedRecord` (content → content, role → role, timestamp → occurred_at, source_format → source, everything else → `attrs`).

### 2.3 Segmentation & topic tagging — ChatMiner (Python), but the taxonomy must change

- **ChatMiner `segmenters/segmenter_local.py`** — sentence-transformers (all-MiniLM-L6-v2) sliding-window cosine-similarity boundary detection + keyword classification + small-segment merging. Plus a `segmenter_configurable.py` variant.
- **Current `TopicTag`:** `PERSONAL_LEGAL | DEVELOPMENT | EMOTIONAL | EVIDENCE | MIXED | UNKNOWN`.
- **⚠️ Owner requirement (this session):** Relationship/Personal history must be its **own first-class lane** with heavy entity extraction + timeline construction. Today it is bundled inside `PERSONAL_LEGAL`. **Proposed new taxonomy:**

  `RELATIONSHIP_HISTORY | PERSONAL_LEGAL | DEVELOPMENT | EMOTIONAL | EVIDENCE | MIXED | UNKNOWN`

  - `RELATIONSHIP_HISTORY` = the factual narrative substrate (who/what/when between people) — feeds entity + timeline + graph hardest.
  - `PERSONAL_LEGAL` = legal strategy/case-handling that sits on top of that substrate.
  - Tag at **segment** level, multi-tag allowed, `MIXED`/`UNKNOWN` kept as catch-alls.
  - **Note:** ChatMiner's keyword lists are currently hardcoded to the matter (names, places). Decision needed (§5) on whether to keep case-tuned keywords or generalize + config-load them.

### 2.4 Artifact extraction — ChatMiner (Python) + dial-stack entity NER

- **ChatMiner `core/artifacts.py`** — regex extractors for code blocks, file refs, URLs, created-documents, **evidence references**, and **legal-strategy mentions**.
- **dial-stack** — `nlp_runner.py` (spaCy NER: person/org/place + sentiment + keywords). Merge: ChatMiner artifact regex + dial-stack spaCy entities → richer entity layer.

### 2.5 Behavioral / legal analysis (Part 2) — **dial-stack wins outright** (TypeScript, kept as MCP service)

- `server/mcp/forensics/pattern-analyzer.ts` (1660 lines): ~25 modules (gaslighting, DARVO, blame-shifting, minimization, threats, isolation, financial/medical/reproductive coercion, parental alienation, projection, power asymmetry; positive: love-bombing, future-faking, affirmations, apologies; neutral: scheduling, child-welfare) — each mapped to **MCL 722.23 factors (a–l)**, with **contradiction detection** (love-bomb→devalue, apology→repeat) and **linguistic markers** (pronoun ratio, hedge/certainty, overelaboration scoring). DB-backed custom patterns.
- `server/mcp/forensics/timeline-generator.ts`: timestamp extraction (regex + `compromise` NLP), **Walker cycle-of-abuse detection** (tension/incident/reconciliation/calm with weighted indicators), escalation tracking, markdown reports.

### 2.6 Knowledge graph + bitemporal contradictions — **dial-stack wins** (this *is* the P3 substrate, already built)

- `server/mcp/storage/graphiti-client.ts` (750 lines): Neo4j + Graphiti, **bi-temporal** relationships (`valid_from`/`valid_to`), `queryTemporalState(t)`, `invalidateRelationship`, and `detectContradictions` — same-day location conflicts, overlapping exclusive relationships (married-to/partner-of), temporal overlaps. Entities carry `mclFactors`. Bridges to `python-tools/graphiti_runner.py`.
- **This is the engine for the relationship-history timeline** the owner asked for.

### 2.7 Storage & chain of custody — dial-stack has the strongest version; spine owns the gate

- **dial-stack `drizzle/schema.ts`** — documents → sections → chunks → spans → entities, `evidenceChains`, `mclFactors` reference table, `schemaResolvers` (AI-generated field mappings = the "ParserSchema" two-pass idea), `behavioralPatterns`, `forensicResults`, hurtlex lexicon. `drizzle/message-schemas.ts` — per-platform message tables with `conversation_cluster_id` (PLAT_YYMM_TOPIC_iii) + preliminary-analysis fields + custody fields.
- **dial-stack `migrations/004_chain_of_custody.sql`** — Ed25519 signatures + hash-linked `chain_of_custody` (blockchain-style) + plpgsql `verify_custody_chain`. **Stronger than the spine's current custody.**
- **Agno `evidence/custody.py`** stays the **single append-only write gate** to the `evidence` schema; the dial-stack custody design is the model to harden it toward.

### 2.8 Ontology — dial-stack TTL files

- `ontologies/{mcl_722_23,behavioral_patterns,positive_behaviors}.ttl` — formal RDF (the "Salem Ontology" equivalent), MCL-factor-tagged.

---

## 3. The spine chassis (what already exists and stays)

`evidence/` (Agno, Python):
- **`custody.py`** — single entry gate: hash → evidence row → write-once blob. Only writer of the `evidence` schema (append-only, immutable).
- **`registry.py`** — capability-based `ToolRegistry`: a tool = one capability + contract; `resolve(capability)` returns preferred + substitution candidates; `@register` + `load_builtin_tools()` auto-discovery (one parser = one swappable module). **Explicitly supports polyglot tools (TS/Go/MCP/HTTP runners) — this is the hook for dial-stack-as-MCP.**
- **`normalize.py`** — `NormalizedRecord` + bitemporal fields (§2.2).
- **`store.py`** — normalized records → `analysis` schema + knowledge-engine ingest.
- **`workflows.py`** — named workflows on native `agno.workflow`, custody-gated.
- **`cli.py` / `__main__.py`** — `python -m evidence …`.

---

## 4. Target architecture (per locked decision: TS-as-MCP-behind-Agno)

```
                         ┌─────────────────────────────────────────────┐
                         │              Agno AgentOS (Python)            │
                         │   Ops / Builder agents · native /approvals    │
                         └───────────────┬───────────────────────────────┘
                                         │ resolves steps by CAPABILITY
                         ┌───────────────▼───────────────┐
                         │   evidence/ spine (Python)      │
                         │   custody · registry · normalize │
                         │   store · workflows · cli        │
                         └───┬───────────────┬──────────────┘
        in-process Python    │               │  polyglot runner (HTTP/MCP)
        atomic tools         │               │
            ┌────────────────▼──┐      ┌──────▼─────────────────────────────┐
            │  ChatMiner (vend.) │      │  dial-stack MCP services (TS)       │
            │  10 AI-chat parsers│      │  • forensic parsers (SMS/FB/iMsg)   │
            │  segmenter         │      │  • pattern-analyzer (behavioral)    │
            │  artifact extract  │      │  • timeline-generator               │
            └────────────────────┘      │  • graphiti-client (bi-temporal KG) │
                                        └──────┬──────────────────────────────┘
                                               │ calls
                                        ┌──────▼──────┐   ┌──────────────┐
                                        │ Neo4j/Graphiti│  │ py-mcp-server │
                                        │  (live)       │  │ embeddings/   │
                                        └───────────────┘  │ LanceDB       │
                                                           └──────────────┘
```

- **Vendor into the spine as Python in-process tools:** ChatMiner (parsers + segmenter + artifacts). One module per parser, registered under `parse.transcript` / `parse.*` capabilities.
- **Wrap as MCP services (no rewrite):** dial-stack forensic parsers, pattern-analyzer, timeline-generator, graphiti-client — registered in the spine via the polyglot/HTTP runner so workflows resolve them by capability.
- **Storage:** spine `custody.py` remains the only `evidence`-schema writer; adopt dial-stack's Ed25519 chain-of-custody as the hardening target; normalized + analysis tables follow `normalize.py`.

---

## 5. Open decisions before build (need owner answers)

1. **Topic taxonomy** — adopt the 7-tag set with `RELATIONSHIP_HISTORY` as its own lane? Keep case-tuned keyword lists, or generalize them and load case-specific terms from config?
2. **dial-stack scope** — wrap **all four** TS capabilities as MCP services (forensic parsers, pattern-analyzer, timeline, graphiti), or stage them (e.g. graphiti + behavioral first, since they're the relationship-history engine)?
3. **Custody hardening** — port the Ed25519 signed chain-of-custody now, or after parsers land?
4. **ChatMiner keyword/name scrubbing** — the segmenter and case codes contain real names/places; confirm they stay (private repo) vs. get parameterized.
5. **Build order** (proposed): (a) vendor ChatMiner parsers + adapter → NormalizedRecord; (b) add `RELATIONSHIP_HISTORY` lane to segmenter; (c) wrap graphiti-client as MCP service + wire entity/timeline for the relationship-history vertical; (d) wrap pattern-analyzer + timeline; (e) harden custody. Confirm or reorder.

---

## 6. Confirmed-missing / not-yet-located (follow-up crawl)

- **ChatMiner ↔ dial-stack overlap not yet reconciled** for Gemini/Perplexity (both have variants) — pick canonical per format.
- **`Chat Parser App v2.0`** (`MCP_Tool_Platform-REF-READ-ONLY/.../Chat_Parser_App/`) — the LLM-driven `ParserSchema` two-pass design referenced last session is **not in dial-stack**; needs its own crawl if its schema-resolver approach is wanted (dial-stack has the `schemaResolvers` table but maybe not the runner).
- **Tether trained ML models / priority-screener (256+ custody patterns)** mentioned in prior sessions — not confirmed inside dial-stack; locate before assuming they're covered by `pattern-analyzer.ts`.
- The literal full-file inventory of dial-stack is dominated by a third-party prompt library under `utilities/External_Utils_Lib/...System-Prompt-Library` (thousands of reference JSONs).

> **Owner classification (this session):** `utilities/External_Utils_Lib/` is a **deferred reference resource** — there is good material to *use or reference* there, but we do **not** dig into it now; revisit after the core build. `docs/`, `.plannotator/`, `.planning/`, `.full-review/` and similar are **context**, not platform code.

---

## 7. Difference-scan findings (subsystems Morph initially skipped)

The first Morph pass read only ~12 of ~200 real code files. A targeted second pass over the unscanned high-value subsystems found the following — several are **major assets** not previously accounted for:

### Newly found — high value, carry forward

- **Document-intelligence engine layer** (`py-mcp-server/document_intelligence/`): a clean abstract `DocumentEngine` base + `EngineRegistry` + `DocumentRouter` with **fallback chains** and **locality/cost preference** (local-free → cloud-paid → enterprise). **11 engines**: Tesseract, Docling, docTR, OCRopus, Pandoc, Unstructured, GLM-OCR, LlamaParse, **AWS Textract, Google DocAI, IBM watsonx**. Unified `DocumentIntelligenceResult`. → *Directly serves the Google/IBM platform direction; strong candidate to wrap as an MCP service or port.*
- **Two-pass analysis is REAL and implemented** (this is the "umbrella" design):
  - `analysis/multi-pass-classifier.ts` — **Pass 1 (blind/surface)**: 6 passes (priority screen → spaCy → NLTK VADER → pattern-analyzer → TextBlob → sentence-transformers → keywords), consensus sentiment, sarcasm detection, severity.
  - `orchestration/forensic-workflow.ts` — the **preliminary → full-context → meta-analysis → reconciliation** state machine with **HITL checkpoints** and **contradiction detection** (severity delta between passes). This is the bitemporal Pass-1-vs-final-pass delta, operationalized.
- **`analysis/priority-screener.ts`** (Pass 0): immediate HIGH-severity flagging of child references, call/visit blocking, parenting-time denial, custody interference → MCL factors. (Case-specific: child-name variants hardcoded.)
- **`analysis/conversation-segmentation.ts`**: cluster IDs `PLAT_YYMM_TOPIC_iii`, embedding-similarity + time-gap + topic-change boundaries. (Case-specific TOPIC_CODES.)
- **Forensic Python tools** (`py-mcp-server/tools/`): `evidence_signing.py` (**Ed25519/PyNaCl** signing + Python `ChainOfCustody` — the runtime twin of `004_chain_of_custody.sql`), `hash_verification.py` (multi-algo + batch), **`sqlite_wal_parser.py` (deleted-message recovery from iOS `sms.db` / Android `mmssms.db` WAL)** — forensic gold, no equivalent elsewhere.
- **~40-plugin tool catalog** (`server/mcp/plugins/`): nlp, ocr, ml, bert-sentiment, vector-db/store, graph-db/analytics, retrieval, summarization, evidence-hasher, evidence-linker, schema-resolver, text-miner, timeline-parser, format-converter, n8n, llamaindex, etc. *(File list captured; individual plugin bodies not yet read — see "still unscanned".)*

### Newly found — needs a decision / caveat

- **Orchestration is LangGraph-based** (`langgraph-adapter.ts`, `langchain-memory.ts`, `sub-agents.ts`) and **much of it is placeholder/simulated** (auto-approve, hardcoded sample patterns). **We are replacing the orchestration layer with Agno** — keep the *workflow shape* (preliminary→meta→reconcile + HITL), drop the LangGraph runtime.
- **`tools/user_detection.py`** wraps the owner's *custom behavioral detector* (DARVO, coercive control via the **Karystianis 48-behavior taxonomy**) — but the implementations are **PLACEHOLDERS** ("TODO: connect to user's actual detection system"). **→ Confirms your instinct: the trained behavioral ML ("Tether") is NOT in dial-stack. It's referenced as an external system still to be located/connected.**

### Still unscanned (lower priority or deferred)

- Individual bodies of the ~40 `server/mcp/plugins/*.ts` (catalogued by name; contents not yet read — the Morph result exceeded size limits and was spooled to disk).
- `server/mcp/pipelines/*`, `server/mcp/loaders/*` (a second set of FB/SMS/PDF parsers — overlap with `ts-mcp-server/tools` to reconcile), `server/mcp/storage/*` (chroma/pgvector/directus clients), `server/mcp/llm/smart-router.ts`, `server/mcp/export/pipeline.ts`, `server/mcp/queue/redis-queue.ts`, `server/mcp/observability/tracing.ts`.
- `server/core/*` (DIAL app glue: oauth, gcp-ai, aws-ai, encryption, storage) — mostly **DIAL-runtime, likely dropped**.
- `mcp-servers/py-mcp-server/document_intelligence/engines/*` individual engine bodies (registry + 2 engines read; the other 9 not yet opened).
- `drizzle/production-message-schemas.ts`, `patterns-schema.ts`, `prompts-schema.ts`, `relations.ts`.

### The plugin tool catalog (≈100 tools — the "serves its tools" surface)

Enumerated from `server/mcp/plugins/` (tool IDs grouped by namespace). This is the reference for what the **Agno gateway** should expose as servable tools:

- **evidence.**: create_chain, add_stage, verify, hash_file, hash_content, hash, export, generate_report
- **doc./convert./format./pandoc./tesseract./stirlingpdf./unstructured.**: convert_to_markdown, ocr_image_or_pdf, segment, parse, ocr, check_schema, to_format, convert, partition, process
- **ocr.**: extract_text, extract_from_pdf, detect_text_regions, detect_handwriting
- **nlp.**: detect_language, extract_entities, extract_keywords, analyze_sentiment, split_sentences
- **ml.**: embed, semantic_search, classify
- **vector.**: store, search, delete  •  **graph.**: create_entity, create_relationship, query, search  •  **mem0.**: add, search, share_context
- **search.**: ripgrep, ugrep, web, news, research, text_mine, text_mine_report, smart
- **forensics.**: analyze_patterns, detect_hurtlex, score_severity  •  **schema.**: resolve, apply, auto_resolve, save_mapping, cache_stats, clear_cache
- **browser.**: navigate, screenshot, extract, click, fill  •  **n8n.**: trigger, status  •  **notebooklm.**: ask, add, list, select, search, remove, stats
- **langchain./llamaindex./langgraph.**: format_prompt, split_text, chunk_text, run, createGraph, executeGraph, streamGraph (⚠ langgraph → replace with Agno)
- **js.**: cheerio, xml_parse, json5, yaml, csv, natural, compromise, franc, string_similarity
- **py.**: spacy, nltk, transformers, beautifulsoup, pdfplumber, pandas, llamaindex
- **fs.**: list_dir, read_file, write_file  •  **misc**: diff.text, rules.evaluate, summarize.hierarchical, retrieve.supporting_spans, text.mine

> Inventory of real platform code is now effectively complete at the **capability/catalog** level. Individual plugin *bodies* remain unread by deliberate choice (owner: "don't dig too deep yet"); they can be opened on demand when a specific tool is being ported/wrapped.

---

## 8. Pre-scan deep read (bodies) — Sonnet, 2026-06-13

_Byline: Claude Code · Sonnet 4.6 · 2026-06-13_

> This section records body-level findings from the targeted deep read ordered by the task instructions. All files are under `dev-resources/Archives/dial-stack/` (read-only donor material). Findings are factual capability notes; no decisions are made here.

---

### 8a. `server/mcp/plugins/*.ts` — 37 plugin files

| File | Capability | Key dep | REAL vs stub |
|---|---|---|---|
| `registry.ts` | `PluginRegistry` — tag-indexed tool registry with `registerTool`, `searchByTags`, `listByCategory`, `getByName`; the discovery core for the gateway's `search_tools`/`describe_tool`/`invoke_tool` surface | None (pure TS) | REAL |
| `bert-sentiment.ts` | BERT-based emotion + forensic-marker detection (`deception`, `anger`, `manipulation`, `love_bombing`); uses HuggingFace `@huggingface/transformers` pipelines for sentiment + emotion classification | `@huggingface/transformers` | REAL structure; `initialize()` requires model download at runtime |
| `nlp.ts` | Multi-provider NLP: language-detect, entity-extract, keyword-extract, sentiment, sentence-split, toxicity; built-in JS provider (no dep) + spaCy/NLTK/compromise via `python-bridge`; `detectToxicity` present | `python-bridge` + optional spaCy | REAL (JS provider runs w/o deps; others need bridge) |
| `ocr.ts` | OCR via Tesseract CLI + `pdf-parse` fallback; text-region bounding boxes, handwriting flag, confidence scoring; PNG/JPEG/TIFF/BMP/PDF | `tesseract` CLI + `pdf-parse` | REAL (requires Tesseract installed) |
| `ml.ts` | Embedding (local BERT / Ollama / OpenAI / Gemini) + semantic search + classification over Chroma; **off by default** (`enabled: false`); uses `all-MiniLM-L6-v2` | `chromadb` + optional GPU runner | Partial — config stub but Chroma integration real |
| `vector-db.ts` | Pluggable vector store: Qdrant / pgvector / Chroma (TTL 72 h working memory); configurable per provider; Chroma internal-only (not exposed externally) | `qdrant-client` / `pg` / `chromadb` | REAL (provider-selectable) |
| `vector-store.ts` | Dual-backend (Chroma + FAISS) with unified `IVectorStore` interface; add/search/delete; integrates `cachedEmbeddingService` from `real-embedding-service.ts` | `chromadb` + `faiss-node` | REAL |
| `graph-db.ts` | Neo4j + optional Graphiti; entity CRUD, relationship management, temporal tracking, contradiction detection; off by default (`enabled: false`) | `neo4j-driver` | REAL (requires Neo4j running) |
| `graph-analytics.ts` | Neo4j GDS community detection (Louvain/LP/CC), PageRank/Betweenness centrality, entity deduplication/resolution; writes `detected_patterns` to PG via `pattern-persistence` | `neo4j-driver` + GDS plugin | REAL (requires GDS library in Neo4j) |
| `agent-memory.ts` | Agent working-memory in Graphiti: store reasoning process, intermediate conclusions, session context, agent-to-agent messages (request/response/notification/coordination); SEPARATE from evidence memory | `graphiti-client` (local) | REAL |
| `schema-resolver.ts` | AI-powered field mapping for unknown message formats: heuristic-first (exact→fuzzy→content-pattern), AI fallback, disk-cached hash-keyed `SchemaMapping`; maps to canonical fields (body/date/contactName/address/messageType) | `crypto` + optional LLM | REAL heuristic path; AI path needs LLM config |
| `evidence-hasher.ts` | SHA-256 hash-linked chain-of-custody per processing stage (original→imported→converted→normalized→analyzed→redacted→exported); `verifyChain`, forensic JSONL export; legal-admissibility target | `crypto` + `fs` | REAL |
| `evidence-linker.ts` | Cross-evidence analysis: link evidence to KG entities, find supporting/contradicting evidence, cluster by topic/entity, cross-source correlation (message+GPS+document), timeline reconstruction; writes PG + Neo4j | `postgres` + `neo4j-driver` | REAL (live DB connections) |
| `pattern-persistence.ts` | Auto-save detected patterns (temporal/inferred/spatial/evidence-cluster) to PG `detected_patterns` table with `status='pending'` (HITL-gated); helper for graph-analytics, evidence-linker, spatial-analytics | `postgres` | REAL |
| `spatial-analytics.ts` | PostGIS-backed geospatial forensics: proximity clustering, movement pattern analysis (Haversine), geofencing alerts, spatial-temporal entity correlation, location prediction; writes via `pattern-persistence` | `postgres` + PostGIS | REAL (requires PostGIS) |
| `timeline-parser.ts` | Google Location History JSON parser: VISIT/ACTIVITY/PATH events, Haversine distance, multi-device anomaly detection, semantic type (HOME/WORK), activity type (WALKING/DRIVING) | None (pure TS math) | REAL |
| `text-miner.ts` | Smart forensic text search routing ugrep vs ripgrep by content type (conversation/code/document/mixed); timeline extraction from timestamps; result grouped by file + timeline view | `ugrep` / `ripgrep` CLI | REAL (CLI binaries required) |
| `search.ts` | ripgrep JSON-output wrapper + ugrep support + JS fallback; structured `SearchResult` with file/line/context; web/news/research stubs via config | `ripgrep` CLI | REAL (ripgrep path); web search = stub |
| `summarization.ts` | Hierarchical map-reduce summarization: chunk→chunk-summary→combine; citation tracking; concise/detailed/bullet styles; configurable LLM provider | Content store + LLM | REAL structure; LLM call requires provider config |
| `retrieval.ts` | BM25 (k1=1.2, b=0.75) keyword retrieval + hybrid (BM25+embeddings) over content store; supporting-span extraction for Q&A | Content store | REAL |
| `document.ts` | Pandoc format→markdown + Tesseract OCR; heading/paragraph/sentence/fixed segmentation; stores results in content store | `pandoc` CLI + `tesseract` CLI | REAL (CLI tools required) |
| `document-processors.ts` | Composite: `pandocConvert` (content-store-aware, handles sha256: refs) + `ocrImageOrPdf` + Stirling-PDF orchestration; temp-file lifecycle management | `pandoc` + `tesseract` + optional Stirling | REAL |
| `format-converter.ts` | Universal I/O: Tesseract OCR, Pandoc, pypdf text extraction, native JSON/CSV/HTML parsers; tool-availability cache (check at startup); 12 input + 6 output formats | `tesseract`/`pandoc` CLI + optional pypdf | REAL (graceful tool-check) |
| `markdown-parser.ts` | Streaming markdown parser splitting by `#` headers or date patterns; yields `ParsedJournalEntry` with content/date/title/metadata | `readline` (Node stdlib) | REAL |
| `html-parser.ts` | Schema-driven HTML chat parser (loads JSON schemas from `server/mcp/schemas/`); streaming cheerio + htmlparser2; detects schema by filename pattern; extracts sender/content/timestamp | `cheerio` + `htmlparser2` | REAL |
| `xml-parser.ts` | SMS Backup & Restore XML parser with Zod schema (sms + mms parts, base64 image data); uses `fast-xml-parser`; full MMS part extraction | `fast-xml-parser` + `zod` | REAL |
| `xml-streaming-parser.ts` | SAX-streaming XML parser (memory-safe for multi-GB files); emits `ParsedMessage` with uuid/record_hash/address/contact_name/body/_parts; per-record SHA hash | `sax` + `crypto` | REAL |
| `diff.ts` | Text diff (unified/JSON/inline) + Levenshtein/Jaccard/cosine similarity + merge-proposal with conflict detection + patch generation/application | Content store (pure TS impl) | REAL |
| `rules.ts` | YAML/JSON rule-set engine: regex/keyword/path/structural/semantic rules; action proposals (move/delete/merge/label); all actions approval-gated | `fs` + YAML parser | REAL |
| `browser-search.ts` | Playwright headless browser (navigate/screenshot/extract/click/fill) + LLM-optimized search via Tavily/Perplexity/SerpAPI (each disabled by default, requires API key) | `playwright` + optional API keys | REAL (Playwright); search APIs = config-disabled |
| `llamaindex.ts` | LlamaIndex `SentenceSplitter` text chunking (configurable size/overlap); pure Node, no external service | `llamaindex` | REAL |
| `langgraph-plugin.ts` | Exposes LangGraph forensic-investigation + document-processing workflows as MCP tools (`createGraph`/`executeGraph`/`streamGraph`); wires to `forensic-workflow.ts` state machine | `langgraph-adapter` (local) | Partial — orchestration is mostly simulated/placeholder (per §7 prior note) |
| `library-tools.ts` | JS library wrappers as MCP tools: cheerio (HTML), fast-xml-parser, franc (language-detect), JSON5, natural (NLP), compromise (NLP), string-similarity, yaml, csv-parse | Pure JS libs | REAL |
| `filesystem.ts` | Sandboxed filesystem ops (allowlist roots `SANDBOX_ROOT`/`DATA_ROOT`): list-dir, read-file (→content store), gated write (approval required), glob | `fs` (Node stdlib) | REAL (with sandbox guard) |
| `python-tools.ts` | Generic Python subprocess bridge: runs arbitrary Python scripts via `spawn`, passes JSON payload via stdin, returns parsed JSON; 30 s timeout | `python3` / `python` CLI | REAL (Python must be installed) |
| `n8n.ts` | n8n workflow trigger + status check + webhook registration; **off by default** (`enabled: false`); `N8N_URL`/`N8N_API_KEY` env | `n8n` REST API | REAL (config-disabled; requires n8n running) |

---

### 8b. `mcp-servers/py-mcp-server/src/document_intelligence/engines/*.py` — 11 engines

| Engine | cost_tier | locality | capabilities | supported_formats | is_available() requires | REAL vs stub |
|---|---|---|---|---|---|---|
| `TesseractEngine` | FREE | LOCAL | OCR, MULTILINGUAL (100+ langs) | .png .jpg .jpeg .tiff .bmp .webp .pdf | `tesseract` CLI + `pytesseract` | REAL |
| `DoclingEngine` | FREE | LOCAL | OCR, TABLE_EXTRACTION, LAYOUT_ANALYSIS, CHUNKING, RAG_NATIVE | .pdf .docx .pptx .xlsx .html .png .jpg .jpeg .tiff | `import docling` | REAL |
| `DocTREngine` | FREE | LOCAL | OCR, LAYOUT_ANALYSIS (deep-learning, messy scans) | .pdf .png .jpg .jpeg .tiff .bmp .webp | `import doctr` | REAL (process() has TODO note but core available) |
| `OcropusEngine` | FREE | LOCAL | OCR, LAYOUT_ANALYSIS (trainable, domain-specific) | .png .jpg .jpeg .tiff .bmp | `ocropus-nlbin` or `ocropus-gpageseg` CLI | REAL (requires owner approval to enable) |
| `PandocEngine` | FREE | LOCAL | FORMAT_CONVERSION, CHUNKING (40+ formats) | .docx .odt .rtf .html .md .rst .tex .epub .txt .pdf .pptx | `pandoc` CLI | REAL |
| `UnstructuredEngine` | FREE | LOCAL | OCR, CHUNKING, LAYOUT_ANALYSIS, RAG_NATIVE, FORM_EXTRACTION (65+ types) | .pdf .docx .html .eml .msg .png .jpg .csv .xlsx .pptx + more | `from unstructured.partition.auto import partition` | REAL |
| `GlmOcrEngine` | FREE (local) / PAID_PER_USE (cloud) | LOCAL / CLOUD (endpoint-dependent) | OCR, CONTEXT_AWARE, MULTILINGUAL (vision-LM) | .pdf .png .jpg .jpeg .tiff .bmp .webp | `GLM_OCR_ENDPOINT` env + `requests` health-check | Partial — process() has TODO; endpoint must be stood up |
| `LlamaParseEngine` | PAID_PER_USE | CLOUD | OCR, TABLE_EXTRACTION, CHUNKING, RAG_NATIVE, LAYOUT_ANALYSIS | .pdf .docx .html .pptx .png .jpg .jpeg | `LLAMA_CLOUD_API_KEY` + `import llama_parse` | Partial — process() has TODO; requires API key + approval |
| `AwsTextractEngine` | PAID_PER_USE | CLOUD | OCR, TABLE_EXTRACTION, FORM_EXTRACTION (industry-best tables/key-value) | .pdf .png .jpg .jpeg .tiff | `AWS_ACCESS_KEY_ID` or `AWS_PROFILE` + `import boto3` | REAL (core detect_document_text implemented; advanced table cell relations TODO) |
| `GoogleDocAIEngine` | PAID_PER_USE | CLOUD | OCR, HANDWRITING, MULTILINGUAL (200+ langs), FORM_EXTRACTION, TABLE_EXTRACTION | .pdf .png .jpg .jpeg .tiff .gif .bmp .webp | `GOOGLE_APPLICATION_CREDENTIALS`/`GOOGLE_DOCAI_PROJECT_ID` + `from google.cloud import documentai` | Partial — process() has TODO; needs GCP setup + approval |
| `IbmWatsonxEngine` | ENTERPRISE | CLOUD | OCR, LAYOUT_ANALYSIS, FORM_EXTRACTION, TABLE_EXTRACTION, CONTEXT_AWARE (compliance/legal) | .pdf .docx .html .txt | `WATSONX_API_KEY` + `WATSONX_PROJECT_ID` + `from ibm_watsonx_ai import APIClient` | Partial — process() has TODO; enterprise license required + approval |

> **Summary:** 5 engines are fully REAL and runnable without cloud creds (Tesseract, Docling, DocTR, Pandoc, Unstructured). OCRopus is REAL but requires CLI install + explicit owner enable. GLM-OCR/LlamaParse/Textract/DocAI/Watsonx have partial implementations; their `is_available()` guards work correctly (no silent failures), but `process()` bodies all have a `TODO: Full implementation requires owner approval` note. None are silently broken stubs — they will raise informative errors if called without deps/creds.

---

### 8c. `server/mcp/loaders/*.ts` and `server/mcp/pipelines/*.ts` — second parser set

**Loaders (11 files):**

| File | Capability | Completeness |
|---|---|---|
| `facebook-parser.ts` | Streaming HTML Facebook export parser (handles 100 MB+ files); line-by-line depth-tracking; extracts text/timestamp/sender/threadId/reactions | REAL (streaming) |
| `xml-sms-parser.ts` | Streaming XML SMS parser (multi-GB safe); SAX-style line-buffering, handles `<sms>` and `<mms>` tags | REAL (streaming) |
| `pdf-imessage-parser.ts` | iMessage PDF parser via Python `pdf_extractor.py` subprocess (`pdfplumber`); timestamp/sender pattern matching | REAL (requires Python + pdfplumber) |
| `sms-loader.ts` | `BaseDocumentLoader` subclass for SMS (iOS SQLite, Android XML, CSV, JSON); routing by format | REAL structure; iOS SQLite branch is partial |
| `real-embedding-service.ts` | Production embedding via `BUILT_IN_FORGE_API_URL` / `BUILT_IN_FORGE_API_KEY` (OpenAI-compatible); batch support, retry logic | REAL (requires env creds: Manus-specific) |
| `embedding-pipeline.ts` | pgvector embedding pipeline: chunk→embed→store; semantic search with filters (platform/case_id/date_range); references Supabase pgvector | REAL schema/types; Supabase-specific (replace PG URL with project PG) |
| `lexicon-importer.ts` | Dynamic HurtLex + custom-lexicon GitHub fetcher; CSV/JSON/txt, language-filter, category mapping, priority conflict resolution; writes to `behavioralPatterns` via Drizzle | REAL |
| `document-hierarchy.ts` | Document→section→chunk→span hierarchy builder; structural document model | REAL |
| `base-loader.ts` | `BaseDocumentLoader` ABC: `load()`, `chunk()`, standardized `LoadedDocument`/`DocumentChunk`/`DocumentMetadata` | REAL |
| `unstructured-loader.ts` | `Unstructured.io` API-based loader (cloud or local); partition strategies; multiple format support | REAL (Unstructured endpoint required) |

**Pipelines (3 files):**

| File | Capability | Completeness |
|---|---|---|
| `production-pipeline.ts` | Full pipeline: detect format (FB HTML/XML SMS/PDF iMessage) → parse → chunk (100 msg/chunk) → MultiPassClassifier → route to Supabase (messages/behaviors) + Neo4j entities + Chroma TTL; progress callbacks | REAL (wired to live storage clients) |
| `end-to-end-pipeline.ts` | Same format routing as production but lighter; outputs `ProcessedMessage` with full prelim analysis fields; `ConversationSegmenter` integration; designed as the reference pipeline shape | REAL |
| `document-pipeline.ts` | Document-centric pipeline (less forensic focus): format detect → load → chunk → embed → store | REAL |

**OVERLAP / duplication assessment:**

- `loaders/facebook-parser.ts`, `loaders/xml-sms-parser.ts`, `loaders/pdf-imessage-parser.ts` are **DUPLICATE** of `mcp-servers/ts-mcp-server/src/tools/FacebookExportParser.ts`, `SmsXmlParser.ts`, `ImessagePdfParser.ts`. The `mcp-servers/ts-mcp-server` versions are the **more complete / canonical** (they are wrapped by `SmsEvidenceIngestor` with DuckDB vault + hash + Postgres write). The `loaders/` versions are standalone streaming parsers without the custody layer.
- The `pipelines/` files are **NOT duplicated** in `mcp-servers/ts-mcp-server/` — they represent a higher-level orchestration layer (MultiPassClassifier + segmenter + storage routing) not present in the MCP tool server. The pipeline shape (preliminary→full→meta→reconcile) is the most complete TS-level orchestration and is the reference for the Agno workflow design.
- **Verdict:** `mcp-servers/ts-mcp-server` parsers win for parser fidelity (custody layer); `pipelines/` win for orchestration shape. The `loaders/` versions are intermediate and can be deprecated in favor of the two winners.

---

### 8d. `drizzle/*.ts` — schemas not yet covered

| File | Tables defined | DB engine |
|---|---|---|
| `production-message-schemas.ts` | `mclFactors`, `behaviorCategories`, `messagingDocuments`, `messagingConversations`, `messagingMessages` (with `conversation_cluster_id` PLAT_YYMM_TOPIC_iii + preliminary analysis fields + custody fields), `messagingAttachments`, `messagingBehaviors`, `messagingEvidenceItems`, `messagingFactorCitations` | PostgreSQL (Drizzle pg-core) |
| `patterns-schema.ts` | `behavioralPatterns` (user-owned regex patterns, severity, MCL factors, match count), `patternCategories` | MySQL (mysqlTable — legacy; target is PG) |
| `prompts-schema.ts` | `systemPrompts` (versioned, success-rate tracked, per-tool), `workflowTemplates` (JSON steps, public/private) | MySQL (legacy) |
| `relations.ts` | Drizzle relation definitions connecting `users` → many of: apiKeys, behavioralPatterns, bertConfigs, forensicResults, hurtlexCategories/Terms, patternCategories, schemaResolvers, severityWeights, systemPrompts, workflowTemplates | Both (follows parent table engine) |
| `settings-schema.ts` | `nlpConfig` (similarity threshold, time-gap, chunking strategy per user), `llmProviders` (encrypted API key per provider, priority, base URL), `llmRoutingRules` (task-type→provider routing, per user) | MySQL (legacy) |

> **Note:** `patterns-schema.ts`, `prompts-schema.ts`, `settings-schema.ts` use MySQL (`mysqlTable`) — these are legacy dial-stack MySQL schemas, not the target PostgreSQL schema. The data model they define (patterns, prompts, NLP config, LLM routing rules) is valuable and should be ported to PG when those capabilities are built into the Agno platform.

---

### 8e. `server/mcp/storage/*`, `server/mcp/llm/smart-router.ts`, `server/mcp/forking/tool-fork.ts`, `server/mcp/forensics/{behavior-service,chain-custody,identity-service,hurtlex-fetcher,hurtlex-stream}.ts`

| File | Capability | REAL vs stub |
|---|---|---|
| `storage/chroma-client.ts` | Dual-collection Chroma: evidence-processing (72 h TTL with `expires_at`) + project-context (persistent); preliminary classification stored in metadata | REAL |
| `storage/pgvector-client.ts` | LangChain `PGVectorStore` + Ollama embeddings (`nomic-embed-text`) for permanent semantic search (Tier 3); store/search/delete | REAL (LangChain/Ollama-specific; replace Ollama embedder with NIM for this project) |
| `storage/directus-client.ts` | Directus CMS binary vault: file upload/download with SHA-256 verification; collection management; chain-of-custody tracking for files | REAL |
| `storage/systemRouter.ts` | Routes storage writes by tier (Chroma T1 → Postgres T2 → LanceDB T3 → Neo4j T4); promotion workflow for ad-hoc → federated schema | REAL (storage-tier router) |
| `llm/smart-router.ts` | LLM routing by task type (simple/complex/creative/long-context/embedding/code/math/speed/multimodal), cost tier (free→cheap→moderate→expensive), latency, context window, load balancing (multi-key round-robin), failover | REAL |
| `forking/tool-fork.ts` | Multi-surface tool export: creates platform-specific ToolFork variants (generic / claude-mcp / gemini-extension / openai-function) with parameter overrides, pre/post processing hooks, platform config | REAL — this is the multi-surface gateway differentiator |
| `forensics/behavior-service.ts` | Pattern-matching behavioral analysis from PG `behavioralPatterns` (or in-memory default patterns: threat, gaslighting, blame-shifting, minimizing); regex-based, with DB cache (1 h TTL); **STUB patterns only** — note explicitly says "DB table not yet implemented" | Partial-STUB (default patterns are 4 hardcoded regex, not the 256-behavior Karystianis taxonomy) |
| `forensics/chain-custody.ts` | SHA-256 hash-linked chain-of-custody with `previousEntryId` chaining (blockchain-style); JSONL persistence; `verifyChain`; legal admissibility design | REAL |
| `forensics/identity-service.ts` | Deterministic conversation ID from participant list (SHA-256 of sorted participants); get-or-create `messagingConversations` in PG via Drizzle; uses `uuidv7` | REAL |
| `forensics/hurtlex-fetcher.ts` | Fetch + cache HurtLex lexicon from GitHub to PG (`hurtlexTerms`/`hurtlexCategories`/`hurtlexSyncStatus`); language-filtered; 18 category codes defined; versioned sync status | REAL |
| `forensics/hurtlex-stream.ts` | Streaming HurtLex queries — NO local storage; fetches from GitHub on-demand, streams results; 18 category codes hardcoded; alternative to fetcher for low-storage use | REAL |

### Scan closed (2026-06-13) — final capability confirmations

- **Document-intelligence engines (11, all confirmed)**: `IbmWatsonxEngine`, `GoogleDocAIEngine`, `TesseractEngine`, `DoclingEngine`, `DocTREngine`, `OcropusEngine`, `PandocEngine`, `GlmOcrEngine`, `LlamaParseEngine`, `AwsTextractEngine`, `UnstructuredEngine` — each implements `capabilities / supported_formats / cost_tier / locality / is_available / process`. Registry auto-loads + builds fallback chains (local-free preferred). **Strong wrap-as-MCP candidate; covers the Google + IBM direction out of the box.**
- **ts-mcp-server tool classes (confirmed)**: `EvidenceIngestor`, `SmsEvidenceIngestor`, `SmsXmlParser`, `FacebookExportParser`, `ImessagePdfParser`, `MessageChunker`, `Pass1Runner`, `DuckDbVault` (+`DuckDbService`), `PostgresWriter`, `ReviewQueue`, `AdminTools`, `SbvClient`, `SbvIngestor`. Many have `(2)` duplicate twins = merge artifacts to dedupe on port.
- **`tools/nlp/manipulative-expression-recognition/`**: an **LLM-prompt-based** manipulation recognizer (GPT calls w/ backoff, NER anonymization, chunking, open/closed-ended analysis, HTML highlight rendering). Third-party reference tool — **NOT** the owner's trained "Tether" ML.
- `server/mcp/*` non-plugin exports (chroma working-memory/stream-processor, storage clients chroma/pgvector/directus, llm provider-hub/smart-router, forking/tool-fork, forensics behavior/identity/hurtlex services, prompts, workers, queue, observability) catalogued via export grep (spooled to disk) — capability-level coverage achieved; bodies on demand.

**Status: archive inventory COMPLETE at capability level across all three corpora.** Remaining work is the plan/build sequencing (§5) — not more scanning. The one genuine hole is the owner's trained behavioral ML ("Tether"), deferred by owner decision.

### Located but deferred / elsewhere

- ~~**CORRECTION:** the owner's trained behavioral ML, **Tether, IS in dial-stack** — at `dial-stack/utilities/apps/ml-nlp/Tether/` (working HuggingFace models `SamanthaStorm/tether-*`: 18-label abuse detection, DARVO regressor, boundary-health, 140+ motif regexes). It sits under the **deferred `utilities/` area**, so it was intentionally not scanned this session.~~ **SUPERSEDED 2026-08-23 (Claude Code · Opus 5) — the path is wrong.** `dial-stack/` has **no `utilities/` directory at all** (verified: its top level is AGENTS.md, CLAUDE.md, docs, drizzle, mcp-servers, migrations, ontologies, scripts, server, shared, plus config files). Tether is real, but it lives at the **workspace root**, not inside dial-stack:

      E:/AI_Workspace/utilities/External_Utils_Lib/Context_Analysis_Suite/ml-nlp/Tether

  Verified contents: `app.py`, `abuse_type_mapping.py`, `motif_tagging.py`, `README.md`,
  `requirements.txt`. Real HuggingFace model IDs in `app.py`:
  `SamanthaStorm/tether-multilabel-v6` (:64), `tether-sentiment-v3` (:69-70),
  `tether-darvo-regressor-v1` (:83-84).
  The `py-mcp-server/tools/user_detection.py` placeholder wrapper is still *not* Tether — that part
  of the note stands.
  **Relevance note:** per owner ruling 2026-08-23 the behavioral-analysis mechanism over-flags and
  needs a full rework, so wiring Tether is deferred behind that redesign, not queued as-is.
- **ChatMiner's AI-chat parsers** live in `Agno-MCP-Platform-alpha` (confirmed separate corpus).
- **Chat Parser App v2.0** `ParserSchema` two-pass *runner* (the `schemaResolvers` table exists; the LLM schema-proposing runner may be in `MCP_Tool_Platform-REF-READ-ONLY`).
