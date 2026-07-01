# A1 — Platform Capability Inventory & Tool-Use Plan

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Discovery run: A1-CAPABILITIES · Platform: SPEC-1-MCP-Forensic-Evidence-Agent-Platform (the-platform-workspace) · Refresh: re-verify liveness before each major phase (MCP endpoints + index freshness drift).

Reasoning process selected for this phase (per MP lines 138-150): **Inventory, classification, and tool-selection reasoning** — enumerate every capability, classify by type/persistence/risk, verify liveness empirically (no proxy signals), and rank by relevance to forensic DB design. Liveness was probed live, not assumed.

## Liveness verification performed (this run)
- `graphiti.get_status` → **ok, connected to Neo4j** → LIVE.
- `coolify.get_infrastructure_overview` → **v4.1.2, 4 servers all reachable/usable** (ovh1-agno 100.72.169.40, ovh2-worker 100.91.190.107, ovh-3 100.119.96.29, localhost) → LIVE.
- `opencode.health` → **healthy, v1.17.8** → LIVE.
- `agno-gateway.get-agentos-config` → **LIVE**: `os_id=mcp-forensic-platform`; 6 forensic agents (ingestion-orchestrator, analysis-orchestrator, review-gatekeeper, dev-copilot, project-pal, forensic-data-agent) + transcript-miner prompts; 3 teams (mcp-platform-router, platform-ops, builder); tables agno_sessions/memories/learnings/metrics + platform_knowledge_contents; models = Ollama `glm-5.1`.
- `claude-context.get_indexing_status` (workspace root) → **NOT indexed** → server live, index STALE/empty for this path.
- `context-mode.ctx_stats` → LIVE but **outdated v1.0.162→.169**; 0 calls this session; 125 prefs across 5 projects (casebible heaviest).
- Disk: `E:/AI_Workspace/.memsearch/opencode-turns.db` (332 KB, **Jun 11** → data STALE); `.memsearch/memory/*.md` digests (latest **Jun 27**); LanceDB at `E:/AI_Workspace/.osgrep/lancedb/chunks.lance` **+ per-repo** `Agno-MCP-Platform/.osgrep/lancedb` & `dev-resources/.osgrep/lancedb` (LIVE); `D:/casebible/casebible.duckdb` (68 MB, **Jun 23** → LIVE).
- Plugin state from `~/.claude/settings.json` (authoritative). **CORRECTION to task brief:** `memsearch` plugin is **enabled (true)** — only its on-disk turn DB is stale. Confirmed DISABLED: `claudikins-kernel`, `remember`, `ralph-loop`, `claude-session-driver` (all `false`). `recall@FlineDev`=true.

---

## Capability Inventory Table

Columns: Capability | Type | Purpose | When to Use | When NOT | Inputs | Outputs | Persistence | Risks | Priority | Liveness

