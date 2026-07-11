> _Byline: Claude Code · Sonnet (R1a) · 2026-07-11_

# Agno Memory & Learning — Expert Reference

Covers Agno's two coexisting memory subsystems as of `agno==2.6.13`: the legacy
`MemoryManager` (per-agent/team unstructured "memories") and the newer
`LearningMachine` (multi-store learning system: user_profile, user_memory,
session_context, entity_memory, learned_knowledge, decision_log), plus the
separate `SessionSummaryManager`. Verified against installed source in
`.venv/Lib/site-packages/agno/memory/` and `.venv/Lib/site-packages/agno/learn/`
(agno 2.6.13, per `.venv/Lib/site-packages/agno-2.6.13.dist-info/METADATA`).

Docs were fetched live from docs.agno.com via WebFetch (the Agno docs MCP
server — `claude.ai agno` — disconnected mid-task and never reconnected; a raw
`sitemap.xml` pull confirmed the doc-tree scope and surfaced 4 pages beyond the
owner's original checklist — see "## Coverage").

## Doc-vs-source discrepancies

1. **`Curator.prune()` / `Curator.deduplicate()` are effectively no-ops against
   the default schema.** Both methods (`agno/learn/curate.py:36-119`) operate
   exclusively on `self.machine.stores.get("user_profile")` and require
   `hasattr(profile, "memories")`. But the default `UserProfile` schema
   (`agno/learn/schemas.py:60-103`) has **no `memories` field** — only
   `user_id`, `name`, `preferred_name`, `agent_id`, `team_id`, timestamps. The
   `memories: List[Dict]` field lives on the *`Memories`* schema
   (`agno/learn/schemas.py:174-195`), i.e. the **`user_memory`** store, which
   `Curator` never touches. Net effect: `learning.curator.prune(...)` and
   `.deduplicate(...)` silently return `0` for every default-schema user —
   they only do anything if you hand-roll a custom `UserProfile` subclass with
   a `memories` field, which nobody would naturally do. Yet:
   - `docs.agno.com/learning/overview` shows `lm.curator.prune(user_id="alice", max_age_days=90)`
     as a working example with no caveat.
   - `docs.agno.com/memory/best-practices` recommends "Memory Pruning:
     Implement scheduled cleanup removing memories older than 90 days" as a
     production practice, again without flagging that the shipped `Curator`
     can't actually prune `user_memory` (the store that actually accumulates
     unbounded observations) at all.
   - The `curate.py` module docstring itself says "Currently supports
     user_profile store only" — so the *scoping* is intentional/documented in
     source comments, but the *non-functionality against the default schema*
     is not called out anywhere, in source or docs.

2. **`docs.agno.com/learning/overview`'s LearningMachine constructor example is
   wrong.** It shows:
   ```python
   agent = Agent(..., learning=True)
   lm = agent.get_learning_machine()
   ```
   Neither an `Agent(learning=...)` kwarg nor `agent.get_learning_machine()`
   exists in `agno/agent/agent.py` (grepped — no match) or anywhere in
   `agno/learn/`. `LearningMachine` in 2.6.13 is a **standalone
   dataclass** (`agno/learn/machine.py:52`) that you construct directly and
   wire into an Agent/Team's `learning=` (or similarly-named) tools/context,
   not something an `Agent(...)` constructor param toggles by itself. The
   correct pattern — confirmed by our own `server/agents/providers.py:225-262`
   and by `docs.agno.com/learning/quickstart` (which is internally consistent
   and does NOT use `learning=True`) — is:
   ```python
   from agno.learn import LearningMachine
   learning = LearningMachine(db=db, model=model, knowledge=knowledge, user_profile=True, ...)
   ```
   Treat the `learning/overview` snippet as aspirational/incorrect; trust
   `learning/quickstart` and the source instead.

