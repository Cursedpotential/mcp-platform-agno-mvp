> _Byline: Claude Code · Sonnet (R1d) · 2026-07-11_

# RAG Patterns, Knowledge/Memory Tools & Context Engineering

Reference for Agno's agent-level knowledge/memory configuration surface, the
`KnowledgeTools`/`MemoryTools` toolkits, tool-result caching, context
engineering, context providers, and the use-case patterns (product agents,
data agents, deep research) that compose them. Companion files in this
directory cover storage substrates and memory/learning semantics — this file
is the RAG + tools + context layer that sits on top of those.

**Method note**: the Agno docs MCP (`claude_ai_agno`) was unreachable for the
entire research session (`MCP server "claude.ai agno" is not connected`,
retried repeatedly). Every doc page below was instead fetched with `WebFetch`
directly against `docs.agno.com`, and cross-checked against
`.venv/Lib/site-packages/agno` (Agno 2.6.13) wherever a knob or default was
load-bearing. `sitemap.xml` and `llms.txt` were used to enumerate sibling
pages beyond the checklist floor (both are incomplete for the newer
`use-cases/` and `teams/usage/` trees — see Coverage).

---

## 1. Agent-level knowledge/memory knob matrix

Verified against `agno/agent/agent.py` (Agno 2.6.13). All of these are
`Agent.__init__` kwargs (dataclass fields of the same name).

| Knob | Default | What it does |
|---|---|---|
| `knowledge` | `None` | A `Knowledge` instance, **or a callable** `Callable[..., KnowledgeProtocol]` resolved per-run. Enables agentic RAG when set. |
| `search_knowledge` | `True` | Adds a `search_knowledge` tool (agentic RAG) to the model **whenever `knowledge` is set**. This is the default retrieval path — most agents get RAG "for free" just by setting `knowledge=`. |
| `add_search_knowledge_instructions` | `True` | Injects instructions into the system prompt telling the model how/when to call `search_knowledge`. Turn off if you're writing fully custom retrieval instructions. |
| `add_knowledge_to_context` | `False` | **Eager** RAG: runs a knowledge search up front and stuffs references directly into the system message every turn, instead of letting the model decide to call a tool. Mutually complementary with `search_knowledge`, not exclusive — you can do both, but doing both means references appear twice (once eager, once on-demand). |
| `knowledge_filters` | `None` | `Dict[str, Any]` or `List[FilterExpr]` — static metadata filters applied to every knowledge search (e.g. restrict to `case_id="X"`). |
| `enable_agentic_knowledge_filters` | `False` | Lets the **model** choose filter values per-call instead of a fixed static filter (agentic filtering — the model picks, e.g., which `document_type` to search). |
| `knowledge_retriever` | `None` | Escape hatch: `Callable(agent, query, num_documents, **kwargs) -> Optional[list[dict|str]]` — replaces the default `search_knowledge` implementation entirely with a custom retrieval function (custom rerankers, hybrid pipelines, non-Agno vector stores). |
| `references_format` | `"json"` | `"json"` or `"yaml"` — how retrieved references are serialized into the prompt/tool result. |
| `update_knowledge` | `False` | Adds a tool letting the **agent itself write** into the knowledge base at runtime (agent-driven ingestion, not just retrieval). |
| `dependencies` | `None` | `Dict[str, Any]` — arbitrary values (DB handles, config, request-scoped state) injected into `RunContext` and available to `system_message`, tool functions, and dynamic instructions without going through the LLM. Distinct from `knowledge`/`memory` but frequently used alongside a callable `knowledge=` to resolve per-tenant/per-request knowledge instances. |
| `callable_knowledge_cache_key` | `None` | `Callable(...) -> Optional[str]` — when `knowledge` is a callable (resolved dynamically per run), this generates a cache key so the agent doesn't re-resolve/re-instantiate the `Knowledge` object on every single run. Backed by `self._callable_knowledge_cache: Dict[str, Any]` on the agent instance (in-process, not persisted). Only relevant when `knowledge` is callable — irrelevant for a static `Knowledge` instance (which is just held as-is). |

**Callable knowledge + cache key pattern.** `knowledge=` accepts a factory
function instead of an instance:

```python
def resolve_knowledge(run_context: RunContext) -> Knowledge:
    tenant = run_context.session_state["tenant_id"]
    return per_tenant_knowledge[tenant]

agent = Agent(
    knowledge=resolve_knowledge,
    callable_knowledge_cache_key=lambda run_context: run_context.session_state["tenant_id"],
    ...
)
```

Without a cache key, a callable `knowledge=` is re-invoked (and the returned
`Knowledge` object potentially re-constructed) on every run. The cache key
lets the agent skip re-resolution when the key repeats — this matters
because standing up a `Knowledge`/vector-db client per call is not free.

**Related agent-level history knob** (not knowledge, but sits in the same
"what's in context" family, and directly load-bearing for our-stack): `
add_history_to_context: bool = False`, `num_history_runs: Optional[int] = None`,
`num_history_messages`, `max_tool_calls_from_history`. Our agents set
`add_history_to_context=True, num_history_runs=10` uniformly (§ Our-stack
annotations).

---

## 2. KnowledgeTools vs plain `search_knowledge`

Verified against `agno/tools/knowledge.py` (Agno 2.6.13) and
`docs.agno.com/tools/reasoning_tools/knowledge-tools` +
`docs.agno.com/tools/toolkits/others/knowledge`.

**Plain `search_knowledge`** (the agent-level default, § 1) is a single
tool: the model calls it with a query string, gets back a list of documents,
and decides in one shot whether that's enough. No structured
plan/search/verify loop — just "search when you think you need to."

**`KnowledgeTools`** is a `Toolkit` (`agno.tools.knowledge.KnowledgeTools`)
that wraps the *same* underlying `knowledge.search()` call in a three-tool
**Think → Search → Analyze** cycle:

- **`think(thought)`** — scratchpad appended to `run_context.session_state["thoughts"]`; never shown to the user. Used to plan search terms / refine approach before searching.
- **`search_knowledge(query)`** — identical retrieval call to the plain tool (`self.knowledge.search(query=query)`), returned as JSON-dumped `Document.to_dict()` list, or `"No documents found"`.
- **`analyze(analysis)`** — scratchpad appended to `run_context.session_state["analysis"]`; the model explicitly evaluates relevance/completeness/reliability/consistency of what came back, and can loop back to `think`/`search` with refined queries.

