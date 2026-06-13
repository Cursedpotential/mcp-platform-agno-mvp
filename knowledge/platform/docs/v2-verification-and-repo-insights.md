# v2 Verification + Repo Insights → inputs for v3

This is the working note behind the v3 handoff. Part A is the best-practice verification of v2 against live Agno docs (via the Agno docs MCP). Part B is the analysis of the five repos you pointed at, with explicit adopt / adapt / skip calls.

---

## Part A — v2 verified against live Agno docs

### Validated (no change needed)
- **`AgentOS(base_app=app)` → `agent_os.get_app()`** is the official "bring your own FastAPI app" pattern. v2 was right; v1's subpath mount was wrong.
- **`PgVector(..., search_type=SearchType.hybrid)`** is the documented hybrid pattern. Correct.
- **`contents_db` is an optional component** that tracks content metadata/processing status and powers the UI. v2 framing correct.
- **One `MCPTools` per server**, tools attached on the `Agent` (`tools=[mcp_tools]`). Correct.
- **`MCPTools(transport="streamable-http", url=...)`** is exactly how to reach an HTTP MCP server (e.g. Graphiti). Correct. (Bonus: the Agno docs themselves are an MCP server at `https://docs.agno.com/mcp` — usable as an institutional-knowledge provider.)
- **Provider-agnostic** with pinned IDs is idiomatic; docs use `Claude(id="claude-sonnet-4-0")` etc.

