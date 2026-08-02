# SESSION HANDOFF — 2026-07-13 (chat: Opus 4.8)

Conversation got long/expensive. Full state dump. Read, then continue.

## COMMITTED VS NOT

**Committed + pushed (on GitHub):**
- `traceiq-rebuild` → NEW private repo, branches `master` + `ui-scaffold`. Was zero-backup local-only; now safe. Has its own ADR ledger to ADR-0016 (path model, overnight def, verification scope) + a validated bronze pattern (raw per-provider `src` tables, 41,963 records hash-verified, unaccounted=0).
- `console/c4-knowledge` → commit 25b692b (Graphiti pane + agno-2.8 MCP door :8001→:8000). Pushed.
- Monorepo `E:\AI_Workspace` → snapshot-2 committed; push to NEW private `ai-workspace` was IN FLIGHT. VERIFY: `git -C E:\AI_Workspace ls-remote --heads origin`. One vendored .mp3 = broken LFS pointer, disposable.

**On disk, NOT committed — branch `docs/adr-graphiti-memory` (off workbench/sprint):**
- docs/adr/0036-dozerdb-multidb-rbac-memory-evidence-isolation.md
- docs/adr/0037-graphiti-mcp-contextforge-write-enabled.md
- docs/adr/0038-agno-agents-graphiti-native-library.md
- docs/adr/0039-graphiti-extraction-llm-hosted-structured-output.md
- Commit: `git add docs/adr/003[6-9]-*.md && git commit -m "docs(adr): 0036-0039 graphiti memory (drafts)"`

**Never committed:** 8-file platform doc set + PLATFORM-DOCS.html (chat container / downloads only).

## DECISIONS MADE THIS SESSION (locked unless owner reopens)

1. **Go additive** — never port Python/Agno. Go = format-blind streaming ingestor CORE + pluggable per-source DECODERS. Coordinate via Postgres manifest table (FOR UPDATE SKIP LOCKED). `if format=="sms"` in core = defect.
2. **SMS decoder first** (hardest: multi-GB XML + base64 MMS; highest-value corpus). Timeline JSON second.
3. **sbv-forensic IS the SMS engine** — REVERSAL of an earlier "build fresh" call. Reality (from reading the repo): sbv upstream is a Go backend (Echo, streaming xml.NewDecoder, HEIC) + React frontend, and the fork ALREADY has Phase-5a custody hashing (custody.go, H1/H2/H3, "hash before normalize" owner-verified) + headless automation endpoints. Keep it. One surgical change: swap SQLite (go-sqlite3) for Postgres emission on platform path. Keep React frontend as viewer. Media → discrete hashed files, never blobs.
4. **Bronze→silver data model** — raw per-source tables (faithful, hashed, re-derivable) → normalizer (write-time, ONLY writer of silver, dedup + tier-1 identity) → ONE physical `messages` table (UNION-shaped not JOIN; superset cols designed vs iMessage + native_extras JSONB). One-way flow. Confirmed EXISTS in repo as `working.normalized_record` — bitemporal (occurred_at/knowledge_time/disclosure_tier), attrs JSONB, artifact_id→evidence.evidence_hash provenance. 138 tables across evidence/analysis/ai/messaging/public schemas.
5. **Field policy (3 tiers):** promoted common columns / native_extras JSONB / raw row via provenance. No per-source columns on silver. Promote → add column in normalizer, re-derive.
6. **pg_duckdb = one engine two sides** — DuckDB/columnar (raw, hash, bulk, Knowledge domains) vs Postgres/relational (conformed, FKs, provenance, pgvector).
7. **Two graphs, hard partition** — evidence graph (Semantica) vs memory graph (Graphiti), both on Neo4j. Agent asymmetry: reads evidence (never writes), read+writes memory.
8. **DozerDB** (ADR-0036) — one Neo4j instance, named DBs `memory`+`evidence`, RBAC-scoped writer roles. Chosen over 2 containers (saves RAM, RBAC enforces partition harder). GPL-fork provenance is a NON-issue for a Genesee County family case; reliability lives in traceability/audit logs.
9. **Graphiti = agent working memory, WRITE-enabled** (ADR-0037). NOT currently behind ContextForge — it's a standalone no-auth read-only tailnet nginx door (GRAPHITI_MCP_URL :8071). Fix: register as ContextForge virtual server for auth, retire nginx door.
10. **Agno uses graphiti-core natively** (ADR-0038); MCP door only for GUI Claude clients. Session state stays in SurrealDB (ADR-0024).
11. **Extraction LLM hosted** (ADR-0039) — NIM primary / OpenRouter alt; NO local model (no GPU, JSON reliability). Ollama Cloud embeddings-only.
12. **SurrealDB = whole-truth convergence layer** (already ADR-0032) — normalized results only, cross-modal analysis. Convergence DB separate from Agno-memory DB.
13. **Knowledge stream feeds analysis as LABELED subjective lens** ("Matt's account"), never merged as fact. Entity+alias registry (people AND places), HITL-curated, extends ADR-0031 CaseBible entity layer.
14. **FalkorDB = PARKED** (owner correction — was stale in earlier drafts). Not in use; re-enters only if a Mongo-style doc store is ever required (pg_duckdb+Surreal cover it). Neo4j is semi-hard-coded in Semantica.

