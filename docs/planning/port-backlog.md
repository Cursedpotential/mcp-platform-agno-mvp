# Port Backlog — what the pre-Agno platform built that never made it over

> _Byline: Claude Code · 2026-07-04_
> Status: **INVENTORY for owner triage** · Method: three comprehensive crawls of
> `Cursedpotential/mcp-tool-platform` (server + everything else) and
> `Cursedpotential/TheBigOne/01_MCP_Tool_Platform_Repo` (unique snapshot content),
> each with port-verdicts against this repo's current state.
> Companions: `EVIDENCE_MERGE_MAP.md` (the dial-stack merge map — this doc is its
> sibling for the pre-Agno TS platform) · `HANDOFFS.md` (units) · `gui-integration-spec.md`.
>
> **Context:** the successor deliberately deviated toward a modular design; a lot of
> code/design that was *supposed* to come along never did. This is the ranked recovery
> list. Overall maturity surprise: the old server is mostly WORKING code, not stubs.

## ⚠️ Security first (act before any porting)

- `TheBigOne/01_MCP_Tool_Platform_Repo/GROQ_COMPOUND_HANDOFF.md` contains **live
  plaintext credentials**: Coolify API key, Hetzner API key, **Cloudflare global API
  key**, server IPs. `TheBigOne` root also has a committed `.env.production`.
  **Rotate all of these**, then purge/redact the files. Do not port them.
- Cross-cutting code caveats for ANY port from the old server: (1) several analysis
  modules shell out with unsanitized string interpolation (`multi-pass-classifier`,
  `nlp-classifier`, `conversation-segmentation`) — reimplement with arg arrays;
  (2) `timeline-generator` injects `Math.random()` into severity — remove (forensic
  determinism); (3) case-specific hardcoding (child-name variants in
  `priority-screener`/segmentation topic map) — make configurable (`case_terms.yaml`
  already exists here for exactly this); (4) `smart-router` provider prices are stale.

## Tier 1 — Forensic domain gold (fills this repo's known gaps; Part-2 material)

These map to HANDOFFS **Part 2 — Behavioral** (owner-gated) and **Track 0** (schemas).
The engines are owner IP that cannot be reconstructed from memory — the phrase corpora
and mappings took real research.

| # | Asset (old repo path) | What it is | Verdict / lands where |
|---|---|---|---|
| 1 | `server/mcp/forensics/pattern-analyzer.ts` (1659 ln, WORKING) | **22-module dual-polarity behavioral engine**: gaslighting, DARVO, blame-shift, love-bombing, future-faking, medical abuse, reproductive coercion, power-asymmetry, parental alienation… ~250 curated phrase patterns, per-module weights, **MCL 722.23 factor tags**, linguistic markers (pronoun I/you ratios, hedge-vs-certainty, over-elaboration), severity formula `min(100, avgWeight·min(2, 1+log10(n+1)))`, proximity contradiction detection (love-bomb→devalue, apology→repeat) | **PORT (highest)** → `evidence/tools/patterns/` capability `analyze.patterns`. Persistence re-points at NormalizedRecord/PG |
| 2 | Pattern seed data: `data/content-store/objects/fe/fe2f39…` (17-module JSON w/ MCL letters) + `docs/EXPANDED_PATTERN_LIBRARY.md` (562 ln, research-backed regex/phrase lists — **never imported**, ends "STOP: present to user for approval") + `analysis/archive/RESEARCH_BEHAVIORAL_ANALYSIS.md` (adds DARVO/triangulation/word-salad/hoovering/intermittent-reinforcement + contradiction rules) | The pattern DEFINITIONS as data: modules, indicator phrases, severities, MCL letter mappings, cycle-of-abuse temporal model, pronoun-ratio analysis | **PORT (high)** → seed migration for the `mcl_factors` reference + pattern tables (pairs with H0.4); the 3 sources merge into ONE seed set |
| 3 | `drizzle/production-message-schemas.ts` (351 ln, production-grade) | The "900-line production schema" distilled: `mcl_factors` A–L w/ statutory text, 18 `behavior_categories`↔MCL mappings, custody fields (acquiredBy/method/verifiedBy/R2 path), `messaging_messages` forensic record (timestampPrecision exact/approx/inferred, E.164 normalization, behavior flags), `messaging_behaviors` (matchedText + char offsets + context + detectionMethod + verification), **`messaging_evidence_items` (exhibit numbers) + `messaging_factor_citations`** (evidence→factor w/ supportingText) | **PORT (high)** → informs `sql/0004+` (H0.4 entities/events/relationships migration) and the forensic staging schema. The factor-citation table is the court-artifact linchpin |
| 4 | `server/mcp/forensics/timeline-generator.ts` (1287 ln, WORKING) | Timestamp extraction (regex+NLP, confidence-ranked), **Cycle-of-Abuse detection (Walker model: tension→incident→reconciliation→calm)** w/ weighted phase indicators, escalation trends (week/month), court-ready markdown report generator | **PORT (high)** → `evidence/tools/timeline/`. NormalizedRecord timestamps become primary (extraction = free-text fallback). Fix `Math.random()` |
| 5 | `deploy/gcp/graphiti/main.py` (330 ln, WORKING, **already Python/FastAPI**) | Graphiti temporal-graph REST API: `/entity/add|search|timeline`, `/relationship/add`, **`/detect/contradictions`**, **`/query/as_of`** | **PORT (high, cheapest)** → retarget Cloud Run→compose, point at our Neo4j+Graphiti. Near drop-in |
| 6 | `server/mcp/analysis/priority-screener.ts` (287 ln, WORKING) | "Pass 0" triage: call-blocking / visit-denial / parenting-time-interference regex families flagged severity 8–10 with MCL factors, bypassing full analysis | **PORT (high)** → cheap pre-filter in the analysis pipeline; generalize hardcoded names to `case_terms.yaml` watchlist |
| 7 | `server/mcp/analysis/classifier.ts` prompt (ln 319–363) + `multi-pass-classifier.ts` design | The forensic **LLM system prompt** (detect positive AND negative patterns so meta-analysis can reclassify love-bombing under later contradiction) + 7-pass consensus voting + sarcasm heuristic (`subjectivity>0.7 ∧ negative-patterns ∧ polarity>0.2`) | **PORT (design+prompt, not code)** → LiteLLM classification tool; safe subprocess handling |

