# n8n Capability Assessment — Evidence Platform Fit

> _Byline: Research agent · Opus · 2026-08-25_

**Scope.** What n8n can and cannot do for this platform, read out of n8n's own documentation
(docs.n8n.io, accessed 2026-08-25) plus the live n8n MCP server's own reference material.
Every claim below is sourced. Where I could not verify something from the docs, I say so.

**Version context.** n8n's current major line is **2.x**. **n8n 3.0 is scheduled for October
2026** and removes a meaningful amount of what exists today. That timing matters for anything
built between now and then.

---

## 1. Executive summary — answer first

### What n8n should own in this stack

| Role | Why n8n is the right tool |
| --- | --- |
| **File-arrival watcher** for the drop directory and the R2 bucket | It has a real filesystem trigger and a durable, restart-surviving scheduler with per-poll cursors. It hands off to Temporal and gets out of the way. |
| **Human-approval surface** (the screen a person clicks Approve on) | Slack / Telegram / Discord / Teams / WhatsApp / Email / web-form approval widgets already exist and are configured by dropdown, not code. |
| **Utility integrations exposed as MCP tools** | The MCP Server Trigger turns any workflow into an MCP tool endpoint with bearer/header auth. Cheap way to give your agents Gmail, Drive, Slack, etc. without writing clients. |
| **Non-custody parsing and triage** — the "I have a pile of PDFs/CSVs/spreadsheets and want structured rows" work | Extract From File covers 10 formats out of the box; Information Extractor turns text into a JSON-schema-shaped object with no code. |
| **Change detection** (deferred workstream) | Remove Duplicates has a native "remove items already processed in previous executions" mode, plus built-in Data Tables to hold cursors. |
| **Agent playground** — assistants that talk to people in Slack, run on a schedule, and call your tools | First-class Agents are a real product now: persisted, versioned, publishable, with per-tool human approval. |

### What n8n should NOT own

| Role | Why not |
| --- | --- |
| **The custody path** — hashing, the write-once evidence spine, sequencing, promotion gating | n8n's durability model is an execution row in its own Postgres, not a durable workflow history. A restart mid-flight, a queue-mode stall, or a webhook timeout is a silent gap. Temporal already owns this and should keep owning it. |
| **The bitemporal evidence store or its query layer** | n8n has no concept of valid-time vs knowledge-time. Its vector filters can approximate a timestamp range only if you store timestamps as plain numbers (see §5). This is a downgrade from what PG18 + SurrealDB give you. |
| **Your custom parsers** (SMS XML, chat-export ZIPs, iMessage HTML) | n8n can *unzip* and *convert XML to JSON*. It cannot reconstruct a message thread model. Keep the Python; let n8n trigger it. |
| **Optimized extraction / classification programs** | Information Extractor is a single prompt with a schema attached. DSPy compiles and optimizes. Different tools; don't confuse them. |
| **Long-running orchestration with real waits** | An n8n wait shorter than 65 seconds never touches the database at all — it lives in process memory and dies with a restart. |

### The one-line verdict

> **n8n is an excellent edge and interface layer for this platform, and a poor durable core.**
> Put it at the boundaries — where files arrive, where humans click, where tools get exposed —
> and keep Temporal, PG18, and your Python in the middle.

### Two findings the owner will want up front

1. **First-class n8n Agents cannot attach Weaviate.** The Agent config schema supports exactly four
   native vector stores: Pinecone, Qdrant, Supabase, and Postgres. Weaviate is not among them.
   You *can* reach Weaviate from an Agent, but only indirectly — by wrapping a Weaviate workflow as
   an Agent tool, or exposing it over MCP. (Source: n8n Agent config schema, `vectorStores`, served
   by the live `n8n://agents/reference`.) The *workflow* AI Agent node has a full Weaviate node with
   hybrid search; the *Agent artifact* does not.
2. **n8n's LangChain foundation does not give you LangGraph portability.** n8n wraps LangChain **JS**
   at the node level. Concepts transfer; code does not. See §3 for the full read on the LangGraph
   question.

---

## 2. First-class n8n Agents (the persisted Agent artifact)

### What it actually is

An **Agent** in n8n is now a saved object that lives beside your workflows in a project — not a node
on a canvas. It has its own builder screen, its own draft/published lifecycle, and its own version
history. n8n's own guidance to MCP clients is explicit: *"An n8n Agent is a first-class persisted
resource… An AI Agent node is a node inside a workflow."*