Constructor: `KnowledgeTools(knowledge, enable_think=True, enable_search=True,
enable_analyze=True, instructions=None, add_instructions=True,
add_few_shot=False, few_shot_examples=None, all=False, **kwargs)`.
`add_few_shot` **defaults to `False`** here (contrast `MemoryTools` below,
where it defaults to `True`) — few-shot examples for the think/search/analyze
loop are opt-in.

**When to use which:**

- **Plain `search_knowledge`** is right when retrieval is genuinely one-shot — a well-scoped knowledge base, queries that map cleanly to what's stored, no need for the model to second-guess result quality. Lower token overhead (no think/analyze turns), simpler traces.
- **`KnowledgeTools`** earns its overhead when: (a) the knowledge base is heterogeneous/noisy enough that a single query often misses, and iterative query refinement measurably helps; (b) you want an auditable "why did the agent conclude X" trail — the think/analyze scratchpad *is* that trail; (c) the retrieval task benefits from explicit self-critique before answering (the doc's own framing: multi-hop or ambiguous questions like "what are the dietary guidelines for mild hypertension" where the first search is usually incomplete).
- It costs more per turn (extra tool round-trips for think/analyze) and is not a drop-in replacement — swapping requires removing the agent-level `knowledge=`/`search_knowledge=True` combo and passing `KnowledgeTools(knowledge=...)` as an explicit tool instead (the two are alternate integration paths for the same `Knowledge` object, not stackable in the obvious way — using both would double up search tools with overlapping purpose and confuse the model about which to call).

**Doc-vs-source discrepancy (flagged):** `docs.agno.com/tools/reasoning_tools/knowledge-tools`'s own code example constructs the toolkit with `KnowledgeTools(knowledge=agno_docs, think=True, search=True, analyze=True, add_few_shot=True)` — but the installed source (`agno/tools/knowledge.py`, 2.6.13) has **no** `think`/`search`/`analyze` kwargs; the real parameter names are `enable_think`, `enable_search`, `enable_analyze` (confirmed by both the source constructor signature and by the *other* doc page, `tools/toolkits/others/knowledge`, which correctly lists `enable_think`/`enable_search`/`enable_analyze`). The `reasoning_tools/knowledge-tools` example as written would raise `TypeError: unexpected keyword argument 'think'` against 2.6.13. Two Agno doc pages for the same toolkit disagree with each other, and one disagrees with source — filed via `submit_feedback` is worth doing but out of scope for this research pass; noted here so nobody in-repo copies the broken example.

---

## 3. MemoryTools (agent-facing CRUD)

Verified against `agno/tools/memory.py` (2.6.13) and
`docs.agno.com/tools/reasoning_tools/memory-tools`.

`MemoryTools` is the **explicit, agent-driven** counterpart to the
implicit `enable_agentic_memory=True` / `update_memory_on_run=True` knobs
documented elsewhere (see the memory/learning-substrate researcher's file
for those). Where implicit agentic memory happens as a side-channel the
model doesn't directly operate, `MemoryTools` gives the model **direct CRUD
tool calls** against `db.get_user_memories` / `upsert_user_memory` /
`delete_user_memory`:

- **`think(thought)`** — planning scratchpad (`session_state["memory_thoughts"]`), same pattern as `KnowledgeTools.think`.
- **`get_memories()`** — `db.get_user_memories(user_id=run_context.user_id)`, returns JSON list. Note: **no query/filter param** — it's a full list-for-this-user fetch, not a search.
- **`add_memory(memory, topics=None)`** — constructs a `UserMemory(memory_id=uuid4(), memory=memory, topics=topics, user_id=user_id)` and `db.upsert_user_memory(...)`.
- **`update_memory(memory_id, memory=None, topics=None)`** — fetches existing by id first (404s cleanly as a JSON error if not found), merges provided fields, upserts.
- **`delete_memory(memory_id)`** — existence-checks then `db.delete_user_memory(memory_id)`.
- **`analyze(analysis)`** — same self-critique scratchpad pattern as `KnowledgeTools.analyze`, applied to whether the CRUD op "worked."

Constructor: `MemoryTools(db, enable_get_memories=True, enable_add_memory=True,
enable_update_memory=True, enable_delete_memory=True, enable_analyze=True,
enable_think=True, instructions=None, add_instructions=True,
add_few_shot=True, few_shot_examples=None, all=False, **kwargs)`. Note
`add_few_shot=True` **by default** here (vs `KnowledgeTools`'s `False`) —
the four bundled few-shot examples (add/update/delete/get) ship on by
default.

Every operation stores its result into `run_context.session_state
["memory_operations"]` as a running audit log (success/error/payload) —
useful for post-hoc inspection of what an agentic-memory-writing agent
actually did during a run, independent of whatever ends up in the DB.

`MemoryTools` requires a raw `db: BaseDb` (not a `LearningMachine`), so it
operates one level below the learning-substrate abstraction — it's for
agents that need direct, user-visible "remember this" / "forget that"
control, not for the ambient always-on memory capture that `LearningMachine`
configs (`UserMemoryConfig(mode=...)`) provide. The two are not mutually
exclusive: an agent can have both ambient `LearningMachine`-driven memory
capture *and* `MemoryTools` for explicit user-requested memory edits
("forget my old address").

---

## 4. Tool-result caching

Verified against `agno/tools/toolkit.py` and `agno/tools/function.py`
(2.6.13); `docs.agno.com/tools/caching` under-documents this (see
discrepancy note below).

**Knobs**, settable at the `Toolkit` level (applies to every tool the
toolkit exposes) or per-tool via `@tool(...)`:

- `cache_results: bool = False` — master switch.
- `cache_ttl: int = 3600` — seconds. Expired entries are deleted on next lookup miss.
- `cache_dir: Optional[str] = None` — defaults to `<tempdir>/agno_cache/functions/<function_name>/`.

Per-tool settings **override** toolkit-level settings when both are present
(`Function.cache_results if Function.cache_results else Toolkit.cache_results`,
similarly for `cache_dir`; `cache_ttl` overrides only when the function's
value differs from the library default of `3600` — i.e. you must actually
set a non-default `cache_ttl` on the `@tool` decorator for it to win over
the toolkit's).

**Mechanism**: file-based, on disk, one JSON file per cache key —
`<cache_dir>/functions/<tool_name>/<md5_key>.json`, `{"timestamp": ..., "result": ...}`.
Cache key = `md5(f"{function_name}:{json.dumps(sorted_args)}:{sorted(call_args)}")`
— `agent`/`team`/`run_context`/media params (`images`/`videos`/`audios`/`files`)
are stripped from the key before hashing, so identical logical calls made by
different agents/runs still hit the same cache entry. This is **not**
per-session or per-agent-instance caching — it's a shared, process-wide
(actually disk-wide — survives process restarts) cache keyed purely on
function name + arguments.

**Limitations** (not mentioned in the doc page at all):
- **Generators are never cached** — `Function.execute()` explicitly skips the cache read/write path when `isgeneratorfunction(entrypoint)` (or `isgenerator(result)`/`isasyncgen(result)` for the async path). Streaming tool results are incompatible with this cache.
- **Serialization is silent-fail-open** — `_save_to_cache` wraps the `json.dump` in a bare `try/except`, logs, and swallows on failure. A tool returning something non-JSON-serializable (and not a Pydantic `BaseModel`, which gets `.model_dump()`'d first) simply never gets cached — no error surfaces to the caller, the tool result is still returned correctly, it just silently isn't persisted.
- **No cache invalidation hook** beyond TTL expiry — there's no "bust this key" API; the only way to force a refresh mid-TTL is to delete the file or change an argument.

**Doc-vs-source discrepancy (flagged):** `docs.agno.com/tools/caching`
documents only `cache_results=True` and doesn't mention `cache_ttl` or
`cache_dir` at all, despite both being real, load-bearing constructor
params in 2.6.13 (default TTL of 1 hour is a meaningful behavior most users
would want to know about). It also doesn't mention the generator exclusion
or the silent-fail-open serialization behavior — both worth knowing before
relying on this for anything correctness-sensitive.

---

## 5. Use-case patterns

### 5.1 Product agents — sessions + memory, connecting your data

**`use-cases/product-agents/sessions-and-memory`**: the core framing is
"an agent needs two kinds of state: what was said in this thread, and what
the agent knows about this user" — session history (`add_history_to_context`,
`num_history_runs`) vs. user memory (`enable_agentic_memory` /
`update_memory_on_run`). Every call needs both `user_id` and `session_id`.
For long threads: `num_history_runs=N` caps context growth, or
`enable_session_summaries=True` condenses older turns into a running
summary instead of dropping them.

**`use-cases/product-agents/connecting-your-data`**: this is the Context
Providers pitch in use-case form. Core line: "Context providers navigate
the source at query time, the way a coding agent runs `ls`, `grep`, and
`cat`" — i.e. **live navigation, not pre-indexed retrieval**. This is
explicitly framed as the alternative to vector-DB RAG for *structured/live*
sources (Slack, Drive, Postgres, wikis) where staleness and "citations that
aren't clickable paths" are the failure modes of pre-indexing. Collapsing
N tools into one `query_<source>` avoids the ~20-tool confusion threshold
the docs cite for raw tool sprawl. `write=False` on a provider removes
mutation capability at the provider level (not just prompt-level) —
same infrastructure-guarantee pattern as our `DatabaseContextProvider`
read/write split (§ Our-stack annotations).

**`use-cases/product-agents/serve-as-an-api`** (found via sitemap, not on
the assigned checklist — see Coverage): `AgentOS` turns an `Agent` into a
FastAPI app with built-in run/session/memory/trace endpoints for free —
`agent_os.serve(app="module:app", port=7777)`, clients POST to
`/agents/{id}/runs` with `user_id`/`session_id`/`message`. `stream=true` for
SSE, `background=true` for long jobs, `authorization=True` for JWT
enforcement on all but `/health` and `/openapi.json`.

### 5.2 Data agents — querying / self-correcting / safe-data-access / serve-and-embed

This category is the closest doc analogue to our own
`DatabaseContextProvider` read-only-engine pattern (ADR-0005) — worth
reading in full even beyond the checklist, so all 6 sibling pages found via
enumeration are covered here (2 beyond the checklist's 4).

**`querying-your-data`**: baseline pattern — `SQLTools` for schema
introspection (`list_tables`, `describe_table`) + query execution
(`run_sql_query`), with the agent's own `db` (session storage) kept
**separate** from the `SQLTools` connection (analytics warehouse). Core
line: "A data agent that guesses column names is wrong confidently" —
mandates introspect-before-query.

**`grounding-in-context`** (found via enumeration): six-layer grounding
stack for data agents, ordered by how "curated" vs "live" they are:
(1) validated queries (curated, highest leverage — "one known-good query
... is worth more than a page of schema notes"), (2) table metadata
(curated), (3) business rules (curated — e.g. "'active' excludes trialing
accounts"), (4) institutional knowledge/wiki (live), (5) learnings from
self-correction (live), (6) runtime schema introspection (live). Mechanism:
a `Knowledge` + `PgVector` store with `search_knowledge=True` so the agent
pulls matching context per-question instead of carrying the whole data
dictionary in every system prompt — this is exactly the on-demand-not-eager
pattern our agents use (§ Our-stack annotations, § 1 `add_knowledge_to_context`).

**`self-correcting-agents`**: `learning=True` (or a full `LearningMachine`
with `UserMemoryConfig`) turns errors into durable corrections: error →
diagnose (schema issue, join logic, stale data) → persist as a learning →
future similar queries retrieve it contextually. `ALWAYS`/`AGENTIC`/`PROPOSE`
modes gate capture automaticity. Two inspectable stores: **Learned
Knowledge Store** (cross-user corrections) and **Decision Log Store** (audit
trail of *why* logic changed) — `lm.learned_knowledge_store.print(query=...)`,
`lm.decision_log_store.print(agent_id=..., limit=...)`.

**`safe-data-access`**: the security-hardening companion to
`querying-your-data`. Headline principle, worth quoting exactly: **"A
prompt that says 'only run SELECT' is a suggestion. A connection that
physically cannot write is a guarantee."** Recommends a **three-role split**
beyond our two-engine pattern:
- **Analyst** — read-only, public schema, queries + introspection only.
- **Engineer** — read access to public schema, **write access scoped to an agent-owned schema only** (e.g. `dash`) — never production tables.
- **Leader** — orchestration only, no direct DB access at all.
Mutations that matter use `@tool(requires_confirmation=True)` — but
scoped to genuinely irreversible actions only: **"Approval everywhere kills
adoption. Gate the irreversible actions, not the reads."** Defense stacks:
DB role enforcement → schema-scoped permissions → human approval →
decision logging.

**`materialization`** (found via enumeration): recurring-question caching
at the **database** layer, not the tool-result-cache layer (§ 4) — "When a
question repeats, build a view once and answer from it forever." The
Engineer-role agent creates a view in its own schema (e.g. `dash`) on first
validation of a recurring query pattern; subsequent identical questions read
the view instead of regenerating SQL. Framed as compounding with
self-correction and grounding: validated queries feed the knowledge store,
which improves grounding, which produces more validated (and thus
materializable) queries. Agent-owned-schema isolation makes mistakes cheap:
"a wrong view is a cheap mistake. Drop it and let the agent rebuild."

**`serve-and-embed`**: deploy the same agent behind `AgentOS` to power a
Slack channel, a BI dashboard's NL box, a scheduled digest, or a pipeline
sanity check — identical serving infra as § 5.1's `serve-as-an-api`, applied
to data agents specifically. State scoping: "Conversation thread" stays
per-user/session; **learnings live in a shared namespace across users** —
i.e. the self-correction learnings from `self-correcting-agents` are
deliberately *not* session-scoped.

### 5.3 Deep research — grounding, structured deliverable

Directly relevant to the AI Legal Team Part 3 build. Checklist covers 2 of
6 sibling pages found via enumeration; all 6 read.

**`grounding-research`**: three-layer grounding architecture, distinct from
(but structurally parallel to) the data-agents six-layer stack:
- **Layer 1 — Static context (rules)**: hard constraints (mandate, policy) loaded once from markdown into every system prompt — "no specialist can drift from the mandate."
- **Layer 2 — Research library (knowledge/RAG)**: shared vector DB, searched per-query via `search_knowledge=True` on a shared `team_knowledge` object — "pulls relevant profiles and analyses per question instead of carrying the whole library in context."
- **Layer 3 — Prior work (decisions/archive)**: file-based archive of past memos/conclusions; **read** access is broad, **write** access is separate and explicit — grounds new work in what was already concluded without letting every agent freely rewrite institutional history.
Each layer answers a different question (rules / domain knowledge / prior
reasoning) — the doc's explicit claim is that conflating them causes three
distinct failure modes (missing rules, missing knowledge, missing
reasoning trail).

**`structured-deliverable`**: research should terminate in a **typed**
decision, not prose — enforced via `output_schema` (Pydantic model) on the
final agent's output. Example `Decision` schema: `call` (enum
`BUY`/`HOLD`/`PASS`), `conviction` (`low`/`medium`/`high`, gates downstream
automation — high triggers automation, medium queues for human review),
`allocation_usd`, `rationale` ("required not optional"), `citations`
("A decision without its citations is unverifiable"). **Two-artifact output
pattern**: the typed `Decision` object for automated routing/audit, plus a
Markdown memo for human context — same run, two consumption surfaces.
Irreversible downstream actions still require human approval regardless of
`conviction`.

**`orchestration-patterns`** (found via enumeration): five patterns mapped
to question shape — **Route** (single specialist owns it, `Team` route
mode), **Coordinate** (lead model adaptively picks which analysts to
consult, then synthesizes — best for open-ended research), **Broadcast**
(every specialist independently evaluates the *same* question in parallel,
lead reconciles — reduces groupthink/bias vs. sequential exposure),
**Task** (multi-step, team decomposes autonomously via `Team` tasks mode),
**Pipeline** (fixed, auditable sequence via `Workflow` — "must run the same
way every time"). Explicit framing: **Teams explore, Workflows decide** —
production systems typically use both, teams for the adaptive research
phase, a workflow for the final standardized review/publish step.

**`parallel-investigation`** (found via enumeration): `Workflow` +
`Parallel(Step(...), Step(...))` blocks run independent specialists
concurrently — "a five-specialist review that runs the three independent
specialists at once finishes in roughly the time of the longest one, not
the sum of all five." The actual skill is dependency analysis, not maximum
parallelism — only steps with no inter-dependency should run concurrently
(e.g. market assessment must precede both fundamental and technical
analysis, which can then run in parallel, before a risk assessment that
needs both).

**`institutional-learning`** (found via enumeration): a shared
`LearningMachine` with a common learned-knowledge store (e.g.
`team_learnings`) that every agent across every review reads from and
writes to — "the committee remembers," not any single analyst. Distinct
from per-agent memory (which stays isolated to that analyst). Same
`ALWAYS`/`AGENTIC`/`PROPOSE` mode vocabulary as self-correcting data
agents. Curatorial guidance on *what* to capture: sector-specific insights,
data-source corrections, revisions to prior conclusions — explicitly
**excludes** one-off numbers, restated mandates, or anything already in the
research library (Layer 2 of `grounding-research`). This is the exact
capability our `learned_knowledge` `LearningMode.PROPOSE` config
(`server/agents/providers.py`) targets, minus the multi-analyst-team
framing (we're single-agent per orchestrator today, not a broadcast
committee — see Open questions).

---

## 6. Context engineering

Two overlapping doc pages cover this: the general `context/overview` and
the more detailed `context/agent/overview` (also titled "Context
Engineering" — same content, `context/agent/overview` is the fuller
version; `context/overview` reads like a landing/summary page for it).
`context/team/overview` covers the team-specific superset.

**What goes into agent context** — four components, consistently stated
across both pages:
1. **System message** — built from `description` + `instructions` +
   `expected_output`, plus optional datetime/location/agent-name/session-
   summaries/memories/state injections.
2. **User message** — the actual query.
3. **Chat history** — prior turns (`add_history_to_context`).
4. **Additional input** — few-shot examples (`additional_input=[Message, ...]`) or other supplementary data.

**Ordering / token discipline**:
- **Caching-driven ordering**: "Agno's context construction is designed to place the most likely static content at the beginning of the system message" — this is explicitly to align with provider-side prompt caching (OpenAI, Anthropic, OpenRouter all cache on a shared prefix), so static content first = more cache hits = lower token cost on repeated calls.
- **History truncation**: `num_history_runs` / `num_history_messages` cap how much prior conversation enters context per turn; `max_tool_calls_from_history` separately caps how many *tool calls* (as opposed to messages) get pulled from history — "your database always contains the complete history" even when the in-context view is filtered, i.e. truncation is a context-window optimization, not data loss.
- **Session summaries** as an alternative to raw truncation: `enable_session_summaries=True` condenses older turns into a running summary instead of dropping them outright — preserves gist at much lower token cost than full history.
- **Dynamic instructions** (`context/agent/dynamic-instructions`): `instructions` can be a `Callable(run_context) -> str` instead of a static string — used for per-user/per-session personalization pulled from `run_context.session_state`, at the cost of a small compute overhead per run vs. a static string.
- **Few-shot** (`context/agent/few-shot-learning`): `additional_input=[Message(...), ...]` — paired example messages demonstrating desired response shape/tone, distinct from `add_knowledge_to_context`'s eager-RAG references.

**The process itself is explicitly framed as iterative, not a fixed
pipeline**: "an iterative process: refining the system message, trying out
different descriptions and instructions, and using features such as
schemas, delegation, and tool integrations." No formal token-budget
numbers are given anywhere in these pages — the only concrete lever
documented is prefix-caching-aware ordering + history/tool-call truncation
knobs.

**Team context (`context/team/overview`) adds a delegation layer** on top
of the four agent-level components:
- The team leader's system message includes explicit coordination framing ("You cannot use a member tool directly. You can only delegate tasks to members.") and delegation requires `member_id` + `task_description` + `expected_output`.
- **Member context is assembled independently per member** — "member information is automatically injected into the system message. This includes the member ID, name, role, and tools" for the *leader's* view of each member; each member still builds its own full four-component context separately.
- `share_member_interactions` — when `True`, prior member interactions are shared with members receiving *new* delegations mid-run, letting later-delegated members build on earlier members' work in the same run.
- Team-level context-injection knobs mirroring the agent-level ones: `add_memories_to_context`, `add_session_summary_to_context`, `add_history_to_context`/`num_history_runs`, and **`add_knowledge_to_context`** (same name, same eager-injection semantics as the agent-level knob in § 1).

---

## 7. Context providers — Wiki (+ the provider family generally)

`context-providers/overview` frames the whole family: a `ContextProvider`
"wraps an external system and exposes it as one or two tools" —
`query_<id>` (read) / `update_<id>` (write, optional) — specifically to
avoid the ~20-tool confusion threshold and naming collisions that come from
attaching raw toolkits directly to an agent. Each provider runs its own
sub-agent internally, so a cheap model can do source-specific navigation
work while the calling agent's (possibly stronger/pricier) model only sees
the two collapsed tools.

**Three `ContextMode` values** (`agno.context.mode.ContextMode`, verified
against source — `default`, `agent`, `tools`):
- **`default`** — provider-specific "recommended" exposure; each subclass decides what this means (for `DatabaseContextProvider` it's the full two-tool read/write split via two internal sub-agents; for `WorkspaceContextProvider`, which is read-only by nature, it's a single `query_<id>` sub-agent tool).
- **`agent`** — force a single `query_<id>` tool backed by one sub-agent, regardless of the provider's default (read-only framing even for providers that support writes).
- **`tools`** — bypass sub-agents entirely; the calling agent sees the provider's raw underlying toolkit methods directly (e.g. `DatabaseContextProvider` in `tools` mode exposes raw `SQLTools` read methods, no natural-language `query_<id>` wrapper).

**Wiki provider specifics** (`context-providers/providers/wiki`):
`WikiContextProvider`-style read/write over markdown wikis. Backends:
`GitBackend` (auto-commits and pushes on write — needs `asetup()`/`aclose()`
lifecycle calls) or `FileSystemBackend` (local directory, no VCS). Optional
`web` backend param lets the provider fetch a URL and convert it into a
wiki page (web-content-to-wiki ingestion). `read`/`write` toggle tool
exposure independently (both default `True`); `id` customizes tool naming.
Not currently used in our stack — flagged as a candidate if we ever want
agent-writable docs/runbooks instead of the current git-committed-Markdown-only
docs model (see Open questions (c) discussion doesn't cover this — separate
consideration, noted only for completeness).

**`DatabaseContextProvider` and `WorkspaceContextProvider`** — the two
providers actually wired into our stack — are documented at
`context-providers/providers/database` and `.../workspace` respectively;
covered in full under § Our-stack annotations since our usage matches the
documented pattern almost exactly (one intentional deviation: our
`DatabaseContextProvider(write=False)` instance for the Forensic Data Agent
never even constructs a write sub-agent, going one step past the doc's
`write=False` "disables the update tool" framing into "the write path
doesn't exist to disable").

---

## 8. Teams — building, memory/knowledge sharing, streaming

**`teams/building-teams`**: minimum viable team = model + members +
instructions; each member needs `name` + `role` for the leader to delegate
correctly. **Four modes** (doc language differs slightly from the generic
orchestration-patterns page in § 5.3, which additionally names a
`Workflow`-based "Pipeline" pattern that sits outside `Team` proper):
`coordinate` (default — leader delegates + synthesizes), `route` (directs
to one member by content), `broadcast` (all members work the same input
simultaneously), `tasks` (iterative cycles, `max_iterations`-bounded).
Members inherit `model` from the parent team when not explicitly set.
Teams support "nested teams" (a team as a member of another team) and
callable factories for `members`/`tools`/`knowledge` resolved dynamically
per session (parallel to the agent-level callable-`knowledge=` pattern in
§ 1). The doc is explicit that **team-level knowledge/memory sharing
specifics live one level down** (in `memory/team/*` pages, owned by the
substrate researcher in this doc set) — `building-teams` only asserts that
teams *support* knowledge/memory "at the team level" without detailing the
propagation rules; those rules are covered concretely in § 6's
`context/team/overview` breakdown (`share_member_interactions`,
`add_memories_to_context`, `add_knowledge_to_context`).

**`teams/usage/basic-team`**: a minimal two-specialist example
(HackerNews + Finance agents) under a `coordinate`-mode leader with
domain-scoped delegation instructions. No explicit state-sharing beyond
delegation — coordination is entirely instruction-driven, not a shared
memory/context object.

**`teams/usage/streaming`**: `team.print_response(..., stream=True)`
streams progressively; `show_members_responses=True` additionally surfaces
each *member's* individual output as it's produced, not just the leader's
final synthesis — useful for showing research/work-in-progress rather than
only a final answer.

---

## 9. Agents usage pages (with-knowledge / with-memory / with-storage)

**`agents/usage/agent-with-knowledge`**: canonical agentic-RAG walkthrough
— `Knowledge(vector_db=LanceDb(..., search_type=SearchType.hybrid,
embedder=OpenAIEmbedder(...)))`, three ingestion paths
(`knowledge.insert(url=...)` / `path=...` / `text=...`), then
`Agent(knowledge=agno_docs, ...)` — `search_knowledge` defaults on, no
extra config needed for the baseline agentic-RAG loop. Confirms hybrid
search (semantic + keyword) as the doc's own recommended default
`search_type`, not just an option.

**`agents/usage/agent-with-memory`**: distinguishes storage (session
history) from memory (cross-session user facts) at the usage-example
level: "storage maintains conversation history within a session, while
memory captures user-level information across multiple conversations."
Two activation modes: `enable_agentic_memory=True` (agent decides
when to persist) vs `update_memory_on_run=True` (memory manager runs after
every response, unconditionally — slower, more complete).
`agent.get_user_memories(user_id=...)` for inspection. Framing: memory
answers "what do you know about me?", not "what did we just say?"

**`agents/usage/agent-with-storage`**: `db=SqliteDb(...)` +
`add_history_to_context=True` + `num_history_runs=5` + a stable
`session_id` across calls = resumable multi-turn conversation, including
across process/script restarts (session state is fully DB-backed, not
in-memory). "Same `session_id` = continuous conversation, even across
script runs."

---

## Our-stack annotations

Cross-referenced against `server/agents/providers.py` and
`server/agents/factory.py` (this repo, current state).

**Knowledge is attached to exactly three agents** — `ingestion_orchestrator`,
`analysis_orchestrator`, `dev_copilot` (`factory.py:141,171,264`, wired via
`ctx.knowledge` in `build_agent_team`). `project_pal`, `forensic_data_agent`,
and `review_gatekeeper` get `learning=` but no `knowledge=` — consistent
with their roles (PAL is pure operational memory, Forensic Data Agent is a
read-only DB query surface not a document-RAG surface, Gatekeeper is a
translation layer with no retrieval need).

**All three knowledge-bearing agents use the § 1 defaults as-is** —
`knowledge=knowledge` is passed with no `search_knowledge=`,
`add_knowledge_to_context=`, `knowledge_filters=`, or
`enable_agentic_knowledge_filters=` overrides anywhere in `factory.py`.
That means, per § 1's defaults: `search_knowledge=True` (agentic RAG tool
present), `add_knowledge_to_context=False` (no eager reference-stuffing —
matches the task brief's framing exactly), `references_format="json"`.
No agent uses `KnowledgeTools` (§ 2) or `MemoryTools` (§ 3) — retrieval and
memory-CRUD both go through the implicit agent-level knobs, not the
explicit toolkits.

**`num_history_runs=10` is uniform across every agent and team** in
`factory.py` (12 occurrences) — `ingestion_orchestrator`,
`analysis_orchestrator`, `review_gatekeeper`, `platform_ops_team`,
`dev_copilot`, `project_pal`, `forensic_data_agent`, `builder_team`,
`router` all set the identical value, always paired with
`add_history_to_context=True`. No agent uses `enable_session_summaries` —
at `num_history_runs=10` this repo hasn't hit the point where raw
truncation stops being good enough (§ 6).

**HITL write path**: `apply_db_modification` (`factory.py:73-105`) is a
single `@approval` + `@tool(requires_confirmation=True)`-decorated function,
attached only to `ingestion_orchestrator` and `analysis_orchestrator`
(never `dev_copilot`, `forensic_data_agent`, or the Gatekeeper). It
enforces `target_schema == "analysis"` and regex-rejects any statement
referencing `evidence\s*\.` **before** the approval-gated body runs a
single SQL statement inside a fresh transaction. This is our version of the
docs' `safe-data-access` three-role split (§ 5.2) — but collapsed to **one**
gated write tool shared by two orchestrator agents, rather than the docs'
separate Analyst/Engineer/Leader agents with an Engineer-owned schema. We
get the same infrastructure-guarantee half of the pattern (writes are
schema-scoped and approval-gated) without the doc's second half
(materialized views owned by a dedicated Engineer agent — see Open
questions (c)).

**`DatabaseContextProvider` — exact match to the documented pattern**,
instantiated twice in `providers.py`: once as `write=True` (default) for
`ingestion`/`analysis` (`sql_engine=analysis_engine`,
`readonly_engine=evidence_engine`), and once as `write=False` for the
Forensic Data Agent (`evidence_provider`, both `sql_engine` and
`readonly_engine` slots point at the same read-only-enforced engine — "even
the 'write' slot is read-only," per the inline comment). The infrastructure
guarantee is one layer deeper than the provider itself: `_make_engine(url,
readonly=True)` sets `default_transaction_read_only=on` at the Postgres
connection-options level (`connect_args={"options":
"-c default_transaction_read_only=on"}`), so the read-only guarantee holds
even if someone constructed a `DatabaseContextProvider(write=True)` against
that engine by mistake — the DB itself refuses the write, not just the
provider's tool surface. This is ADR-0005's "infrastructure-level, not a
prompt instruction" claim, verified concretely in code (matches the docs'
own framing almost verbatim: "a connection that physically cannot write is
a guarantee").

**`WorkspaceContextProvider(root="/app", id="workspace", model=model)`** —
single instance, feeds `code_tools` used by `dev_copilot` and folded into
`source_tools` for the ops agents. No `exclude_patterns` override (accepts
the documented default dependency/build/venv exclusion list) and no
`max_file_lines`/`max_file_length` override (accepts `100_000` /
`10_000_000` defaults).

**Graphiti MCP tools are wired as `MCPTools(...)` with no
`cache_results=`/`cache_ttl=`/`cache_dir=` set** (`providers.py:184-195`) —
default `cache_results=False`, i.e. every Graphiti call hits the live MCP
server fresh. See Open questions (b) for whether that should change.

**Tool-shape convention note** (from `sbv_tools.py`'s own docstring,
directly relevant to § 4): our one hand-written `@tool` outside the G4/SBV
registries, `apply_db_modification`, deliberately does *not* raise on
failure — it returns a string-prefixed `"OK: .../REJECTED: .../ERROR: ..."`
tri-state result instead, because it's a HITL-approval-gated write that
needs to report an outcome as natural language within a *successful* tool
call. Every other `@tool` in the codebase (SBV wrappers, G4 meta-ops) lets
exceptions propagate and relies on Agno's own `Function.execute()` catching
them into `FunctionExecutionResult(status="failure", ...)`. Neither
convention currently sets `cache_results=True` anywhere in this repo.

---

## Open questions answered

### (a) Should our agents adopt `KnowledgeTools` (think/search/analyze) over bare `search_knowledge`?

**Not yet, selectively.** Our three knowledge-bearing agents
(`ingestion_orchestrator`, `analysis_orchestrator`, `dev_copilot`) each
search a fairly well-scoped knowledge base for their role (ingestion
docs/schemas, analysis methodology, codebase/docs respectively) — the
"first query usually misses, needs iterative refinement" problem
`KnowledgeTools` is built for (§ 2) is a better match for **noisy,
heterogeneous, multi-hop retrieval**, which describes deep-research-style
work (AI Legal Team Part 3, § 5.3) more than our current three agents'
day-to-day retrieval. The overhead (extra think/analyze round-trips, doubled
token cost per retrieval-heavy turn) isn't obviously worth paying for
`dev_copilot` reading well-organized repo docs.

Where it *would* earn its keep: any future **AI Legal Team research agent**
doing multi-hop grounding across the case-bible knowledge base (§ 5.3's
`grounding-research` three-layer pattern is close kin) — an ambiguous
"find every instance of X pattern across N years of evidence" query is
exactly the shape `KnowledgeTools`'s think→search→analyze loop targets, and
the `analysis`/`session_state["thoughts"]` audit trail it produces for free
is independently valuable for a legal-evidence context (defensible "why did
the agent conclude this" trail — mirrors the `structured-deliverable`
pattern's `rationale`/`citations` requirement, § 5.3). Recommendation:
don't retrofit the three existing agents; **default to `KnowledgeTools`
for the first Legal Team research agent** when that build starts, given
both the retrieval-quality and the audit-trail arguments point the same
direction there.

### (b) Is tool-result caching applicable to our expensive Graphiti/SBV MCP tools?

**Mechanically yes (`MCPTools` inherits `Toolkit`, so `cache_results=True`
on the `MCPTools(...)` constructor call in `providers.py` would cache every
generated Graphiti tool's results, § 4) — but apply it selectively, not
blanket, and never to write operations.**

Graphiti's MCP surface mixes read tools (`graphiti-search-memory-facts`,
`graphiti-search-nodes`, `graphiti-get-episodes`, `graphiti-get-status`)
with write/mutating tools (`graphiti-add-memory`, `graphiti-clear-graph`,
`graphiti-delete-episode`, `graphiti-delete-entity-edge`). `MCPTools`-level
`cache_results=True` is toolkit-wide — it would cache the mutating calls
too, which is actively wrong (a cached `graphiti-add-memory` result would
make a second identical-looking call silently no-op instead of writing a
second episode; a cached `graphiti-clear-graph` result is nonsensical).
**Toolkit-level caching is therefore the wrong knob for Graphiti as
currently wired.** The right mechanism is `MCPTools`'s
`include_tools`/`exclude_tools` params (already available, unused today)
combined with **per-tool `@tool(cache_results=True, cache_ttl=...)`**
overrides — except `MCPTools`-generated functions aren't hand-written
`@tool`-decorated functions, they're built dynamically inside
`agno/tools/mcp/mcp.py` at connection time (`Function(...,
cache_results=self.cache_results, cache_dir=self.cache_dir,
cache_ttl=self.cache_ttl)`, all sourced from the *toolkit's* settings, not
overridable per-generated-tool without subclassing or post-hoc mutation of
the built `Function` objects). Practically: either (1) accept
toolkit-wide caching is all-or-nothing for a single `MCPTools` instance and
split Graphiti into **two `MCPTools` instances** — one for the read tools
(`include_tools=[...]`, `cache_results=True, cache_ttl=<short, e.g. 60-300s
given temporal-graph data changes>`) and one for the write tools
(`include_tools=[...]`, no caching) — or (2) leave it uncached, which is
the current, safe-by-default state.

Given Graphiti calls go over `streamable-http` with `refresh_connection=True`
already set (`providers.py:189`) — meaning the connection itself is
already re-established per run, so there's no cheap-connection-reuse
argument being left on the table — and given the read/write split-instance
approach adds real complexity (two MCP connections instead of one, doubled
`header_provider` config, doubled reconnect surface), **recommendation:
don't adopt caching for Graphiti yet**. It's a legitimate lever if Graphiti
read-latency becomes a measured bottleneck (repeated identical fact/node
searches within a short window — e.g. a research agent re-querying the
same entity across several reasoning steps), but the win isn't proven
against the added operational complexity today. SBV tools (`sbv_tools.py`)
are plain `@tool`-wrapped functions (not toolkit-attached, no
`cache_results` set anywhere) — same analysis applies: SBV's read
endpoints (health, hash lookups) are candidates for `@tool(cache_results=True,
cache_ttl=...)` per-function if SBV latency becomes a bottleneck, since
per-tool caching (unlike `MCPTools`) doesn't have the toolkit-wide
all-or-nothing problem — that's the cheaper, safer first move if caching
is ever actually needed, before touching Graphiti's MCP surface at all.

### (c) Anything in data-agents/safe-data-access we should adopt beyond our readonly-engine pattern?

**Two concrete candidates, one soft recommendation:**

1. **Materialization (§ 5.2)** is the most directly actionable gap. Our
   `apply_db_modification` writes arbitrary single statements to the
   `analysis` schema on approval, but nothing captures "this exact query
   pattern has now been validated three times" into a reusable view. If
   `analysis_orchestrator` repeatedly runs structurally-similar aggregation
   queries (which behavioral-analysis workloads plausibly do — the same
   "findings by category" or "timeline reconstruction" shape recurring
   across cases), a `CREATE VIEW` in the `analysis` schema on first
   validation, read thereafter, is a low-risk, high-leverage addition that
   fits *inside* our existing single-tool HITL gate (no new tool needed —
   `apply_db_modification` already accepts arbitrary DDL/DML against
   `analysis`, a `CREATE VIEW ...` statement is just another approved
   write). This wouldn't require adopting the docs' separate Engineer-role
   agent — our existing gate already gives us the "agent-owned schema,
   drop-and-rebuild-is-cheap" safety property the docs cite as the reason
   materialization works.

2. **The three-role split (Analyst/Engineer/Leader) is *not* worth
   adopting as-is.** It solves a problem we've architected around
   differently: the docs split roles because their baseline assumes a
   single agent might have both read and write tools in the same context
   window, so role-splitting is how they bound blast radius. We instead
   bound blast radius via `apply_db_modification`'s explicit `@approval`
   gate plus the evidence-schema regex guard plus the infrastructure-level
   `default_transaction_read_only` split (three independent layers already,
   vs. the docs' role-separation being effectively one layer). Adding a
   dedicated Engineer agent would be net-new orchestration complexity
   (another team member, another delegation path) to re-derive a safety
   property we already have. Skip it.

3. **Soft recommendation — grounding-in-context's "validated queries as
   highest-leverage knowledge" framing (§ 5.2)** is worth deliberately
   folding into what actually goes *into* `knowledge` for
   `analysis_orchestrator`, distinct from whatever schema/documentation
   content is already ingested: specifically curate and ingest known-good
   analysis SQL patterns (once materialization above starts producing
   validated views, their defining queries are natural candidates) rather
   than relying solely on ambient schema knowledge. This is a content/
   curation change to what's fed into `knowledge`, not a code change — no
   new provider or tool required, just discipline about what gets inserted.

---

## Coverage

**Method**: the Agno docs MCP (`claude_ai_agno` — both `search_agno` and
`query_docs_filesystem_agno`) was unreachable for the entire session
(persistent `"MCP server is not connected"` across ~10 retries spread over
the whole task). All pages below were fetched via `WebFetch` directly
against `docs.agno.com`. Sibling-page enumeration beyond the checklist used
`docs.agno.com/sitemap.xml` and `docs.agno.com/llms.txt` plus direct probes
of plausible sibling URLs (both index files are demonstrably incomplete —
`sitemap.xml` has zero `/use-cases/` or `/tools/` or `/teams/usage/`
entries despite those pages existing and returning real content; `llms.txt`
truncates at 100k characters with "2490 pages... omitted"). Enumeration is
therefore **best-effort, not exhaustive** — pages that exist but aren't
linked from any page I fetched, and aren't in either index, would not have
been found.

### Checklist URLs (assigned floor) — all read

- [x] https://docs.agno.com/use-cases/data-agents/querying-your-data
- [x] https://docs.agno.com/use-cases/data-agents/safe-data-access
- [x] https://docs.agno.com/use-cases/data-agents/self-correcting-agents
- [x] https://docs.agno.com/use-cases/data-agents/serve-and-embed
- [x] https://docs.agno.com/use-cases/deep-research/grounding-research
- [x] https://docs.agno.com/use-cases/deep-research/structured-deliverable
- [x] https://docs.agno.com/use-cases/product-agents/connecting-your-data
- [x] https://docs.agno.com/use-cases/product-agents/sessions-and-memory
- [x] https://docs.agno.com/tools/caching
- [x] https://docs.agno.com/tools/reasoning_tools/knowledge-tools
- [x] https://docs.agno.com/tools/reasoning_tools/memory-tools
- [x] https://docs.agno.com/tools/toolkits/others/knowledge
- [x] https://docs.agno.com/context/overview
- [x] https://docs.agno.com/context-providers/providers/wiki
- [x] https://docs.agno.com/agents/usage/agent-with-knowledge
- [x] https://docs.agno.com/agents/usage/agent-with-memory
- [x] https://docs.agno.com/agents/usage/agent-with-storage
- [x] https://docs.agno.com/teams/building-teams
- [x] https://docs.agno.com/teams/usage/basic-team
- [x] https://docs.agno.com/teams/usage/streaming
- [x] https://docs.agno.com/other/agent-ui
- [x] https://docs.agno.com/other/install

### Extras found beyond the checklist (enumerated, on-topic, read)

Found via `use-cases/data-agents/overview`, `use-cases/deep-research/overview`,
and `use-cases/product-agents/overview` sibling listings, plus
`sitemap.xml` for the `context`/`context-providers` trees:

- [x] https://docs.agno.com/use-cases/data-agents/grounding-in-context
- [x] https://docs.agno.com/use-cases/data-agents/materialization
- [x] https://docs.agno.com/use-cases/deep-research/orchestration-patterns
- [x] https://docs.agno.com/use-cases/deep-research/parallel-investigation
- [x] https://docs.agno.com/use-cases/deep-research/institutional-learning
- [x] https://docs.agno.com/use-cases/product-agents/serve-as-an-api
- [x] https://docs.agno.com/context-providers/overview
- [x] https://docs.agno.com/context-providers/providers/database
- [x] https://docs.agno.com/context-providers/providers/workspace
- [x] https://docs.agno.com/context/agent/overview
- [x] https://docs.agno.com/context/agent/dynamic-instructions
- [x] https://docs.agno.com/context/agent/few-shot-learning
- [x] https://docs.agno.com/context/team/overview

### Enumerated but deliberately not read (out of RAG/knowledge/memory/context scope)

- `use-cases/product-agents/interfaces` — Slack/Telegram/WhatsApp/browser transport, not a retrieval/context concern.
- `context-providers/providers/{calendar,drive,filesystem,gmail,mcp,slack,web}` — non-knowledge source connectors; only `database`/`workspace`/`wiki` are on-topic (and are the three actually wired into or documented for our stack).
- `context-providers/custom-providers`, `context-providers/using-providers` — provider-authoring mechanics, not a RAG/context-content question.
- `context/agent/{instructions,instructions-via-function,datetime-instructions,location-instructions,filter-tool-calls-from-history}`, `context/team/filter-tool-calls-from-history` — basic instruction/system-message mechanics tangential to knowledge/memory/token-budget; `dynamic-instructions` and `few-shot-learning` were read because § 6 (context engineering) explicitly covers ordering/token discipline and both bear directly on that.
- `agents/usage/{agent-with-followup-suggestions,agent-with-structured-output,agent-with-tools}` — sibling pages of the assigned three (found via sitemap); `agent-with-structured-output` is tangential to § 5.3's `structured-deliverable` pattern (already covered from the use-case-page angle) and `agent-with-tools` is generic tool-calling, not knowledge/memory-specific.
- `tools/reasoning_tools` (base `ReasoningTools` — generic `think`/`analyze` only, no knowledge/memory binding) — distinct toolkit from `KnowledgeTools`/`MemoryTools`, confirmed to exist as a sibling but out of this file's scope (it's not a knowledge or memory tool).
- `use-cases/deep-research/serve-and-embed` — referenced in one fetched page's "Learn How To" table without its own description card; unclear whether this is a real distinct page or a mislabeled link back to `use-cases/data-agents/serve-and-embed` (same pattern, deep-research context). Not independently verified — flagged rather than silently assumed.

### Doc-vs-source discrepancies flagged (see body for full detail)

1. **`tools/reasoning_tools/knowledge-tools`** — code example uses `think=True, search=True, analyze=True`; real `KnowledgeTools.__init__` params (verified in `agno/tools/knowledge.py`, 2.6.13) are `enable_think`/`enable_search`/`enable_analyze`. The example as written raises `TypeError` against installed source. A second doc page (`tools/toolkits/others/knowledge`) correctly uses the `enable_*` names — the two Agno doc pages disagree with each other.
2. **`tools/caching`** — documents only `cache_results=True`; source (`agno/tools/toolkit.py`) also has `cache_ttl` (default 3600s) and `cache_dir` as real, load-bearing params, plus undocumented behavior (generators never cached; non-JSON-serializable results silently fail to persist rather than erroring).
   new provider or tool required, just discipline about what gets inserted.