## Tier 2 — Platform capabilities (ingestion/gateway/ops)

| # | Asset | What it is | Verdict / lands where |
|---|---|---|---|
| 8 | `server/mcp/gateway.ts` (1431 ln) + `server/mcp/store/content-store.ts` (286 ln) + executor dedup | `search_tools`/`describe_tool`/`invoke_tool`/`get_ref` + `recommend_tools` intent scoring; SHA-256 content-addressed store w/ **4 KB byte-range paging**; input-hash dedup cache + inline-vs-ref threshold | **PORT (planned)** — this IS gui-spec **G4** (tool-finder meta-server). Scoring heuristics + `getPage` logic liftable |
| 9 | `server/mcp/analysis/conversation-segmentation.ts` (318 ln) | Topic clustering: **time-gap >2h ∨ cosine-similarity drop <0.6 ∨ entity change**, human-readable cluster IDs `PLAT_YYMM_TOPIC_iii` (`SMS_2401_KAILAH_001`) | **MERGE** into existing chatminer segmenters (partial overlap): adopt the triple-signal boundary + cluster-ID scheme; embeddings via our stack, topics from `case_terms.yaml` |
| 10 | `server/mcp/plugins/schema-resolver.ts` (462 ln) | Heuristic unknown-column→standard-field mapper (exact→fuzzy→content-pattern), hash-keyed layout cache | **PORT (medium)** → front-end adapter for `messaging_csv.py` (novel export layouts parse without code changes) |
| 11 | `server/mcp/stats/collector.ts` (359 ln) + `server/mcp/llm/smart-router.ts` policy | Usage/cost/latency rollups, dashboard payload (success rate, top tools, day×hour heatmap); task-type→provider preference chains + daily/monthly **budget caps** + 26-provider cost DB | **PORT (medium)** → Postgres-backed stats for the shell's analytics page (G5); budget/preference policy as a layer **on top of LiteLLM** (which lacks it). Implement the missing percentiles; refresh stale prices |
| 12 | `server/mcp/forensics/hurtlex-fetcher.ts` + `scripts/check-hurtlex.js` | HurtLex multilingual abuse-lexicon importer (17 categories) + source URL/TSV format | **PORT (medium)** → lexicon-based detection tool + one-time PG import |
| 13 | `server/mcp/plugins/evidence-hasher.ts` export half | **Court-ready exports**: `court_csv`, `timeline_json`, full markdown `forensic_report` w/ chain-continuity verification table | **PORT (medium)** → onto `evidence/custody.py` data (chain itself = superseded) |
| 14 | `server/mcp/forking/tool-fork.ts` + `server/mcp/config/mcp-generator.ts` | Tool forking + **Claude MCP / Gemini OpenAPI / OpenAI-function format adapters** + curated skill templates | **PORT (medium)** — this IS gui-spec **G6** (config generator retargeted at CF virtual servers) |