### MCP servers
| Capability | Type | Purpose | When to Use | When NOT | Inputs | Outputs | Persistence | Risks | Priority | Liveness |
|---|---|---|---|---|---|---|---|---|---|---|
| **graphiti** (Neo4j KG memory) | MCP | Entity/relationship + temporal memory; add_memory, search_memory_facts, search_nodes, get_episodes | Recording durable decisions; entity timeline; recall at task start | Bulk evidence dump; transient state | NL text/JSON episodes, queries | Facts/nodes/edges w/ temporal validity | **Yes** (Neo4j, group_id) | Cloud LLM extracts entities → don't feed raw sensitive evidence; clear_graph destructive | **P0** | live |
| **agno-gateway** (AgentOS) | MCP | The forensic platform itself: run agents/teams/workflows, sessions, memories, knowledge base | Orchestrating ingestion/analysis/review agents; platform-native memory & knowledge | Quick local file ops | agent/team id, prompts, session ids | Agent runs, memories, knowledge contents | **Yes** (Postgres agentos-db) | Agents run on Ollama glm-5.1 (local, CPU-bound ≤ small model); writes need review-gatekeeper | **P0** | live |
| **coolify** (read-only) | MCP | Infra topology, server/app/db/service status | Verifying where Postgres/Milvus/Neo4j live; deploy targets | Any mutation (it's read-only) | UUIDs | Server/app/db JSON | None (read-only) — safe | None material | **P1** | live |
| **claude-context** | MCP | Semantic codebase index/search (index_codebase, search_code) | After indexing repo for schema/ontology/prior-art discovery | Before indexing (returns "not indexed") | abs path, NL query | Code chunks | **Yes** (its own vector store) | Index is STALE for workspace root → must (re)index first | **P1** | live (index stale) |
| **filesystem-with-morph** | MCP | NL codebase_search + fast edit_file + github_codebase_search | Exploring unfamiliar code; bulk edits | Symbol/regex lookup (use Grep) | NL question, repo_path | Relevant code spans / edits | No (operates on files) | edit_file mutates source → review diffs | **P1** | live |
| **opencode** | MCP | Delegate coding tasks to autonomous agent; find_symbol/find_text/AST, session mgmt | Offloading long builds/migrations; symbol search | Trivial single edits | provider/model, prompts | Code, diffs, sessions | Yes (opencode sessions) | Needs provider/model chosen first; can mutate repo | **P2** | live (v1.17.8) |
| **sequential-thinking** | MCP | Structured multi-step reasoning scratchpad | Schema/temporal modeling design reasoning | Simple lookups | thoughts | Reasoning chain | No | None | **P1** | live |
| **context-mode** (ctx_*) | MCP | Token-saving exec + persistent insight/index/search store | Batched shell w/ context savings; cross-project prefs | One-off calls | commands, queries | Insights, stats | **Yes** (on-disk DBs) | Outdated build; learns prefs (privacy) | **P2** | live (outdated) |
| **exa** | MCP | Web search/fetch (current external info) | Looking up libraries, standards (e.g. UCO/CASE forensic ontology), legal refs | Anything touching private evidence | NL query/URL | Web content | No | External egress; never send case data | **P2** | live |
| **claude-in-chrome** | MCP | Browser automation (deferred; load via ToolSearch) | Driving web UIs (Coolify, Windmill, Attu) | Headless data tasks | nav/click/JS | Page text, screenshots | No | Site perms; visual; slow | **P3** | unknown (deferred) |
| **claude.ai Google Drive** | Connector | Search/read/create Drive files | Pulling source exports stored in Drive | Local-first evidence | queries, file ids | File content | Drive | Cloud exposure of evidence → caution | **P2** | live (deferred) |
| **claude.ai Lucid** | Connector | Diagrams/ERD/sequence (schema visualization) | Rendering DB schema ERD for the spec | Text-only deliverables | spec/SVG | Diagrams, share links | Lucid cloud | Cloud; account-scoped | **P3** | live (deferred) |
| **claude.ai Lawve AI** | Connector | Read-only legal-AI skill catalogue (audit-trail, agent-authority, delegation) | Court-readiness/chain-of-custody legal framing | Code/schema work | skill slug | Skill methodology | No | Read-only, safe | **P3** | live (deferred) |
| **claude.ai agno docs** | Connector | Search Agno framework docs | Implementing Agno agents/knowledge | Non-Agno work | NL query | Doc excerpts | No | Read-only | **P3** | live (deferred) |
| **Mermaid / Gamma / SlidesGPT / M365 / HeyGen / Yardi** | Connector | Diagram render / decks / Office (most need auth) | Mermaid for inline diagrams | Until authenticated | spec | Diagrams/decks | varies | Several need OAuth; cloud | **P3** | unknown (auth) |

### Local stores / indexes (disk)
| Capability | Type | Purpose | When to Use | When NOT | Inputs | Outputs | Persistence | Risks | Priority | Liveness |
|---|---|---|---|---|---|---|---|---|---|---|
| **casebible.duckdb** `D:/casebible/` | DuckDB | Per-project catalog/memory store (R2 corpus catalog, prefs) | Local analytics, artifact registry, append-only ledgers, schema prototyping | Concurrent multi-writer | SQL | Tables/views | **Yes** (file, 68 MB) | Single-file lock; backup before bulk write | **P0** | live (Jun 23) |
| **LanceDB** `E:/AI_Workspace/.osgrep/lancedb` (+ per-repo) | Vector idx | Existing code/embedding index (osgrep / smart-explore) | Vector code search w/o re-embedding | Stale repos | embeddings/queries | Nearest chunks | **Yes** (chunks.lance) | May lag repo edits | **P1** | live |
| **memsearch opencode-turns.db** | SQLite | Prior AI conversation-turn search | Recovering past decisions/prompts | Fresh data needs (Jun 11) | SQL/text | Turn rows | **Yes** | DATA STALE (Jun 11); plugin enabled but unfed | **P2** | live engine / stale data |
| **memsearch memory digests** `.memsearch/memory/*.md` | Markdown | Daily session digests | Conversation-log recall | — | — | MD digests | Yes | latest Jun 27 | **P2** | live |
| **Claude auto-memory** `~/.claude/.../MEMORY.md` + `.claude/memories` | Markdown | Cross-session project memory index (READ ON RESUME entries) | Start of every task | — | — | MD | Yes | Keyed to working dir | **P0** | live |
| **PostgreSQL (agentos-db)** on OVH | RDBMS | Platform-native relational store behind agno-gateway | Canonical evidence/message schema target (the actual deliverable home) | Local-only quick work | SQL | Tables | Yes | Remote; via gateway/forensic-data-agent w/ validated queries | **P0** | live (via gateway) |

### Skills / subagents / commands (forensic/legal/db/thinking relevant — summarized)
| Capability | Type | Purpose | When to Use | When NOT | Persistence | Risks | Priority | Liveness |
|---|---|---|---|---|---|---|---|---|
| **case-bible** plugin (cb-init, cb-lake, cb-r2-sort, cb-status, cb-vsearch; agents: case-bible-architect/-forensics/-lakehouse/-organizer/-r2-sorter) | Skills+subagents | Vault governance, R2 lakehouse, forensic evidence handling, sorting | Evidence ingestion, vault structure, lakehouse schema | Generic coding | Vault/R2/DuckDB | R2 Class-A $ on transfers (dry-run first) | **P0** | live (enabled) |
| **duckdb-skills** (query, attach-db, install-duckdb, s3-explore, iceberg, time-travel) | Skills | DuckDB ops, S3/R2/Iceberg, time-travel | Schema proto, catalog queries, temporal | Remote PG | DuckDB file | — | **P1** | live |
| **database-schema-designer**, **db-migrations**, **mastering-postgresql**, **postgres-patterns** | Skills | SQL schema design, normalization, indexing, migrations | THE schema-design deliverable | NoSQL-only | docs | — | **P0** | live |
| **evidence-review**, **evidence-templates**, **mre-authentication**, **source-audit**, **verify**, **multi-pass-bug-hunting** | Skills | Chain-of-custody, provenance, authentication, verification | Evidence ingestion & court-readiness | — | docs | — | **P0** | live |
| **behavioral-pattern-analyzer**, **mcl-factor-mapper**, **mi-case-research**, **irac-formatter**, **secondary-source-auditor** (scoped under dev-resources/AI_Config) | Skills | Abuse-pattern / MCL 722.23 / MI family-law analysis & IRAC | Abuse-pattern & user-reaction analysis, legal lane | Schema/code | docs | False-positive control needed | **P1** | live (scoped) |
| **thinking-skills** (model-router + first-principles, inversion, systems, theory-of-constraints, pre-mortem, red-team, probabilistic, reversibility, second-order…) | Skills | Phase-appropriate structured reasoning | Each MP phase (ontology, schema, timeline, abuse) | — | — | — | **P1** | live |
| **ontology**, **map-entities**, **graph-thinking**, **networkx**, **json-canvas** | Skills | Taxonomy/ontology recovery, entity mapping, graph modeling | Ontology review phase | — | — | — | **P1** | live |
| **iceberg**, **lance**, **lakehouse**, **flink/fluss/iggy/paimon** | Skills | Lakehouse / table-format / streaming patterns | Storage-tier & temporal design | Small local | — | — | **P2** | live |
| **sdd, make-plan, architecture-decision-records, adr-***, software-architecture, clean-architecture, domain-driven-design** | Skills | Spec-driven design, ADRs, architecture | Designing & documenting the DB structure | — | docs/ADRs | — | **P1** | live |
| **memory-systems**, **memory-management**, **project-memory**, **session-memory**, **digital-brain** | Skills | Memory architecture & persistence patterns | Memory-persistence phase | — | varies | — | **P2** | live |
| **legal-quality-checker, irac-practice, appellate-***, family-law/custody skills** | Skills | Court-safe narrative & legal QA | Final court-safe export | Code | docs | Unsupported legal conclusions | **P2** | live |
| **coolify, ssh, docker/-compose, doppler-***, n8n-***, gh-cli, mastering-git-cli** | Skills | Infra/secrets/deploy/VCS ops | Deploying/securing the DB tier | — | — | Secrets handling | **P2** | live |

### KNOWN-DISABLED (verified stale — DO NOT USE)
| Plugin | settings.json | Status |
|---|---|---|
| claudikins-kernel | `false` | DISABLED (confirmed stale) |
| remember | `false` | DISABLED |
| ralph-loop | `false` | DISABLED |
| claude-session-driver | `false` | DISABLED |
| **memsearch** | `true` | **NOT disabled — brief was wrong.** Engine enabled; only its turn DB data is stale (Jun 11). Use read-only with awareness of staleness. |

---

## Tool-Use Plan

**Use first (P0, this & next phase):**
1. `graphiti` (search_memory_facts/search_nodes) + Claude auto-memory `MEMORY.md` → recall prior decisions before designing.
2. `casebible.duckdb` (duckdb-skills:query) → read existing corpus catalog/schema as prior art; prototype schema locally.
3. `agno-gateway` config/knowledge + **PostgreSQL agentos-db** → the real schema target; forensic-data-agent runs *validated* queries.
4. `database-schema-designer` / `mastering-postgresql` / `postgres-patterns` + `evidence-review`/`mre-authentication`/`source-audit` → schema + chain-of-custody.
5. `coolify` (read-only) → confirm where PG/Neo4j/Milvus actually live before any deploy assumption.

**Useful later (not yet):**
- `claude-context.index_codebase` then `search_code`, and `filesystem-with-morph.codebase_search` → AFTER indexing, for codebase/schema/ontology pre-scan (A-series scan phases).
- `iceberg`/`lance`/`lakehouse` skills → storage-tier & temporal-table design phase.
- `opencode` → only when delegating long migration/build work.
- `Lucid`/`Mermaid` → schema ERD visualization at documentation/export.

**Required for memory persistence:** graphiti (entity/temporal lane) + Claude auto-memory MEMORY.md + casebible.duckdb append-only ledgers + agno-gateway memories. (Complementary, not redundant — SSOT docs win on conflict.)
**Required for codebase indexing:** claude-context + LanceDB (.osgrep) + filesystem-with-morph.
**Required for conversation-log search:** memsearch SQLite (stale-aware) + memory digests + opencode sessions.
**Required for schema/ontology discovery:** duckdb-skills, claude-context/morph search, ontology/map-entities/graph-thinking skills.
**Required for artifact tracking:** casebible.duckdb registry + graphiti lineage + ADR skills.
**Required for evidence ingestion:** case-bible (cb-*, case-bible-forensics) + agno ingestion-orchestrator + evidence-templates.
**Required for human-review workflows:** agno **review-gatekeeper** (approval/audit log) + plannotator + verify/verification-before-completion.
**Required for final export:** legal-quality-checker, pandoc/latex, Lucid/Mermaid ERD, redaction-aware review.

**Avoid / do NOT use:** all 4 confirmed-disabled plugins (claudikins-kernel, remember, ralph-loop, claude-session-driver); `graphiti.clear_graph` and `agno delete-*` (destructive); exa/web & cloud connectors for anything containing case data.

**Require user approval before use:** any `rclone`/R2 transfer (cost + sweep risk — dry-run + sign-off per HARD RULE); coolify deploys / git push; agno-gateway *write* runs (route through review-gatekeeper); filesystem-with-morph/opencode edits that mutate source.

**May expose sensitive data — handle with caution:** exa (external egress), Google Drive / Lucid / M365 / Gamma (cloud), graphiti & agno (cloud/LLM entity extraction) → never feed raw forensic/abuse evidence to external LLM-extracting or cloud tools; keep evidence content local (CPU-only, ≤ small-model constraint).

**Note:** No specialized tool is *missing* for this task — local persistence (DuckDB/PG/LanceDB/Neo4j), indexing, conversation search, forensic skills, and review gating are all present and (where probed) live. Proceed with the integrated workflow; refresh this inventory (re-probe MCP liveness + re-index claude-context) at the start of the codebase-scan phase.
