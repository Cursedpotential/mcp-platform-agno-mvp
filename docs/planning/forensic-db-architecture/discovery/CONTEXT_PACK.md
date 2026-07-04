# CONTEXT PACK — Forensic DB Architecture (digest for section drafters)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Compact carry-forward digest (~1.4k words). Source of truth: A1–A5 + GAP_AND_STALENESS_REPORT.md in this folder. On conflict, SSOT docs (`Agno-MCP-Platform/docs/PROJECT_CANON.md` + ADRs) win.

---

## 1. DATA-TIER TOPOLOGY (owner-mandated HARD CONSTRAINT — never contradict)

FOUR independently-deployable resources, **no shared lifecycle** (separate bind-mounted volumes, independent start/stop/rebuild; a crash of one must never tear down the others — ref the decision to split the single-Coolify-app coupling):

1. **RELATIONAL/ANALYTICAL/SPATIAL = ONE unified resource**: PostgreSQL + PostGIS + embedded DuckDB via the **pg_duckdb** extension, all in a SINGLE service/container. **DuckDB is NOT standalone; PostGIS is NOT standalone** — both live INSIDE this one Postgres resource. (This is the correct resolution of the ADR-0003 vs ADR-0013 conflict: pg_duckdb-embedded wins.)
2. **MILVUS** (vector) = its own separate resource.
3. **NEO4J** (graph; Graphiti + Semantica are writers into it) = its own separate resource.
4. **SURREALDB** (consolidated analysis, IF adopted) = its own separate resource.

Never describe DuckDB or PostGIS as a separate/standalone deployable; never co-locate Milvus/Neo4j/SurrealDB into a shared lifecycle.

---

## 2. LOCKED STACK DECISIONS (ADR refs + state, from A2)

| Layer | Locked decision | ADR | State |
|---|---|---|---|
| Relational+analytics+spatial PG | Custom **PostgreSQL 18** image `agno-postgres:18-duckdb`: native `uuidv7()`, **pg_duckdb**, **PostGIS**, pgvector (legacy-resident), pg_trgm, pgcrypto, pg_stat_statements | **ADR-0013** (supersedes 0003) | **LIVE** |
| DuckDB | **pg_duckdb extension INSIDE Postgres** — NOT standalone | 0013, reaffirmed 0030/0032 | LIVE |
| Vector/ANN | **Milvus** = single platform-wide vector store (code index + Case Bible + Knowledge + evidence text); Agno-native; 1 collection/embedder; hybrid dense+sparse/BM25 | **0027** (+0026) | LIVE on ovh2 (Knowledge migration = Phase B/D) |
| Embedding contract | one collection per embedder; raw docs = source of truth; text `nemotron-embed-vl-1b-v2` 2048-d / code `nv-embedcode-7b` 4096-d; Milvus code+CaseBible use OpenRouter `codestral-embed-2505` 1536-d | 0010 (storage→Milvus), 0011, 0026 | In force |
| Graph cognition | **Neo4j community + Graphiti MCP** = bitemporal cognition substrate (VIP, never replaced); valid+knowledge-time + disclosure-tier multi-pass | 0014/0018/0031 (supersedes FalkorDB) | LIVE |
| Analysis sink / bitemporal | **SurrealDB** (Agno-native multi-model, native bitemporal); PG→Surreal downstream | **0024** (amended 0027/0032) | RATIFIED, NOT deployed (Phase D) |
| Semantica | decision/provenance substrate (PROV-O), pulled forward as bitemporal substrate; writer into Neo4j | CANON §5 | Locked, build pending |
| R2/S3 reach | SQL/forensic reads via pg_duckdb account-wide S3 secret; file ingest via rclone bucket mount | **0030** | LIVE |
| Federation | drop Multicorn2/neo4j-fdw; reach = pg_duckdb (files/S3/relational) + native Cypher (Neo4j) + Milvus SDK (vectors); PG→Surreal pipeline | **0032** | Accepted |
| Model gateway | **LiteLLM** :4000; **Ollama Cloud `glm-5.1` = PRIMARY LLM**; NVIDIA NIM = embed/rerank/backup. **CLOUD-PRIMARY compute** (no GPU; local ≤4B only) | 0015 | LIVE |
| Tool gateway | **IBM ContextForge** MCP gateway (off-the-shelf, NOT custom/DIAL), pinned 0.8.0 | 0025 | Accepted |
| Object store | **Cloudflare R2** (buckets `nexus`, `casebible-*`) | 0007 | LIVE |

