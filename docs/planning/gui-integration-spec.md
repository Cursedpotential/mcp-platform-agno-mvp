# One-Platform GUI & Tool-Surface Integration — Design Spec

> _Byline: Claude Code · 2026-07-04 (rev 2: prior-art survey of the pre-Agno GUI folded in)_
> Status: **DRAFT for owner brainstorm** · Companion to ADR-0023 (universal API+MCP),
> ADR-0025 (gateway topology), canon §5. Nothing here is built yet; this doc exists to
> be argued with.
> Prior-art sources: `Cursedpotential/mcp-tool-platform` + `Cursedpotential/TheBigOne/
> 01_MCP_Tool_Platform_Repo` (same codebase at two adjacent checkpoints; the TheBigOne
> snapshot is slightly earlier + documentation-heavy).

## 1. Goal

One cohesive platform surface. Today the custom AgentOS UI and the chat UI sit side by
side without a shared frame, and every supporting tool lives on its own port. The
platform is *supposed* to be an integrated whole: one shell where chat, agent control,
evidence workflows, and the polyglot third-party tools all live behind one nav, one
origin, one auth — plus a way for agents (not just humans) to discover the growing tool
catalog without drowning in it.

## 2. Hard constraints

1. **Minimize custom code** (ADR-0025). Off-the-shelf first; custom only for glue and
   the situation-specific pages (evidence browser, approvals).
2. **VIPs — integrate around, never overwrite:** Agno (+ native AgentOS UI), CopilotKit,
   IBM ContextForge, forked SBV, custom Graphiti, Semantica. Keep: LiteLLM, OpenCode,
   agent-sandbox, persistent Kasm.
3. **Registry contract is frozen** (owner, 2026-07-04): parser/tool *implementations*
   may change shape freely; `@register` ids, capabilities, and capability-based
   resolution stay stable. Every surface integrates against the registry manifest and
   ContextForge catalog, never against parser internals.
4. **ADR-0023 stands:** everything gets an API; every API gets an MCP wrapper,
   federated by ContextForge. The GUI is one more consumer of those same APIs — no
   private side-channels.
5. Tailnet-only exposure stays the default (`BIND_IP` pattern); the shell is the one
   thing that may eventually get a public face, behind auth.

## 3. Current state (what broke cohesion)

| Surface | Where | Problem |
|---|---|---|
| AgentOS control-plane UI | agentos-api :8000 | Separate world from chat; no shared nav |
| Chat UI | custom | Duplicates what Agno/AG-UI provides; drifted |
| SBV GUI | platform-tools :8085 | Own port, own look, bookmark-navigation |
| Attu (Milvus) | :3001 | Same |
| Neo4j Browser | :7474 | Same |
| Kasm desktop | :6901 | Same |
| ContextForge Admin UI | contextforge :4444 | Same (Phase C service) |
| LiteLLM proxy UI | gateway :4000 | Same |
| Tool catalog | `evidence/registry.py` in-process | No human-facing view; agents get all-or-nothing tool lists |

## 4. Prior art — the pre-Agno GUI is a donor, not a mockup

The predecessor platform ("MCP Tool Shop" / *"the Home Depot of preprocessing tools"*,
explicitly **"NOT a chat interface"**) got further than remembered. Survey findings
(2026-07-04), and what they change:

### 4.1 The old gateway already solved progressive disclosure

