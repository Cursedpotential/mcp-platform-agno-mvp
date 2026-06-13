# ADR Reconciliation — Proposals for Owner/Opus Review

> **PROPOSALS for owner/Opus review — no decisions made here. Authoritative decisions live in PROJECT_CANON.md §5.**
>
> _Byline: Claude Code · Sonnet 4.6 · 2026-06-13_
>
> **Purpose:** Sweep of all ADR-0001 through ADR-0022 against the 2026-06-13 locked decisions (Agno as gateway core, IBM ContextForge MCP Gateway as tool-gateway fallback only, TS-as-MCP strategy, ChatMiner vendored as atomic modules, dial-stack as parts donor, RELATIONSHIP_HISTORY as first-class TopicTag lane, SSOT = PROJECT_CANON.md). Also flags contradictions in `docs/planning/` files against the current SSOT.
>
> **Status codes:** Unaffected | Affected-needs-note | Superseded-in-part

---

## Task 2 — ADR Supersession Sweep

| ADR | Title | Status | Proposed Action |
|---|---|---|---|
| ADR-0001 | Build fresh from the Agno skeleton; abandon the v1 repo | **Unaffected** | None. Decision to build on Agno skeleton remains the core decision; DIAL abandonment was implicit at the time and is now explicit — no conflict. |
| ADR-0002 | Native Agno HITL (requires_confirmation + continue_run) | **Unaffected** | Already superseded in part (noted inline in the ADR itself re: agno 2.6.13 `@approval` decorator). Canon-compliant. No new action from 2026-06-13 decisions. |
| ADR-0003 | PostgreSQL 18 (native uuidv7), pgvector-only, no DuckDB; FalkorDB deferred | **Superseded-in-part** | ADR-0013 already formally supersedes the "no DuckDB" and FalkorDB-deferred positions. ADR-0003's text should carry a header noting "see ADR-0013 for pg_duckdb reversal". (owner/Opus to confirm) |
| ADR-0004 | Memory = native LearningMachine; no hand-rolled learned_knowledge table | **Unaffected** | Fully compatible with 2026-06-13 decisions. |
| ADR-0005 | Context Providers as the source-access layer (ports-and-adapters) | **Unaffected** | Fully compatible. The "TS-as-MCP" decision is the *implementation* of the MCP side of this pattern — no conflict. |
| ADR-0006 | Two-layer team topology — root Router (route) over coordinate families | **Affected-needs-note** | ADR-0019 added the AI Legal Team as the third coordinate family. ADR-0006 describes two families; a note should be added referencing ADR-0019's extension. No content change required. (owner/Opus to confirm) |
| ADR-0007 | Incorporate n8n + Cloudflare R2; R2 = blob/object landing zone | **Unaffected** | Fully compatible. |
| ADR-0008 | Provider-agnostic model factory, no hard default, pinned IDs | **Unaffected** | Still in force; runtime provider choices superseded by ADR-0011/0015 respectively, which this ADR anticipated. |
| ADR-0009 | Build and run on the OVH Debian VPS; author locally and sync over SSH | **Unaffected** | Operational decision; unaffected by architecture locked decisions. |
| ADR-0010 | Per-task embeddings = one vector collection per embedder | **Unaffected** | Still in force; specific embedder superseded by ADR-0011 (which acknowledged this). |
| ADR-0011 | NVIDIA NIM is the MVP provider; embedder dimension contract 2048-d / 4096-d | **Superseded-in-part** | ADR-0015 supersedes the "NVIDIA NIM as PRIMARY LLM" decision (Ollama Cloud GLM-5.1 is now primary; NIM relegated to embeddings + rerank + backup). ADR-0011's own text already marks this "supersedes" correctly at header. No new action needed beyond the existing ADR-0015 reference. |
| ADR-0012 | Phase 0 Decisions Locked | **Unaffected** | Phase 0 decisions (D1–D7) remain locked; D7 was closed by ADR-0015. No new conflicts. |
| ADR-0013 | Adopt pg_duckdb in a custom PG18 image | **Unaffected** | Fully current and compatible. |
| ADR-0014 | Pull Graphiti temporal memory forward on Neo4j (not FalkorDB) | **Unaffected** | Fully current. The 2026-06-13 confirmation that TS-as-MCP capabilities wrap graphiti-client reinforces this decision. |
| ADR-0015 | LiteLLM gateway; Ollama Cloud is the primary LLM | **Affected-needs-note** | **This is the MODEL gateway.** The 2026-06-13 locked decisions introduced a *second* gateway concept: IBM ContextForge MCP Gateway as the **tool gateway** (distinct from the model/LLM gateway). ADR-0015 does not mention this distinction, and the two gateway concepts are easily confused. **Proposed addition:** append a note clarifying: "ADR-0015 governs the MODEL/LLM gateway (LiteLLM, `:4000`). The TOOL gateway — serving/consuming/proxying tool calls across surfaces — is a separate concern: first preference is Agno native; fallback only if Agno cannot cover it is IBM ContextForge MCP Gateway (see PROJECT_CANON.md §5)." (owner/Opus to confirm) |
| ADR-0016 | Consolidated tool containers (platform-tools / sandbox / gateway) + Kasm desktop | **Affected-needs-note** | The `gateway` container in ADR-0016 is described as LiteLLM + OpenCode. With the 2026-06-13 locked decisions, the platform may also need to host or integrate IBM ContextForge MCP Gateway (tool gateway fallback). Proposed note: "If IBM ContextForge MCP Gateway is adopted as tool-gateway fallback (per PROJECT_CANON.md §5), consider whether it co-locates in the `gateway` container or gets its own slim service." (owner/Opus to confirm) |
| ADR-0017 | Polyglot evidence orchestration mesh (custody → workflows → atomic tools) | **Affected-needs-note** | The TS-as-MCP decision (2026-06-13) is the concrete implementation mechanism for "TS tools as atomic tool sources" (per §consequences: "Existing TS/Py/JS MCP servers attach as atomic-tool sources"). This ADR fully anticipated that shape. **Proposed enhancement:** add a note naming the four specific TS MCP services to wrap first (forensic-parsers, pattern-analyzer, timeline-generator, graphiti-client) per EVIDENCE_MERGE_MAP §4. This is a documentation addition only. (owner/Opus to confirm) |
| ADR-0018 | Bitemporal evidence memory + disclosure-tier | **Unaffected** | Fully current and confirmed by the RELATIONSHIP_HISTORY lane decision (which requires this substrate). |
| ADR-0019 | Three agent families — add the AI Legal Team (Part 3) | **Unaffected** | Fully current. |
| ADR-0020 | Multi-domain knowledge engine — domain-separated | **Affected-needs-note** | The 2026-06-13 locked decisions clarify that RELATIONSHIP_HISTORY is its own **first-class TopicTag lane**, and TopicTag remains a separate metadata field (not a knowledge domain). ADR-0020's domain list (`timeline_relationship`, `personal_history`, `platform_design`, `legal_strategy`) does not map 1:1 to TopicTag taxonomy — they are different axes. **Proposed note:** clarify that knowledge domains (ADR-0020) and TopicTag values (per EVIDENCE_MERGE_MAP §2.3) serve different purposes: domains are retrieval namespaces; TopicTags are per-segment classification labels. `RELATIONSHIP_HISTORY` TopicTag feeds the `timeline_relationship` knowledge domain, but they are not the same thing. (owner/Opus to confirm) |
| ADR-0021 | Engineering conventions — no-stub discipline, harness-first tests | **Unaffected** | Fully current and compatible. |
| ADR-0022 | The wiki is a comprehensive, living, dual-purpose knowledge base | **Unaffected** | Fully current. Status already "vision locked; build deferred." |

