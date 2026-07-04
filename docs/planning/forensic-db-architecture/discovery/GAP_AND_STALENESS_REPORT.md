# GAP, BLIND-SPOT & STALENESS REPORT — Forensic DB Architecture

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Inputs synthesized: A1 (capabilities/liveness), A2 (SSOT/ADR drift), A3 (prior-work crosswalk), A4 (prior reports), A5 (conversation-log mining).
> Mandate: compare what THIS design already covers vs what prior work ACTUALLY contains; flag gaps/blind spots; verify staleness of every resource; recommend trust/re-verify/ignore.

---

## PART 1 — HAVE vs AVAILABLE: GAP & BLIND-SPOT ANALYSIS

"HAVE" = covered by the current design (A2 locked stack + A3 crosswalk + A1 tooling). "AVAILABLE" = what prior schemas/ontologies/parsers/reports actually contain (A3/A4/A5). Gaps are AVAILABLE-but-not-HAVE.

### 1.1 Parsers that EXIST but are NOT in the crosswalk/plan (biggest blind spot)

A3's crosswalk only mapped the three **Chunker HTML config** files (facebook/snapchat/generic JSON selector maps). It did **not** map the far richer, already-salvaged parser corpus that A5 catalogs in `extracted-code/` (the deliberate, deduped, provenance-tracked staging copy — which A3 never consulted; A3 used arbitrary `dev-resources/Archives/**` copies instead). Missing from the plan:

| Parser (AVAILABLE) | Location | Forensic value not yet captured | Gap severity |
|---|---|---|---|
| **enhanced-xml-chunker.py** | `dev-resources/Archives/TheBigOne/02_TraceIQ_Repo/20260106033151884/` | tz handling, **base64 image extraction**, **CALL LOGS** (SMS-vs-calls detection) | HIGH — call-logs are a whole evidence class absent from the `message` model |
| **sms_backup_parser.py** | `extracted-code/parsers/messaging/` | **blocked-call type 5/6 forensic indicators** | HIGH — distinct evidentiary signal |
| **SMS XML parser / SmsXmlReader** (streaming, 4GB-capable, SMS-Backup&Restore attr map) | `extracted-code/parsers/messaging/xml-sms-parser.ts` | streaming ingest design for huge XML | MED |
| **GVoice / pdf-imessage / facebook-parser (TS)** | `extracted-code/parsers/messaging/` | Google Voice + iMessage-PDF + structured FB (vs brittle CSS Chunker config) | MED |
| **Chat-export parsers** (ChatGPT/Claude JSONL, Takeout, output_schemas) | `extracted-code/parsers/chat-exports/` | AI-chat-log evidence class — **entirely absent from data model** | MED |
| **Location/Takeout parsers** (Google location-history, photos) | `extracted-code/parsers/location/` | feeds PostGIS/timeline raw layer | MED |
| **Snapchat parser** (source, not the HTML config) | `dial-stack/utilities/parsers/snapchat/` (salvage skipped — 112MB w/ exe) | real Snapchat-JSON ingest | MED — A3 only has the brittle HTML-selector config |
| **schema-resolver.ts** (AI field-mapping for UNKNOWN export formats) | `extracted-code/tools/schema-resolver.ts` | auto-maps novel/unseen export shapes → future-proofs ingestion | HIGH — strategic capability, unmapped |
| **SBV cluster** (Go upstream + TS client + ingestor + MCP) | `extracted-code/sbv/` | full SMS-Backup&Restore pipeline | MED |
| **XLSX** | skill `xlsx-processing-anthropic` present (A1); **no XLSX ingest path in plan** | spreadsheet evidence (financials, logs) | MED — flagged in brief, confirmed gap |

**Net:** the plan models messaging well via TraceIQ V4.1 `messages`, but **call-logs, blocked-call indicators, AI-chat-export logs, XLSX, and the AI schema-resolver** are blind spots. The `normalized_messages` universal-schema design (A5, 05-26/06-01: raw XML → `raw_data` JSON column, platform-hop reconstruction, query JSON natively in DuckDB) is also unmapped and **partially conflicts** with TraceIQ's typed `messages` table — needs an explicit raw-JSON-landing vs typed-row reconciliation decision.

### 1.2 Ontology / pattern assets that EXIST but are NOT in the crosswalk

A3 deeply mapped **salem_v3** (entities/edges) — good. But it flagged the "models only adversarial conduct / lacks both-parties + full-relational-cycle" gap as something to **invent with the user**. That is a FALSE gap: the fill already exists and was simply not cross-referenced:

