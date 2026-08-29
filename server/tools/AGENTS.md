# server/tools/ — cross-domain tool registry

> _Byline: Claude Code · 2026-07-27; verification refresh by Codex · GPT-5.6-Sol · 2026-08-29._

> Nested map. Parent: `../AGENTS.md`. Root: `../../AGENTS.md`.

## What's here

The atomic-tool capability layer (D-026): a polyglot registry consumed by
`evidence/`, `analysis/`, `agents/`, workflows, and the CLI — not owned by any one
domain, so it's a top-level sibling of `evidence/`, not nested inside it.

```
registry.py              capability registry (@register, load_builtin_tools)
_common.py                shared parser helpers (underscore = NOT a tool, skipped)
_chatminer_adapter.py     ChatMiner -> NormalizedRecord bridge (underscore-prefixed)
_sbv_client.py            SBV REST client, shared by sbv_sms.py + the docker/tools facade
parsers/
  messaging/               imessage_{html,txt,pdf}, sms_xml, sbv_sms, facebook_{html,json},
                            messaging_{csv,transcript}
  ai_chat/                  chatgpt_{official,share}, claude_{ai_export,code,code_jsonl,md},
                            gemini_{chrome,json}, perplexity_{gdpr,md,plugin}
  generic/                  generic_md, whole_file_fallback
extractors/                extract_text (capability extract.text)
visualizers/               geo_map (capability viz.geo_map) + vendored Leaflet assets
gateway/                   G4 progressive-disclosure tool gateway (moved here from
                            server/evidence/tool_finder/, ADR-0035) — see below
```

## Registry / capability model

Each tool registers via `@register(id=..., capability=..., description=...)` and
implements `accepts(media_hint, size_bytes)` + `run(payload)`. Workflows resolve by
**capability** (e.g. `parse.sms-xml`), not by hard-coded function — when the preferred
tool rejects an input, the workflow tries the next same-capability candidate. IDs are
explicit strings, never derived from module path, so moving a module never churns its ID.

## How to add a parser

1. Add one module under the right `parsers/{messaging,ai_chat,generic}/` subdir,
   `extractors/` for extraction, or `visualizers/` for rendered visual outputs.
2. Self-register: `@register(id="parse.<format>", capability="parse.<capability>", ...)`.
3. Nothing else to wire up — `registry.load_builtin_tools()` uses
   `pkgutil.walk_packages` (recursive, since ADR-0035) and auto-discovers it. It skips
   `_`-prefixed leaf modules, the `gateway/` sub-package, and sub-package `__init__`s.

## `gateway/` (G4)

Progressive-disclosure meta-ops over the registry — `get_tool_categories`,
`search_tools`, `describe_tool`, `execute_tool`, `get_ref` — so consumers get five
thin functions instead of one per parser (23+ tools would flood agent context).
Wrapped as agno `@tool`s in `server/agents/tools/gateway_tools.py`. This was
`server/evidence/tool_finder/` before ADR-0035; it is a registry **consumer**, never
itself a registered tool, and is excluded from `load_builtin_tools()` discovery.

## Facade mount<->import contract

`docker/tools/tools/facade.py` (the dep-light platform-tools container) volume-mounts
the **whole `server/` tree**, not just `server/tools/` — parsers transitively import
`server.contracts.records` (the record schema) and `server.vendored.chatminer` (the
parser core), both deliberately lightweight (no sqlalchemy/agno at import time).
**`server.contracts` must stay import-light** — see `server/contracts/AGENTS.md` — or
this facade FATAL-loops (the 2-day outage ADR-0033 era already paid for once). Full
contract details are in the facade's own module docstring; don't restate them here.

## Relevant ADRs

- ADR-0035 — sub-namespacing, gateway extraction, `walk_packages` discovery (the source
  of everything on this page — read it for the as-built details, not repeated here)
- D-026 (`docs/DECISION_LOG.md`) — tools promoted out of `evidence/` to top-level

---

> _Sprint-mode policy REMOVED 2026-08-25 on owner order ("you're grounded — remove it entirely"). Confirm-and-discuss-before-changing is back in force._
