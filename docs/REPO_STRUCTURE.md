# REPO STRUCTURE — the one structure

> **Authoritative for:** where every kind of file goes. Entry point: `docs/PROJECT_CANON.md` (§0).
> The point of this doc: a new capability has exactly ONE correct home, so iterations never scatter
> into competing architectures again. Last updated: 2026-07-09 (D-026: tools + registry promoted
> out of the evidence spine to `server/tools/`).
> _Byline: Claude Code · Opus 4.8 · 2026-06-13 (D-026 update: Claude Sonnet 5 · 2026-07-09)_

## The one active build

`Agno-MCP-Platform/` is **the only active repo**. Everything under the workspace root *outside* it
is reference (donor archives, mined code, planning history). **Never build a parallel stack.**

## Canonical layout (`Agno-MCP-Platform/`) — ONE backend boundary (ADR-0033)

> Repacked 2026-07-09 (ADR-0033): every backend package lives under `server/`; import paths
> are `server.*`. The old flat siblings (`app/ agents/ db/ evidence/ gateway/ tools/ chatminer/`)
> are gone. Amended 2026-07-09 (D-026): the atomic-tools capability layer + registry moved OUT
> of `server/evidence/` to top-level `server/tools/` — tools are cross-domain (evidence, analysis,
> agents, workflows, CLI all consume them), not evidence-owned.

```
server/         THE backend — one boundary, domain-separated inside:
  api/          AgentOS entrypoint — main.py (base_app, router, HITL+knowledge), mcp_main.py, config.yaml
  core/         settings.py (model factory), session.py, embedder.py (NimEmbedder), reranker.py, url.py
  agents/       factory.py (build_agent_team), providers.py (context providers, learning, Graphiti MCP), instructions
  evidence/     THE SPINE (Python chassis) — see below; includes tool_finder/ (G4 gateway, was gateway/)
  tools/        CROSS-DOMAIN CAPABILITY LAYER (D-026) — registry + atomic tool modules; see below
  analysis/     behavioral domain: detection.py, patterns.py (OntologyChain), court_language.py, milvus_forensic.py, semantica_wiring.py + config/
  vendored/
    chatminer/  vendored parser core (import-only)
ui/             CopilotKit shell (G1) — DEFERRED, not built yet
shared/         cross-boundary contracts — created only when ui/ needs them (DEFERRED)
sql/            numbered migrations only: NNNN_name.sql (e.g. 0003_normalized_records.sql)
docker/         one folder per service image: postgres/ (pg_duckdb), tools/, sandbox/, gateway/, milvus/, n8n/, coolify-mcp/
compose*.yaml   the stack, split by tier (compose.yaml / compose.exec.yaml / compose.data*.yaml)
evals/          agno-eval cases (harness-first)
scripts/        format.sh, validate.sh, ingest_*, generate_requirements.sh, repack_to_server_layout.py
knowledge/      curated knowledge inputs (NEVER secrets/case-data)
docs/           canon + the authoritative docs + adr/ + planning/ + wiki/ + visualizations/
tests/          the pytest suite (186)
```

## The spine — `server/evidence/`

```
server/evidence/
  __init__.py     lazy (PEP 562) exports so light consumers don't drag in sqlalchemy/agno
                  (re-exports `registry`/`ToolRegistry` from server.tools.registry for back-compat)
  custody.py      THE single entry gate — hash → evidence row → write-once blob. ONLY writer of the `evidence` schema (append-only, immutable).
  normalize.py    NormalizedRecord (bitemporal: occurred_at / knowledge_time / disclosure_tier / attrs) — the ONE canonical shape
  store.py        normalized records → `analysis` schema + knowledge-engine ingest
  workflows.py    named workflows on native agno.workflow, custody-gated
  cli.py          `python -m server.evidence ...`
  tool_finder/    G4 token-efficient tool gateway (was gateway/): content_store, toolfinder, api
```

## The capability layer — `server/tools/` (D-026)

Cross-domain: consumed by evidence, analysis, agents, workflows, and the CLI — not owned by any
single domain, so it lives at the top level of `server/`, a sibling of `evidence/`, not nested
inside it.

```
server/tools/
  __init__.py     package marker
  registry.py     capability-based ToolRegistry (@register, load_builtin_tools auto-discovery over server.tools; supports polyglot/HTTP/MCP runners)
  _common.py      shared helpers (underscore prefix = NOT a tool; skipped by auto-discovery)
  _sbv_client.py  SBV (SMS Backup & Restore) session-cookie REST client — shared by sbv_sms.py and the docker/tools facade
  <format>.py     e.g. chatgpt_official.py — one parser per format/platform
```

The `docker/tools` platform-tools facade (`docker/tools/tools/facade.py`) volume-mounts the
**whole `server/` tree** read-only at `/opt/tools/server` (`compose.yaml`/`compose.exec.yaml`:
`./server:/opt/tools/server:ro`) — not just `server/tools/` — because `server.tools.*` has real
transitive deps outside itself (`server.evidence.normalize` for the record schema,
`server.vendored.chatminer` for the parser core; both lightweight, no sqlalchemy/agno at import
time). With `/opt/tools` on `sys.path`, the facade imports it as plain `server.tools.registry` /
`server.tools._sbv_client` — the same import path the main app uses — see the facade's module
docstring for the full mount<->import contract.

## Placement rules (where does X go?)

| You are adding… | It goes… |
|---|---|
| A new parser/extractor/analysis tool (Python) | `server/tools/<name>.py` — one capability, self-register via `@register` |
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
