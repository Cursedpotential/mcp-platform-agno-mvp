# Knowledge Workbench API

> _Byline: Claude Code · Sonnet (agent) · 2026-07-19 (drift-fix 2026-08-14 Claude Code · glm-5.2:cloud: Milvus → Weaviate per ADR-0040; note data-vector DOWN since 2026-08-10)_
> _Current-product repair: Codex · GPT-5 · 2026-08-15._
> _Neutral Portkey streaming chat: Codex · GPT-5 · 2026-08-16._
<!-- Updated by: Codex (migration-passes/doc-patching) | Date: 2026-08-15 | Rev: 1 | Platform: Codex / win32 | Changes: Correct deploy path, layering, vector-store, and Knowledge status | Context: Align operator documentation with current source without claiming uncommitted work is deployed -->

A staging + promote surface. It stages uploaded files locally (LanceDB
whole-file store) and promotes them through the **existing** platform
ingestion API. It never chunks, embeds, or writes the vector/PG stores itself
(~~Milvus~~ → Weaviate per ADR-0040; `data-vector`/Milvus DOWN deliberately since 2026-08-10) —
see `deploy/workbench.yaml` for the Coolify deployment manifest and
`docs/PROJECT_CANON.md` for where this fits in the wider platform.

> **Implementation status — 2026-08-15:** the case-scoped Knowledge page and its
> Workbench API/service changes are committed and pushed to `main`, but not deployed or
> verified against live Weaviate/Graphiti services. See the R9 handoff for current gates.

> **Additional held slice:** the Matter/CourtCase BFF and Knowledge-to-Evidence flow are
> locally tested, committed, and pushed. Migration
> `sql/0030_matter_case_foundation.sql` remains unapplied and the feature remains
> undeployed. Commit `be286a8` adds a redacted evidence-detail proxy so review can
> inspect the exact canonical record and custody chain. The Workbench owns no
> case-domain truth; it proxies and validates neutral spine contracts.
> Commit `7b6aaf6` adds a read-only proxy for the exact Matter/item
> court-export evaluation. It distinguishes actual `analysis.vw_court_export`
> membership from stricter supplemental checks and performs no authentication,
> confidence, redaction, or legal-release mutation.

> **Neutral chat slice:** `/v1/chat` now accepts Vercel AI SDK UI messages and
> returns a plain-text stream through Portkey. A saved `PORTKEY_CONFIG` is
> mandatory so provider fallback and audit remain gateway-owned. The code is
> locally tested and built but is not deployed; the live Coolify app still
> tracks `workbench/sprint`, and activation remains owner-gated.

## Layering

`types` -> `config` -> `repo` -> `service` -> `runtime` is the declared dependency
direction; lower layers should not import higher ones. `tests/test_structure.py` is
present and enforces this boundary. SDK-facing clients remain under `app/repo/`.

| Layer | Files | Role |
|---|---|---|
| `config` | `settings.py` | S3-agnostic object-store env knobs + LanceDB path + spine URL + MCP server list |
| `repo` | `object_store_client.py`, `lancedb_client.py`, `staging.py`, `mcp_client.py`, `spine_client.py`, `graphiti_client.py`, `opencode_client.py` | Object storage + LanceDB + MCP/Graphiti + spine/OpenCode HTTP clients |
| `service` | upload/files/promote/runs/inspect/flags/knowledge/Graphiti/tools/repairs/chat/Copilot/classification/sentiment/comparison modules | Business orchestration over repository clients and the neutral Portkey HTTP adapter |
| `runtime` | matching FastAPI routers under `app/runtime/` | HTTP validation and error translation |

## Endpoints

- `POST /api/upload` — stream-hash + stage a file (dedupes by sha256)
- `GET /api/files`, `GET /api/files/{id}`, `PATCH /api/files/{id}` — list/detail/edit staged files
- `POST /api/promote/{id}`, `POST /api/promote-all` — framework-neutral document ingest through `/v1/ingest`, tracked by the durable `/v1/runs/{run_id}` receipt; AI-chat exports remain denied by D-082
- `POST /api/runs` (json `{staged_id, workflow, domain, mode, source_meta}` or multipart `file`), `GET /api/runs`, `GET /api/runs/{id}` — proxy to the spine's `/v1/runs` pipeline (custody → parse → store → knowledge)
- `POST /api/runs/{id}/continue`, `POST /api/runs/{id}/abort`, `POST /api/runs/{id}/retry` — C2 supervised-gate controls
- `POST /api/runs/parse-dryrun` (json `{sha256}` or multipart `file`) — C3 dry-run parse (which parser would claim this file), no run created
- `GET /api/records`, `PATCH /api/records/{id}/meta` — C3 per-run record browser (parse-quality review) + curation edits
- `GET /api/schemas` — C3 raw PG table/column/count views plus **Weaviate** collection
  inspection. The spine currently also returns the same vector result under a deprecated
  `milvus` compatibility key because the Workbench schema component/types still use that
  name; the label is stale, not a live Milvus read.