3. **`docs.agno.com/learning/learning-modes` omits the PROPOSE→ALWAYS
   fallback for `EntityMemoryStore` and `UserProfileStore`.** The docs page
   correctly states Entity Memory's "Supported modes: Always, Agentic" (no
   PROPOSE) — so the *docs* are accurate on what's supported. But nothing in
   the docs (or in `EntityMemoryConfig`'s own docstring) warns that passing
   `mode=LearningMode.PROPOSE` anyway does **not** raise, and does **not**
   inertly no-op — it silently **falls back to full ALWAYS-mode auto-write**
   with only a `log_warning` (`agno/learn/stores/entity_memory.py:91-93`:
   `"EntityMemoryStore does not support PROPOSE mode. Falling back to ALWAYS mode."`).
   Same for `UserProfileStore` (`user_profile.py:89-91`). A caller who reads
   only the learning-modes page and assumes PROPOSE is "safely ignored" would
   be surprised that it actually strips the human gate entirely. See
   "How WE use it" below — this is exactly the trap our own `build_learning()`
   fell into for `entity_memory`.

4. **`docs.agno.com/memory/agent/overview` describes `enable_agentic_memory`
   and `update_memory_on_run` with no mention of `enable_user_memories`.**
   Source (`agno/agent/agent.py:403`) shows `enable_user_memories` still
   exists as a constructor kwarg but is commented `# Soon to be deprecated.
   Use update_memory_on_run` — it's a soft-alias that, when passed, sets
   `self.update_memory_on_run = enable_user_memories` (`agent.py:534-538`).
   Not a doc bug per se (the docs correctly steer toward the new name) but
   worth flagging since the task brief explicitly asked about it: it is **not
   yet removed**, just discouraged — a straight rename-in-progress, still
   read/written for backward compat and for the AgentOS API schema
   (`agno/os/routers/agents/schema.py:210`).

## Open questions answered

### (a) Does LearningMachine fully supersede MemoryManager, or do they coexist in 2.6.13?

**They fully coexist — LearningMachine does not supersede or wrap
MemoryManager.** Both are independent, live classes with separate constructor
surfaces, separate DB methods, and separate schemas:

- `MemoryManager` (`agno/memory/manager.py`) is the older, single-purpose
  manager: it drives `Agent(db=..., update_memory_on_run=True)` /
  `enable_agentic_memory=True`, persists via `db.upsert_user_memory` /
  `db.get_user_memories` / `db.delete_user_memory` (the classic `UserMemory`
  row shape), and is what all the `memory/*` doc pages describe.
- `LearningMachine` (`agno/learn/machine.py`) is the newer, six-store
  orchestrator (`user_profile`, `user_memory`, `session_context`,
  `entity_memory`, `learned_knowledge`, `decision_log`), persists via the
  generic `db.get_learning` / `db.upsert_learning` / `db.delete_learning` /
  `db.get_learnings` methods against a single `learnings` table (Postgres:
  `agno/db/postgres/postgres.py:4374-4560`, auto-created), and is what the
  `learning/*` doc pages describe.
- `LearningMachine`'s own `user_memory` store is a **third, parallel**
  representation of "unstructured user memory" — distinct from
  `MemoryManager`'s — with its own `Memories` schema and its own `learnings`
  table row (`learning_type="user_memory"`), not backed by the same
  `agno_memories`/`memories` table `MemoryManager` uses. Running both on the
  same Agent gives you two independent, non-synchronized memory stores.
- Nothing in source (`agno/agent/agent.py`, `agno/team/team.py`) references
  `LearningMachine` at all — it is not wired into `Agent.__init__` the way
  `MemoryManager`/`SessionSummaryManager` are. Integration is manual/consumer-side
  (build a `LearningMachine`, call `.build_context()` to inject into the system
  prompt and `.get_tools()`/`.process()` yourself — exactly the pattern our
  `server/agents/providers.py` follows).
- Conclusion: pick one (or both, understanding they don't share data).
  Agno's own `learning/overview` docs never mention `MemoryManager` for
  comparison, and `memory/overview` never mentions `LearningMachine` except
  in a passing "see also" — the two doc trees are written as if the other
  doesn't exist, reinforcing that this is genuinely two systems, not an
  old/new API pair with a migration path.

### (b) Does the SurrealDb backend support ALL LearningMachine stores with parity to PostgresDb?

**No — SurrealDb has zero functional parity with PostgresDb for
LearningMachine.** All four generic learning methods on
`agno/db/surrealdb/surrealdb.py:1990-2034` are unimplemented stubs:

```python
# -- Learning methods (stubs) --
def get_learning(...) -> Optional[Dict[str, Any]]:
    raise NotImplementedError("Learning methods not yet implemented for SurrealDb")
def upsert_learning(...) -> None:
    raise NotImplementedError("Learning methods not yet implemented for SurrealDb")
def delete_learning(self, id: str) -> bool:
    raise NotImplementedError("Learning methods not yet implemented for SurrealDb")
def get_learnings(...) -> List[Dict[str, Any]]:
    raise NotImplementedError("Learning methods not yet implemented for SurrealDb")
```

Compare `agno/db/postgres/postgres.py:4374-4560+`, which has a full
SQLAlchemy-backed `learnings` table implementation (auto-creates the table,
handles `ON CONFLICT DO UPDATE` upserts, filters by
`learning_type`/`user_id`/`agent_id`/`team_id`/`workflow_id`/`session_id`/
`namespace`/`entity_id`/`entity_type`). `queries.py` and `models.py` under
`agno/db/surrealdb/` have **zero** mentions of "learning" — this isn't a
partial gap, it's simply not built.

Every `LearningStore` implementation routes exclusively through these four
generic methods **except** `LearnedKnowledgeStore`, which bypasses `db`
entirely and calls `self.knowledge.insert()` / `.search()` /
`.delete_content()` (`agno/learn/stores/learned_knowledge.py:768-1075`) — i.e.
it persists through the `Knowledge` object's own vector store + contents DB,
not through the operational `db`.

**Consequence for our stack** (`server/core/session.py:129` `get_agno_db()`
returns `SurrealDb`, wired into `build_learning()` at
`server/agents/providers.py:225-262`):

| Store (our config) | Mode | Works on SurrealDb? |
|---|---|---|
| `user_profile` | ALWAYS | **No** — `db.get_learning`/`upsert_learning` raise `NotImplementedError` on every call |
| `user_memory` | AGENTIC | **No** — same stub methods |
| `session_context` | ALWAYS, planning | **No** — same stub methods |
| `entity_memory` | PROPOSE (intended HITL) | **No** — same stub methods (also see discrepancy #3: even if the DB worked, PROPOSE silently degrades to ALWAYS here) |
| `learned_knowledge` | PROPOSE (intended HITL) | **Yes** — routes through `Knowledge` (Milvus + Postgres contents_db via `create_knowledge()`), never touches SurrealDb's learning stubs |

Confirmed via `Grep` across `server/`: there is no monkeypatch, subclass, or
override of `SurrealDb.get_learning`/`upsert_learning`/`delete_learning`
anywhere in this repo. `LearningMachine._resolve_store()` and every store's
`process()`/`recall()` wrap their `self.db.*` calls in bare `try/except` with
only a `log_warning`/`log_debug` on failure (see `machine.py:548-554`,
`session_context.py:298-300`, etc.) — so **this fails silently**. In
production, `user_profile`, `user_memory`, `session_context`, and
`entity_memory` are configured but are currently no-ops: nothing is ever
persisted or recalled for them, and the only symptom is a debug-level log line
that is easy to miss. Only `learned_knowledge` (namespace="platform") is
actually live today.

**Note:** `MemoryManager`'s legacy path (`db.upsert_user_memory` /
`get_user_memories` / etc., `surrealdb.py:731-1015+`) IS fully implemented on
SurrealDb — real `UPSERT`/`CREATE` queries against a `memories` table. If the
platform needs `user_memory`/`user_profile`-equivalent persistence to actually
work on SurrealDb today without a DB-layer fix, `MemoryManager` (or `Agent`'s
`update_memory_on_run`) is the only currently-functional path; `LearningMachine`'s
generic-store path needs either a SurrealDb `get_learning`/`upsert_learning`
implementation contributed upstream, or a swap to `PostgresDb` as the
operational store.

### (c) Is there a decision_log store, and are we using it?

**Yes, it exists in agno 2.6.13** — `DecisionLogStore` /
`DecisionLogConfig` (`agno/learn/config.py:378-407`,
`agno/learn/stores/decision_log.py`), scope AGENT (keyed by `agent_id`),
default `mode=LearningMode.ALWAYS`, with `agent_can_save`/`agent_can_search`
tool toggles and a `DecisionLog` schema (`id`, `decision`, `reasoning`,
`decision_type`, `context`, `alternatives`, `confidence`, `outcome`,
`outcome_quality`, timestamps — `agno/learn/schemas.py:896-936`). It exists as
a first-class `LearningMachine.decision_log` field alongside the other five
stores (`machine.py:85`, `_create_decision_log_store()` at `machine.py:289-305`).

**We are not using it.** `server/agents/providers.py:225-262`'s
`build_learning()` constructs `LearningMachine(user_profile=..., user_memory=...,
session_context=..., entity_memory=..., learned_knowledge=...)` — no
`decision_log=` kwarg at all, and a repo-wide grep for `decision_log`/
`DecisionLog` in `server/` returns only that one call site's absence (zero
hits). Even if it were enabled, it would hit the same SurrealDb
`get_learning`/`upsert_learning` `NotImplementedError` stubs as
`user_profile`/`user_memory`/`session_context`/`entity_memory` (see (b)), so
enabling it today would not persist anything either.

---

## Part 1 — MemoryManager (legacy/classic memory)

### 1.1 Overview & mental model

`MemoryManager` (`agno/memory/manager.py`, `@dataclass`) is Agno's original
per-user "unstructured observations" memory system. An `Agent` or `Team` owns
zero or one `MemoryManager` (constructed implicitly if you just set
`db=...` + `update_memory_on_run=True`/`enable_agentic_memory=True`, or
explicitly via `memory_manager=MemoryManager(...)`). Memories are `UserMemory`
rows (`agno.db.schemas.UserMemory` / `agno.db.base.UserMemory`: `memory_id`,
`user_id`, `agent_id`, `team_id`, `memory` text, `topics`, `input`,
`updated_at`) persisted via `db.upsert_user_memory` /
`db.get_user_memories` / `db.delete_user_memory` / `db.clear_memories`.
Scope is `user_id` (defaults to the literal string `"default"` if unset —
see best-practices below for why that's dangerous in multi-tenant use).

Two mutually-exclusive activation modes on the owning `Agent`/`Team`:
- `update_memory_on_run=True` — after every run, `MemoryManager` is invoked
  automatically (background LLM call) to extract/add/update memories.
- `enable_agentic_memory=True` — the agent itself gets a tool
  (`update_user_memory`) and decides in-line whether to call it.
Docs (`memory/agent/overview`, `memory/best-practices`) explicitly warn: don't
enable both — they're not additive, and if both are set agentic mode takes
precedence, silently disabling the automatic pass.

### 1.2 MemoryManager constructor & knobs

From `agno/memory/manager.py:77-107` (`__init__`, all keyword-only):

| Param | Default | Purpose |
|---|---|---|
| `model` | `None` → falls back to `OpenAIChat(id="gpt-4o")` at first use (`get_model()`, `manager.py:112-123`) if never set | Model used for memory extraction |
| `system_message` | `None` | Full override of the memory-manager system prompt |
| `memory_capture_instructions` | `None` → built-in default (personal facts/opinions/life events/context) | The `<memories_to_capture>` criteria text |
| `additional_instructions` | `None` | Appended to the (default or custom) system message |
| `db` | `None` | Where memories persist — required for anything to work |
| `delete_memories` | `False` | Exposes the `delete_memory` tool to the extraction call |
| `update_memories` | `True` | Exposes `update_memory` |
| `add_memories` | `True` | Exposes `add_memory` |
| `clear_memories` | `False` | Exposes `clear_memory` (dangerous — wipes all memories for the user) |
| `debug_mode` | `False` | |
| `id`, `name`, `owner_id`, `owner_type` | `None` | Identity/registration metadata (AgentOS) |

Note the dataclass-level field defaults (`manager.py:59-75`) differ slightly
from the `__init__` defaults for `delete_memories`/`clear_memories`
(`True`/`True` at class level vs `False`/`False` in `__init__`) — `__init__`
wins at runtime since it's what actually executes; the bare dataclass
defaults are effectively dead unless someone bypasses `__init__`.

### 1.3 Capture instructions / custom memory instructions

`memory_capture_instructions: Optional[str]` — a free-text criteria block
injected into `<memories_to_capture>` in the system prompt
(`get_system_message()`, `manager.py:967-1047`). Example
(`docs.agno.com/memory/working-with-memories/custom-memory-instructions`):

```python
memory = MemoryManager(
    model=OpenAIResponses(id="gpt-5.2"),
    memory_capture_instructions=(
        "Memories should only include details about the user's academic "
        "interests. Only include which subjects they are interested in. "
        "Ignore names, hobbies, and personal interests."
    ),
    db=memory_db,
)
```
`additional_instructions` is the softer variant — it doesn't replace the
default capture criteria, it appends extra rules after them (e.g. "never
store the user's real name — use 'The User' instead", per the
`custom-memory-manager` doc example). `system_message` is the nuclear
override — if set, `get_system_message()` returns it verbatim and skips
building anything from `memory_capture_instructions`/existing-memories/
`additional_instructions` entirely.

### 1.4 Add / update / delete / clear toggles

Both at the `MemoryManager` level (gate which tools are ever exposed to the
extraction/agentic call — §1.2 table) and passed per-call
(`create_or_update_memories(update_memories=..., add_memories=...)`,
`run_memory_task(delete_memories=..., clear_memories=..., update_memories=...,
add_memories=...)`). The db-facing tool functions themselves
(`_get_db_tools()`/`_aget_db_tools()`, `manager.py:1328-1580`) are
`add_memory(memory, topics)`, `update_memory(memory_id, memory, topics)`,
`delete_memory(memory_id)`, `clear_memory()` — plain Python closures over
`user_id`/`db`/`agent_id`/`team_id`, turned into `Function` objects via
`Function.from_callable(..., strict=True)`.

### 1.5 Retrieval

`get_user_memories(user_id)` / `get_user_memory(memory_id, user_id)` — direct
reads. `search_user_memories(query, limit, retrieval_method, user_id)`
(`manager.py:597-647`) supports three `retrieval_method` values:
- `"last_n"` (default when unset) — most recent N by `updated_at`.
- `"first_n"` — oldest N.
- `"agentic"` — an LLM call (`_search_user_memories_agentic`,
  `manager.py:665-737`) that's shown the full memory list (id + text +
  topics) and asked to return the IDs matching a free-text `query`, via a
  structured `MemorySearchResponse{memory_ids: List[str]}` — requires
  `query` to be set or it raises `ValueError`.

### 1.6 Memory optimization strategies (summarize, etc.)

`optimize_memories(user_id, strategy=MemoryOptimizationStrategyType.SUMMARIZE,
apply=True)` (`manager.py:802-871`, async twin `aoptimize_memories`). Strategy
is pluggable via the abstract `MemoryOptimizationStrategy` base
(`agno/memory/strategies/base.py`: `optimize()`, `aoptimize()`,
`get_system_prompt()` optional, `count_tokens()` provided). **As shipped,
exactly one concrete strategy exists**: `SummarizeStrategy`
(`agno/memory/strategies/summarize.py`) — collapses every memory for a user
into a single LLM-generated third-person narrative, preserving/deduping
topics and `agent_id`/`team_id` only if consistent across all inputs. The
`MemoryOptimizationStrategyType` enum (`strategies/types.py`) has a single
member, `SUMMARIZE = "summarize"`; `MemoryOptimizationStrategyFactory` maps
it to `SummarizeStrategy`. `apply=True` (default) replaces the user's entire
memory set in the DB (`clear_user_memories()` then re-`upsert`); `apply=False`
returns the optimized list without touching the DB. Custom strategies: pass an
already-constructed `MemoryOptimizationStrategy` subclass instance instead of
the enum.

### 1.7 Standalone memory (no agent)

`MemoryManager` needs no `Agent` to function — construct it directly with
`db=`, then call `add_user_memory(UserMemory(...))`,
`create_user_memories(message=... | messages=[...])`,
`replace_user_memory(memory_id, memory)`, `delete_user_memory(memory_id)`,
`get_user_memories(user_id)` directly. This is the pattern for
backfill/admin scripts or non-agent pipelines that still want Agno's memory
schema and extraction prompt.

### 1.8 / 1.9 Postgres / SQLite memory examples

Both are the same three-line pattern — only the `db` swaps:
```python
# Postgres
db = PostgresDb(db_url="postgresql+psycopg://ai:ai@localhost:5532/ai")
# SQLite
db = SqliteDb(db_file="tmp/data.db")

agent = Agent(db=db, update_memory_on_run=True)
```
Docs also show **MongoDb** (`db = MongoDb(db_url="mongodb://localhost:27017")`,
needs `pymongo`) and **RedisDb** (`db = RedisDb(db_url="redis://localhost:6379")`,
needs `redis` + a running Redis instance) with identical wiring — these two
pages are not in the owner's original checklist but exist in the live doc
tree (`memory/working-with-memories/mongodb-memory`,
`memory/working-with-memories/redis-memory`) and confirm `update_memory_on_run`
is DB-backend-agnostic at the `Agent` level.

### 1.10 Agentic memory vs `update_memory_on_run` (enable_user_memories deprecation)

- `enable_agentic_memory=True` → agent gets an in-line `update_user_memory`
  tool; the model decides per-turn whether anything is memory-worthy. Costs
  nothing extra when it decides not to act, but per `memory/best-practices`
  this can be 8x more expensive than automatic mode on conversations with
  many existing memories (nested LLM calls scale with memory-set size), so
  the docs recommend a cheap dedicated model for the memory tool call.
- `update_memory_on_run=True` → always runs `MemoryManager` once after the
  turn, unconditionally, as one extra background LLM call.
- `enable_user_memories` (`agent.py:403,534-538`) is the **old name** for
  `update_memory_on_run` — passing it just assigns
  `self.update_memory_on_run = enable_user_memories`. Source marks it "Soon
  to be deprecated" but it is still read/written today (including by the
  AgentOS REST schema at `agno/os/routers/agents/schema.py:210`), so it's not
  yet a hard break — just don't write new code against it.

