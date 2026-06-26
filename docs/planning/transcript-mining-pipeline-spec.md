# Transcript-Mining → Forensic Knowledge Pipeline — Design Spec

> _Byline: Claude Code · Opus 4.8 · 2026-06-19_
> Status: **DRAFT for review** · Author: Matt + Claude Code (brainstorm session)

## 1. Goal

Turn ~9–12 months of scattered AI-chat transcripts and evidence dumps (Claude Code,
Codex, Gemini, OpenCode, **Perplexity exports**, Downloads, phone extractions) into
**structured, court-usable forensic records** and **searchable knowledge** that the Agno
agents can consume for evidence search, presentation, and timeline creation.

The forensic subject is a **high-conflict custody case** (Salem v. Kinzel): documenting
coercive control, parental alienation, DARVO, triangulation, and manufactured incidents,
mapped to **MCL 722.23** best-interest factors.

## 2. Hard constraints

1. **Token-frugal** — bulk work runs locally / in-DB at **$0 Claude tokens**. Claude is
   reserved for ambiguous judgment calls and final synthesis only.
2. **No OneDrive hydration** — content is read from the **R2 bucket**, never by hydrating
   OneDrive placeholders. Metadata-only walks for any OneDrive inventory.
3. **Trauma-aware** — pipeline surfaces structured output; Matt is not required to re-read
   raw dumps. Some content is severe (suicide-baiting, targeted trauma).
4. **Don't reinvent** — reuse Matt's existing parsers, ontology, and schema (in
   `extracted-code/`). Net-new code is glue only.
5. **Don't collide with the platform agent** — additive, read-mostly. Land in an **isolated
   test target**; reconfigure nothing on the live platform.

## 3. Reused assets (already built — `the-platform-workspace/extracted-code/`)

| Stage | Asset |
|---|---|
| Ingest transcripts | `parsers/chat-exports/`: `ClaudeCodeJSONLParser`, `chatgpt_parser.py`, `robust_conversation_extractor.py`, `TakeoutExtractor` |
| Data model | `ontologies-datasets/zep_salem_ontology_v3_final.py` (Person/Location/Incident/Statement/Vulnerability + coercive-tactic/DARVO/gatekeeping edges) + `ontologies/mcl_722_23.ttl` + `behavioral_patterns.ttl` |
| Local extraction | `test_gliner.py` (GLiNER NER) + `unsloth_dataset.jsonl` (behavioral-pattern fine-tune set) |
| Relational schema | `schemas/drizzle/*.ts`, `agno-alpha-schema.sql`, `Salem_SMS_Tables_*.sql` |

> Note: `extracted-code` is a **2026-06-10 staging snapshot** ("nothing wired live; port
> deliberately"). Treat as canonical source-of-design; verify before porting.

## 4. Infrastructure (confirmed this session)

- **Bucket:** Cloudflare **R2** (S3-compatible) — transcript + evidence dumps.
- **PG:** `agentos-db`, **PostgreSQL 18.1** @ `100.119.96.29:5432` (OVH-3, **tailnet-only**),
  extensions: `pg_duckdb`, `pgvector`, `postgis`, `pg_trgm`, `unaccent`, `pgcrypto`.
  Creds are dev defaults — **source from env/secret store; rotate before real evidence.**
- **Agno REST:** `http://100.72.169.40:8000` (tailnet). MCP is **not** wired (ContextForge
  empty, AgentOS MCP 404) — use REST only.
  - `POST /knowledge/content` → embeds via **OpenRouter** → vectors to **Milvus** + contents
    to **PG `*_contents`**. (`GET /knowledge/config`, `GET /knowledge/content` to inspect.)
  - `/agents` is **empty** (no agents defined yet) → `/agents/{id}/runs` unusable for now.
- **Embeddings:** OpenRouter — use `bge-m3` or `codestral-embed`; **avoid NVIDIA NIM
  asymmetric models** (400 without `input_type`).

## 5. Architecture

```
Cloudflare R2 (transcript + evidence dumps)
   │  DuckDB (local CLI or pg_duckdb) reads CSV/Parquet/JSON directly from R2   [no hydration]
   ▼
[in-DB] filter + segment mixed convos        DuckDB/SQL · pg_trgm fuzzy   [$0 tokens]
   ▼
local GLiNER + unsloth fine-tune → Salem-ontology entities/incidents/statements   [$0 tokens]
   ▼
LOCAL SQLite — mirrors the canonical PG schema/tables   ← primary staging store: offline, $0, zero platform risk
   │   ontology records + edges, MCL factor, source/line/timestamp provenance (no vectors — deferred to import)
   ▼
Claude: ambiguous-case adjudication + final timeline / MCL-722.23 synthesis   [small]
   ▼
Human sign-off before "established fact"
   ▼
IMPORT when ready → PG via pg_duckdb (SQLite scan) or sqlite_fdw · push text → Knowledge (/knowledge/content → Milvus)
```

**Provenance / chain-of-custody:** every structured record carries `source_file`,
`line/offset`, `timestamp`, and `tool_origin`. Nothing is "established" without Matt's review.

## 6. Phasing

### Phase 1 — Local SQLite staging schema (offline; zero platform risk)
Consolidate the canonical table design from `extracted-code/schemas/` + the Salem ontology
into a single **SQLite** database mirroring the PG schema. Fully local — no tailnet, no live
platform, $0 tokens. This is the staging store everything writes to first.

### Phase 2 — Bulk extraction into SQLite (the value)
Local DuckDB reads the R2 dumps → your parsers normalize → local GLiNER/unsloth extract
Salem-ontology records → write to **local SQLite**. Claude only on ambiguous cases + synthesis.
Runs entirely offline; nothing touches PG or Knowledge yet.

### Phase 3 — Import & promote (when ready)
Import SQLite → PG via **pg_duckdb** (DuckDB SQLite scan) or **`sqlite_fdw`**; push the
searchable text to Knowledge (`POST /knowledge/content` → Milvus), TEST collection first,
then live so the Agno agents consume it for evidence search / presentation / timeline.

## 7. Open items / dependencies

- **R2 secret** for `pg_duckdb` (account id, access key, endpoint) — needed for Phase 2.
- **Test isolation mechanism** for `/knowledge/content` — confirm a separate collection/
  namespace exists, or tag + plan `DELETE` cleanup.
- **No Agno agents defined** — Phase-2 synthesis runs on Claude until agents surface
  (`build_agent_team` not surfacing; platform-agent's issue, not this pipeline's).
- **Backend durability** — Zep deprecated, Windmill dead; this design avoids both.
- **Perplexity content** is web-only → needs export into R2 before it can be processed.

## 8. Non-goals (YAGNI)

- No MCP wiring (REST only until ContextForge is populated).
- No new ontology/parser authoring — reuse `extracted-code`; only consolidate/port.
- No touching the live `ai` platform tables or live Knowledge until Phase 3.