- `POST /api/verify/{sha256}` — C3 active hash verification (re-fetch + recompute, walks the H1/H2/H3 custody chain for full-tier runs)
- `POST /api/flags`, `GET /api/flags`, `PATCH /api/flags/{id}` — C3 corroboration flags ("needs corroborating evidence")
- `GET /api/knowledge/search` — evidence-only owner search through the native,
  horizon-prefiltered route. Non-evidence and cross-lane semantic search fail closed until
  their framework-neutral projections exist.
- `GET /api/knowledge/contents` — locally verified proxy to the Platform API's paginated knowledge-content catalog.
- `GET /api/graphiti/search`, `GET /api/graphiti/episodes` — locally verified, read-only
  Graphiti memory inspection; a Graphiti group is a namespace, not an authorization boundary.
- `GET|POST /api/matters`, `GET /api/matters/{id}`, and
  `POST /api/matters/{id}/court-cases` — held Workbench proxies to neutral Matter APIs.
- `POST /api/matters/{id}/knowledge/resolve` and
  `GET|POST /api/matters/{id}/evidence-items` — exact source resolution and default-unsafe,
  idempotent evidence promotion; held until migration/application/deployment review.
- `GET /api/matters/{id}/evidence-items/{item_id}` — Matter-scoped, redacted canonical
  record/H1/source/file-node custody inspection; storage paths and private metadata are
  excluded.
- `GET /api/matters/{id}/evidence-items/{item_id}/court-readiness` — read-only,
  Matter-scoped export-view membership plus typed supplemental blocker/gate detail;
  database status only, not an admissibility conclusion.
- `GET /api/tools`, `POST /api/tools/call` — proxy to every configured MCP server (`MCP_SERVERS` env) for the Tool Explorer
- `GET /api/documents/stats` — staging-table counts by status/type
- `POST /v1/chat` — framework-neutral Vercel AI SDK text stream; Portkey saved
  config owns routing/fallback and every request carries a trace id plus audit metadata.
- `GET /health`, `GET /metrics`

## Inbound authentication

`WORKBENCH_API_KEY` is mandatory. The Workbench fails closed when it is empty:
all API routes, API documentation, and static frontend paths return `503`. The
exact `/health` path is the sole public exception so the container healthcheck
continues to work.

API clients send `Authorization: Bearer <WORKBENCH_API_KEY>`. Browsers can use
HTTP Basic authentication with username `owner` and the same key as the
password. Successful requests expose the authenticated `owner` principal in
the request scope; the Workbench's outbound Platform API bearer remains a
separate runtime-read credential and must never be used as the inbound Workbench key.

## Origin

Scaffolded from a donor "Agentic RAG Vector Starter Kit" (Backblaze B2 +
LanceDB + chunking/embedding pipeline). The workbench keeps the kit's layered
`app/` structure and its whole-file object-store + LanceDB plumbing, but
**deletes every chunking/embedding/retrieval/chat module** (`chunker.py`,
`embedder.py`, `pipeline.py`, `classifier.py`, `contextualizer.py`, `crag.py`,
`reranker.py`, `retrieval.py`, `summarizer.py`, the donor `chat.py`, `sessions.py`,
`dashboard.py`, and their repo-layer counterparts) — this app is staging-only;
the platform's own ingestion API owns chunking/embedding/vector writes. The
current `app/runtime/chat.py` is new Horizon code: a stateless Portkey gateway
adapter, not the donor retrieval/chat implementation.

The donor kit's MIT license (Backblaze, Inc.) is preserved at
`../LICENSE.b2-kit` per its terms; this directory's own code is licensed
under this repo's root `LICENSE`.
