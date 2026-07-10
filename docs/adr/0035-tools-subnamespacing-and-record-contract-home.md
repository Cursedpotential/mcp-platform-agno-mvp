# ADR-0035: Tools sub-namespacing, tool_finder extraction, and the record contract's home

> _Byline: Claude Code · Opus 4.8 · 2026-07-10_

**Status:** Proposed (awaiting owner sign-off on the record-contract home — see Decision 3)
**Supersedes/relates:** [ADR-0033](0033-server-package-layout-repack.md) (server/ repack), D-026 (tools → server/tools/ cross-domain layer)
**Note on numbering:** `0034` is reserved by the unmerged `docs/adr-0033-0034-evidence-model` branch (evidence model); this decision takes `0035` to avoid collision.

## Context

Two structural smells surfaced after the `server/` repack settled:

1. **`server/evidence/` still hosts a cross-domain squatter.** `server/evidence/tool_finder/`
   (the G4 progressive-disclosure tool **gateway** — `toolfinder.py`, `content_store.py`,
   `api.py`) has zero evidence semantics. It is generic capability-discovery over the tool
   registry, consumed by `server/agents/tools/gateway_tools.py`. It lives under `evidence/`
   only by history. The rest of `evidence/` (`custody.py`, `store.py`, `workflows.py`,
   `cli.py`, `config/`, `normalize.py`) is legitimately the evidence bounded context.

2. **`server/tools/` is a flat 25-file dump.** 23 tool modules + 4 infra modules
   (`registry.py`, `_common.py`, `_chatminer_adapter.py`, `_sbv_client.py`) sit in one
   directory with no sub-structure, despite an obvious taxonomy already encoded in each
   tool's `capability=` tag (`parse.imessage`, `parse.sms-xml`, `parse.facebook`,
   `parse.transcript`, `extract.text`).

3. **The record contract's location understates its role.** `NormalizedRecord` /
   `RecordType` / `DisclosureTier` live in `server/evidence/normalize.py` but are imported
   by 15 parser modules + evidence internals + tests + (by mount contract) the facade —
   it is the platform's canonical record contract, not an evidence-private type.

## Decision

### 1. Extract the tool gateway: `server/evidence/tool_finder/` → `server/tools/gateway/`

Discovery belongs next to the registry it indexes. `git mv server/evidence/tool_finder
server/tools/gateway`. Update the two importers in
`server/agents/tools/gateway_tools.py` (`server.evidence.tool_finder.*` →
`server.tools.gateway.*`) and any `__main__`/`api` self-references.

### 2. Sub-namespace `server/tools/` by capability

```
server/tools/
├── registry.py            # capability registry (core — stays at root)
├── _common.py             # shared parser base/helpers (core)
├── _chatminer_adapter.py  # chatminer→record adapter (core)
├── _sbv_client.py         # SBV HTTP client (core)
├── parsers/
│   ├── messaging/         # imessage_{html,txt,pdf}, sms_xml, facebook_{html,json},
│   │                      #   messaging_{csv,transcript}, sbv_sms
│   ├── ai_chat/           # chatgpt_{official,share}, claude_{ai_export,code,code_jsonl,md},
│   │                      #   gemini_{chrome,json}, perplexity_{gdpr,md,plugin}
│   └── generic/           # generic_md, whole_file_fallback
├── extractors/            # extract_text  (capability extract.text)
└── gateway/               # ← tool_finder (Decision 1)
```

**Required code change — the linchpin.** `registry.load_builtin_tools()` currently
auto-discovers with `pkgutil.iter_modules(pkg.__path__)`, which is **top-level only**.
Sub-packaging breaks auto-discovery unless it becomes recursive. Change to
`pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + ".")`, still skipping any
path segment whose leaf starts with `_`, and preserving the package-agnostic mount
contract (facade imports this package as top-level `tools`, no `server` package present).

**Zero ID churn.** Tool `id`s are explicit strings in `@register(id=...)`, never derived
from module path (verified: no `__name__`/`__module__`/`__file__` use in `registry.py`).
∴ the registry manifest, facade `/tools` endpoints, and all 14 ContextForge registrations
stay byte-identical. **No CF re-registration; no deploy-semantics change.**

### 3. Promote the record contract out of evidence — home is the open question

Move `NormalizedRecord` / `RecordType` / `DisclosureTier` out of
`server/evidence/normalize.py` and rewrite ~23 importers
(`server.evidence.normalize` → new home).

**Constraint that decides the home — facade mount weight.** The facade container is
deliberately lightweight (no sqlalchemy / agno / duckdb). Its registry load imports every
parser, each of which imports the record contract. Therefore the contract's package
`__init__` **must not** transitively import heavy deps, or the facade FATAL-loops (the
2-day outage ADR-0033 era already paid for once).

- `server/core/` is **disqualified as-is**: `server/core/__init__.py` eagerly imports
  `server.core.session` (postgres/agno/duckdb). `from server.core.records import X` runs
  that `__init__` first → crash in the facade.

Two admissible homes:

- **(A, recommended) `server/contracts/records.py`** — new, deliberately import-light
  package (minimal `__init__`, no heavy deps). Facade-safe; name states the cross-domain
  contract role explicitly.
- **(B) `server/core/records.py` + slim `server/core/__init__.py`** — honors the literal
  "promote to core" intent, but requires making `core/__init__` lazy (widening blast
  radius to every `from server.core import get_postgres_db` site).

**Owner picked "promote to `server/core/records.py`"; this ADR flags that the DB-heavy
`core/__init__` makes it unsafe as written, and asks to confirm A or B before execution.**

## Migration steps (execute only after Decision 3 is confirmed)

1. `git mv` tool_finder → `server/tools/gateway/`; fix `gateway_tools.py` imports.
2. Create `parsers/{messaging,ai_chat,generic}/`, `extractors/` packages (`__init__.py`
   each); `git mv` the 23 tool modules into place.
3. Switch `load_builtin_tools()` to `walk_packages` (recursive, `_`-skip, package-agnostic).
4. Move the record contract to the confirmed home; rewrite ~23 importers + the facade
   docstring's MOUNT↔IMPORT contract note.
5. Gates: `ruff format` + `ruff check` + `mypy` + `pytest` (baseline 208) all green.
6. **Facade smoke test (mandatory, non-negotiable):** build the platform-tools image and
   confirm `/health` reports `registry_ok: true` with the full tool count — this is the
   one failure mode that unit tests cannot catch (heavy-dep import in the light container).
7. Deploy exec tier; verify facade `/tools` count unchanged and CF `platform_tools`
   server still lists 14.

## Consequences

- **Positive:** `evidence/` becomes purely the evidence context; `tools/` is navigable by
  capability; the record contract's cross-domain role is explicit; discovery lives with
  the registry.
- **Cost:** ~23 import rewrites + one discovery-mechanism change + a mandatory facade
  smoke test. Pure import-path churn — no tool IDs, no CF, no runtime behavior changes.
- **Risk (contained):** the facade heavy-import landmine (Decision 3) is the only real
  hazard; step 6 gates against it before any deploy.

## Alternatives considered

- **Leave `normalize.py` in evidence.** Rejected by owner — wanted the cross-domain role
  explicit. (Correct-dependency-direction argument noted, but promotion won.)
- **Top-level `server/gateway/` for tool_finder.** Rejected in favor of
  `server/tools/gateway/` — discovery is fundamentally over the tool registry, so
  co-location beats a new top-level context.
- **Deeper `tools/` nesting (per-vendor dirs).** Rejected — capability-level grouping is
  the right granularity; per-vendor would re-fragment `ai_chat`.
