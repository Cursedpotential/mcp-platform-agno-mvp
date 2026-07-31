# ContextForge adoption list — claude.ai cloud connectors

> _Byline: Claude Code · Fable 5 · 2026-07-31_
> **Status:** inventory + triage. Nothing adopted yet — this is the worklist.

## Why this exists

claude.ai cloud connectors are **auto-fetched from the Anthropic account at every session
start**. Disabling one in the UI only holds for that session; the next launch re-fetches the
list and it is back. That is why the legal connectors kept reappearing no matter how many
times they were switched off — it was never a local setting, it was a sync.

They also **bypass ContextForge entirely**, which contradicts the canon (§5: ContextForge is
*the* tool gateway; everything gets an API, every API gets an MCP, federated through CF).

**Fix applied 2026-07-31:** `deniedMcpServers` in `~/.claude/settings.json` — per-connector,
**local**, and therefore immune to the cloud re-fetch. 26 denied, 3 kept.
Names must match `claudeAiMcpEverConnected` in `~/.claude.json` verbatim, `claude.ai ` prefix
included. Backup at `settings.json.bak-2026-07-31-mcpdeny`.

## Kept (owner call)

| Connector | Tools | Note |
|---|---|---|
| `claude.ai Google Drive` | 8 | keep for now |
| `claude.ai Mermaid Chart` | 1 | keep |
| `claude.ai Remote Desktop Commander` | — | keep; currently **failing to connect** — worth a look |

## Denied — duplicates of things we already run

These were pure redundancy. Each already has a local or CF-federated equivalent.

| Connector | Duplicates |
|---|---|
| `claude.ai Exa` | `exa` — already federated through ContextForge |
| `claude.ai Basic Memory Cloud` (**20 tools**) | Graphiti (dev + case lanes) + memsearch |
| `claude.ai Context7` | `context7` plugin, already enabled |
| `claude.ai agno` | `agentos` / `agno-gateway` |
| `claude.ai Cloudflare Developer Platform` | Cloudflare/R2 tooling + coolify MCP |
| `claude.ai Linear`, `Mozilla MDN`, `pg-aiguide`, `SlidesGPT`, `Claude Code Remote` | unused here |

## Denied — legal category (the ones that kept re-enabling)

| Connector | Tools | Note |
|---|---|---|
| `claude.ai Legal Data Hunter` | 7 | **worst context offender** — injects a ~1,000-word "legal-research" instruction block into the system prompt every session |
| `claude.ai CourtListener` | 16 | real caselaw source — **strong CF adoption candidate** |
| `claude.ai Courtroom5` | — | needs auth |
| `claude.ai Descrybe Legal Engine` | — | needs auth |
| `claude.ai Lawve AI` | — | needs auth |
| `claude.ai Scite` | — | citation analysis; research-adjacent |

## Denied — everything else (all CF adoption candidates)

`Unstructured Transform` (7 tools — ⚠ also injects an instruction block; **flagged**, easily
un-denied if wanted) · `Gmail` · `Google Calendar` · `Gamma` · `In Practise` ·
`Jobs and Careers` · `Lucid` · `Mem` · `Orbismo` · `Postman`

---

## Adoption triage — what's actually worth bringing into ContextForge

Ranked by fit with this platform, not by what happened to be installed.

### Tier 1 — genuinely useful for the case work
1. **CourtListener** (16 tools) — free/open caselaw + docket data (RECAP). The single most
   defensible legal source on the list, and it fits the Michigan family-law research lane.
   Adopt as a CF virtual server so the AI Legal Team agents can reach it under one auth layer.
2. **Unstructured Transform** (7 tools) — document parsing across ~70 formats. Overlaps the
   `nemo-retriever` skill and the evidence parsers; adopt only if it beats what we have on
   scanned/PDF exhibits. **Evaluate before adopting.**

### Tier 2 — plausible, not urgent
3. **Scite** — citation verification; pairs with the verify-citations discipline.
4. **Descrybe Legal Engine / Lawve AI / Courtroom5** — unknown quality, all need auth.
   Evaluate one at a time; do not bulk-adopt.

### Tier 3 — skip unless a concrete need appears
`Gamma`, `Lucid`, `SlidesGPT`, `Jobs and Careers`, `In Practise`, `Orbismo`, `Postman`,
`Mem`, `Linear`, `Mozilla MDN`.

### Already covered — do not adopt
`Exa`, `Context7`, `agno`, `Basic Memory Cloud`, `Cloudflare Developer Platform`.

## Adoption procedure (per connector)

1. Confirm it has a reachable **remote MCP endpoint** (CF federates MCP upstreams; a
   claude.ai-only OAuth connector may not expose one — check first, this is the likely blocker).
2. Register as a ContextForge virtual server with bearer auth (`token_env`), same pattern as
   the existing `graphiti` / `coolify` / `exa` / `platform_tools` servers.
3. Verify tools list through CF, then remove from `deniedMcpServers` **only if** the direct
   connector is still wanted — normally it stays denied and CF becomes the sole door.

⚠ **Known risk:** several of these authenticate via claude.ai's own OAuth flow and may have no
independently addressable MCP endpoint. If so they cannot be federated, and the choice is
direct-or-nothing. Determine this per connector before promising adoption.

## Verification owed

`deniedMcpServers` is documented as an enterprise-style denylist; it is applied here at **user**
scope. It has **not yet been confirmed to take effect** — that needs a Claude Code restart and a
re-count of `mcp__claude_ai_*` tools. If user scope turns out to be ignored, the fallback is
`disableClaudeAiConnectors: true` (all-or-nothing, would also drop Drive/Mermaid/RDC) or
disconnecting them in the claude.ai web UI.
