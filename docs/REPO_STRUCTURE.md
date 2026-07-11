# REPO STRUCTURE — the one structure

> **Authoritative for:** where every kind of file goes. Entry point: `docs/PROJECT_CANON.md` (§0).
> The point of this doc: a new capability has exactly ONE correct home, so iterations never scatter
> into competing architectures again. Last updated: 2026-07-10 (ADR-0035: `server/tools/`
> sub-namespaced by capability, `tool_finder/` → `server/tools/gateway/`, record contract →
> `server/contracts/records.py`). Progressive-disclosure detail for each package now lives in that
> package's own `AGENTS.md` (root map: `../AGENTS.md`) — this doc stays the single structural index.
> _Byline: Claude Code · Opus 4.8 · 2026-06-13 (D-026 update: Claude Sonnet 5 · 2026-07-09; ADR-0035 update: Claude Opus 4.8 · 2026-07-10)_

## The one active build

`Agno-MCP-Platform/` is **the only active repo**. Everything under the workspace root *outside* it
is reference (donor archives, mined code, planning history). **Never build a parallel stack.**

## Canonical layout (`Agno-MCP-Platform/`) — ONE backend boundary (ADR-0033)

> Repacked 2026-07-09 (ADR-0033): every backend package lives under `server/`; import paths
> are `server.*`. The old flat siblings (`app/ agents/ db/ evidence/ gateway/ tools/ chatminer/`)
> are gone. Amended 2026-07-09 (D-026): the atomic-tools capability layer + registry moved OUT
> of `server/evidence/` to top-level `server/tools/` — tools are cross-domain (evidence, analysis,
> agents, workflows, CLI all consume them), not evidence-owned. Amended 2026-07-10 (ADR-0035):
> `server/tools/` sub-namespaced by capability (`parsers/{messaging,ai_chat,generic}/`,
> `extractors/`); the G4 gateway moved `server/evidence/tool_finder/` → `server/tools/gateway/`;
> the record contract (`NormalizedRecord`) moved `server/evidence/normalize.py` →
> `server/contracts/records.py` (import-light, facade-safe — `normalize.py` is now a deprecated
> re-export shim).

```
server/         THE backend — one boundary, domain-separated inside:
  api/          AgentOS entrypoint — main.py (base_app, router, HITL+knowledge), mcp_main.py, config.yaml
  core/         settings.py (model factory), session.py, embedder.py (NimEmbedder), reranker.py, url.py
  contracts/    IMPORT-LIGHT record contract (ADR-0035) — records.py (NormalizedRecord/RecordType/DisclosureTier); see below
  agents/       factory.py (build_agent_team), providers.py (context providers, learning, Graphiti MCP), instructions, tools/ (@tool wrappers)
  evidence/     THE SPINE (Python chassis) — see below; purely evidence-domain since ADR-0035
  tools/        CROSS-DOMAIN CAPABILITY LAYER (D-026), sub-namespaced by capability (ADR-0035) — registry + parsers/extractors/gateway; see below
  analysis/     behavioral domain: detection.py, patterns.py (OntologyChain), court_language.py, milvus_forensic.py, semantica_wiring.py + config/
  vendored/
    chatminer/  vendored parser core (import-only)
    semantica/  vendored project (installed dist, not `server.vendored.semantica`-imported)
ui/             CopilotKit shell (G1) — DEFERRED, not built yet
shared/         cross-boundary contracts — created only when ui/ needs them (DEFERRED)
sql/            numbered migrations only: NNNN_name.sql (e.g. 0003_normalized_records.sql)
docker/         one folder per service image: postgres/ (pg_duckdb), tools/, sandbox/, gateway/, milvus/, n8n/, coolify-mcp/
compose*.yaml   the stack, split by tier (compose.yaml / compose.exec.yaml / compose.data*.yaml)
evals/          agno-eval cases (harness-first)
scripts/        format.sh, validate.sh, ingest_*, generate_requirements.sh, repack_to_server_layout.py
knowledge/      curated knowledge inputs (NEVER secrets/case-data)
docs/           canon + the authoritative docs + adr/ + planning/ + wiki/ + visualizations/
tests/          the pytest suite (208)
```

Progressive-disclosure detail (files, dependency direction, "how do I add X") for `server/` and
each of `contracts/`, `evidence/`, `tools/`, `agents/` now lives in that directory's own
`AGENTS.md` — this section stays the structural index, not restated blow-by-blow below.

## The record contract — `server/contracts/` (ADR-0035)

```
server/contracts/
  __init__.py     deliberately dependency-free (no sqlalchemy/agno/duckdb) — facade-safety, see below
  records.py      NormalizedRecord (bitemporal: occurred_at / knowledge_time / disclosure_tier / attrs), RecordType, DisclosureTier — the ONE canonical shape
```

Promoted out of `server/evidence/normalize.py` (Option A, owner-confirmed) because 15+ parser
modules + evidence internals + tests + the facade all import it — it's the platform's cross-domain
record contract, not an evidence-private type. Must stay import-light: the dep-light
`docker/tools` facade imports every parser, and every parser imports this. `server/core/` was
disqualified as the new home because `server/core/__init__.py` eagerly imports
`server.core.session` (sqlalchemy/agno/duckdb). See `server/contracts/AGENTS.md` and ADR-0035.

