# One-Platform GUI & Tool-Surface Integration — Design Spec

> _Byline: Claude Code · 2026-07-04_
> Status: **DRAFT for owner brainstorm** · Companion to ADR-0023 (universal API+MCP),
> ADR-0025 (gateway topology), canon §5. Nothing here is built yet; this doc exists to
> be argued with.

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

## 4. Target architecture

```
┌──────────────────────────── SHELL (one origin, one nav, one auth) ───────────────────────────┐
│  CopilotKit app (Next.js) riding Agno's AG-UI interface                                      │
│  ├─ Chat + agent surfaces      ← AG-UI protocol (AgentOS serves it natively)                 │
│  ├─ First-party pages          ← REST: agentos-api + platform-tools facade                   │
│  │    evidence browser · workflow runs · approvals (/approvals) · tool catalog view          │
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
  same AgentOS REST endpoints.
- **Third-party UIs are embedded, not rebuilt.** A reverse proxy (Caddy or the existing
  Traefik labels) mounts each tool under one origin (`/x/sbv/`, `/x/attu/`, `/x/neo4j/`,
  `/x/forge/`, `/x/kasm/`). The shell nav frames them in iframes. Where a tool refuses
  framing (`X-Frame-Options`) or breaks on a path prefix, the nav entry opens a new tab
  instead — cohesion via nav + origin + auth, not via forcing every app into a frame.
- **The GUI consumes only public contracts:** AG-UI, AgentOS REST, facade OpenAPI,
  ContextForge catalog API. Parser churn at home never touches it (constraint 3).

## 5. Tool integration & progressive disclosure

The registry already carries everything needed: `registry.manifest()` returns
`id / capability / description / provenance` per tool, and **capability is the
category** (`parse.transcript`, `parse.sms-xml`, `parse.imessage`, `parse.facebook`,
`extract.text`, …). The pipeline:

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

### Level 2 — meta-tool disclosure (small custom MCP server)

Native support is [CF issue #2230] (virtual meta-server: `get_tool_categories` /
`search_tools` / `describe_tool` / `execute_tool`) — open, "would-like", not shipped.
The same pattern is ~one file for us, following the tools-facade pattern:

- **`tool-finder` MCP server** exposing exactly 4 meta-tools:
  - `get_tool_categories()` → distinct capabilities + counts (from `registry.manifest()`
    + CF catalog for federated/third-party tools)
  - `search_tools(query, category?)` → id + one-line description matches
  - `describe_tool(id)` → full schema/contract
  - `execute_tool(id, payload)` → proxied invoke (through CF so auth/rate-limit apply)
- Agents then carry **4 tools of context instead of 50+**, and the catalog can grow
  without touching any agent config. When IBM ships #2230 natively, swap ours out —
  the meta-tool names above deliberately mirror the upstream proposal.

Both levels together: humans browse categories in the shell's tool-catalog page (same
manifest), agents get virtual servers for standing mounts and the tool-finder for
open-ended discovery.

## 6. Phasing (each = one PR-sized HANDOFFS unit)

| Unit | What | Offline-buildable? |
|---|---|---|
| **G1** | CopilotKit/Next.js shell scaffold + AG-UI chat against agentos-api | yes (mock AG-UI in dev) |
| **G2** | Reverse-proxy embed layer + shell nav (SBV, Attu, Neo4j, Forge, Kasm, LiteLLM); per-tool iframe-vs-new-tab decision table | mostly (needs VPS to verify each embed) |
| **G3** | ContextForge virtual servers + tags per capability family; agents' MCPToolbox mounts narrowed | config on VPS |
| **G4** | `tool-finder` meta-MCP server (4 meta-tools over manifest + CF catalog) | yes |
| **G5** | First-party pages: tool catalog view, approvals (native `/approvals`), workflow runs, evidence browser | yes against fixtures |

Suggested order: G1 → G4 (both fully offline) → G2/G3 on the next VPS window → G5.

## 7. Open questions (for the brainstorm session)

1. **Shell placement:** same repo (`ui/` dir) or sibling repo? Same repo keeps the
   docs/HANDOFFS loop; sibling keeps Python tooling clean.
2. **Auth:** single basic-auth/JWT at the proxy for everything, or ride ContextForge's
   JWT for tool surfaces and keep the shell separate? (Multi-user auth is deferred per
   DEBT.md — but the proxy choice should not paint us into a corner.)
3. **How much AgentOS UI to keep:** frame it under `/x/agentos/` as-is initially, or
   port its functions into shell pages immediately? (Recommend: frame first, port
   opportunistically.)
4. **Kasm/OpenCode:** first-class nav entries, or a "workbench" section that's allowed
   to feel different? (They're full desktops; cohesion expectations differ.)
5. **CF version drift:** live 0.8.0 vs compose-pinned 1.0.3 — reconcile before G3, since
   virtual-server/tag APIs differ slightly across versions.
6. **Which first-party page is the real MVP:** evidence browser (owner value) vs tool
   catalog (platform value)?

## 8. Non-goals (YAGNI)

- No rebuilding chat, agent control, or tool management from scratch — AG-UI/CopilotKit,
  AgentOS REST, and the ContextForge Admin UI already exist (ADR-0025).
- No public internet exposure in G1–G5; tailnet + proxy auth only.
- No per-parser UI. The GUI binds to registry ids/capabilities only (constraint 3).
- No workflow *designer* UI — workflow design remains the separate owner brainstorm
  (HANDOFFS "NOT NOW").

[CF issue #2230]: https://github.com/IBM/mcp-context-forge/issues/2230