| Asset (AVAILABLE) | Location (A5) | Fills which design gap |
|---|---|---|
| **positive_behaviors.ttl** | `extracted-code/ontologies-datasets/ontologies/` | **Directly fills A3's "full relational cycle (positive/love-bombing/repair)" gap — do not invent, ADOPT** |
| **behavioral_patterns.ttl** | same dir | structured behavior taxonomy behind Tactic/BehavioralPattern |
| **mcl_722_23.ttl** (12 MCL best-interest factors, RDF/Turtle) | same dir | custody legal-lane factor model (ties to `mcl-factor-mapper` skill) |
| **detection_patterns.py** (256-pattern classifier, MCL A–L, 18 behavior categories, child-name patterns, **DARVO sequence**) | R5 inventory | the actual abuse-pattern engine — unmapped |
| **seed-patterns.ts ~303 / patterns-schema.ts / behaviors.yaml** | `extracted-code/schemas/drizzle/` + rules | 303-row behavioral rule library + its schema |
| **hurtlex_loader.py** (EN lexicon) | `extracted-code/ontologies-datasets/` | offensive-lexicon scoring |
| **Semantica pipeline** (997 ln: NER, relation extraction, temporal KG, **conflict detection**, **PROV-O provenance**, `source_hash` linking) | `dial-stack/utilities/python-tools/semantica_pipeline.py` | the provenance + conflict engine A2 lists as substrate but A3 never mapped its model |

**Net:** the abuse-pattern/legal-conduct lane has rich prior art (TTL ontologies + 303-pattern library + 256-pattern classifier + DARVO + PROV-O conflict engine) the crosswalk did not ingest. The both-parties/positive-cycle requirement is satisfiable by ADOPTING `positive_behaviors.ttl`, not by inventing new node types.

### 1.3 Schema fields / tables that EXIST but are NOT yet mapped

- **Drizzle alpha schema** (`production-message`, `patterns-schema (303)`, prompts, settings, relations) and SQL deployments (`agno-alpha-schema.sql`, `Salem_SMS_Tables_Complete_Deployment_2025-12-27.sql`) — A5 lists them in `extracted-code/schemas/`; A3 crosswalk omits them entirely.
- **Doc-intelligence tables** (A4 R8/R6): `sections / chunks / spans / summaries / entities / keywords / findings / approvals` — the HITL **approvals** table and document-decomposition tables are unmapped, despite HITL being a hard guardrail.
- **Alpha forensic-DB tables** (A4 R7 "missing-then" list): `behavioralPatterns, patternCategories, hurtlexTerms/Categories, bertConfigs, severityWeights, mclFactors, schemaResolvers, forensicResults` — verify which now exist; map the survivors.
- **UUIDv7 + SHA-256 chain-of-custody** design (A5, 05-26): aligns with ADR-0013 native `uuidv7()` but is not carried as an explicit column contract in the crosswalk.
- **Timestamp-precision class (exact/approximate/inferred/uncertain)**: A3 correctly notes it is **missing from ALL prior schemas** → must be added (guardrail). A real, confirmed gap (an addition, not prior art).

### 1.4 GPS / PostGIS prior art (mostly HAVE, minor gaps)

Well covered by A3 section D (normalized_geo_schema_v5: `location_key` dedup, geohash8/9, dual-provider `geocode_resolution` with `disagreement_flag`/`tie_break_reason`, append-only `geocode_audit`). Minor gaps: confirm PostGIS `geography` vs `geometry` SRID choice; ensure `location_fuzzy` (privacy-fuzzed coords) is preserved as a distinct provenance class, not silently normalized away; A3's swap of manual geohash for PostGIS generated columns is sound but should be ratified.

### 1.5 Cross-cutting blind spots (from A4 §3, still open)

1. **No as-built/runtime verification** — every prior report is design-intent or status-claim; R6 "85% done" directly conflicts with R7/R8 "40%, placeholders." The "current forensic DB architecture" is answered by **ADRs + live probes (A1)**, NOT by any report.
2. **Reports assume a dead stack** (Supabase + Chroma + LanceDB + pgvector). Current = self-hosted PG(+pg_duckdb+PostGIS) + Milvus + Neo4j + R2/DuckDB. All schema reuse must be re-targeted.
3. **Migration/port progress untracked** — "alpha monolith → modular ts/py servers" backlog defined (R2) but no progress report exists.
4. **Open parser items**: Email parser (format TBD), Instagram "defined not built", iMessage two-pass, OCR pipeline.
5. **No security/PII-governance as-deployed audit** beyond "don't ingest Secrets/".
6. **extracted-code/MANIFEST.md was not consulted by the crosswalk** — A5 says PREFER it (deduped, provenance-tracked). The crosswalk should be re-anchored on it before adoption.