### 1.11 Sharing memory between agents / teams

Two flavors:
- **Memory only** (`memory/agent/agents-share-memory`) — multiple agents
  point at the same `db`; because memories are keyed by `user_id` (not
  `agent_id`), any agent that queries `user_id=X` sees memories any other
  agent wrote for `X`. `agent_id`/`team_id` on each `UserMemory` row are
  audit metadata only, not an isolation boundary.
- **Memory + chat history** (`memory/agent/share-memory-and-history-between-agents`)
  — same shared `db`, plus `add_history_to_context=True` on each agent and a
  shared `session_id`. This additionally surfaces prior turns (not just
  extracted memories) to every agent reading that session.

### 1.12 Multi-user / multi-session chat (incl. concurrent)

- Non-concurrent (`memory/agent/multi-user-multi-session-chat`): `user_id`
  scopes the memory pool across all of that user's sessions; `session_id`
  scopes a single conversation thread. `get_user_memories(user_id=...)`
  returns memories accumulated from *every* session for that user, so an
  agent picking up in session B can already know facts learned in session A.
- Concurrent (`memory/agent/multi-user-multi-session-chat-concurrent`): same
  model, but multiple users' conversations run in parallel via
  `agent.arun()` + `asyncio.gather(user_1_conversation(), user_2_conversation(), ...)`.
  Isolation relies entirely on distinct `user_id`/`session_id` pairs per
  coroutine plus the DB layer's own concurrency handling — the docs do not
  describe any additional locking, and neither does `MemoryManager` source
  (no mutex/lock objects anywhere in `manager.py`).

