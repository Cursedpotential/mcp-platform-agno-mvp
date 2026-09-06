# Parser Activity Runtime

Production Go service for the two atomic parser Activities used by the n8n
wrappers inside the Proffer. It registers every supported
SBV parse-only adapter, persists streamed extraction bundles outside request
and Temporal history, and returns compact UUID references only.

## Coolify application

- Build pack: Dockerfile
- Repository base directory: `/`
- Dockerfile: `/docker/parser-activity-runtime/Dockerfile`
- Exposed port: `8090`
- Health check: `GET /healthz`
- Persistent storage: bind the shared host parser-bundle directory at
  `/data/proffer/parser-bundles`, exactly matching the worker path
- Watch paths: `engine/**`, `vendored/sbv/**`, and
  `docker/parser-activity-runtime/**`

Required runtime environment:

| Variable | Purpose |
|---|---|
| `PLATFORM_DATABASE_URL` | PostgreSQL connection string for the fresh `platform` database; `DATABASE_URL` is accepted only as a compatibility fallback. |
| `PARSER_ACTIVITY_TOKEN` | Dedicated bearer token shared only with the n8n parser Activity credentials. |
| `PARSER_BUNDLE_DIR` | Durable bundle path; the image default is `/data/proffer/parser-bundles`. |

Optional environment:

| Variable | Default |
|---|---|
| `PARSER_ACTIVITY_ADDR` | `:8090` |

SQL `0036_context_import_foundation.sql` (or the consolidated fresh-database
baseline containing the same `context.*` contracts) must be installed before
the service can become ready.

## Routes

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| `GET` | `/healthz` | none | Process liveness for Coolify. |
| `GET` | `/readyz` | none | PostgreSQL readiness and registered parser count. |
| `GET` | `/capabilities` | bearer | Immutable parser/version/format capability inventory. |
| `POST` | `/activities/select_parser_activity` | bearer | Select and persist an exact parser version pin. |
| `POST` | `/activities/execute_parser_activity` | bearer | Execute only the pinned parser and return bundle/receipt UUIDs. |

Both Activity requests use the reference-only wire shape:

```json
{
  "request_id": "workflow-id",
  "source_version_ref": "source-version-uuid",
  "declared_format": "sms_xml_backup",
  "refs": {
    "original": "retained-object-uuid",
    "parser_selection": "selection-receipt-uuid"
  }
}
```

The select request omits `original` and `parser_selection`; the execute request
requires both. Source bytes, extracted rows, metadata payloads, and record
arrays are rejected at this HTTP boundary.

## Build and verification

From `engine/`:

```text
go test -tags fts5 ./...
go vet -tags fts5 ./...
go build -tags fts5 ./cmd/parser-activity-runtime
```

The `fts5` tag is mandatory because the registered SBV adapters use the
vendored SBV module. The Coolify Dockerfile sets `CGO_ENABLED=1` and the tag.
