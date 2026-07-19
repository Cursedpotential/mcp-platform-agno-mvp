# Knowledge Workbench API

> _Byline: Claude Code · Sonnet (agent) · 2026-07-19_

A staging + promote surface. It stages uploaded files locally (LanceDB
whole-file store) and promotes them through the **existing** platform
ingestion API. It never chunks, embeds, or writes Milvus/Postgres itself —
see `compose.workbench.yaml` (repo root) for how this deploys, and
`docs/PROJECT_CANON.md` for where this fits in the wider platform.

## Layering

`types` -> `config` -> `repo` -> `service` -> `runtime`, lower layers never
import from higher ones (enforced by `tests/test_structure.py`). `boto3` and
`lancedb` are confined to `app/repo/`.

| Layer | Files | Role |
|---|---|---|
| `config` | `settings.py` | S3-agnostic object-store env knobs + LanceDB path + spine URL |
| `repo` | `object_store_client.py`, `lancedb_client.py`, `staging.py` | boto3 + LanceDB, confined here |
| `service` | `upload.py`, `detect.py`, `files.py`, `documents.py`, `promote.py`, `metadata.py` | business logic, no SDK imports |
| `runtime` | `upload.py`, `files.py`, `promote.py`, `documents.py`, `health.py`, `metrics.py` | FastAPI routers |

## Endpoints

- `POST /api/upload` — stream-hash + stage a file (dedupes by sha256)
- `GET /api/files`, `GET /api/files/{id}`, `PATCH /api/files/{id}` — list/detail/edit staged files
- `POST /api/promote/{id}`, `POST /api/promote-all` — push staged file(s) through the platform ingestion API
- `GET /api/documents/stats` — staging-table counts by status/type
- `GET /health`, `GET /metrics`

## Origin

Scaffolded from a donor "Agentic RAG Vector Starter Kit" (Backblaze B2 +
LanceDB + chunking/embedding pipeline). The workbench keeps the kit's layered
`app/` structure and its whole-file object-store + LanceDB plumbing, but
**deletes every chunking/embedding/retrieval/chat module** (`chunker.py`,
`embedder.py`, `pipeline.py`, `classifier.py`, `contextualizer.py`, `crag.py`,
`reranker.py`, `retrieval.py`, `summarizer.py`, `chat.py`, `sessions.py`,
`dashboard.py`, and their repo-layer counterparts) — this app is staging-only;
the platform's own ingestion API owns chunking/embedding/vector writes.

The donor kit's MIT license (Backblaze, Inc.) is preserved at
`../LICENSE.b2-kit` per its terms; this directory's own code is licensed
under this repo's root `LICENSE`.