### 1.13 Custom memory manager

Two ways to customize, both shown in `memory/agent/custom-memory-manager`:
1. Instantiate `MemoryManager(model=..., additional_instructions=..., db=db)`
   yourself and pass it as `agent.memory_manager=` (plus
   `update_memory_on_run=True` to actually invoke it).
2. Full subclass — override `get_system_message()`, the DB tool builders, or
   `create_or_update_memories()`/`run_memory_task()` for bespoke extraction
   logic. Source has no ABC/Protocol gate on `MemoryManager` (it's a plain
   `@dataclass`), so subclassing is unrestricted — same shape as any Python
   class override.

### 1.14 Session summaries (SessionSummaryManager)

**Not part of either MemoryManager or LearningMachine** — a third, separate
subsystem living at `agno/session/summary.py`. `SessionSummaryManager`
(`@dataclass`) generates a `SessionSummary{summary: str, topics: Optional[List[str]],
updated_at}` and writes it to `session.summary` on the `AgentSession`/
`TeamSession` object itself (i.e. it lives in session storage, not in the
`memories`/`learnings` tables). Enabled via `Agent(enable_session_summaries=True)`
or by passing a pre-built `session_summary_manager=SessionSummaryManager(...)`
(which auto-sets `enable_session_summaries=True` — `agent.py:544-546`).
Constructor knobs: `model`, `session_summary_prompt` (full override),
`summary_request_message` (default `"Provide the summary of the conversation."`),
`last_n_runs` (must be `>0` if set), `conversation_limit` (must be `>0` if
set). `create_session_summary()`/`acreate_session_summary()` call the model
once with a structured `SessionSummaryResponse{summary, topics}` output and
stash the result on the session. This is functionally closest to
LearningMachine's `session_context` store (both summarize "what's happened in
this session") but is older, simpler (no goal/plan/progress planning mode),
and uses an entirely different storage path.

### 1.15 Team memory (team-with-memory-manager, team-with-agentic-memory)

Teams support the identical two flags as Agents:
```python
team = Team(model=..., members=[agent], db=db, update_memory_on_run=True)   # automatic
team = Team(model=..., members=[agent], db=db, enable_agentic_memory=True)  # agentic
```
Docs describe Team memory as handled "just like agents" — same `user_id`/
`session_id` semantics, same `MemoryManager` under the hood. One extra
pattern: you can assign a distinct, custom `MemoryManager` to an individual
member `Agent` *before* adding it to the `Team`, for per-member memory
behavior inside an otherwise team-managed conversation.

### 1.16 Production best practices

From `docs.agno.com/memory/best-practices` (full extraction):
- **Default to `update_memory_on_run=True`**, not `enable_agentic_memory`,
  unless you specifically need in-line agent control — automatic mode is
  simpler and (per the cost analysis below) usually cheaper.
- **Always pass an explicit `user_id`.** Omitting it collapses everyone onto
  the literal string `"default"` (confirmed in source —
  `manager.py:178,206,240,270,300,316`, every method defaults `user_id` to
  `"default"` when `None`) — a real cross-tenant data leak, not just a
  hygiene nit.
- **Agentic memory has a real token-cost trap**: with ~100 existing memories,
  a 10-message conversation needing 7 memory updates can cost ~8x more in
  agentic mode (~40k tokens) vs automatic (~5k tokens), because each agentic
  memory tool call re-sends the growing memory list as context.
  Recommendation: pair a cheap model (docs cite "60x less expensive") for the
  memory manager specifically, cutting memory-related spend ~98%, and/or
  instruct the model to batch updates and skip transient state.
- **Prune on a schedule**: remove memories older than 90 days (see
  discrepancy #1 above — the shipped `Curator` can't actually do this against
  the default schema; this is a docs recommendation you'd currently have to
  implement by hand, e.g. custom SQL/DB calls, not `learning.curator.prune()`).
- **Cap tool calls per conversation** to bound runaway memory-tool loops in
  agentic mode.
- **Monitor per-user memory counts**, alert past ~500 as a smell that
  something (probably an over-eager agentic loop or duplicate-heavy capture
  instructions) is misbehaving.
- **Don't combine `update_memory_on_run=True` and `enable_agentic_memory=True`**
  expecting both to run — agentic mode wins and automatic extraction is
  disabled.

### 1.17 Memori integration