## Tier 3 — Smaller lifts & reference material

- `server/mcp/plugins/nlp.ts`: regex **entity-extraction fallback** (dates/money/emails/names) + `deduplicateEntities` (offset-overlap, keep-higher-confidence) → pairs with H0.5. Small, zero-dep.
- `server/mcp/auth/api-keys.ts`: clean key-gen/hash/rotate/permissions impl → FastAPI reimpl when auth lands (DEBT: deferred).
- `server/mcp/prompts/prompt-manager.ts`: prompt **versioning + per-version success/latency A/B metrics** concept (renderer regex is buggy — rewrite).
- `server/mcp/approval/approval-system.ts`: mostly **superseded** by Agno-native `@approval` (see DEBT.md audit) — only the diff-preview UX idea carries (gui-spec G5).
- `deploy/salem-trinity/phase1-vps1-fix/vps1-postgres-fix.sql`: **33-extension PG checklist** — notably `pgmq`/`pg_cron`/`pg_net` (in-DB queue/schedule/webhooks) and `pgaudit` (forensic audit) worth adding to our PG18 image.
- `deploy/salem-trinity/MASTER_DEPLOYMENT_GUIDE.md`: **TrinityRouter** pattern — atomic multi-store writes + capability-routed queries (semantic→pgvector, temporal→Graphiti, spatial→PostGIS) — architecture reference for our PG/Milvus/Neo4j/Surreal fan-out; plus cross-VPS `FIREWALL_RULES.sh` template.
- `deploy/cloudflare/evidence-hasher.js` chain create/append/verify state-machine + `r2-storage.js` presigned-URL CRUD → algorithm reference for custody/R2.
- `config/litellm_config.yaml` `model_alias_map` (cheap/fast/smart/reasoning + task aliases) → routing-policy convention for our gateway.
- `drizzle/settings-schema.ts`: `nlpConfig` chunking-strategy enum + time-gap defaults; `topicCodes`/`platformCodes` seed (case-specific).
- `docs/MCP_TOOL_CATALOG.md`: the intended ~60-tool taxonomy incl. `forensics.generate_timeline`, `detect_contradictions`, `workflow.legal_evidence_package` + standard response envelope → tool-surface roadmap.
- TheBigOne research set: **3-tier memory** (permanent / 72 hr-TTL working / session), **6-pass no-LLM preliminary → LLM meta-analysis** two-phase design, reference-return spec (`{"ref":"sha256:…","size":…,"preview":…}`), task→model selection matrix, `analysis/DRIVE_UTILITIES_ANALYSIS.md` (P0/P1 backlog over 40+ standalone forensic scripts: semantic chunker, forensic_diff, file fingerprinting, schema inference).
- TheBigOne parent-repo inventory (for later sessions): `02_TraceIQ_Repo` (Google-Timeline/Azure timeline forensics), `02/04_Voice_Analysis` (Chronicle Voice, story-voice-backend), `03/05_Evidence_Analysis` (ConflictAnalysisApp, forensic-data-refinery), `archive/04_Utilities` (the 40+ scripts), `00_Documentation` (AI_Firm_Strategy etc.).

## Explicitly superseded (do NOT port)

Old tool registry (ours is better-factored) · chain-of-custody core (`custody.py` exists) ·
Chroma/pgvector/Directus/Graphiti TS clients (native stack exists) · LangChain/LangGraph
orchestration + loaders (Agno workflows + our parsers) · `core/router.ts` tiers (LiteLLM) ·
per-platform placeholder message tables (unified `messaging_messages` model wins) ·
n8n service-control workflow (pg_cron/compose) · Coolify-era compose files · custom
approval tables/routes (Agno-native `@approval`) · `nlp-classifier.ts` (thin duplicate).

## Suggested unit cuts (for HANDOFFS when owner approves)

Part-2 gate applies to the behavioral engines (owner decision stands). When opened:
- **P2.1** pattern seed migration (assets #2+#3 → `mcl_factors` + pattern tables + seed)
- **P2.2** pattern-analyzer port (#1) on NormalizedRecords
- **P2.3** priority-screener (#6) + case-terms watchlist wiring
- **P2.4** timeline/cycle tool (#4) + court report export (#13)
- **P2.5** Graphiti REST service port (#5)
- **P2.6** classifier prompt + consensus design (#7)
Non-gated (platform): G4/G6 already in gui-spec · schema-resolver (#10) · stats collector
(#11) · HurtLex (#12) · segmentation merge (#9) · PG extension additions.