### Summary: ADR supersession counts
- **Unaffected:** 16 (ADR-0001, 0002, 0004, 0005, 0007, 0008, 0009, 0010, 0012, 0013, 0014, 0018, 0019, 0021, 0022, 0011 header already self-superseded)
- **Affected-needs-note:** 5 (ADR-0006, 0015, 0016, 0017, 0020)
- **Superseded-in-part:** 2 (ADR-0003 — covered by 0013; ADR-0011 — covered by 0015)

**The single most important proposed ADR note:** ADR-0015 — add explicit language distinguishing the LiteLLM MODEL gateway from the IBM ContextForge TOOL gateway. Without this note, any reader of ADR-0015 who sees "gateway" will conflate the two. (owner/Opus to confirm)

---

## Task 3 — Planning/* Contradictions vs SSOT

The following planning files were scanned: `BUILD_TODO.md`, `EXECUTION_PLAN.md`, `MIGRATION_PLAN_v8.md`, `TOOL_SOURCES_INVENTORY.md`, `DEV_RESOURCES_INDEX.md`, `VERIFIED_AGNO_API.md`.

**Status note:** `BUILD_TODO.md` and `EXECUTION_PLAN.md` both carry explicit `⚠️ STATUS (2026-06-11): ... this file is retained as build history` banners. They self-deprecate correctly. The main risk is a future agent reading them without noticing the banner.