`docs.agno.com/integrations/memory/memori` — Memori is a **third-party,
external** open-source memory layer (not an Agno-authored subsystem),
integrated by calling `.agno.register()` on a Memori instance against an
Agno model. It:
- Auto-records conversations, extracts key facts, and supports search over
  them, scoped by caller-supplied `entity_id`/`process_id` (its own
  identity model — distinct from Agno's `user_id`/`agent_id`).
- Works across OpenAI/Anthropic/Bedrock/Gemini/Grok, sync/streaming/async.
- Backs onto its own SQLAlchemy connection — Postgres, MySQL, SQLite,
  MongoDB, CockroachDB, Neon, Supabase — independent of whatever `db=` the
  Agno `Agent`/`Team` itself uses.
- Setup: `uv pip install -U memori sqlalchemy python-dotenv` → build a
  SQLAlchemy engine → `Memori(...).agno.register(model)` → set
  `entity_id`/`process_id` per call → `.config.storage.build()` once to
  create tables.
- The docs page does not compare it against `MemoryManager`/`LearningMachine`
  at all — treat it as an alternative you'd reach for if you want Memori's
  own entity/process memory model or its multi-provider auto-capture,
  independent of (and not interoperable with) Agno's native memory. We do
  not use it anywhere in this platform (not referenced in `server/`).

---

## Part 2 — LearningMachine (current system)

### 2.1 Overview & architecture

`LearningMachine` (`agno/learn/machine.py:52`, `@dataclass`) is a standalone
orchestrator over up to six independently-configurable `LearningStore`
implementations, plus arbitrary `custom_stores`. Construct it directly
(there is no `Agent(learning=...)` shortcut that "just works" — see
discrepancy #2):

```python
from agno.learn import LearningMachine, LearningMode, UserProfileConfig, UserMemoryConfig

learning = LearningMachine(
    db=db,               # BaseDb/AsyncBaseDb — shared default for all stores unless overridden per-store
    model=model,          # default model for all stores unless overridden per-store
    knowledge=knowledge,  # required for learned_knowledge; auto-enables that store if you set this and leave learned_knowledge unset
    user_profile=True,           # or UserProfileConfig(...), or a LearningStore instance, or False/omit to disable
    user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC),
    session_context=True,
    entity_memory=False,
    learned_knowledge=False,
    decision_log=False,
    namespace="global",   # default namespace for entity_memory / learned_knowledge
    custom_stores=None,
    debug_mode=False,
)
```

Every store field accepts `bool | <ItsConfig> | LearningStore` (type aliases
`UserProfileInput` etc., `machine.py:44-49`). `True` → default config for that
store; a `*Config` instance → merged with `machine.db`/`machine.model` only
where the config left `db`/`model` unset (`_create_*_store()` methods,
`machine.py:198-305`); a `LearningStore` instance → used verbatim, bypassing
config resolution entirely (this is the extension point for `custom_stores`
too). Stores are **lazily initialized** on first access to `.stores`
(`machine.py:104-109`) — nothing is constructed at `LearningMachine(...)`
call time.

Main API surface:
- `build_context(user_id, session_id, message, entity_id, entity_type,
  namespace, agent_id, team_id) -> str` — calls `recall()` then formats every
  store's result via its `build_context(data)` into one newline-joined string
  for the system prompt. Async twin `abuild_context`.
- `get_tools(...) -> List[Callable]` / `aget_tools(...)` — unions
  `store.get_tools(**context)` across every enabled store (each store decides
  whether it returns tools based on its own mode/`enable_agent_tools`).
- `process(messages, user_id, session_id, namespace, agent_id, team_id)` /
  `aprocess(...)` — call after a conversation; each store's `process()` is a
  no-op unless its mode requires post-hoc extraction (ALWAYS stores
  extract; AGENTIC/PROPOSE stores mostly act via their tools instead — see
  each store's `process()` guard clause).
- `recall(...)` / `arecall(...)` — lower-level: raw dict of
  `{store_name: data}` without formatting; `build_context` is `recall` +
  `_format_results`.
- `.curator` (lazy `Curator(machine=self)`) — `.prune()`/`.deduplicate()`,
  scoped to `user_profile` only (see discrepancy #1).
- `.to_dict()`/`.from_dict()` — serializes *which stores are enabled* +
  `namespace`/`debug_mode` only; `db`/`model`/`knowledge` must be re-injected
  after `from_dict()` (not serialized — they're runtime objects).
- `.requires_history` — `True` if any configured store's mode is `PROPOSE`
  or `HITL` (both need multi-turn chat history for confirmation flows).
- Every per-store call in `process`/`recall`/`get_tools` is wrapped in
  `try/except` with only a `log_warning` — **failures are swallowed**, which
  is exactly why our own SurrealDb `NotImplementedError`s (open question (b))
  don't crash anything, they just silently do nothing.

### 2.2 Learning modes: ALWAYS / AGENTIC / PROPOSE / HITL

`LearningMode` enum (`agno/learn/config.py:32-44`):

| Mode | Value | Semantics | Extra LLM call? |
|---|---|---|---|
| `ALWAYS` | `"always"` | Automatic extraction after every response, no agent visibility | Yes, always |
| `AGENTIC` | `"agentic"` | Agent gets tools and decides in-line whether/what to save | Only when the model calls the tool |
| `PROPOSE` | `"propose"` | Agent proposes via a tool call, but the save requires separate human confirmation before it lands | Only when proposing; confirmation step is out-of-band |
| `HITL` | `"hitl"` | Per source docstring "Reserved for future use" — no store implements it as a first-class mode today | N/A |

Per-store support (confirmed by both docs and source `__post_init__` mode
warnings):

| Store | ALWAYS | AGENTIC | PROPOSE | HITL |
|---|---|---|---|---|
| `user_profile` | yes (default) | yes (`update_profile` tool) | **falls back to ALWAYS**, `log_warning` | **falls back to ALWAYS**, `log_warning` |
| `user_memory` | yes (default) | yes (`update_user_memory` tool) | not supported, `log_warning` | not supported, `log_warning` |
| `session_context` | **only** mode (default) | not supported, `log_warning`, mode setting ignored | not supported | not supported |
| `entity_memory` | yes (default) | yes (`search_entities`/`create_entity`/`update_entity`/`add_fact`/`update_fact`/`delete_fact`/`add_event`/`add_relationship`) | **falls back to ALWAYS**, `log_warning` | **falls back to ALWAYS**, `log_warning` |
| `learned_knowledge` | yes | yes (default; `search_learnings`/`save_learning`) | yes — genuine soft-approval flow (`save_learning` proposes, needs separate confirm) | not supported — docs say "use PROPOSE mode for soft approval" instead, `log_warning` |
| `decision_log` | yes (default) | yes (`log_decision`/`record_outcome`/`search_decisions`) | not evaluated in source read for this doc (no warning found in `__post_init__`) | not evaluated |

The `PROPOSE→ALWAYS` silent fallback on `user_profile`/`entity_memory` is the
single sharpest gotcha in the whole system — see discrepancy #3 and "How WE
use it" below, since it directly undermines the intended HITL gate on our
`entity_memory` store.

### 2.3 Stores overview

Six built-in `LearningStore` implementations
(`agno/learn/stores/{user_profile,user_memory,session_context,entity_memory,
learned_knowledge,decision_log}.py`), all implementing the
`LearningStore` `Protocol` (`agno/learn/stores/protocol.py:16`):
`learning_type` (str id), `schema` (dataclass type), `recall`/`arecall`,
`process`/`aprocess`, `build_context(data) -> str`, `get_tools`/`aget_tools`,
`was_updated`. `@runtime_checkable` — any object satisfying this shape (duck
typing, not required inheritance) can be dropped into `custom_stores`.

### 2.4 Store: user_profile

`UserProfileStore` (`agno/learn/stores/user_profile.py`). Scope: **user**
(keyed by `user_id` only). Schema `UserProfile`
(`agno/learn/schemas.py:60-171`): `user_id` (required), `name`,
`preferred_name`, plus `agent_id`/`team_id`/`created_at`/`updated_at`
(internal/audit fields, excluded from `get_updateable_fields()`). Persists
forever, updated in place as new info arrives — "exact recall of fixed-schema
fields" per docs, contrasted with `user_memory`'s free-text search.
`UserProfileConfig` knobs (`config.py:53-105`): `enable_update_profile=True`,
`enable_agent_tools=False`, `agent_can_update_profile=True`, plus the shared
`instructions`/`additional_instructions`/`system_message` trio. Retrieval:
`lm.user_profile_store.get(user_id=...)`. Persistence routes through
`db.get_learning`/`upsert_learning`/`delete_learning` (`user_profile.py:636-788`)
— i.e. subject to the SurrealDb gap in open question (b).

### 2.5 Store: user_memory

`UserMemoryStore` (`agno/learn/stores/user_memory.py`). Scope: **user**.
Schema `Memories` (`schemas.py:174-306`): `user_id` (required),
`memories: List[Dict[str, Any]]` (each entry has `id`/`content` and optional
metadata), `agent_id`/`team_id`/timestamps. `MemoriesConfig` is a
**backwards-compat alias for `UserMemoryConfig`** (`config.py:167`:
`MemoriesConfig = UserMemoryConfig`). Config knobs
(`config.py:108-163`): `enable_add_memory=True`, `enable_update_memory=True`,
`enable_delete_memory=True`, `enable_clear_memories=False` (danger flag,
off by default), `enable_agent_tools=False`, `agent_can_update_memories=True`.
Persists via `db.get_learning`/`upsert_learning`/`delete_learning`
(`user_memory.py:469-621`) — same SurrealDb stub gap. This is the
"third, parallel memory system" flagged in open question (a) — it looks
similar to `MemoryManager`'s memories but is a completely separate table row
shape (`learnings` table, `learning_type="user_memory"`, one row per user
holding a *list* of memory dicts) vs `MemoryManager`'s `memories` table (one
row per individual memory).

### 2.6 Store: session_context

`SessionContextStore` (`agno/learn/stores/session_context.py`). Scope:
**session** (keyed by `session_id` only — `user_id`/`agent_id`/`team_id` are
stored as audit columns but don't gate retrieval, so any agent sharing the DB
and `session_id` sees the same context). Schema `SessionContext`
(`schemas.py:308-418`): `session_id` (required), `user_id`, `summary`,
`goal`, `plan: List[str]`, `progress: List[str]`,
`agent_id`/`team_id`/timestamps. **`ALWAYS` is the only supported mode** —
`__post_init__` logs a warning and ignores any other mode setting entirely
(`session_context.py:89-92`). Key behavioral property: extraction *builds on*
the previous context rather than starting fresh each time (explicit design
goal so continuity survives truncated message history) — `extract_and_save()`
fetches `existing_context` first and feeds it back into the system prompt as
a "Previous Context" section the model is told to *integrate*, not replace.
`enable_planning=False` (default) → summary-only `save_session_context(summary)`
tool for the extraction model; `enable_planning=True` →
`save_session_context(summary, goal, plan, progress)` with each unset field
falling back to the previous value rather than being cleared. No agent-facing
tools ever (`get_tools()` always returns `[]` — "system-managed only").
`.print(session_id, raw=False)` gives a formatted debug panel.

### 2.7 Store: entity_memory

`EntityMemoryStore` (`agno/learn/stores/entity_memory.py`). Scope:
**namespace** (`"user"` private-per-user / `"global"` shared / custom string
e.g. `"sales_west"`) — not `user_id`-only. Schema `EntityMemory`
(`schemas.py:505-587`): `entity_id` (required, lowercase+underscores
convention, e.g. `"acme_corp"`), `entity_type` (required — company/project/
person/system/product/...), `name`, `description`,
`properties: Dict[str, str]`, `facts: List[Dict]` (semantic/timeless),
`events: List[Dict]` (episodic/time-bound), `relationships: List[Dict]`
(graph edges to other entities), plus `namespace`/`user_id`/`agent_id`/
`team_id`/timestamps (internal). Config knobs (`config.py:290-370`):
per-operation `enable_create_entity`/`enable_update_entity`/`enable_add_fact`/
`enable_update_fact`/`enable_delete_fact`/`enable_add_event`/
`enable_add_relationship` (all `True` by default), plus
`enable_agent_tools=False` and `agent_can_create_entity`/
`agent_can_update_entity`/`agent_can_search_entities` (all `True` when tools
are on). AGENTIC-mode tools: `search_entities`, `create_entity`,
`update_entity`, `add_fact`, `update_fact`, `delete_fact`, `add_event`,
`add_relationship`. **Supports ALWAYS and AGENTIC only — PROPOSE/HITL both
silently fall back to ALWAYS** (see §2.2, discrepancy #3). Persists via
`db.get_learning`/`get_learnings`/`upsert_learning` (`entity_memory.py:1654-2614`)
— subject to the SurrealDb gap.

### 2.8 Store: learned_knowledge

`LearnedKnowledgeStore` (`agno/learn/stores/learned_knowledge.py`). Scope:
**namespace** (`"user"` / `"global"` default / custom). **Requires a
`Knowledge` instance** (vector store + embedder) — without one, learnings
can't be saved or searched at all; `LearningMachine` auto-enables this store
if you pass `knowledge=` and leave `learned_knowledge` unset
(`machine.py:143-148`). Schema `LearnedKnowledge` (`schemas.py:420-449`):
`title` (required), `learning` (required — the actual insight text),
`context`, `tags: List[str]`, plus `user_id`/`namespace`/`agent_id`/`team_id`/
timestamps (internal). Config knobs (`config.py:228-286`): `mode` default
`AGENTIC` (the only store defaulting to AGENTIC rather than ALWAYS),
`namespace="global"` default, `enable_agent_tools=True` default (also unlike
the others), `agent_can_save=True`, `agent_can_search=True`. **Persistence
does not go through `db` at all** — `save()`/`search()`/`delete()` call
`self.knowledge.insert()` / `.search()` / `.delete_content()` directly
(`learned_knowledge.py:768,941,1054` + async twins). This is why it's the
one store that actually works end-to-end on our SurrealDb-backed operational
store: it never touches `SurrealDb.upsert_learning`. **PROPOSE mode here is
real** — `process()` only auto-extracts in `ALWAYS` mode
(`learned_knowledge.py:186-216`); in `PROPOSE` the `save_learning` tool
proposes a candidate and the store's own `build_context()` for PROPOSE mode
explicitly tells the model "saving requires user approval"
(`learned_knowledge.py:318-321`) — this is a genuine soft-approval UX, not
just a label.

### 2.9 Store: decision_log

`DecisionLogStore` (`agno/learn/stores/decision_log.py`). Scope: **agent**
(keyed by `agent_id`). Schema `DecisionLog` (`schemas.py:896-936+`): `id`,
`decision`, `reasoning`, `decision_type` (tool_selection/response_style/
clarification/escalation/approach/...), `context`, `alternatives`,
`confidence` (0.0-1.0), `outcome`, `outcome_quality` (good/bad/neutral),
`tags`, `session_id`/`user_id`/`agent_id`/`team_id`/timestamps.
`DecisionLogConfig` (`config.py:378-407`): `mode` default `ALWAYS`,
`enable_agent_tools=True` default, `agent_can_save=True`,
`agent_can_search=True`. AGENTIC tools: `log_decision`, `record_outcome`,
`search_decisions`. In `ALWAYS` mode the docs describe it as "automatically
logs all tool calls as decisions." Persists via `db.get_learnings`/
`upsert_learning` (`decision_log.py:733-970`) — subject to the SurrealDb gap.
Not used anywhere in this repo (see open question (c)).

### 2.10 Custom schemas

Every store's `schema` config field accepts a subclass of that store's base
dataclass (`UserProfile`, `Memories`, `SessionContext`, `EntityMemory`,
`LearnedKnowledge`, `DecisionLog`) — extraction/serialization
(`from_dict()`/`to_dict()`, `schemas.py`) is written to auto-handle subclass
fields via `dataclasses.fields()`, so no override of those methods is needed.
Convention: new fields must be `Optional[...] = field(default=None,
metadata={"description": "..."})` — never required, since extraction can
legitimately produce partial data, and the `description` metadata is what the
LLM sees when deciding how to populate the field. Example
(`learning/custom-schemas`):

```python
from dataclasses import dataclass, field
from typing import Optional
from agno.learn.schemas import UserProfile

@dataclass
class CustomerProfile(UserProfile):
    company: Optional[str] = field(default=None, metadata={"description": "Company or organization"})
    plan_tier: Optional[str] = field(default=None, metadata={"description": "Subscription tier: free | pro | enterprise"})

learning = LearningMachine(user_profile=UserProfileConfig(schema=CustomerProfile), ...)
```
Docs show domain examples for SaaS support (company/plan/account_id/
primary_use_case), dev tools (primary_language/framework/experience_years/
editor), entity memory (industry/funding_stage/employee_count), and learned
knowledge (applicable_languages/performance_impact/complexity).

### 2.11 Namespaces

Applies only to `entity_memory` and `learned_knowledge` (the two
"sharing boundary" stores — `user_profile`/`user_memory`/`session_context`/
`decision_log` are hard-scoped to `user_id`/`session_id`/`agent_id` and don't
take a namespace). Three conventions, not enum-enforced (plain `str`):
- `"user"` — private per user (needs `user_id` at call time to scope).
- `"global"` — shared with everyone (the default on both stores).
- Any custom string (e.g. `"engineering"`, `"sales_west"`, our own
  `"platform"`) — explicit grouping, fully caller-defined.
`LearningMachine.namespace` (default `"global"`) is the fallback used
whenever a per-call `namespace=` isn't passed to `recall`/`process`/
`get_tools`/`build_context`, and also seeds each store's own `namespace`
default when constructing it from a bare `True`/config without an explicit
`namespace=`.

### 2.12 agent_can_save / agent_can_search and other agent-tool toggles

Present on `EntityMemoryConfig` (`agent_can_create_entity`,
`agent_can_update_entity`, `agent_can_search_entities`),
`LearnedKnowledgeConfig` (`agent_can_save`, `agent_can_search`), and
`DecisionLogConfig` (`agent_can_save`, `agent_can_search`) — all gated behind
the store's own `enable_agent_tools` flag first (if that's `False`, none of
the `agent_can_*` flags matter — `get_tools()` returns `[]` regardless).
`UserProfileConfig`/`UserMemoryConfig` have analogous single flags
(`agent_can_update_profile`, `agent_can_update_memories`). This two-level gate
(`enable_agent_tools` then per-operation `agent_can_*`) lets you expose a
narrower tool surface than "everything this store can do" even in AGENTIC
mode — e.g. `agent_can_search_entities=True` but
`agent_can_create_entity=False` to let the agent look things up without ever
writing new entities itself.

### 2.13 Custom stores (LearningStore protocol)

Pass any object satisfying the `LearningStore` `Protocol` (§2.3) via
`LearningMachine(custom_stores={"my_store": MyStoreInstance})`
(`machine.py:91,157-160`) — merged into `.stores` verbatim, participates in
`recall`/`process`/`get_tools`/`build_context` exactly like a built-in store.
No registration mechanism beyond the dict key (used as the store's name in
logging and in the `recall()` results dict) — this is the officially
documented extension point for domain-specific learning types the six
built-ins don't cover.

### 2.14 Curator (maintenance: prune, deduplicate)

`Curator` (`agno/learn/curate.py`, `@dataclass(machine: LearningMachine)`),
lazily created via `learning.curator` (`machine.py:695-709`).
`prune(user_id, max_age_days=0, max_count=0)` and
`deduplicate(user_id)` — **both operate exclusively on the `user_profile`
store** and both require `hasattr(profile, "memories")`, which the default
`UserProfile` schema never satisfies (see discrepancy #1 — this is the
single biggest gap between what the docs advertise and what actually runs).
`prune`'s age filter treats unparseable/missing `created_at` as "keep";
count filter keeps the N newest by `created_at`. `deduplicate` does exact
normalized-string matching on `content` (case/whitespace-insensitive per
`_normalize()`), not semantic/embedding dedup. Both return an `int` count of
removed entries and only call `store.save()` if anything was actually
removed.

---

## How WE use it (our-stack annotations)

- `server/agents/providers.py:215-262` (`build_learning()`) constructs a
  **`LearningMachine`** — NOT `MemoryManager` — the sole memory subsystem
  wired into this platform's agents. `MemoryManager`/`SessionSummaryManager`
  are not referenced anywhere in `server/`.
- Backend: `server/core/session.py:129` `get_agno_db()` returns **`SurrealDb`**
  (WS client built lazily from `db_url`/`db_creds`/`db_ns`/`db_db`), passed
  as the `db=` for the whole `LearningMachine`. `build_learning()`'s own
  docstring says "native operational memory on **Postgres** (ADR-0004)" —
  that docstring is stale/inaccurate relative to what the function actually
  wires today (SurrealDb via `get_agno_db()`), worth reconciling separately
  from this doc.
- Configured lanes (`build_learning()`):
  - `user_profile=UserProfileConfig(mode=LearningMode.ALWAYS)`
  - `user_memory=UserMemoryConfig(mode=LearningMode.AGENTIC)`
  - `session_context=SessionContextConfig(mode=LearningMode.ALWAYS, enable_planning=True)`
  - `entity_memory=EntityMemoryConfig(mode=LearningMode.PROPOSE)` — code
    comment says `# HITL`
  - `learned_knowledge=LearnedKnowledgeConfig(mode=LearningMode.PROPOSE,
    knowledge=knowledge, namespace="platform", agent_can_save=True,
    agent_can_search=True)` — code comment says `# HITL`
  - top-level `namespace="platform"`
  - `decision_log` — **not configured** (see open question (c))
- **Everything except `learned_knowledge` is currently a silent no-op in
  production**, per open question (b): `SurrealDb.get_learning` /
  `.upsert_learning` / `.delete_learning` / `.get_learnings`
  (`agno/db/surrealdb/surrealdb.py:1990-2034`) are all
  `raise NotImplementedError("Learning methods not yet implemented for
  SurrealDb")`, and every `LearningStore`/`LearningMachine` call site wraps
  `self.db.*` in `try/except log_warning` — so `user_profile`, `user_memory`,
  `session_context`, and `entity_memory` never persist or recall anything;
  the only observable symptom is a debug/warning-level log line. Only
  `learned_knowledge` works, because it bypasses `db` and writes through the
  `Knowledge` object (Milvus vectors + Postgres `contents_db`, per
  `create_knowledge()` in `server/core/session.py`).
- **The `entity_memory` HITL intent is doubly moot right now**: even setting
  aside the SurrealDb gap, `EntityMemoryConfig(mode=LearningMode.PROPOSE)`
  itself silently degrades to full `ALWAYS` (auto-write, no human gate) per
  `agno/learn/stores/entity_memory.py:91-93` — agno's own `EntityMemoryStore`
  doesn't support `PROPOSE` at all (confirmed by both source and the
  `learning/learning-modes` docs page, which lists Entity Memory's supported
  modes as "Always, Agentic" only). So the `# HITL` comment on our
  `entity_memory` line does not describe real behavior even independent of
  the DB question — fix requires either dropping the PROPOSE setting (it's
  not doing what the comment claims) or building a custom store/wrapper that
  actually gates entity-memory writes on human confirmation.
- `learned_knowledge`'s `PROPOSE` mode, by contrast, **is genuine** —
  `LearnedKnowledgeStore` is one of only two stores where PROPOSE is a
  first-class supported mode (the other being none, structurally — it's the
  *only* store PROPOSE is designed for per the docs), so that HITL gate is
  real and functioning as intended today.
- Practical next step if `user_profile`/`user_memory`/`session_context`/
  `entity_memory` need to actually work: either (a) implement
  `get_learning`/`upsert_learning`/`delete_learning`/`get_learnings` on our
  `SurrealDb` usage (upstream contribution or a local subclass/monkeypatch —
  the `learnings` table shape needed is fully specified by
  `agno/db/postgres/postgres.py:4374+`'s implementation to mirror), or (b)
  point `LearningMachine.db` at `PostgresDb` instead of `SurrealDb` for the
  learning-specific tables while keeping SurrealDb for whatever else it's
  used for, or (c) accept that these four stores are inert until one of the
  above lands, and treat `learned_knowledge` as the only production-ready
  lane today.

---

## Coverage

### memory (23 pages — 20 from owner's checklist + 3 found via live sitemap enumeration)
- [x] https://docs.agno.com/memory/agent/agent-with-memory
- [x] https://docs.agno.com/memory/agent/agentic-memory
- [x] https://docs.agno.com/memory/agent/agents-share-memory
- [x] https://docs.agno.com/memory/agent/custom-memory-manager
- [x] https://docs.agno.com/memory/agent/multi-user-multi-session-chat
- [x] https://docs.agno.com/memory/agent/multi-user-multi-session-chat-concurrent
- [x] https://docs.agno.com/memory/agent/overview
- [x] https://docs.agno.com/memory/agent/share-memory-and-history-between-agents
- [x] https://docs.agno.com/memory/best-practices
- [x] https://docs.agno.com/memory/overview
- [x] https://docs.agno.com/memory/team/overview
- [x] https://docs.agno.com/memory/team/team-with-agentic-memory
- [x] https://docs.agno.com/memory/team/team-with-memory-manager
- [x] https://docs.agno.com/memory/working-with-memories/custom-memory-instructions
- [x] https://docs.agno.com/memory/working-with-memories/memory-creation
- [x] https://docs.agno.com/memory/working-with-memories/memory-optimization
- [x] https://docs.agno.com/memory/working-with-memories/overview
- [x] https://docs.agno.com/memory/working-with-memories/postgres-memory
- [x] https://docs.agno.com/memory/working-with-memories/sqlite-memory
- [x] https://docs.agno.com/memory/working-with-memories/standalone-memory
- [x] https://docs.agno.com/memory/working-with-memories/memory-search **(extra — beyond checklist)**
- [x] https://docs.agno.com/memory/working-with-memories/mongodb-memory **(extra — beyond checklist)**
- [x] https://docs.agno.com/memory/working-with-memories/redis-memory **(extra — beyond checklist)**

### learning (11 pages — 10 from owner's checklist + 1 found via live sitemap enumeration)
- [x] https://docs.agno.com/learning/custom-schemas
- [x] https://docs.agno.com/learning/learning-modes
- [x] https://docs.agno.com/learning/overview
- [x] https://docs.agno.com/learning/stores/decision-log
- [x] https://docs.agno.com/learning/stores/entity-memory
- [x] https://docs.agno.com/learning/stores/intro
- [x] https://docs.agno.com/learning/stores/learned-knowledge
- [x] https://docs.agno.com/learning/stores/session-context
- [x] https://docs.agno.com/learning/stores/user-memory
- [x] https://docs.agno.com/learning/stores/user-profile
- [x] https://docs.agno.com/learning/quickstart **(extra — beyond checklist)**

### integrations (1 page — matches checklist; sitemap confirms it's the only page under integrations/memory/)
- [x] https://docs.agno.com/integrations/memory/memori

### Method note
The Agno docs MCP server (`claude.ai agno`) disconnected partway through this
task and never reconnected despite retries. All 35 pages above were instead
fetched directly via `WebFetch` against `docs.agno.com`. To satisfy the scope
update ("the checklist is a floor, not a ceiling — enumerate the full
`/memory/`, `/learning/`, `/integrations/memory/` doc trees"), the raw
`sitemap.xml` was pulled via `curl` and grepped for `/memory/`, `/learning/`,
`/learnings/` (bypassing WebFetch's own summarizing model, which was
observed to silently drop entries on the large sitemap file). This confirmed
the three trees above are now complete — no other guide pages exist under
those prefixes as of 2026-07-11. (Excluded as out-of-scope by prefix, not
fetched: `/api-reference/memory/*`, `/api-reference/learnings/*`,
`/reference-api/schema/{memory,learnings}/*`, `/reference/memory/memory`,
`/examples/**` — these are REST-API-reference and cookbook-example trees,
distinct from the `/memory/` and `/learning/` prose-guide trees the task
scoped to; also noted but out of scope: `/agent-os/learnings/manage-learnings`
and `/agent-os/usage/client/memory-operations`, which are AgentOS-admin docs
under the `/agent-os/` prefix, not `/memory/` or `/learning/`.)