### Corrections to apply in v3
1. **Ingestion method name:** the current API is **`knowledge.insert(...)` / `knowledge.ainsert(...)`** (kwargs: `name=`, `path=` or `url=`, `metadata=`). v2's `add_content_async(...)` is not the current name. Fix everywhere.
2. **Default port is 7777**, not 8000. (The dash/template examples expose 8000 via their own `PORT` env; AgentOS's own default is 7777. Pick one explicitly and be consistent — v3 standardizes on 8000 via `PORT`, matching the Agno Docker examples, and notes 7777 is the bare-AgentOS default.)
3. **`reload` guidance, made precise:** not a blanket ban. The official MCP examples carry the comment *"Don't use reload=True here, this can cause issues with the lifespan."* So: reload is fine in general dev (`RUNTIME_ENV=dev`), but **must be off when MCPTools are attached** because it breaks the MCP lifespan. State the reason, not just the rule.
4. **Native-memory flag name:** it's **`enable_user_memories`** (plural), persisted in the agent's `db`. Also: `update_memory_on_run` and `enable_agentic_memory` are **mutually exclusive** (agentic wins if both set). `AgentMemory`/`TeamMemory` were removed in v2; customize via `memory_manager=MyMemoryManager()`. Fix the v2 fragile-areas hedge.
5. **Route-conflict control:** when our custom approval/knowledge routes collide with AgentOS routes, use `on_route_conflict="preserve_base_app"`. Add to the wiring section.
6. **Two MCP roles:** AgentOS can *consume* MCP (our TS/Py/Graphiti servers) **and** *expose itself* as an MCP server via `enable_mcp_server=True`. Distinguish them; the latter is a cheap way to let other agents/coding tools drive our platform.

### Strategic note (not a correction)
Native Agno memory is more capable than v1 implied — agentic modes, db-persisted, customizable `MemoryManager`, plus an API/client surface (`AgentOSClient`) and UI. This does **not** overturn Graphiti (Graphiti still wins on temporal-graph reasoning and shared-FalkorDB-with-Semantica), but v3 should soften "reinvents the wheel" and present native memory as a legitimate, lighter fallback.

---

## Part B — Repo insights (adopt / adapt / skip)

### 1. `agno-agi/dash` — the Forensic Data Agent, done right (HIGH VALUE)
Dash is almost exactly our Forensic Data Agent, and it upgrades several of our designs.

**ADOPT:**
- **Schema-level read-only enforcement, not prompt-level.** Analyst connects with `default_transaction_read_only=on` (Postgres rejects writes); a SQLAlchemy event listener blocks DDL/DML against the protected schema. *"Infrastructure guardrails, not prompt instructions. They hold regardless of what the model generates."* This is a far stronger primitive than our prompt-based "no schema writes" and directly serves evidence integrity.
- **Dual-schema boundary:** `public` (read-only source data, never modified by agents) vs an agent-managed schema (views, summaries, computed assets). Maps onto evidence: raw evidence read-only; derived analysis in its own schema.
- **Two-system memory split:** *Knowledge* (curated validated queries + business rules, curated by human + agent) vs *Learnings* (auto-managed error patterns/fixes). Confirms our Knowledge-vs-temporal-memory split and gives the Forensic agent its "save_validated_query" / "schema gotchas" behavior. In v3 these map to Agno Knowledge + Graphiti respectively.
- **Six grounded context layers** incl. `introspect_schema` (live runtime schema) and MCP (institutional knowledge). Better-articulated retrieval grounding than v2.
- **Evals as first-class:** five categories — accuracy (AccuracyEval 1–10), routing (ReliabilityEval), security/governance/boundaries (AgentAsJudge binary). Adopt this structure for our testing section, especially governance (refuses destructive ops) and boundaries (schema access).
- **`scheduler=True, tracing=True`** on AgentOS for proactive + observable behavior.
- **RBAC/JWT in prod** via AgentOS (`RUNTIME_ENV=prd` enables it; `JWT_VERIFICATION_KEY` from the control plane). Relevant once the platform is multi-surface.

**ADAPT:** Dash's "Engineer writes views into `dash` schema" is a nice model for our Analysis Orchestrator writing derived artifacts — but keep it behind our approval gate (Dash leans on schema guardrails; we add HITL on top).

**SKIP for MVP:** Slack interface, Railway specifics (we're local/self-host first), synthetic SaaS dataset.

### 2. `agno-agi/scout` — heterogeneous-source navigation (HIGH VALUE, architectural choice)
Scout is the closest match to your "ingest heterogeneous sources" goal and poses a real design fork.

**ADOPT (as a documented option):**
- **"Navigation over search" + per-source sub-agents.** Rather than flatten every source into one vector store, wrap each source type in a sub-agent that owns its quirks and exposes a clean tool (Scout's `query_slack` etc.). For your sources — live codebase, zip archives, scattered dirs, multi-platform chat logs — this argues for a **per-source-type provider/sub-agent** behind the Ingestion Orchestrator, complementing (not replacing) Knowledge ingestion. Fits our MCP-per-source structure perfectly.
- **Builds its own wiki/CRM as it learns** — i.e. derived, queryable structure accrues over time. Mirrors writing durable structure into Graphiti.
- **Scheduled proactive actions** (cron summaries/follow-ups), not just on-demand.

**DECISION TO SURFACE:** pure Knowledge-ingestion (embed everything) vs Scout-style navigation (sub-agents fetch on demand) vs hybrid. For a forensic/evidence corpus where provenance and "don't hallucinate from a stale chunk" matter, the navigation pattern is attractive for *live* sources, while embedding stays right for *frozen archives*. v3 documents this as an explicit architectural option, not a silent default.

### 3. `agno-agi/agentos-docker-template` — canonical project shape (ADOPT WHOLESALE)
**ADOPT:**
- **Canonical layout:** `agents/`, `app/`, `db/`, `scripts/` + `Dockerfile`, `compose.yaml`, `example.env`, `pyproject.toml`. Align our scaffold to this so any Agno-familiar coding agent is instantly oriented.
- **`db/get_postgres_db()`** as the single DB-config entry point — matches our "only place env is read" rule; fold `config/settings.py` responsibilities here or keep settings + a thin `db/` helper.
- **Dependency management via `pyproject.toml` + `./scripts/generate_requirements.sh`**, then build into the image. Replaces v2's "pip install at startup."
- **Knowledge load via `docker exec ... python -m agents.knowledge_agent`** (module entrypoint) — clean pattern for our `ingest_knowledge`.
- **`RUNTIME_ENV=dev` toggles auto-reload** — the sanctioned home for reload, paired with the MCP-off-reload caveat (Part A #3).
- The template's two agents are literally **Knowledge Agent (Agentic RAG) + MCP Agent** — our two core primitives, confirming the shape.

### 4. `agno-agi/vibe-to-prd` — intent→spec→handoff flow (ADAPT THE DIRECTION)
You liked the direction; here's the transferable core, not a wholesale import.

**ADAPT:**
- **Flow:** drop loose intent → agent asks **structured clarifying questions** (`UserFeedbackTools` / `ask_user`) → produces a markdown spec via `FileTools` → hand to a coding agent. This is exactly our Dev Copilot / builder planning loop, and it's how *this very handoff* should be regenerated.
- **`MemoryManager` learns preferences across sessions and skips questions it already knows** — pre-selects smarter defaults. Perfect fit for your stream-of-consciousness, parse-intent style; our Project PAL should do this (via Graphiti).
- **CLI + AgentOS web, no heavy interfaces** — right minimalism for MVP.

**SKIP:** the PRD-product-template content itself (not our domain).

### 5. `agno-agi/vibe-video` SPEC (bonus) — handoff-doc structure (ADOPT THE FORM)
Found while researching vibe-to-prd; its `docs/SPEC.md` is a model "mini demo agent" handoff.
**ADOPT (form, not content):**
- **Explicit non-goals / "No X in v0"** section — prevents scope creep; we should add one.
- **`TeamMode.coordinate`** (leader delegates once per turn, synthesizes) — concrete model for our routing-agent stretch goal and platform/builder leader.
- **Session-history policy stated numerically:** "last 10 runs in-context; last N sessions searchable" (`add_history_to_context`, `num_history_runs`). Make ours explicit.
- **`CodeExplorer`: on-demand git clone + read-only code inspection** — directly useful for ingesting your *live codebase* source (pairs with Scout's navigation idea).
- **"No learnings KB when there are no conventions to learn"** — the reminder that memory layers should be justified, not reflexively added.

---

## Net effect on v3
- Apply Part A corrections (insert/ainsert, port, precise reload rule, `enable_user_memories`, route-conflict, dual MCP roles).
- Adopt dash's schema-level read-only + dual-schema + evals-as-first-class; soften native-memory framing.
- Add an explicit "ingestion strategy" section presenting embed-vs-navigate (Scout) as a real choice, with per-source sub-agents behind the Ingestion Orchestrator.
- Re-shape the scaffold to the docker-template's canonical layout; switch to pyproject + generated requirements + module entrypoints.
- Add a vibe-to-prd-style structured-question intake to the builder flow and a vibe-video-style **Non-Goals** section + numeric session-history policy + `CodeExplorer` for the live-codebase source.
