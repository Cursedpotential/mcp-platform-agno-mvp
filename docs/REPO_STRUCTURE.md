# REPO STRUCTURE — the one structure

> **Authoritative for:** where every kind of file goes. Entry point: `docs/PROJECT_CANON.md` (§0).
> The point of this doc: a new capability has exactly ONE correct home, so iterations never scatter
> into competing architectures again. Last updated: 2026-06-13.
> _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## The one active build

`Agno-MCP-Platform/` is **the only active repo**. Everything under the workspace root *outside* it
is reference (donor archives, mined code, planning history). **Never build a parallel stack.**

## Canonical layout (`Agno-MCP-Platform/`) — ONE backend boundary (ADR-0033)

> Repacked 2026-07-09 (ADR-0033): every backend package lives under `server/`; import paths
> are `server.*`. The old flat siblings (`app/ agents/ db/ evidence/ gateway/ tools/ chatminer/`)
> are gone.

```
server/         THE backend — one boundary, domain-separated inside:
  api/          AgentOS entrypoint — main.py (base_app, router, HITL+knowledge), mcp_main.py, config.yaml
  core/         settings.py (model factory), session.py, embedder.py (NimEmbedder), reranker.py, url.py
  agents/       factory.py (build_agent_team), providers.py (context providers, learning, Graphiti MCP), instructions
  evidence/     THE SPINE (Python chassis) — see below; includes tool_finder/ (G4 gateway, was gateway/)
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
  custody.py      THE single entry gate — hash → evidence row → write-once blob. ONLY writer of the `evidence` schema (append-only, immutable).
  registry.py     capability-based ToolRegistry (@register, load_builtin_tools auto-discovery; supports polyglot/HTTP/MCP runners)
  normalize.py    NormalizedRecord (bitemporal: occurred_at / knowledge_time / disclosure_tier / attrs) — the ONE canonical shape
  store.py        normalized records → `analysis` schema + knowledge-engine ingest
  workflows.py    named workflows on native agno.workflow, custody-gated
  cli.py          `python -m server.evidence ...`
  tools/          ATOMIC TOOL MODULES — one capability per file, self-registering (incl. cross-domain extract_text)
    _common.py    shared helpers (underscore prefix = NOT a tool; skipped by auto-discovery)
    <format>.py   e.g. chatgpt_export.py — one parser per format/platform
  tool_finder/    G4 token-efficient tool gateway (was gateway/): content_store, toolfinder, api
```

## Placement rules (where does X go?)

| You are adding… | It goes… |
|---|---|
| A new parser/extractor/analysis tool (Python) | `evidence/tools/<name>.py` — one capability, self-register via `@register` |
| A tool that's really a TS/Go binary or external service | wrap as an **MCP service behind Agno**; register in the spine via the polyglot/HTTP runner (don't rewrite it in Python unless trivial) |
| A shared helper (not itself a tool) | `evidence/tools/_helpers.py` (underscore prefix) or `evidence/<module>.py` |
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
  Agno-MCP-Platform-alpha/chatminer/  Python PARSER CORE to vendor into evidence/tools/
../extracted-code/                    mined reusable code (+ MANIFEST.md)
```

**Never ingest** `Secrets/` or case-data directories into Knowledge. Secrets live only in gitignored `.env` (local + VPS).