### Contradictions and stale statements found

- **`DEV_RESOURCES_INDEX.md` line 8:** States `"The old Agno-MCP-Platform/ repo is abandoned."` This is stale relative to the current SSOT — the platform is now being built *inside* `Agno-MCP-Platform/` (the active build directory, not the v1 repo). The confusion is between the v1-era content of the repo (abandoned) and the repo path itself (now active). Proposed note: clarify that the statement means "v1-era code within the repo is abandoned / not built on"; the repo path `Agno-MCP-Platform/` is the active platform home. (owner/Opus to confirm)

- **`TOOL_SOURCES_INVENTORY.md` §2, line under `Archives/dial-stack/mcp-servers/`:** States `"older SUBSET of the modular servers (not canonical)"` and recommends using `MCP_PLATFORM` instead. This is accurate for the MCP server tools, but does not reflect the 2026-06-13 locked decision that `dial-stack/server/mcp/` (the gateway-layer, forensics, plugins — NOT the mcp-servers subfolder) is the primary TS capability donor for wrapping as MCP services. The `TOOL_SOURCES_INVENTORY.md` refers only to `dial-stack/mcp-servers/` (a subset), missing the much richer `dial-stack/server/mcp/` capability layer. Proposed: add a note pointing to `EVIDENCE_MERGE_MAP §4` as the current source for what dial-stack capabilities to wrap. (owner/Opus to confirm)

- **`MIGRATION_PLAN_v8.md` §0 table row "Provider factory, no hard default, pinned IDs":** Lists `claude-opus-4-8`/`claude-sonnet-4-6` as the pinned provider. Current SSOT (ADR-0015) sets Ollama Cloud GLM-5.1 as primary with NVIDIA NIM for embeddings. The Anthropic models remain in the factory preference order but are not the primary. This is a historical accuracy issue (the migration plan reflects the pre-ADR-0015 state). Since this document is marked as build history, no urgent fix — but a future agent reading it may be confused. Proposed: add a banner reference to ADR-0015 at the top of the provider-factory section. (owner/Opus to confirm)

- **`MIGRATION_PLAN_v8.md` §0 table row "Blob landing zone (§17)":** States `"R2 volume already wired — Adopt R2 as the §17 blob zone"`. This remains accurate and matches ADR-0007/0013. No contradiction.

- **`BUILD_TODO.md` Phase 0 D7:** References choosing between "Anthropic (pinned) vs the skeleton's NVIDIA/OpenRouter default vs OpenAI." D7 is now closed by ADR-0015 (Ollama Cloud primary, NVIDIA NIM for embeddings). The TODO is historical; the banner covers this.

- **`TOOL_SOURCES_INVENTORY.md` §0 one-line shape:** Lists `Archives/dial-stack/mcp-servers = older SUBSET of the modular servers (not canonical)`. Accurate for that specific subdirectory, but misleads about the broader `dial-stack` value. No urgent action needed given EVIDENCE_MERGE_MAP is now the authoritative inventory, but the two documents point in different directions for dial-stack scope.

- **No planning document mentions IBM ContextForge MCP Gateway.** This is expected (it was decided 2026-06-13, after these documents were authored). No contradiction — a gap rather than a conflict. The tool-gateway preference order should be added to `PROJECT_CANON.md §5` when that section is updated. (owner/Opus to confirm)

- **`DEV_RESOURCES_INDEX.md` and `TOOL_SOURCES_INVENTORY.md` both refer to `Archives/MCP_PLATFORM/mcp-servers/` as "CANONICAL modular tool servers."** Per 2026-06-13 locked decisions, the target architecture wraps `dial-stack/server/mcp/` capabilities (forensic parsers, pattern-analyzer, timeline-generator, graphiti-client) as MCP services — this is *in addition to* the MCP_PLATFORM servers, not a replacement. No hard contradiction; the two sets serve different capability layers (evidence ingest = MCP_PLATFORM; forensic analysis = dial-stack). EVIDENCE_MERGE_MAP §4 is the correct reference for the combined picture. (owner/Opus to confirm)