**Source:** [Build and manage agents](https://docs.n8n.io/build/build-and-manage-agents) ·
[n8n Agent management reference](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/mcp-server-tools-reference)

### The parts of an Agent

- **Model + credential + instructions** — the three required fields. Nothing runs without them.
- **Tools** — three kinds:
  - *Custom tool*: TypeScript source you supply. Only two imports are allowed: `@n8n/agents` and
    `zod`. The default export must be a `Tool` builder chain with a description, a Zod input schema,
    and a handler.
  - *Workflow tool*: point at one of your n8n workflows by name or ID.
  - *Node tool*: any n8n integration node, configured with parameters and a credential.
- **Skills** — a bundle of instructions plus the subset of tools that skill is allowed to use. The
  agent picks a skill from its description. (Same shape as a Claude skill.)
- **Sub-agents** — other *published* agents in the same project, each with a "use when" description.
  You can cap how many run in parallel (`maxChildren`, default 10, max 20).
- **Tasks / Schedules** — hourly, daily, weekly, monthly, or a custom cron. Schedules only run
  against the **published** version.
- **Channels** — Slack, Telegram, and Linear. Each needs a public `WEBHOOK_URL` on the instance.
- **Knowledge base** — uploaded files the agent can search. Supported types: **csv, pdf, markdown,
  txt**. On self-hosted this requires a Daytona sandbox and is flagged Preview.
- **MCP servers** — up to 20 external MCP catalogs per agent, with per-server tool filtering
  (allow-list or exclude-list) and per-server approval policy.
- **Vector stores** — up to 20, but **only** Pinecone, Qdrant, Supabase, or Postgres.

### Memory

Three distinct layers, all configured on the agent:

- **Session memory** — the current conversation. On by default, no setup.
- **Episodic memory** — recalls context from *earlier* sessions. Requires a credential (n8n's docs
  say OpenAI; the config schema allows a `managed` credential or a named one). Tunable: `topK`,
  `maxEntriesPerRun`, separate extractor and reflector models.
- **Observational memory** — a background observer/reflector pair with token thresholds and a render
  budget. This is the closest thing n8n has to a learning loop.

### Human-in-the-loop / approvals

- Every tool entry takes a `requireApproval` boolean.
- MCP servers take an approval policy of either `global` (everything needs approval) or `selected`
  (a named list of tools).
- When an agent hits a gated tool it **pauses** and asks in the chat. The person clicks Approve or
  Reject and the agent resumes from where it stopped.
- n8n's own reference is emphatic that approvals are per-decision and human-only: *"Every approval
  decision must come from the human; resume each returned approval individually."*

### Versioning and lifecycle

- Draft ↔ Published. The draft autosaves; the published snapshot is what actually runs.
- Every publish adds an entry to publish history. You can revert the draft to any old version, or
  republish an old version directly without touching the draft.
- Unpublish takes it offline but keeps the draft editable.

### How agents are called

1. The chat panel in the builder.
2. A connected channel (Slack / Telegram / Linear).
3. A schedule.
4. From inside a workflow — either create an agent inline as a node, or send a message to an already
   published agent.
5. **Over MCP** — n8n's instance-level MCP server exposes agent management tools
   (`create_agent`, `mutate_agent`, `validate_agent`, `call_agent`, `publish_agent`,
   `list_agent_versions`, `revert_agent`, and more). These require n8n **2.34.0+** with both the
   workflow builder and the agents module enabled. Note: every agent tool except `search_agents`
   only operates on agents where `availableInMCP` is set to true.

### Maturity: **Preview / Beta. Do not build load-bearing work on it yet.**

n8n's own warnings, verbatim in substance:

- Agents are **in Preview**; behavior may change.
- Self-hosted agents need **n8n 2.32.3 (Beta)** or later, enabled via `N8N_ENABLED_MODULES=agents`.
- **"Agents aren't ready for self-hosted Enterprise yet."**
- **"Queue mode isn't supported for agents yet, and connecting channels (such as Telegram) can
  fail. Run agents in regular mode for now."**
- Knowledge bases on self-hosted are separately in Preview and need a Daytona sandbox.

### Fit verdict: **Adopt for internal assistants. Do not put on the evidence path.**

- **Good fit:** a "case desk" assistant reachable in Slack that answers questions, runs a nightly
  digest on a schedule, and calls your read-only tools. Per-tool approval gives you a real safety
  gate.
- **Bad fit:** anything that writes to the evidence spine. Preview status plus "queue mode not
  supported" plus "channels can fail" is not a foundation for chain-of-custody work.
- **Blocker to know about:** no Weaviate. If you want an Agent searching your semantic index, you
  will wrap it — either as a workflow tool (a workflow containing the Weaviate node) or as an MCP
  tool. Both work; both add a hop.

---

## 3. AI Agent node + the LangChain relationship

### What exists on the canvas

The **AI Agent node** (`@n8n/n8n-nodes-langchain.agent`) is a root node you wire sub-nodes into:
a chat model, memory, tools, and optionally an output parser.

**Agent patterns.** Historically n8n offered several (Tools, Conversational, ReAct, SQL,
OpenAI Functions, Plan-and-Execute). **All of these except Tools Agent are dead or dying:**
Conversational Agent was deprecated in 1.82.0, and **n8n 3.0 removes version 1 of the AI Agent node
entirely**, taking SQL / Conversational / OpenAI Functions / Plan-and-Execute / ReAct with it.
The migration note tells SQL Agent users to use a Postgres or MySQL *tool* sub-node with a modern
agent instead.

> **Practical read:** there is now exactly **one** agent pattern in n8n — tool-calling. If you were
> hoping for a plan-and-execute or graph-shaped agent inside n8n, that door is closing.

**Source:** [Tools Agent](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/tools-agent) ·
[v3.0 Breaking changes](https://docs.n8n.io/changelog/v30-breaking-changes)

### Tools Agent capabilities

- Implements **LangChain JS's tool-calling interface**, describing tools and their schemas to the
  model.
- Supported chat models for this agent: OpenAI, Groq, Mistral Cloud, Anthropic, Azure OpenAI.
- **`$fromAI()`** lets the model fill in a tool's parameters at call time, so you don't hand-wire
  every field.
- **Max Iterations** defaults to 10.
- **Return Intermediate Steps** exposes the agent's tool-call trace in the output.
- **Tracing Metadata** — arbitrary key/value pairs attached to tracing events (LangSmith).
- **Streaming** on by default; requires a Chat Trigger or a Webhook set to Streaming response mode.
- **Human review for tool calls** — a Tools Panel "Human review" section; gated tools pause the
  workflow and send an approval request over Chat, Slack, Telegram, and others.

### Memory sub-nodes

Simple Memory (in-session window), Redis Chat Memory, Postgres Chat Memory, Motorhead, Xata, Zep.
Plus a **Chat Memory Manager** node for manual memory surgery — trimming, or injecting synthetic
"user" messages to seed context.

**Important limitation, stated plainly in n8n's docs:** *chains* in n8n **do not support memory at
all**. If you need multi-turn, you must use an agent. And for the Tools Agent used with a Chat
Trigger, "memory doesn't persist between sessions" unless you attach a persistent memory sub-node.

### Structured output

Three output parsers: **Structured** (JSON Schema or JSON-example driven), **Auto-fixing** (feeds
schema errors back to the model to repair), and **Item List**.

> This is directly relevant to the platform's existing rule that some models cannot emit
> schema-conformant JSON. n8n's Auto-fixing parser is a retry-with-error-feedback loop, not a
> constrained-decoding guarantee. It reduces failures; it does not eliminate them.

### Multi-agent on one canvas

The **AI Agent Tool** node lets one agent supervise others in a **single execution**, on one canvas
— an alternative to sub-workflows. n8n's own caveat: *"The orchestrating agent does not pass full
execution context by default. Any necessary context must be included in the prompt."*

### The LangChain / LangGraph question — read this carefully

**What n8n actually is:** a set of nodes that wrap **LangChain JS** primitives. The docs say
outright: *"You don't need to know LangChain to use n8n."* There is a **LangChain Code node** that
lets you write LangChain JS inside a node, with n8n-specific helpers (`this.getInputConnectionData`,
`this.addOutputData`, `this.getExecutionCancelSignal`) — and n8n explicitly notes this replaces the
"cancelling a running LLMChain" code you'd write in a normal LangChain app.

**What that gives you:**

- ✅ **Shared vocabulary.** Tools, retrievers, splitters, document loaders, output parsers, memory,
  vector stores — the same nouns as LangChain. Anyone fluent in one reads the other.
- ✅ **Interop through MCP.** An n8n workflow or agent exposed as an MCP tool can be called by a
  LangGraph app, and vice versa. This is real and it is the strongest link.
- ✅ **A cheap prototyping surface.** Try a retrieval strategy visually in an afternoon, then port
  the shape into code.

**What it does NOT give you:**

- ❌ **No code portability.** An n8n workflow is JSON node config. It does not compile to, export
  to, or import from LangGraph. Nothing lifts across.
- ❌ **JS, not Python.** LangGraph's centre of gravity — and this platform's — is Python. Even the
  LangChain Code node is JavaScript.
- ❌ **No graph, no state, no checkpointer.** LangGraph's whole value proposition is a stateful
  graph with a durable checkpointer, conditional edges, interrupts, and time travel. n8n has none of
  it. It has a linear/branching canvas and a single-shape tool-calling loop.
- ❌ **The one advanced agent shape n8n had, it is deleting.** Plan-and-Execute goes away in 3.0.

**Verdict on "does n8n strengthen the LangGraph case?"**

> **Mildly, and only sideways.** n8n does not make LangGraph a better choice; it makes the
> *concepts* familiar and makes MCP the join between them. If LangGraph comes back on the table,
> justify it on its own merits — durable state, interrupts, conditional graphs — not on n8n
> adjacency. And note the real overlap risk: **LangGraph's checkpointer and Temporal's durable
> history solve the same problem.** Running both means owning two sources of truth for "where is
> this workflow." That is the question worth answering before adopting LangGraph, and n8n has
> nothing to say about it.

---

## 4. Workflow building in depth — beyond drag and drop

The owner's instinct ("it's drag and drop, it's easy for me to understand") is right, and there is
also a serious code path underneath. Both are real.

### 4a. The Workflow SDK — building workflows from code

n8n ships **`@n8n/workflow-sdk`**, a TypeScript DSL. This is what the `create_workflow_from_code`
MCP tool consumes. The shape:

```javascript
import { workflow, node, trigger, ifElse, switchCase, merge,
         splitInBatches, languageModel, tool, expr, fromAi } from '@n8n/workflow-sdk';

const start = trigger({ type: 'n8n-nodes-base.scheduleTrigger', version: 1.3, config: {...} });
const fetch = node({ type: 'n8n-nodes-base.httpRequest', version: 4.3, config: {...} });

export default workflow('id', 'name').add(start).to(fetch);
```

Builders exist for every structural concern: `ifElse(...).onTrue(...).onFalse(...)`,
`switchCase(...).onCase(n, ...)`, `merge(...).input(0)/.input(1)`,
`splitInBatches(...).onEachBatch(...).onDone(...)`, and sub-node attachment via
`config.subnodes = { model, tools: [...], memory, outputParser }`.

**Why this matters for you:** workflows become reviewable text. You can generate them, diff them,
and put them in git. That answers the usual "no-code tools are unauditable" objection.

**Source:** live n8n MCP server, `get_workflow_sdk_reference`.

### 4b. The execution model — the thing that bites people

n8n passes **arrays of items** between nodes, and most nodes run **once per item**. Consequences,
straight out of n8n's own SDK guidance:

- **Item multiplication.** If node A emits 10 items and you chain node B after it, B runs 10 times.
  Chain a third and you get 100. The fix is `executeOnce: true` on the node, or parallel branches
  into a Merge node.
- **Zero items skip the rest of the chain.** This is usually correct — a poll with nothing new
  should quietly do nothing. n8n explicitly warns against papering over it with
  `alwaysOutputData: true`, calling it *"a footgun"* that fabricates a `{json:{}}` item downstream.
- **Sub-nodes are different.** In sub-nodes (models, memory, retrievers, splitters, loaders), an
  expression **always resolves to the first item**, never per-item. This warning is repeated on
  nearly every AI sub-node page. **It is the single most common silent bug in n8n AI pipelines.**
- **Code node** has two modes: *Run Once for All Items* and *Run Once for Each Item*.
- **Item linking** (`pairedItem`, `$('Node Name').item`) is how you trace an output item back to its
  source. The old `$getPairedItem` helper is removed in 3.0.

### 4c. Sub-workflows

- **Execute Sub-workflow** node calls another workflow by ID, by URL, by local file, or with inline
  JSON. Executions cross-link both ways in the UI.
- **Convert to sub-workflow** (Alt+X) extracts a selected node range into its own workflow
  automatically, subject to structural rules (single entry, single exit, no triggers in selection).
- **`callerPolicy`** on workflow settings controls who may call it: `any`, `none`,
  `workflowsFromSameOwner` (the default), or an explicit allow-list of workflow IDs.
- **Behavior change in 2.0 worth knowing:** previously, if a sub-workflow entered a waiting state
  (a Wait node over 65s, a webhook, a form, a human-in-the-loop node), the parent got the
  sub-workflow's *input* back as its output. **From 2.0 the parent receives the child's actual
  result.** This is what makes "put the approval in a sub-workflow and act on the answer in the
  parent" viable at all.

### 4d. Error handling

- **Error workflow** — set per workflow in Settings. It fires on failure and receives a structured
  payload: execution id and URL, the error message and stack, `lastNodeExecuted`, workflow id/name.
  A different, thinner payload arrives if the *trigger itself* failed to activate.
- **Error Trigger** node is the entry point of that error workflow.
- **Per-node**: `retryOnFail`, `maxTries`, `waitBetweenTries`, `onError` (the older
  `continueOnFail` is deprecated).
- **Stop And Error** node to throw deliberately, optionally with a structured error object.
- **Retry from the UI**: re-run a failed execution either against the currently saved workflow or
  against the original workflow definition.
- n8n now emails the workflow owner the first time a workflow fails in production on an instance
  with no error workflow configured.

### 4e. Queue mode and scaling

- **Queue mode** = Redis-backed job queue (Bull), main instance(s) plus worker processes.
- Worker concurrency via `--concurrency` or `N8N_CONCURRENCY_PRODUCTION_LIMIT`. n8n **recommends 5
  or higher** — low concurrency across many workers exhausts the database connection pool.
- **Multi-main setup requires an Enterprise licence** (`N8N_MULTI_MAIN_SETUP_ENABLED`).
- **Webhook response relay limit:** in queue mode the worker runs the execution but the client is
  connected to the main/webhook instance, so the response travels back through Redis. Default cap is
  **64 MiB** (`N8N_WEBHOOK_RESPONSE_RELAY_SIZE_MAX`), and Redis holds several copies in flight —
  budget ~1.5× per response. From 2.34 you can offload bodies above that to binary storage
  (`N8N_WEBHOOK_RESPONSE_RELAY_OFFLOAD_ENABLED`), **but an MCP tool result cannot be offloaded** —
  an oversized one reaches the MCP client as a tool error.
- **Bull's stalled-job retry was removed in 2.0.** n8n no longer auto-retries stalled jobs, and its
  own migration note says to implement your own retry logic. *This is a durability gap you should
  read as confirmation that Temporal keeps the sequencing job.*
- Prometheus metrics exist for queue depth, active/completed/failed jobs, and poll-trigger health.

### 4f. Versioning and history

- Workflows have **draft** and **published** versions, same as agents. The published version is what
  runs in production.
- **Version history** in the UI: restore, clone to a new workflow, open in a new tab to compare,
  download as JSON, and **name a version** (named versions are protected from pruning; naming is a
  Cloud Pro / Enterprise feature).
- **Public API**: `GET /workflows/{id}/history` returns version IDs and metadata.
- **Pruning** controlled by `N8N_WORKFLOW_HISTORY_PRUNE_TIME` (hours; `-1` keeps everything).
- **CLI**: `n8n export:workflow --published` exports the live version rather than the draft.
- **Source control / environments** (Enterprise): git-backed push/pull with per-workflow diffs.
  Note that **Data Table *schemas* sync but row data does not**, and a pull that removes columns
  deletes that column's data irreversibly.
- **n8n Packages** (`.n8np`) bundle workflows with dependency resolution — sub-workflows and error
  workflows count as dependencies and the export fails by default if you omit them.

### Fit verdict: **Serious pipelines are buildable. Durable pipelines are not.**

The SDK, sub-workflows, error workflows, version history, and git source control are genuinely
production-grade authoring tooling. What's missing is the thing Temporal provides: a guaranteed,
replayable execution history that survives process death. Queue mode gets you throughput, not
durability — and n8n itself removed its stalled-job retry.

---

## 5. Retrieval methods

### 5a. What vector stores exist

Weaviate, Milvus, Qdrant, Pinecone, Supabase, Postgres (PGVector), Redis, Chroma (self-hosted or
Chroma Cloud, added recently), Azure AI Search, MongoDB Atlas, Zep, and an in-process
**Simple Vector Store**.

**Every vector store node has four modes:**

1. **Get Many** — plain search, returns documents to the workflow.
2. **Insert Documents** — write path.
3. **Retrieve Documents (As Vector Store for Chain/Tool)** — plugs into a retriever or a chain.
4. **Retrieve Documents (As Tool for AI Agent)** — the agent calls it directly, with a description
   and a result limit.

### 5b. The Weaviate node in detail — this is the one that matters for you

n8n's Weaviate node is unusually complete. Full option list from the docs:

**Hybrid search** (added in a recent release, documented on the node page):

| Option | What it does |
| --- | --- |
| **Hybrid: Query Text** | Supplies the keyword half of the search. Presence of this turns on hybrid. |
| **Hybrid: Alpha** | Weighting. `1.0` = pure vector, `0.0` = pure keyword, default `0.5`. |
| **Hybrid: Fusion Type** | `Relative Score` or `Ranked` fusion. |
| **Hybrid: Query Properties** | Which fields the keyword half searches, with optional weights — e.g. `"question^2,answer"`. |
| **Hybrid: Auto Cut Limit** | Trims results at a sudden score drop instead of a fixed `k`. |
| **Hybrid: Max Vector Distance** | Hard ceiling on the vector component's distance. |
| **Hybrid: Explain Score** | Returns the fused-score explanation. Useful for tuning and for showing your work. |

**Metadata filtering (Search Filters).** Weaviate's conditional-filter JSON, with `AND` and `OR`
nesting. Supported operators:

`equal`, `like`, `containsAny`, `containsAll`, `greaterThan`, `lessThan`, `isNull`,
`withinGeoRange`.

> **⚠️ Bitemporal warning — read this one.** `greaterThan` and `lessThan` require a **`valueNumber`**.
> There is no date/timestamp operator in the n8n Weaviate filter surface. If you want to filter by
> `occurred_at` or `knowledge_time` from an n8n retrieval, **you must store those timestamps as
> numeric epoch values in the chunk metadata at ingest time.** An ISO-8601 string will only support
> `equal` and `like`. Decide this before you index, because retro-fitting metadata means re-ingesting.
>
> Also note: n8n gives you **one** filter expression per query. It has no notion of
> "as-of" semantics — you would express a knowledge-horizon query as
> `knowledge_time_epoch <= X AND occurred_at_epoch <= X` by hand, every time.

**Other Weaviate options:**

- **Metadata Keys** — projection. Return only the named properties, reducing payload size.
- **Tenant Name** — Weaviate multi-tenancy. n8n's hard caveat: *"You must pass a tenant name at
  first ingestion to enable multitenancy for a collection. You can't enable or disable multitenancy
  after creation."* If you ever want per-case or per-matter isolation, **decide at first write.**
- **Rerank Results** — toggle; requires a reranker node attached.
- **Text Key** — which document field holds the embedded text.
- **Embedding Batch Size** — default 200 documents per embed call.
- **Init / Insert / Query Timeouts**, **Skip Init Checks**, **gRPC Proxy**.
- **Clear Data** — wipes the collection or tenant before insert. *Sharp edge; keep it off.*

**Source:** [Weaviate Vector Store](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.vectorstoreweaviate)

### 5c. Retrievers

**MultiQuery Retriever** — the one the owner was reading about.

- **What it does:** takes the user's question, asks an LLM to rewrite it into **N different
  phrasings from different angles**, runs all N against the vector store, and unions the results.
- **Why it works:** vector search is brittle to phrasing. A witness statement indexed with the word
  "shoved" won't match a query for "assaulted" on embedding similarity alone. MultiQuery hedges
  across vocabularies.
- **Configuration in n8n:** exactly **one** option — **Query Count** (how many variants to
  generate). That's it. It wraps LangChain JS's `MultiQueryRetriever`.
- **The cost:** one extra LLM call per query to generate the variants, then N searches instead of 1.
  Latency and token spend both go up roughly linearly with Query Count.
- **Honest assessment for this platform:** MultiQuery is a **recall** improvement, and recall is
  exactly what matters in evidence discovery — missing a relevant message is worse than surfacing an
  irrelevant one. It pairs naturally with a reranker to claw back precision. But n8n's version is a
  black box with a single knob; if you need control over *how* the variants are generated (domain
  vocabulary, entity substitution, date-range expansion), you will outgrow it fast. It is the right
  thing to **prototype** with and the wrong thing to **ship** as the final retrieval strategy.

**Contextual Compression Retriever** — post-filters retrieved documents against the query, stripping
irrelevant passages before they hit the model's context. n8n exposes **no options at all** on this
node; it is entirely LangChain-default behavior. Useful for token economy; not tunable.

**Vector Store Retriever** — the plain adapter that makes a vector store look like a retriever.

**Workflow Retriever** — ⭐ **this is your escape hatch.** It lets an entire n8n workflow act as a
retriever. Point it at a workflow by ID or paste workflow JSON. That means you can implement
*any* retrieval logic — a bitemporal SQL query against PG18, a hybrid Weaviate call with
hand-built filters, a fan-out across Weaviate + Postgres + SurrealDB with custom fusion — and the
agent just sees "a retriever." **If n8n ever needs to query your evidence spine intelligently, this
is the node that does it.**

### 5d. Reranking

- **Reranker Cohere** is the documented reranker node.
- Vector store nodes expose a **Rerank Results** toggle that requires an attached reranker, valid in
  Get Many, Retrieve-for-Chain/Tool, and Retrieve-as-Tool modes.
- ⚠️ The reranker inventory is thin. Cohere is what's documented. If your reranking strategy is
  NIM-hosted or local, you'd reach it via HTTP Request inside a Workflow Retriever, not a native node.

### 5e. How retrieval composes with agents

Four documented patterns, in increasing indirection:

1. **Vector store → agent tool connector.** Simplest. The agent searches directly. Set the `Limit`
   and turn on `Include Metadata`.
2. **Vector store → Vector Store Question Answer Tool → agent.** A cheaper model summarizes the
   retrieved chunks first, and only the summary reaches the expensive agent. n8n calls this out
   explicitly as a token-saving trick.
3. **Vector store → retriever → Question and Answer Chain.** No agent. Deterministic Q&A over
   documents. Remember: **chains have no memory.**
4. **Workflow Retriever → chain or agent.** Arbitrary custom retrieval.

You can stack these: Weaviate hybrid → MultiQuery → Contextual Compression → Reranker → agent. Each
layer is a sub-node connection on the canvas.

### 5f. Retrieval gotchas

- **n8n only supports text embeddings.** No image or multimodal vectors.
- **Sub-node expression resolution.** Retrievers and vector stores are sub-nodes. An expression in
  one resolves to the **first input item only**. Batch retrieval over many queries does not work the
  way you'd expect.
- **Metadata is set at ingest, by the document loader.** You cannot filter on what you didn't store.
- **Filter dialects differ per store.** Most stores (Qdrant, Milvus, Supabase, Chroma, Zep) offer a
  simple key/value **AND-only** metadata filter. Weaviate is the exception with real operators and
  AND/OR. **Your existing Weaviate choice is the *best-supported* one in n8n for filtered retrieval.**

### Fit verdict: **Strong prototyping surface; keep production retrieval in code.**

- ✅ **Adopt:** Weaviate hybrid search from n8n for exploratory and non-custody search. The hybrid
  knobs (alpha, fusion, property weights, autocut) are genuinely good and hard to beat for
  time-to-answer.
- ✅ **Adopt:** MultiQuery + reranker as an *experiment* to measure recall lift before you commit
  engineering time to the same idea in Python.
- ⚠️ **Constrain:** anything bitemporal. Store epoch numbers in metadata now if you want any chance
  of range filtering from n8n later.
- ❌ **Don't:** make n8n the retrieval layer for the evidence spine. Use the Workflow Retriever to
  call *your* code instead.

---

## 6. Ingest tools

### 6a. The file-format toolbox

**Extract From File** node — one node, ten operations:

| Operation | Notes |
| --- | --- |
| Extract From CSV | Tabulated data. |
| Extract From HTML | Fields from web-page HTML. |
| Extract From JSON | JSON out of a binary file. |
| Extract From ICS | iCalendar. |
| Extract From ODS | OpenDocument spreadsheet. |
| Extract From PDF | Text from PDF. |
| Extract From RTF | Rich Text. |
| Extract From Text File | Plain text. |
| Extract From XLS / XLSX | Excel, both generations. |
| Move File to Base64 String | Binary → text-safe. |

**Notably absent: XML.** XML is a separate node (`n8n-nodes-base.xml`) that does XML↔JSON
conversion with options for CDATA, surrogate chars, headless output, and root element naming.

**HTML** node — CSS-selector extraction from JSON or a binary `.html` file. Also available inside
the HTTP Request node as response optimization (`Selector (CSS)`, `Return Only Content`,
`Elements To Omit`, `Truncate Response`).

**Compression** node — Zip, Gzip, Tar, Tar+Gzip, compress and decompress, multi-file.

**Convert to File** / **Read/Write Files from Disk** round out the binary handling.

### 6b. Document loaders, splitters, embeddings

**Default Data Loader** — the bridge between n8n items and vector-store documents.

- **Type of Data:** Binary or JSON.
- **Mode:** *Load All Input Data*, or *Load Specific Data* — the latter lets you build a custom
  document from a mix of literal text and expressions. **This is more flexible than it looks:** you
  can hand-assemble a document string with exactly the fields and framing you want.
- **Data Format:** pick a MIME type or auto-detect. If you pin a format and the file's MIME doesn't
  match, **the node errors**. Auto-detect falls back to plain text.
- **Metadata** — arbitrary key/value pairs attached to each chunk. **This is the only thing your
  retrieval filters can ever match on.** Set it deliberately at ingest.
- **Text Splitting:** *Simple* (Recursive Character, chunk 1000 / overlap 200) or *Custom*
  (attach your own splitter).

There is also a **GitHub Document Loader** for repo ingestion (recursive, with ignore paths).

**Text splitters:** Character, **Recursive Character** (splits by Markdown / HTML / code blocks /
characters — n8n's recommended default), and **Token Splitter** (BPE tokens, so chunk sizes map to
actual model context).

**Embedding nodes:** OpenAI, Azure OpenAI, Cohere, Google Gemini, Google Vertex, Google PaLM,
HuggingFace Inference (**including a Custom Inference Endpoint URL**), Ollama, AWS Bedrock, Mistral.

> ⚠️ **No NVIDIA NIM embedding node.** For NIM-hosted embeddings you have two paths: the
> **HuggingFace Inference** node's custom-endpoint field if the API shape matches, or — more
> reliably — an **HTTP Request** node inside a workflow, doing the embedding call yourself and
> writing vectors via the store's own API. The second is more work but it's the one that will
> actually accept a per-call `input_type` parameter.

### 6c. Binary data handling and limits

- **Binary data modes:** `filesystem`, `s3`, `azure`, `database`. **The in-memory `default` mode was
  removed in 2.0.**
- `N8N_BINARY_DATA_DATABASE_MAX_FILE_SIZE` defaults to **512 MiB** and cannot exceed 1024 (a database
  column limit).
- **`N8N_RESTRICT_FILE_ACCESS_TO` now defaults to `~/.n8n-files` from n8n 2.0.** Read/Write Files
  from Disk cannot reach anywhere else unless you set it explicitly. **If you want n8n reading
  `/srv/ingest`, you must set this variable.**
- In Docker, paths are the **container's** filesystem. Host directories need bind mounts.

### 6d. Intake surfaces

- **Webhook** node — full HTTP intake with basic / header / JWT auth, IP allow-listing, raw body,
  custom response headers, and four response modes.
- **Form Trigger** — an n8n-hosted web form. Recently gained a "Show Headers" option and the ability
  to demand end-user credentials before submission.
- **Chat Trigger** — chat UI, hosted or embeddable, with streaming.
- **Local File Trigger** — see §7.
- **S3 / AWS S3** nodes — read and write, but **there is no S3 trigger node**. Polling is on you.

### 6e. Verdict per parser category — the owner's actual question

| Your parser | Can n8n replace it? | Verdict |
| --- | --- | --- |
| **SMS XML** (SMS Backup & Restore export) | The XML node will turn the document into JSON. It will **not** group threads, split MMS parts, decode base64 attachments into files, normalize epoch-millisecond timestamps, or reconcile contacts. | **FRONT-END ONLY.** n8n triggers the run and reports the result. The Python stays. |
| **Chat-export ZIPs** (the five formats) | The Compression node unzips. Extract From File reads the inner text/JSON/HTML. Format *detection* and per-format normalization are yours. | **WRAP.** n8n can do unzip → detect → dispatch, then call your parser per format. A legitimate use, but it's a router, not a parser. |
| **iMessage HTML** | The HTML node can pull fields by CSS selector. Reconstructing sender/recipient/thread/attachment structure from a chat transcript's DOM is well past what a selector list expresses. | **KEEP CUSTOM.** Do not attempt this in n8n. |
| **Generic PDFs / CSVs / XLSX / RTF / ODS** (non-custody) | Yes — Extract From File covers all of these natively. | **REPLACE ad-hoc scripts.** This is where n8n earns its keep. |
| **LLM field extraction** | Information Extractor: input text, plus a schema defined three ways — attribute descriptions, a JSON example, or a hand-written **JSON Schema**. Editable system prompt template. | **COMPLEMENT, not replace.** Fine for one-off triage. **DSPy stays** for anything that needs optimization, few-shot compilation, or measured accuracy. |
| **Document classification** | Text Classifier: named categories, single or multi-label, an "Other" fallback branch or discard, editable system prompt, auto-fixing. | **ADOPT for routing.** Good enough to route a document to the right pipeline. Not a substitute for a trained classifier. |

**On customizability generally:** n8n's parsers are customizable in three escalating ways —
(1) node options and expressions, (2) the **Code node** with JavaScript or Python and, on
self-hosted, imported npm modules, (3) **community nodes** or your own custom node in
`N8N_CUSTOM_EXTENSIONS`. So "parsers that can be customized" is true. What's *not* true is that
they can be customized into your existing parsers without rewriting them in JavaScript. The honest
framing: **n8n's parsers front-end your parsers; they don't absorb them.**

---

## 7. MCP — server and client

### MCP Server Trigger (n8n as an MCP server)

- Exposes a URL that MCP clients connect to. **It only connects to and executes tool nodes** — it is
  not a normal trigger that feeds the next node.
- Expose a whole workflow as a tool with the **Custom n8n Workflow Tool** node.
- **Transports: SSE and streamable HTTP. No stdio.** (Claude Desktop connects via `mcp-remote` as a
  proxy — n8n documents the exact config.)
- **Auth: Bearer or Header.** That's the list.
- Test URL vs Production URL, same as webhooks. Custom path supported.
- Recent nicety: when a tool call is blocked because a credential isn't connected, n8n now presents
  the connect link through the client's native URL elicitation UI rather than as suspicious-looking
  plain text.

**Queue-mode limitation — important for a scaled deployment:** SSE and streamable HTTP need
connection affinity. With a single webhook replica it's fine. With **multiple** webhook replicas you
**must** route all `/mcp*` traffic to one dedicated replica, or *"your SSE and streamable HTTP
connections will frequently break."*

**Reverse-proxy gotcha:** behind nginx you must disable proxy buffering, gzip, and chunked transfer
encoding, and blank the `Connection` header, for the MCP location block. n8n publishes the config.

**Size cap:** an MCP tool result from a queue-mode worker is subject to the same 64 MiB relay limit
and **cannot be offloaded** — oversized results surface to the client as a tool error.

### MCP Client / MCP Client Tool (n8n calling out)

- Connects to an external MCP server. Transport is selectable.
- **Auth: bearer, generic header, multiple headers, and OAuth2.** (Better coverage than the server
  side.)
- Tool list is fetched live from the server.
- Input Mode: Manual (field by field) or JSON (for nested parameters).
- One MCP Client Tool node gives an agent access to **many** tools at once, which keeps the canvas
  clean compared to one node per tool.
- Since 2.22, a set of registry-backed servers (Apify, Linear, monday.com, Notion, PostHog) connect
  with a sign-in instead of manual config.

### Instance-level MCP (the third option)

Distinct from the node. One connection per n8n **instance**, centralized auth, and you choose which
workflows are exposed. Requirements for a workflow to be MCP-callable:

- `availableInMCP: true` in workflow settings (defaults to false),
- the workflow must be **active**,
- it must contain **at least one active Webhook node** — only webhook-triggered workflows qualify.

Auth is **OAuth (recommended) or API key**. Per-client setup UI from 2.33.0. Manageable from env
vars from 2.20.0 (`N8N_MCP_ACCESS_ENABLED`, `N8N_MCP_MANAGED_BY_ENV`). Left preview in July 2026.

⚠️ n8n's own security note: *"When a workflow is available in MCP, it can be discovered and executed
by any MCP client that has the appropriate API credentials for your n8n instance."*

### Fit verdict: **Adopt. This is n8n's best structural fit for your platform.**

MCP is the clean seam between n8n and everything else. Expose utility integrations as MCP tools;
consume your platform's MCP servers from n8n agents. It avoids the coupling that a direct HTTP mesh
would create, and it's the same protocol your other agents already speak.

**Deployment note for the existing instance:** if you scale the n8n on `ovh-files` past one webhook
process, the MCP affinity rule bites immediately. Plan for it or stay single-replica.

---

## 8. Integrating with Temporal (webhook and HTTP patterns)

### Temporal → n8n (n8n as an activity)

**There is no Temporal node in n8n.** Any Temporal call is an HTTP Request node against something
that fronts Temporal.

Calling n8n **from** a Temporal activity means POSTing to an n8n Webhook. Response modes:

| Mode | Behavior | Suitability |
| --- | --- | --- |
| **Immediately** | Returns `Workflow got started` at once. | ✅ **Best for fire-and-forget.** Temporal's activity completes fast, no long-held connection. |
| **When Last Node Finishes** | Returns the last node's output. | ⚠️ Works, but the activity now blocks on an HTTP connection for the whole n8n run. Any timeout, proxy hiccup, or n8n restart is an activity failure with ambiguous state. |
| **Using 'Respond to Webhook' node** | You choose where in the flow to respond. | ⚠️ Same caveat, but with control over *when* you respond — you can reply early and continue working. |
| **Streaming** | Token-by-token. | ❌ Not useful from an activity. |

> **Recommendation.** Use **Immediately** plus an explicit callback. Have the Temporal activity pass
> a callback URL (or workflow ID + signal name) in the request body; n8n does its work and then
> POSTs the result back to Temporal. This makes the boundary async and idempotent, which is what a
> durable orchestrator wants. It also means an n8n restart doesn't corrupt Temporal's view of the
> world — Temporal just doesn't get a callback, and its own timeout fires.

### n8n → Temporal (n8n starting a workflow)

HTTP Request node → your Temporal-fronting HTTP endpoint (a small FastAPI shim over the Temporal
client, or Temporal Cloud's HTTP API). Post the workflow type + args, get back a workflow ID, done.

**This is the shape for the drop-directory trigger:** file lands → n8n detects → n8n POSTs to start
`ChatTranscriptIngest` → n8n's job is over. Custody never touches n8n.

### HITL: who owns the wait?

n8n **can** hold a wait. The **Wait** node with *Resume: On Webhook Call* generates
`$execution.resumeUrl` at runtime, supports Basic / Header / JWT auth on the resume call, IP
allow-listing, an optional **Limit Wait Time**, and a webhook suffix for multiple waits in one
workflow.

**But two facts should settle the design:**

1. **Waits under 65 seconds never hit the database.** n8n's docs: *"For wait times less than 65
   seconds, the workflow doesn't offload execution data to the database. Instead, the process
   continues to run."* In-process = lost on restart.
2. **Partial executions change the resume URL.** The node that *sends* the URL must run in the same
   execution as the Wait node, or the link is dead.

> **Recommended shape.** **Temporal owns the wait; n8n owns the screen.**
>
> - Temporal workflow reaches an approval point and blocks on a **Signal**.
> - Temporal (or n8n on a poll) surfaces the item to a person via an n8n Slack / Telegram / Form
>   approval node.
> - The person clicks. n8n receives the click and **POSTs the Signal to Temporal**.
> - Temporal resumes. Its history is the record of who approved what and when.
>
> This keeps the audit trail in the durable system and uses n8n purely as the presentation layer —
> which is exactly what it's good at.

### Fit verdict: **Adopt at the edges, with async handoffs only.**

Never let a custody-relevant step depend on an HTTP round-trip through n8n completing successfully.

---

## 9. Triggers for file arrival

### Local File Trigger — for the drop directory

Fires on add / change / delete for a **specific file** or **a folder**. Options: include linked
files/folders, **Ignore** patterns (Anymatch syntax, tested against the whole path, not just the
filename), and **Max Folder Depth**.

**Four things you must know before using it:**

1. **Self-hosted only.** Not available on n8n Cloud. (Fine — yours is self-hosted.)
2. **Disabled by default from n8n 2.0.** n8n's warning: *"The Local File Trigger node can introduce
   significant security risks in environments that operate with untrusted users."* It ships in the
   default `NODES_EXCLUDE` list alongside `executeCommand`. **You must explicitly re-enable it.**
3. **Container filesystem, not host.** `/srv/ingest` must be bind-mounted into the n8n container.
4. **`N8N_RESTRICT_FILE_ACCESS_TO`** must be widened if you also want to *read* the files.

### The R2 / rclone-mounted bucket — do NOT use the file trigger

The Local File Trigger is a filesystem watcher (chokidar-style). Watching a **FUSE mount** is
unreliable — inotify events on network filesystems are not dependable, and rclone mounts in
particular do not emit reliable change notifications.

**Use polling instead.** The pattern:

```
Schedule Trigger
  → S3 node (list objects, prefix-scoped)
  → Remove Duplicates  [Operation: Remove Items Processed in Previous Executions]
  → HTTP Request       [start Temporal workflow]
```

`Remove Duplicates` in "previous executions" mode is a first-class dedupe-across-runs primitive.
For a cursor you control explicitly, use a **Data Table** (n8n's built-in tables: create/list/update/
delete tables, insert/get/update/delete/**upsert** rows, with filters, pagination, and Order By).

**Good news on durability — this improved recently.** n8n now has a **durable scheduler**:

- `N8N_SCHEDULER_POLL_TRIGGERS_ENABLED` makes each poll its own durable schedule — **polls survive
  restarts** and spread across instances.
- **Missed polls are always skipped** (correct for a "fetch everything new since last run" poll).
- ⚠️ **A poll can occasionally run twice.** n8n guarantees at-least-once, not exactly-once. Their
  words: *"A poll can repeat, for example when an instance stalls and another takes over."*
- `N8N_POLLER_DURABLE_CURSORS_ENABLED` (n8n **2.36.0+**) stores the cursor in a dedicated table and
  **commits it in the same transaction as the execution the poll produced**, so a mid-poll crash
  can't drop or duplicate items. From 2.37.0 this also requires `N8N_SCHEDULER_ENABLED`,
  `N8N_SCHEDULER_POLL_TRIGGERS_ENABLED`, and `N8N_USE_WORKFLOW_PUBLICATION_SERVICE`.
- Prometheus metrics exist for poll duration, poll errors, overlap, and cursor commits
  (`N8N_METRICS_INCLUDE_POLL_TRIGGER_METRICS`), with a published Grafana dashboard.

> **Because polls can repeat, whatever n8n calls must be idempotent.** Starting a Temporal workflow
> with a deterministic workflow ID derived from the object key gives you that for free — Temporal
> rejects the duplicate start. **This is the correct design and it costs nothing.**

### Fit verdict: **Adopt, with the durable scheduler turned on and idempotent handoffs.**

- Drop directory → Local File Trigger (re-enabled, bind-mounted).
- R2 bucket → Schedule + S3 list + Remove Duplicates, **not** the file trigger.
- Both → start a Temporal workflow with a content-derived ID.

---

## 10. Self-hosting, license, community, and code

### License — Sustainable Use License (fair-code)

Three limitations, quoted in substance from n8n's licence FAQ:

1. Use or modify the software **only for your own internal business purposes**, or for
   non-commercial / personal use.
2. Distribute or provide it to others **only free of charge, for non-commercial purposes**.
3. Don't remove or obscure licensing, copyright, or other notices.

**What's explicitly allowed:**

- Using n8n to sync data you control.
- Building nodes and integrations.
- Consulting and support services around n8n — *including building workflows for money.*
- Running it on an internal company server.

**What's explicitly NOT allowed:**

- White-labeling n8n and selling it.
- Hosting n8n and charging people for access.
- **Powering a feature in your app where n8n collects your users' own credentials to access their
  data.** n8n gives a worked example: collecting a user's HubSpot credentials to sync into your app
  is **not allowed**; an AI chatbot in your app running on *your* company credentials **is allowed**.

**Note:** source files with `.ee.` in the filename are under the separate **n8n Enterprise License**,
not the Sustainable Use License.

> **Fit verdict for this platform: ✅ clean.** The usage scope here is personal/internal, and the
> licence explicitly permits internal use, consulting, and building workflows. The single line to
> keep in view: **if this ever becomes a product where clients connect their own accounts, the
> licence stops covering you** and you'd need a commercial agreement with n8n.

### Community ecosystem

- Community nodes are npm packages tagged **`n8n-community-node-package`**. Install by GUI
  (Settings > Community Nodes), by npm into `~/.n8n/nodes`, or via `N8N_CUSTOM_EXTENSIONS`.
- **Verified community nodes**: n8n inspects a subset and surfaces them in the nodes panel under
  "More from the community." These have passed data- and system-security review.
- **From 1 May 2026**, nodes submitted for verification must be published via GitHub Actions with a
  **provenance statement**, cryptographically tying the package to a repo and commit. Local
  publishing is no longer accepted for verification.
- There's a **blocklist** of community nodes n8n refuses to install.
- Env controls: `N8N_COMMUNITY_PACKAGES_ENABLED`, `N8N_VERIFIED_PACKAGES_ENABLED`,
  `N8N_UNVERIFIED_PACKAGES_ENABLED`, `N8N_COMMUNITY_PACKAGES_PREVENT_LOADING` (a safety valve if a
  bad node stops the instance booting), and a private-registry option.

**Ecosystem size — low confidence.** n8n's docs don't publish a count. Third-party trackers as of
early 2026 report roughly **500–600+ community node *packages*** on npm, and one aggregator counts
~5,800 individual *nodes* including built-ins. Treat these as indicative, not authoritative.
([awesome-n8n](https://github.com/restyler/awesome-n8n), [vps.us tally](https://vps.us/blog/how-many-n8n-integrations/))

⚠️ **The risk is real and n8n says so plainly:** *"community nodes have full access to the machine
that n8n runs on, and can do anything, including malicious actions"* — plus access to all data in
your workflows, plus breaking changes on upgrade. **On a machine that touches evidence, install
verified nodes only, or none.**

### Code node

- **JavaScript** and **Python**. Two modes: Run Once for All Items / Run Once for Each Item.
- **Self-hosted can import npm modules**, gated by `NODE_FUNCTION_ALLOW_BUILTIN` and
  `NODE_FUNCTION_ALLOW_EXTERNAL` (both disabled by default). Cloud gets only `crypto` and `moment`.
  **If task runners are enabled, set these on the task runner, not the main process.**
- **Python changed materially in 2.0.** The Pyodide-based implementation is gone, replaced by
  **native Python via task runners in external mode**. Consequence: *"The native Python Code node
  doesn't support built-in variables like `_input` or dot access notation."* Native Python tools use
  `_query` for the AI-supplied input string. **Existing Python code nodes need review before a 2.x
  upgrade.**
- `N8N_PYTHON_ENABLED` toggles Python entirely.
- **Task runners are enabled by default from 2.0** — Code node executions run isolated.
- **Environment variable access from Code nodes is blocked by default from 2.0.**

### Version cadence and churn

- Release channels renamed in 2.0: `latest`→**`stable`**, `next`→**`beta`** (old tags still work for
  now). n8n's own recommendation: **pin to a specific version number.**
- Cloud offers two cadences: security-and-stability (~every two weeks) or every-new-release
  (**"on average one release per day"**). That's the upstream shipping rate.
- **n8n 3.0 lands October 2026.** What it takes with it:
  - **npm / `npx n8n` installs are no longer supported — Docker only.**
  - Removed nodes: **Function**, **Function Item**, **Item Lists**.
  - **AI Agent node v1 removed**, with SQL / Conversational / OpenAI Functions / Plan-and-Execute /
    ReAct agent modes.
  - **Execute Workflow** node's older behavior removed.
  - `$getPairedItem` expression helper removed.
  - **Chat hub retired**; workflow import-from-URL in the editor removed.
  - Stronger security defaults: tighter risky-resource-name handling, more secure credential
    behavior, **key rotation on by default**.

### Fit verdict: **Self-hosting is fine. Budget for upgrade work twice a year.**

---

## 11. Recommended adoption sequence

Each step is independently useful and independently reversible. Stop at any point.

1. **Pin the version and confirm the deployment shape.**
   Pin the container to an exact version tag. Confirm the `ovh-files` n8n is Docker (not npm) —
   3.0 requires Docker in October. Enable a Postgres backend and a persistent binary-data mode if
   they aren't already. *Low effort, removes a future emergency.*

2. **Wire the R2 drop-detection workflow, read-only.**
   Schedule Trigger → S3 list → Remove Duplicates (previous-executions mode) → log to a Data Table.
   Turn on `N8N_SCHEDULER_POLL_TRIGGERS_ENABLED` and `N8N_POLLER_DURABLE_CURSORS_ENABLED`.
   **Do not start anything yet.** Watch it for a week and confirm it sees every object exactly once.

3. **Add the Temporal handoff.**
   Replace the log step with an HTTP Request that starts `ChatTranscriptIngest`, using a
   **workflow ID derived from the object key** so a repeated poll is a no-op. Add an error workflow.

4. **Add the local drop-directory trigger.**
   Re-enable `n8n-nodes-base.localFileTrigger` in `NODES_EXCLUDE`, bind-mount `/srv/ingest`, widen
   `N8N_RESTRICT_FILE_ACCESS_TO`. Same idempotent Temporal handoff.

5. **Build the HITL approval surface.**
   Slack or Telegram approval node → on click, POST a **Temporal Signal**. Temporal keeps the wait.
   n8n is the screen only. Verify end-to-end against a real paused Temporal workflow.

6. **Expose two or three utility integrations over MCP.**
   MCP Server Trigger + Custom n8n Workflow Tool, bearer auth, single webhook replica. Start with
   something harmless (Drive listing, Slack post) and confirm your agents can call it.

7. **Prototype retrieval against Weaviate.**
   Vector store node in Get Many mode with hybrid search. Tune `alpha` and fusion type on real
   queries. Then layer MultiQuery (Query Count 3–5) and a reranker, and **measure the recall
   difference**. This is the cheapest way to answer "is MultiQuery worth building in Python?"
   **Prerequisite:** confirm your chunk metadata carries epoch-number timestamps, or the answer
   won't generalize to filtered queries.

8. **Adopt Extract From File for non-custody document work.**
   Retire ad-hoc PDF/CSV/XLSX scripts. Keep the message-format parsers in Python.

9. **Try one first-class Agent — internal, read-only, non-custody.**
   A case-desk assistant in Slack. Give it read-only workflow tools and turn on `requireApproval`
   for anything that writes. Accept it may break; it's Preview.
   Remember it cannot see Weaviate natively — wrap it as a workflow tool.

10. **Only then**, revisit change-detection as a real workstream, with the polling and dedupe
    machinery already proven by steps 2–4.

---

## 12. Limits and risks — the honest list

### License risk: 🟢 Low, but know the boundary

Internal use is unambiguously permitted. The line is **"selling a product whose value derives
substantially from n8n functionality"** and **collecting end-users' own credentials**. Nothing in
the current platform crosses it. Revisit if the platform ever becomes something other people log
into with their own accounts.

### Durability risk: 🔴 High — this is the one that matters

- **Waits under 65 seconds are in-process.** They do not touch the database. A restart loses them.
- **Bull's stalled-job retry was removed in 2.0** and n8n tells you to build your own.
- **Poll triggers are at-least-once, not exactly-once** — even with the durable scheduler.
- An n8n "execution" is a database row, not a replayable history. There is no equivalent of
  Temporal's deterministic replay.
- **Queue mode is not supported for Agents at all** right now.

> **Mitigation, and it's not optional: every n8n → platform handoff must be idempotent.** Derive
> Temporal workflow IDs from content. Never let n8n be the only record that something happened.

### Preview / beta risk: 🟠 Medium-high on Agents specifically

Agents are Preview, self-hosted-beta, unsupported on self-hosted Enterprise, unsupported in queue
mode, with channel connections that "can fail" and a Preview-within-Preview knowledge base needing
a Daytona sandbox. **This will change under you.** Fine for an internal assistant; unacceptable
anywhere near evidence.

### Version-churn risk: 🟠 Medium

n8n ships roughly daily upstream and majors are disruptive. 3.0 in **October 2026** removes the
npm install path, three nodes, five agent modes, an expression helper, and the Chat hub, and
tightens security defaults including key rotation. Between 1.0 and 3.0 the Python Code node was
completely reimplemented, task runners became default, and in-memory binary data was removed.
**Pin versions. Read breaking-change pages before every major. Budget upgrade time.**

### Execution-model risk: 🟠 Medium — subtle and silent

- **Sub-node expressions resolve to the first item only.** Repeated across nearly every AI sub-node
  page. Batch behavior will surprise you.
- **Item multiplication** when chaining independent data sources (N×M).
- **`alwaysOutputData: true`** — n8n itself calls it a footgun that fabricates empty items.
- These produce *wrong results*, not errors. Nothing turns red.

### Security risk: 🟠 Medium, mostly self-inflicted

- **Community nodes have full machine access.** Verified-only, on an evidence-adjacent host.
- **Local File Trigger and Execute Command are excluded by default** because of exactly this. If you
  re-enable the file trigger, you're re-opening a door n8n deliberately closed.
- **Instance-level MCP**: any client with valid API credentials can discover and execute every
  MCP-enabled workflow.
- Code node module imports and env-var access are locked down by default — **leave them locked down**
  unless a specific workflow needs them.

### Scaling risk: 🟡 Low-medium, but with sharp edges

- **MCP + multiple webhook replicas requires dedicated routing** or connections break.
- **64 MiB webhook response relay cap** in queue mode; MCP tool results **cannot** be offloaded past it.
- **Multi-main requires an Enterprise licence.**
- Reverse proxies need explicit buffering/gzip/chunking config for MCP endpoints.

### Capability gaps to plan around

| Gap | Workaround |
| --- | --- |
| First-class Agents can't use Weaviate | Wrap as a workflow tool or MCP tool |
| No date/timestamp operator in vector filters | Store epoch **numbers** in chunk metadata at ingest |
| No NIM embedding node | HTTP Request node, or HuggingFace custom endpoint if the shape matches |
| Reranker choice is essentially Cohere | HTTP Request inside a Workflow Retriever |
| No Temporal node | HTTP Request against a Temporal-fronting shim |
| No S3 trigger node | Schedule + list + Remove Duplicates |
| No XML operation in Extract From File | Separate XML node |
| Text embeddings only | Out of scope for n8n; handle multimodal elsewhere |
| Weaviate multi-tenancy can't be turned on later | Decide at first ingestion |

---

## Sources

All n8n documentation pages accessed **2026-08-25** via the n8n docs MCP server.

**Agents**
- [Build and manage agents](https://docs.n8n.io/build/build-and-manage-agents)
- [Set up AI Assistant / Enable agents](https://docs.n8n.io/deploy/host-n8n/configure-n8n/set-up-ai-assistant)
- [MCP server tools reference](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/mcp-server-tools-reference)
- n8n Agent management reference + Agent JSON config schema — served live by the n8n MCP server at `n8n://agents/reference`

**AI / LangChain**
- [Tools Agent](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/tools-agent)
- [Conversational Agent (deprecated)](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/conversational-agent)
- [AI Agent Tool](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolaiagent)
- [What agents do](https://docs.n8n.io/build/integrate-ai/understand-ai-components/what-agents-do)
- [What chains do](https://docs.n8n.io/build/integrate-ai/understand-ai-components/what-chains-do)
- [How memory works](https://docs.n8n.io/build/integrate-ai/understand-ai-components/how-memory-works)
- [LangChain in n8n](https://docs.n8n.io/build/integrate-ai/langchain-in-n8n)
- [LangChain Code node](https://docs.n8n.io/build/code-in-n8n/use-built-in-shortcuts/langchain-code-node) · [LangChain Code](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.code)

**Retrieval**
- [Weaviate Vector Store](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.vectorstoreweaviate)
- [MultiQuery Retriever](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.retrievermultiquery)
- [Contextual Compression Retriever](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.retrievercontextualcompression)
- [Workflow Retriever](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.retrieverworkflow)
- [Vector Store Retriever](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.retrievervectorstore)
- [Reranker Cohere](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.rerankercohere)
- [Store and search data with vectors](https://docs.n8n.io/build/integrate-ai/understand-ai-components/store-and-search-data-with-vectors)
- [Retrieve relevant context](https://docs.n8n.io/build/integrate-ai/understand-ai-components/retrieve-relevant-context)
- Milvus / Qdrant / Pinecone / Supabase / Chroma / MongoDB Atlas / Redis / Simple vector store node pages

**Ingest / parsing**
- [Extract From File](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.extractfromfile)
- [HTML](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.html) · [XML](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.xml) · [Compression](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.compression)
- [Default Data Loader](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.documentdefaultdataloader)
- [Information Extractor](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.information-extractor)
- [Text Classifier](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.text-classifier)
- [Read/Write Files from Disk](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.readwritefile)
- [Work with files and images](https://docs.n8n.io/build/work-with-data/handle-special-data-types/work-with-files-and-images)
- [Binary data env vars](https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/binary-data)
- Text splitter and embeddings sub-node pages (Recursive Character, Character, Token; OpenAI, Azure, Cohere, Gemini, Vertex, PaLM, HuggingFace, Ollama)

**Workflows / execution**
- Workflow SDK reference — served live by the n8n MCP server (`get_workflow_sdk_reference`)
- [Execute Sub-workflow](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executeworkflow) · [Convert to sub-workflows](https://docs.n8n.io/build/flow-logic/convert-to-sub-workflows)
- [Handle errors gracefully](https://docs.n8n.io/build/flow-logic/handle-errors-gracefully) · [Error Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.errortrigger)
- [Enable queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode) · [Queue mode env vars](https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/queue-mode) · [Control concurrency](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/control-concurrency)
- [Save and publish workflows](https://docs.n8n.io/build/understand-workflows/save-and-publish-workflows) · [View change history](https://docs.n8n.io/build/manage-workflows/view-change-history) · [Workflow API](https://docs.n8n.io/connect/n8n-api/workflow)
- [Push and pull changes](https://docs.n8n.io/administer/use-source-control-and-environments/push-and-pull-changes) · [Export a package](https://docs.n8n.io/build/manage-workflows/n8n-packages/export-a-package)
- [Data Table node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.datatable) · [Remove Duplicates](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.removeduplicates)

**Triggers / integration**
- [Local File Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.localfiletrigger)
- [Wait](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.wait) · [Wait (flow logic)](https://docs.n8n.io/build/flow-logic/wait)
- [Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook) · [Respond to Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.respondtowebhook) · [Stream real-time responses](https://docs.n8n.io/build/understand-workflows/understand-executions/stream-real-time-responses)
- [Durable scheduler](https://docs.n8n.io/deploy/host-n8n/configure-n8n/durable-scheduler) · [Scheduler env vars](https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/scheduler)

**MCP**
- [MCP Server Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.mcptrigger)
- [MCP Client Tool](https://docs.n8n.io/integrations/builtin/cluster-nodes/sub-nodes/n8n-nodes-langchain.toolmcp) · [MCP Client](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.mcpclient)
- [Connect to n8n MCP server](https://docs.n8n.io/connect/connect-to-n8n-mcp-server) · [MCP client connection examples](https://docs.n8n.io/connect/connect-to-n8n-mcp-server/mcp-client-examples)

**Licence / community / hosting / versions**
- [Sustainable use license](https://docs.n8n.io/privacy-and-security/sustainable-use-license)
- [Community node risks](https://docs.n8n.io/integrations/community-nodes/risks) · [GUI installation](https://docs.n8n.io/integrations/community-nodes/installation-and-management/gui-installation) · [Install verified community nodes](https://docs.n8n.io/integrations/community-nodes/installation-and-management/install-verified-community-nodes) · [Building community nodes](https://docs.n8n.io/integrations/community-nodes/building-community-nodes)
- [Code node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.code) · [Enable modules in Code node](https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/configuration-examples/enable-modules-in-code-node) · [Nodes env vars](https://docs.n8n.io/deploy/host-n8n/configure-n8n/basic-configuration/use-environment-variables/nodes)
- [v3.0 Breaking changes](https://docs.n8n.io/changelog/v30-breaking-changes) · [v2.0 Breaking changes](https://docs.n8n.io/changelog/v20-breaking-changes) · [v1.0 Migration guide](https://docs.n8n.io/changelog/v10-migration-guide) · [Changelog](https://docs.n8n.io/changelog)
- [What you can do (security)](https://docs.n8n.io/privacy-and-security/what-you-can-do)

**Third-party (low confidence, community-node counts only)**
- [awesome-n8n](https://github.com/restyler/awesome-n8n) · [How many n8n integrations](https://vps.us/blog/how-many-n8n-integrations/)