## STILL TO DO (open, not frozen)

**Blockers / near-term build:**
- **DETECTION BUG** (`server/analysis/detection.py`): matcher uses `content.lower().find(needle)` — plain ASCII substring. Bug 1 (recall killer): seeded patterns have ASCII apostrophes (`i'm sorry`) but real phone text uses Unicode U+2019 (`i'm sorry`) → contraction patterns NEVER match; most mobile text is invisible to detection. Bug 2: no word boundaries (`liar` hits "familiar"). Bug 3: no canonicalization (curly quotes, nbsp, whitespace). FIX = canonicalize-with-offset-map (map spans back to ORIGINAL for offsets/matched_text or idempotency key breaks on re-run), word-boundary option per pattern, before/after dry-run diff as acceptance test. NOTE: "deflection detection" was the real target (voice-to-text said "deflection"); the deflection/self-exculpatory category is ALSO missing from behavior seed (0006) — exists in analyzer prompt + rubric judgment layer but not detection layer. Two things: fix the matcher AND add `deflection_of_accountability` category (contextual match — defined by responding to an accountability moment; ties to antecedent reconstruction).
- **CONTEXTFORGE TRANSPORT CHECK** (closes ADR-0037 blocker): does deployed ContextForge federate Streamable HTTP upstream or SSE-only? Grep ContextForge config/version in repo. Graphiti 1.0 serves Streamable HTTP.
- **VECTOR-DB DECISION** (gates ADR-0039 embedder line): current embed = nv-embed-v1 @ 4096-d. pgvector HNSW index cap is ~2000-d (4000 halfvec) → 4096-d CANNOT be ANN-indexed in pgvector. This may be WHY Milvus is in the stack. Options: keep Milvus for 4096-d, OR step down to ≤2000-d embedder (minimal retrieval loss at this corpus scale) and collapse onto pgvector. Milvus self-hosted (etcd+MinIO+MQ) is heavy on VPS. Owner reported Milvus issues (symptoms not yet specified). Amendment target: ADR-0026/0027. FTS-first ships day one anyway so vector isn't on critical path.
- **IDENTITY-SPINE VERIFICATION** (schema blocker 3): `working.normalized_record` has `participants` as raw JSONB with NO entity FK. Entity tables exist (entity_alias/mention/resolution/merge_event). VERIFY whether resolution stamps entity keys onto records at write time. Read `normalize.py` + entity tables. Provenance ✓ and superset+escape-hatch ✓ already confirmed; identity is the one unverified blocker.

**ADRs housekeeping:**
- Commit 0036-0039 (drafts, `docs/adr-graphiti-memory` branch).
- **ADR-0034 is STRANDED** on unmerged branch `docs/adr-0033-0034-evidence-model` (evidence/context boundary + transcript model) — the gap in the ledger. Merge or re-home it.
- Verify `ai-workspace` monorepo push landed.

**Vector/embedding decision + detection fix are the two highest-value next moves. Detection fix is cheap, measurable (dry-run diff), and gates cycle detection.**

## ANALYSIS ROADMAP (the point of the platform)
Three artifacts, priority order: (1) ANTECEDENT RECONSTRUCTION — for any flagged moment surface what preceded it; (2) CYCLE DETECTION — recurring provocation→reaction→selective-capture signature; frequency/regularity/consistency = proof of intent; (3) DOCUMENTATION-GAP DETECTION — her record has the reaction, full record has the omitted provocation. Bitemporal normalized_record already gives the sequence. This is reactive-abuse/DARVO defense + gaslighting-as-measurable-delta (memory graph "as-it-seemed" diffed vs evidence graph "what's true").

## ENV NOTE
Owner: no GPU, no cloud GPU wanted. Has: NIM cloud, OpenRouter (paid), Ollama Cloud Pro, Colab Pro. Rate-limiting this session was ACCOUNT-LEVEL ("extreme usage"), not connector-specific — tunnels won't fix it. Do heavy repo work in Claude Code LOCAL on Cursed-WS, not via chat+Desktop Commander. Reachable via Desktop Commander (device Cursed-WS). Repos: mcp-platform-agno-mvp workdir = E:\AI_Workspace\Projects\the-platform-workspace\Agno-MCP-Platform.
