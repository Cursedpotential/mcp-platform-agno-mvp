# Universal import worker

This image is the sole Temporal worker for `uiw.UniversalImportWorkflow`. It
registers the workflow and all 23 canonical Activity names on one dedicated
task queue. It must never use the existing `evidence-pipeline` queue and does
not replace or modify the existing Python Temporal worker.

The two parser stages call authenticated n8n mini-workflows. Every other stage
uses the PostgreSQL, immutable-object, observation, hashing, raw-generation,
normalization, lineage, sealing, and publication implementations under
`engine/`.

Four absolute storage roots are required. Coolify mounts identical container
paths into each service that produces or consumes their `file://` references:

- `/data/uiw/source-objects`
- `/data/uiw/parser-bundles` (shared with `parser-activity-runtime`)
- `/data/uiw/normalized-bundles`
- `/data/uiw/inventory-manifests`

The process validates those roots, PostgreSQL database name `platform`, the
active migration `0036` ledger row, all 20 context tables, and the constrained
runtime role before it starts polling Temporal.