`server/mcp/gateway.ts` implemented a 4-endpoint, token-frugal contract:
**`search_tools`** (compact tool cards: name/category/description/tags) →
**`describe_tool`** (full schema on demand) → **`invoke_tool`** (execute; large outputs
return SHA-256 **content-addressed refs**) → **`get_ref`** (paged 4 KB retrieval).
Category = the `category.action` tool-name prefix. This is the same shape as
[CF issue #2230] and §6 Level 2 below — so the "tool-finder" meta-server is a **port of
the owner's own proven design onto the Python registry**, not a new invention. The
`get_ref` reference-return pattern should come along: parse results are large, and
paged refs are how a 50 MB export's records avoid blowing up agent context.

### 4.2 Carry-forward UI primitives (working code, React 19 + Vite + shadcn/Tailwind + tRPC)

| Donor page | What it does | Fate in the new shell |
|---|---|---|
| `Tools.tsx` (Tool Explorer) | search → category pills → grouped cards → detail panel → **"Test Tool" dialog that auto-renders a form from the tool's JSON `inputSchema`** (enum→Select, bool→Switch, number, array) and invokes live with latency + result | **Port.** The strongest page; becomes the shell's tool-catalog page (G5), sourced from `registry.manifest()` + CF catalog instead of hardcoded `CATEGORY_INFO` |
| `Proxy.tsx` (MCP server manager) | register remote MCP servers, status/latency, aggregated tool view | **Superseded** by ContextForge Admin UI (embed it); keep only if CF admin proves clunky |
| `McpConfig.tsx` (client-config generator) | generate ready-to-paste MCP configs for Claude Desktop / Gemini CLI / OpenAI, minting an API key | **Port, retargeted:** generate configs pointing at **ContextForge virtual servers** — "export the `parsers` category to Claude Desktop" in one click |
| `Forks.tsx` (tool forking + per-platform export) | clone/customize a tool, export as Claude MCP / Gemini ext / OpenAI function | Later; pairs with the config generator |
| `Stats.tsx` (Recharts analytics), `Logs.tsx` (filtered live logs) | observability dashboards | Port shells later; wire to AgentOS tracing + CF observability rather than the old collectors |
| `Config.tsx` / `PatternLibrary.tsx` (patterns/behaviors/dictionaries CRUD) | forensic pattern registry UI (256+ patterns, DARVO/gaslighting categories) | Design reference for **Part 2** (behavioral analysis); PatternLibrary was an unwired stub — treat as wireframe only |
| `DashboardLayout.tsx` + ~60 shadcn components | collapsible sidebar shell, full component kit | **Lift wholesale** into the G1 scaffold — G1 is not greenfield |

Caveats: the old data layer is tRPC/Node — the successor binds to FastAPI REST/OpenAPI +
AG-UI instead (don't port tRPC). Several old pages fronted TODO-stub backends
(Settings auto-detect, PatternLibrary's router wasn't even mounted); treat pages as
design reference, verify per-endpoint.

### 4.3 Intended-but-never-built (the old gap lists → our units)

From the old `GAP_ANALYSIS_PRIORITIES.md` / `IMPLEMENTATION_GUIDE.md` / `claude.md`:
evidence browser + entity/contradiction **timeline view** (Graphiti), **HITL
approval UI with diff preview/rollback**, workflow-execution UI, Workflow Builder,
Agent Builder, LLM-router monitor. Mapping: HITL approvals → native Agno `/approvals`
(G5, no custom table needed now); evidence browser + timeline → G5 (the owner-value
page); workflow *builder* stays out (HANDOFFS "NOT NOW" brainstorm); LLM-router monitor
→ LiteLLM UI embed (G2).

### 4.4 Self-hosted chat surface already exists (verified 2026-07-04)

`compose.exec.yaml` already ships an **`agent-ui`** service (`docker/agent-ui/Dockerfile`,
builds open-source `agno-agi/agent-ui`, :3000 tailnet-bound, Traefik labels staged for
`chat.int.*`). Browser → agentos-api directly; zero Agno-cloud dependency — the
self-hosted answer to the paid os.agno.com control plane. The open-source UI covers
chat + basic sessions; the hosted product's extra control-plane views (memory,
knowledge, evals) ride the same AgentOS REST API, which is what the G5 pages cover.
Shell relationship: embed `agent-ui` at `/x/chat/` as the interim chat surface; the
CopilotKit/AG-UI shell absorbs its role in G1 and `agent-ui` then becomes a fallback.

### 4.5 Embed candidates (third-party, CopilotKit/Agno-compatible)

| Candidate | What it adds | Integration mode |
|---|---|---|
| **Evidence.dev** (~~already running~~ **NOT currently deployed for this platform — corrected 2026-09-02, D-129**: its only project moved to traceIQ 2026-08-25, commit 557294c; the decision to use it was never reversed and re-establishing a project here is owed work) | SQL+markdown BI reports. Speaks **Postgres AND DuckDB natively** — with our `pg_duckdb` PG18 it can query the `analysis` schema and R2 parquet directly. "More detail" = author more report pages (offline-buildable unit) | Static build → iframe at `/x/reports/` |
| **Claude Code history viewer** (owner-requested; exact repo TBC) | Browse Claude Code session history. Candidates: `d-kimuson/claude-code-viewer` (web, most embeddable), `InDate/claude-log-viewer`, `daaain/claude-code-log` (static HTML output). Long game: a native shell transcript-viewer over ingested NormalizedRecords covers ALL sources, not just Claude | Embed OSS viewer now (`/x/claude-history/`); native G5 page later |
| **NeoDash** (neo4j-labs) | No-code dashboards straight over Neo4j/Graphiti: entity networks, relationship timelines, incident maps — biggest forensic-viz win | iframe `/x/neodash/` |
| **Surrealist** | SurrealDB admin UI (parallels Attu-for-Milvus) | iframe `/x/surreal/` |
| **CopilotKit generative UI** | Agents render live React components (charts/tables/timelines) inside chat replies — CopilotKit's core trick, rides AG-UI | In-app (G1/G5), not iframe |
| **React Flow** | Workflow-run visualization (custody→parse→store→knowledge DAGs) | In-app component (G5) |
| **Kepler.gl / Leaflet pattern** (per the visit-locations map, PR #7) | Geospatial analysis over PostGIS | In-app or static embed |

## 5. Target architecture

```
┌──────────────────────────── SHELL (one origin, one nav, one auth) ───────────────────────────┐
│  CopilotKit app (Next.js) riding Agno's AG-UI interface                                      │
│  ├─ Chat + agent surfaces      ← AG-UI protocol (AgentOS serves it natively)                 │
│  ├─ First-party pages          ← REST: agentos-api + platform-tools facade                   │
│  │    tool catalog (ported Tool Explorer) · evidence browser · workflow runs · approvals     │
│  └─ Embedded third-party UIs   ← same-origin reverse proxy (iframe), new-tab fallback        │
│       SBV · Attu · Neo4j Browser · ContextForge Admin · Kasm · LiteLLM UI                    │
├────────────────────────────────── GATEWAYS (unchanged, ADR-0025) ────────────────────────────┤
│  ContextForge = TOOL gateway (MCP + REST-wrapped, virtual servers, tags)                     │
│  LiteLLM     = MODEL gateway                                                                 │
├──────────────────────────────────────── SERVICES ────────────────────────────────────────────┤
│  agentos-api · platform-tools facade (registry tools + SBV proxy) · graphiti-mcp · dbs       │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

Key moves:

- **One shell, everything else demoted to a pane.** The CopilotKit/AG-UI app is the only
  first-class UI. The existing AgentOS UI and chat UI stop being separate destinations —
  chat comes through AG-UI; control-plane functions surface as shell pages calling the
  same AgentOS REST endpoints. The shell's skeleton (sidebar layout + component kit) is
  lifted from the donor client (§4.2), so G1 starts from working chrome.
- **Third-party UIs are embedded, not rebuilt.** A reverse proxy (Caddy or the existing
  Traefik labels) mounts each tool under one origin (`/x/sbv/`, `/x/attu/`, `/x/neo4j/`,
  `/x/forge/`, `/x/kasm/`). The shell nav frames them in iframes. Where a tool refuses
  framing (`X-Frame-Options`) or breaks on a path prefix, the nav entry opens a new tab
  instead — cohesion via nav + origin + auth, not via forcing every app into a frame.
- **The GUI consumes only public contracts:** AG-UI, AgentOS REST, facade OpenAPI,
  ContextForge catalog API. Parser churn at home never touches it (constraint 3).

## 6. Tool integration & progressive disclosure

The registry already carries everything needed: `registry.manifest()` returns
`id / capability / description / provenance` per tool, and **capability is the
category** (`parse.transcript`, `parse.sms-xml`, `parse.imessage`, `parse.facebook`,
`extract.text`, …) — the same role the `category.action` name prefix played in the old
platform. The pipeline:

```
evidence/registry (in-process)
  → platform-tools facade exposes /tools/* + /openapi.json      [exists]
  → ContextForge REST-wraps the facade → one MCP tool per op    [script exists, gated]
  → ContextForge VIRTUAL SERVERS group tools by category         [config only]
  → agents mount only the virtual server(s) they need            [Agno MCPToolbox]
```

### Level 1 — category disclosure via virtual servers (NOW, works on CF 0.8.0)

Create one ContextForge virtual server per capability family — `parsers`,
`sbv`, `graph`, `knowledge`, `analysis` — via `POST /servers` (`associatedTools=[...]`)
or the Admin UI; tag tools with their category (CF has universal tags + tag filtering).
An agent (or external MCP client) connected to the `parsers` virtual server sees *only*
parser tools on `tools/list`. That is the owner's "disclose a category, then look inside
it" — coarse-grained, zero code.

### Level 2 — meta-tool disclosure (port of the owner's old gateway design)

Native CF support is [CF issue #2230] — open, "would-like", not shipped. But the
pattern is already proven in the owner's pre-Agno gateway (§4.1); we re-implement it
over the Python registry, following the tools-facade pattern:

- **`tool-finder` MCP server** exposing 5 meta-tools:
  - `get_tool_categories()` → distinct capabilities + counts (from `registry.manifest()`
    + CF catalog for federated/third-party tools)
  - `search_tools(query, category?)` → compact tool cards (id, category, one-liner)
  - `describe_tool(id)` → full schema/contract, loaded on demand
  - `execute_tool(id, payload)` → proxied invoke (through CF so auth/rate-limit apply);
    **large outputs return a content-addressed ref, not the payload**
  - `get_ref(sha, page?)` → paged retrieval of large results (the old 4 KB-page
    pattern; parse outputs routinely exceed sane context sizes)
- Agents then carry **5 tools of context instead of 50+**, and the catalog can grow
  without touching any agent config. When IBM ships #2230 natively, swap ours out —
  the meta-tool names deliberately mirror both the upstream proposal and the old
  gateway.

Both levels together: humans browse categories in the shell's tool-catalog page (ported
Tool Explorer, same manifest), agents get virtual servers for standing mounts and the
tool-finder for open-ended discovery.

## 7. Phasing (each = one PR-sized HANDOFFS unit)

| Unit | What | Offline-buildable? |
|---|---|---|
| **G1** | Shell scaffold: CopilotKit/Next.js + AG-UI chat against agentos-api; lift `DashboardLayout` + shadcn kit from `mcp-tool-platform/client` | yes (mock AG-UI in dev) |
| **G2** | Reverse-proxy embed layer + shell nav (SBV, Attu, Neo4j, Forge, Kasm, LiteLLM, agent-ui, Evidence.dev reports, NeoDash, Surrealist, Claude-history viewer); per-tool iframe-vs-new-tab decision table | mostly (needs VPS to verify each embed) |
| **G3** | ContextForge virtual servers + tags per capability family; agents' MCPToolbox mounts narrowed | config on VPS |
| **G4** | `tool-finder` meta-MCP server (5 meta-tools incl. `get_ref` paged refs, over manifest + CF catalog) | yes |
| **G5** | First-party pages: tool catalog (port `Tools.tsx` incl. schema-driven tester), approvals (native `/approvals`), workflow runs, evidence browser + timeline | yes against fixtures |
| **G6** | Client-config generator (port `McpConfig.tsx`, retargeted at CF virtual servers) | yes |

Suggested order: G1 → G4 (both fully offline) → G2/G3 on the next VPS window → G5 → G6.

## 8. Open questions (for the brainstorm session)

1. **Shell placement:** same repo (`ui/` dir) or sibling repo? Same repo keeps the
   docs/HANDOFFS loop; sibling keeps Python tooling clean. (The donor client argues
   for sibling-with-vendored-components, or an `ui/` dir vendoring `client/src/components/ui`.)
2. **Auth:** single basic-auth/JWT at the proxy for everything, or ride ContextForge's
   JWT for tool surfaces and keep the shell separate? (Multi-user auth is deferred per
   DEBT.md — but the proxy choice should not paint us into a corner. The donor had
   per-user API keys + OAuth via its host platform; neither carries over directly.)
3. **How much AgentOS UI to keep:** frame it under `/x/agentos/` as-is initially, or
   port its functions into shell pages immediately? (Recommend: frame first, port
   opportunistically.)
4. **Kasm/OpenCode:** first-class nav entries, or a "workbench" section that's allowed
   to feel different? (They're full desktops; cohesion expectations differ.)
5. **CF version drift:** live 0.8.0 vs compose-pinned 1.0.3 — reconcile before G3, since
   virtual-server/tag APIs differ slightly across versions.
6. **Which first-party page is the real MVP:** evidence browser (owner value) vs tool
   catalog (platform value)? The tool catalog is now a *port* (cheap); the evidence
   browser is new design (expensive, high value). They may no longer be either/or.
7. **`get_ref` store:** content-addressed results already have a home (custody blob
   layout / R2) — does `get_ref` serve from there, or a separate ephemeral result
   cache with TTL (the old 72 hr working-memory idea)?

## 9. Non-goals (YAGNI)

- No rebuilding chat, agent control, or tool management from scratch — AG-UI/CopilotKit,
  AgentOS REST, and the ContextForge Admin UI already exist (ADR-0025).
- No porting the donor's tRPC/Node data layer — the successor binds REST/OpenAPI + AG-UI.
- No public internet exposure in G1–G6; tailnet + proxy auth only.
- No per-parser UI. The GUI binds to registry ids/capabilities only (constraint 3).
- No workflow *designer* UI — workflow design remains the separate owner brainstorm
  (HANDOFFS "NOT NOW").
- No resurrecting the old 4-tier memory stack wholesale — memory architecture is
  settled elsewhere (canon §10 / MEMORY_ARCHITECTURE.md); only the `get_ref`
  result-paging idea carries over here.

[CF issue #2230]: https://github.com/IBM/mcp-context-forge/issues/2230