**DuckDB-conflict resolution (the named ask):** ADR-0003 ("PG18 pgvector-only, NO DuckDB, FalkorDB deferred") is **NOT a live conflict with 0013** — it is a clean supersession chain: no-DuckDB→0013 (pg_duckdb in PG), FalkorDB-deferred→0014 (Neo4j+Graphiti), pgvector-as-store→0027 (Milvus). **0013 is current & LIVE. Standalone DuckDB is NOT blessed.** (README still mislabels 0003 "Accepted" — drift to fix → "Superseded by 0013/0014/0027".) Master prompt mis-flags **PostGIS** (already in image) and **SurrealDB** (ratified, Phase-D-pending) as "new" — they are not; only *standalone* DuckDB would be new/unratified.

Reaffirmed principles: minimize custom code / off-the-shelf-first; VIP-never-fork (Agno, Graphiti, Semantica, ContextForge, forked SBV, CopilotKit); never-delete→`_stale/`; HITL on every write.

---

## 3. TOP ADOPT/ADAPT CROSSWALK ITEMS (from A3 + gap report)

**salem_v3 ontology (Salem v. Kinzel case KG — HIGHEST VALUE).**
- ADOPT entities → Neo4j nodes mirrored in PG: `Person`, `Incident`/`Event`, `Location` (PostGIS geom), `Statement`, `Evidence` (central provenance anchor).
- ADOPT edges: `WAS_AT`, `PARTICIPATED_IN`, `MADE_STATEMENT`, `CONTRADICTS` (impeachment value), `EXPOSED_CHILD`, `AFFECTED_PARENTING_ACCESS` (custody, renamed).
- ADAPT (sensitive, HITL): `Vulnerability`, `Tactic`/`BehavioralPattern`.
- PRESERVE-AS-HYPOTHESIS (allegation ≠ fact, HITL before court): `USED_TACTIC`, `EXPLOITED_VULNERABILITY` (was TARGETED_WOUND), `DISPARAGES` (was SPREADS_RUMOR).
- SPLIT: vague `RELATED_TO` → typed causal/temporal/topical edges.

**TraceIQ timeline (B/C/D).** ADAPT `timeline_enriched`→`timeline_event` (split raw vs enriched; TEXT timestamps→`timestamptz` + **precision class**); ADOPT raw `visits/activities/paths/trips`, `geocode_resolution` (dual-provider `disagreement_flag`/`tie_break_reason`), append-only `geocode_audit`, `location_key` dedup, `vw_forensic_evidence_package` (HIGH/MED/LOW confidence tiers, HITL). ADOPT V4.1 `messages` (link to timeline; `is_private`→review gate) + Milvus body embeddings, `people` (MERGE with salem `Person`), `screenshots` (OCR=extracted), `social_action`. Google raw-export JSON shape = RAW EVIDENCE contract, keep verbatim.