## The spine — `server/evidence/`

```
server/evidence/
  __init__.py     lazy (PEP 562) exports so light consumers don't drag in sqlalchemy/agno
                  (re-exports `registry`/`ToolRegistry` from server.tools.registry for back-compat)
  custody.py      THE single entry gate — hash → evidence row → write-once blob. ONLY writer of the `evidence` schema (append-only, immutable).
  normalize.py    DEPRECATED re-export shim (ADR-0035) — `from server.contracts.records import *`. New code imports server.contracts.records directly.
  store.py        normalized records → `analysis` schema + knowledge-engine ingest
  workflows.py    named workflows on native agno.workflow, custody-gated
  cli.py          `python -m server.evidence ...`
```

`tool_finder/` (the G4 gateway) moved to `server/tools/gateway/` in ADR-0035 — `evidence/` is now
purely the evidence bounded context. See `server/evidence/AGENTS.md`.

## The capability layer — `server/tools/` (D-026, sub-namespaced ADR-0035)

Cross-domain: consumed by evidence, analysis, agents, workflows, and the CLI — not owned by any
single domain, so it lives at the top level of `server/`, a sibling of `evidence/`, not nested
inside it.

```
server/tools/
  __init__.py            package marker
  registry.py             capability-based ToolRegistry (@register, load_builtin_tools —
                           pkgutil.walk_packages, recursive since ADR-0035 — over server.tools)
  _common.py               shared helpers (underscore prefix = NOT a tool; skipped by auto-discovery)
  _chatminer_adapter.py    ChatMiner -> NormalizedRecord bridge (underscore-prefixed)
  _sbv_client.py           SBV (SMS Backup & Restore) session-cookie REST client — shared by sbv_sms.py and the docker/tools facade
  parsers/
    messaging/              imessage_*, sms_xml, sbv_sms, facebook_*, messaging_{csv,transcript}
    ai_chat/                 chatgpt_*, claude_*, gemini_*, perplexity_*
    generic/                  generic_md, whole_file_fallback
  extractors/               extract_text (capability extract.text)
  gateway/                  G4 token-efficient tool gateway (was server/evidence/tool_finder/) — content_store, toolfinder, api
```

Full file inventory, the capability model, and "how to add a parser" live in
`server/tools/AGENTS.md` — not restated here.

The `docker/tools` platform-tools facade (`docker/tools/tools/facade.py`) volume-mounts the
**whole `server/` tree** read-only at `/opt/tools/server` (`compose.yaml`/`compose.exec.yaml`:
`./server:/opt/tools/server:ro`) — not just `server/tools/` — because `server.tools.*` has real
transitive deps outside itself (`server.contracts.records` for the record schema,
`server.vendored.chatminer` for the parser core; both lightweight, no sqlalchemy/agno at import
time). With `/opt/tools` on `sys.path`, the facade imports it as plain `server.tools.registry` /
`server.tools._sbv_client` — the same import path the main app uses — see the facade's module
docstring for the full mount<->import contract.

## Placement rules (where does X go?)

| You are adding… | It goes… |
|---|---|
| A new parser/extractor tool (Python) | `server/tools/parsers/{messaging,ai_chat,generic}/<name>.py` or `server/tools/extractors/<name>.py` (ADR-0035) — one capability, self-register via `@register`; `load_builtin_tools()` auto-discovers it, nothing else to wire |
| A tool that's really a TS/Go binary or external service | wrap as an **MCP service behind Agno**; register in the spine via the polyglot/HTTP runner (don't rewrite it in Python unless trivial) |
| A shared helper (not itself a tool) | `server/tools/_helpers.py` (underscore prefix) or `server/evidence/<module>.py` (evidence-domain-specific) |
| A DB schema change | new `sql/NNNN_*.sql` migration (never edit an applied one) |
| A new service/container | `docker/<service>/` + a block in `compose.yaml` |
| A decision | an ADR in `docs/adr/` (supersede, don't edit) AND update `PROJECT_CANON.md` §5 same change |
| A stub you couldn't avoid | `# STUB: <tag>` in code + a row in `docs/DEBT.md` (ADR-0021) |

## Reference / read-only (never edit, never build inside)

```
../dev-resources/Archives/
  dial-stack/                         TS forensic/analysis/gateway DONOR (DIAL runtime dropped; mine capabilities)
    utilities/                        DEFERRED external libs — "good stuff, dig later" (incl. apps/ml-nlp/Tether = Part-2 ML)
    docs/, .plannotator/, .planning/  CONTEXT only (markdown/prompts) — not code
  Agno-MCP-Platform-alpha/chatminer/  Python PARSER CORE to vendor into server/tools/
../extracted-code/                    mined reusable code (+ MANIFEST.md)
```

**Never ingest** `Secrets/` or case-data directories into Knowledge. Secrets live only in gitignored `.env` (local + VPS).