---

## PART 2 — STALENESS VERIFICATION TABLE

Verdicts: **current** (trust) / **aging** (use w/ verification) / **stale** (status untrustworthy; inventory may still help) / **superseded** (replaced — ignore as authority).

| Resource | Date (content / mtime) | Verdict | Superseded / corrected by |
|---|---|---|---|
| **ADR-0013** (pg_duckdb custom PG18 image) | 2026-06-10 | **current / LIVE** | — SSOT for the PG resource |
| **ADR-0003** (PG18 pgvector-only, NO DuckDB, FalkorDB deferred) | early | **superseded on every axis** | no-DuckDB→0013; FalkorDB→0014; pgvector-store→0027 |
| **ADR-0003 vs 0013 "conflict"** | — | **NOT a live conflict — supersession chain** | A2 C1: 0013 wins; **pg_duckdb-embedded is the correct resolution**; standalone DuckDB NOT blessed |
| README ADR index listing 0003 "Accepted" | current file | **stale label (drift)** | fix → "Superseded by 0013/0014/0027" (supersede, don't rewrite body) |
| ADR-0027 (Milvus = single vector store) | 2026-06-13 | current / LIVE on ovh2 | retires pgvector's vector role (Knowledge migration = Phase B/D) |
| ADR-0024 (SurrealDB analysis sink) | 2026-06-13 | **ratified, NOT yet deployed** | Phase D pending — locked but unbuilt (prompt mis-flagged as "new") |
| ADR-0030/0032 (R2 reach; federation drop) | 2026-06-23/26 | current | — |
| pgvector physically in PG18 image | live image | aging (legacy-resident) | doc-lag only; new vectors → Milvus; no image change now |
| **R1 DEV_RESOURCES_INDEX.md** | 2026-06-01 / 06-10 | **current (layout)**, stale (repo-status line) | "agno-mvp / abandoned" naming wrong; active repo = `Agno-MCP-Platform/` |
| **R2 TOOL_SOURCES_INVENTORY.md** | 2026-06-01 / 06-10 | **current** (best tool→source map) | same `agno-mvp` naming caveat |
| R3 wiki/INDEX.md (4-tier DuckDB→PG→Neo4j→LanceDB) | 2026-03-12 | **aging** | LanceDB→Milvus (0026); Dragonfly/FerretDB mandate; live OVH/Coolify topology |
| R4 wiki/tools/INDEX.md | 2026-03-15 | aging | tools stable; "production ready" aspirational |
| **R5 COMPLETE_SCHEMA_PARSER_INVENTORY.md** (2 byte-identical copies) | 2026-01-06 / 02-19 | **aging but authoritative on data model** | richest forensic-DB ref; **re-target Supabase/pgvector→PG/Milvus/R2**; dedupe to one |
| R6 STATUS_REPORT_2026-01-29 ("85% done") | 2026-01-29 | **stale (status) / useful (inventory)** | alpha monolith to port, not live stack; conflicts w/ R7/R8 |
| R7 AUDIT_REPORT (placeholders, forensics 0%) | 2026-01 | **stale** | contradicted by R6; use as "known-bad placeholder" checklist |
| R8 COMPREHENSIVE_GAP_REPORT (40% wired) | 2026-01 | **stale** | alpha-era backlog checklist only |
| R9 MCP_TOOL_CATALOG (design spec) | 2026-01 | aging (aspirational contract) | naming/contract conventions only |
| R10 FORENSIC_ANALYSIS_REPORT (TraceIQ) | 2026-01-06 / 05-25 | **stale (cleanup) / useful (timeline-DB design)** | dir-chaos obsolete; timeline schema + ETL passes durable |
| R11 FINAL_RECOVERY_REPORT | 2026-01-06 / 05-25 | **stale** | one-time recovery log; Flask backends gone (don't hunt) |
| R12 TraceIQ INDEX.md | 2026-01-03 / 05-25 | **aging (best timeline-DB doc)** | schema durable; Supabase deployment outdated |
| **Workspace_Manifest_*.json (78 files, Feb–Mar)** | 2026-02..03 | **stale** | superseded by R1/R2; historical noise; last-resort file-existence lookup only |
| memsearch `opencode-turns.db` | Jun 11 | **stale data / live engine** | metadata-only (no message text); plugin enabled but unfed |
| memsearch memory digests `.memsearch/memory/*.md` | latest Jun 27 | **current** | usable session recall |
| casebible.duckdb (`D:/casebible/`) | Jun 23, 68 MB | **current / LIVE** | trust as catalog/prototype store |
| claude-context index (workspace root) | — | **stale/empty** | NOT indexed → must (re)index before code search |
| LanceDB `.osgrep` indexes | — | live (may lag edits) | re-embed if repos changed |
| **TheBigOne tree** (`C:`/`D:`/`E:\…\TheBigOne`) | — | **GONE from disk (all 3 roots)** | migrated to `dev-resources/Archives/` + **`extracted-code/`** (PREFER the latter; MANIFEST.md mined 06-10) |
| All original absolute paths in transcripts | — | **dead pointers** | resolve via `extracted-code/MANIFEST.md` |
| osgrep MCP / process-child.js | uninstalled 06-11 | **superseded/removed** | memory-leak; removed from opencode + Claude configs — ignore |
| Plugins: claudikins-kernel, remember, ralph-loop, claude-session-driver | settings.json `false` | **disabled** | do not use |
| **memsearch plugin** | settings.json `true` | **ENABLED (brief was wrong)** | engine live; only its turn DB data is stale |

---

## PART 3 — TRUST / RE-VERIFY / IGNORE

**TRUST these (authoritative & current):**
- ADR-0013 (PG image SSOT) + ADRs 0014/0024/0027/0030/0031/0032 + PROJECT_CANON §5 — the locked stack.
- A1 live probes (graphiti, coolify, opencode, agno-gateway all LIVE 06-30) for as-built infra.
- `extracted-code/MANIFEST.md` + `extracted-code/` tree — deduped, provenance-tracked salvage (canonical prior-art source).
- R1/R2 (layout + tool→source map), casebible.duckdb, memsearch digests (≤Jun 27).
- A3's salem_v3 crosswalk and section-D geo crosswalk (sound mappings).

**RE-VERIFY before relying (aging / needs re-target):**
- R5 schema inventory, R10/R12 TraceIQ timeline-DB design — durable models, but re-target Supabase/pgvector/PostGIS → PG(+pg_duckdb+PostGIS)/Milvus/R2; verify TEXT-timestamp normalization; add the precision class.
- R3/R4 architecture intent — check each DB/tool against current ADRs.
- R6/R7/R8 — treat ONLY as "what exists to port" / "known placeholders" checklists; verify each claim against live state.
- Which alpha tables (behavioralPatterns, mclFactors, forensicResults, approvals, sections/chunks/spans…) actually exist now.
- `normalized_messages` raw-JSON-landing design vs TraceIQ typed `messages` — decide the reconciliation.
- Re-anchor the A3 crosswalk on `extracted-code/` copies (not arbitrary `Archives/**` copies); dedupe R5's two identical files.

**IGNORE (superseded / dead / disabled):**
- ADR-0003 as an authority (superseded); the README "Accepted" label for it (fix it).
- Workspace_Manifest_*.json snapshots (Feb–Mar) as anything but last-resort file lookup.
- All dead transcript absolute paths / the `TheBigOne` roots / osgrep / process-child.js.
- Disabled plugins (claudikins-kernel, remember, ralph-loop, claude-session-driver).
- MIGRATION_PLAN_v8 / `docs/planning/*` (PG16/pgvector-hybrid/`uuid_generate_v4`) as current — build-history.
- Reports' Supabase + Chroma + LanceDB + pgvector stack assumptions as the target.

---

## Appendix — Biggest corrections to fold downstream
1. **Standalone DuckDB is NOT blessed** — only pg_duckdb-in-PG (resolves the named ADR-0003/0013 "conflict").
2. **The "full relational cycle / both-parties" gap is already solved by `positive_behaviors.ttl`** — adopt, don't invent.
3. **Call-logs, blocked-call indicators, AI-chat-export logs, XLSX, and the AI schema-resolver are missing ingestion lanes** despite parsers existing.
4. **Build the crosswalk on `extracted-code/MANIFEST.md`, not `Archives/**`** — the deduped provenance-tracked source.
5. **Timestamp-precision class is a genuine new requirement** absent from every prior schema.