**Already-salvaged assets the crosswalk MISSED — pull from `extracted-code/MANIFEST.md` (deduped, provenance-tracked — PREFER over `Archives/**`):**
- **positive_behaviors.ttl** → ADOPT to satisfy the both-parties / full-relational-cycle guardrail (do NOT invent new node types).
- **behavioral_patterns.ttl**, **mcl_722_23.ttl** (12 MCL factors), **detection_patterns.py** (256-pattern, MCL A–L, 18 categories, DARVO), **seed-patterns.ts ~303** + patterns-schema, **hurtlex_loader** — the abuse-pattern lane's real prior art.
- **Semantica pipeline** (NER, temporal KG, conflict detection, PROV-O, `source_hash`) → provenance/conflict model.
- **Parsers**: enhanced-xml-chunker.py (call-logs + base64 images), sms_backup_parser (blocked-call type 5/6), GVoice/iMessage-PDF/FB(TS), chat-export (ChatGPT/Claude JSONL), location/Takeout, Snapchat source, **schema-resolver.ts** (AI field-mapping for unknown formats), SBV cluster.
- **normalized_messages** universal raw-JSON-landing design (raw XML→`raw_data` JSON, platform-hop reconstruction) — reconcile vs typed `messages`.
- **UUIDv7 + SHA-256 chain-of-custody** column contract; **doc-intelligence tables** (sections/chunks/spans/entities/findings/**approvals**).

Lane discipline (carry into schema): raw evidence vs extracted (OCR/geocode) vs inferred (overnight/anomalies/home_base) vs analytical (views) vs legal-conclusion — keep distinct. Add **timestamp-precision class** (missing from ALL prior schemas).

---

## 4. AVAILABLE LIVE TOOLS (A1, probed 2026-06-30)

LIVE: **graphiti** (Neo4j KG memory — recall/record durable facts), **agno-gateway** (the platform: 6 forensic agents incl. ingestion/analysis/review-gatekeeper/forensic-data-agent; Postgres agentos-db; Ollama glm-5.1), **coolify** (read-only infra: 4 servers ovh1/ovh2/ovh-3/localhost), **opencode** (v1.17.8), **sequential-thinking**, **filesystem-with-morph**, **exa** (external only — never case data). Local stores: **casebible.duckdb** (D:, Jun 23, LIVE), **LanceDB .osgrep**, Claude auto-memory MEMORY.md, **PostgreSQL agentos-db** (via gateway). Skills: case-bible (cb-*, forensics/lakehouse), duckdb-skills, database-schema-designer/mastering-postgresql/postgres-patterns, evidence-review/mre-authentication/source-audit/verify, behavioral-pattern-analyzer/mcl-factor-mapper/irac-formatter, ontology/map-entities/graph-thinking, ADR/sdd skills.

**Stale-aware:** claude-context index = NOT indexed for workspace root (re-index before code search); memsearch turn DB stale (Jun 11) but plugin ENABLED; context-mode outdated build.
**Approval-gated:** any rclone/R2 transfer (dry-run + sign-off — cost/sweep risk), coolify deploys / git push, agno-gateway *writes* (route via review-gatekeeper), morph/opencode source edits.
**Never feed raw forensic/abuse evidence** to external/cloud LLM-extracting tools (exa, Drive, Lucid, M365, and graphiti/agno entity extraction) — keep evidence local (CPU-only ≤4B).

---

## 5. KEY STALENESS FLAGS

- ADR-0003 = superseded (ignore as authority; fix README label). MIGRATION_PLAN_v8 / `docs/planning/*` = build-history (PG16/pgvector-hybrid/`uuid_generate_v4`) — not current.
- Jan-dated reports R5–R12 = aging/stale; **re-target Supabase/Chroma/LanceDB/pgvector → PG(+pg_duckdb+PostGIS)/Milvus/R2**. R5 = richest data model but two byte-identical copies (dedupe).
- 78 `Workspace_Manifest_*.json` (Feb–Mar) = stale; last-resort file lookup only.
- **TheBigOne tree GONE from all 3 disk roots** — every transcript absolute path is dead; resolve via `extracted-code/MANIFEST.md`. osgrep uninstalled (06-11) — ignore.
- No prior report reflects live infra (OVH/Coolify/Milvus/Neo4j-Graphiti/R2) or as-built state — use ADRs + A1 probes, not reports.

---

## 6. CROSS-CUTTING GUARDRAILS (non-negotiable — verbatim)

- NOT a blank slate: adopt/adapt/merge the user's prior work per the crosswalk; never silently invent.
- Distinguish raw evidence vs extracted facts vs inferred facts vs analytical findings vs legal conclusions.
- Distinguish exact / approximate / inferred / uncertain timestamps.
- Court-safe, evidence-linked language; never present allegations as established fact; never promote a hypothesis to a fact.
- Model BOTH parties' conduct incl. the user's own mistakes/reactions in temporal context (explanation != excuse).
- Model the FULL relational cycle (positive/neutral/love-bombing/repair), not only negative incidents.
- Require human review before sensitive labels (gaslighting, coercive control, alienation, weaponization) reach court-facing output.
- Preserve provenance + append-only history for everything; preserve prior interpretations, never overwrite.

### Data-tier topology (owner-mandated HARD CONSTRAINT — do not contradict anywhere)
The persistence layer is split into FOUR independently-deployable resources, each able to be stopped / restarted / rebuilt WITHOUT affecting the others (no shared lifecycle, separate bind-mounted volumes, independent start/stop):
1. RELATIONAL/ANALYTICAL/SPATIAL = ONE unified resource: PostgreSQL + PostGIS + embedded DuckDB via the pg_duckdb extension, all in a SINGLE service/container. DuckDB is NOT standalone; PostGIS is NOT standalone — both live INSIDE this one Postgres resource. (Correct resolution of the ADR-0003 vs ADR-0013 conflict: pg_duckdb embedded wins.)
2. MILVUS (vector) = its own separate resource.
3. NEO4J (graph; Graphiti + Semantica are writers into it) = its own separate resource.
4. SURREALDB (consolidated analysis, IF adopted) = its own separate resource.
Rationale: a crash/restart of any one store must never tear down the others. Never describe DuckDB or PostGIS as a separate/standalone deployable; never co-locate Milvus/Neo4j/SurrealDB into a shared lifecycle.
