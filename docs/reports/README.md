# docs/reports — generated, not tracked

> _Byline: Claude Code · Opus 5 (1M) · 2026-08-01_

**Everything in this directory except this file is gitignored.** Generated reports
embed real message content — the first one produced contained a name, date of
birth, and social security number in a lineage sample. The generator is tracked;
its output never is.

## Generate

```bash
# from a desktop over the tailnet (.env holds agentos-db, which only resolves
# inside the compose network)
uv run python scripts/evidence_pipeline_report.py --host <data-box-tailnet-ip>

# from inside the compose network, DB_HOST resolves on its own
uv run python scripts/evidence_pipeline_report.py

# suppress message previews before the report leaves this machine
uv run python scripts/evidence_pipeline_report.py --host <ip> --no-content
```

Each run writes three files stamped with a UTC timestamp:

| File | What it is |
|---|---|
| `evidence-pipeline-<stamp>.md` | durable, diffable |
| `evidence-pipeline-<stamp>.html` | the viewer — open it in a browser |
| `evidence-pipeline-<stamp>.json` | the rows, for anything downstream |

## What it reports

Every stage of the evidence pipeline, per layer and per artifact:

- **Layer map** — every table with its architectural role and live row count
- **Reconciliation** — per artifact: does what landed match what the file claims
- **Per-artifact funnel** — declared → parsed → rejected → raw → spine → attestations
- **Ingest run ledger** — every attempt, including failures and rollbacks
- **Dropped and rejected records** — what never made it in, and why
- **Attestation status** — corroborated / single-source / conflicted
- **Clock disagreement** — embedded vs filename vs filesystem export times
- **Derivation lineage** — each spine record back to its raw row and acquisition
- **Integrity checks** — the invariants, each of which must be zero
- **Artifacts that cannot be reconciled** — blind spots

No number is computed by the script. Every figure comes from a view defined in
`sql/0012_pipeline_visibility.sql` and `sql/0013_raw_all_and_funnel_across_formats.sql`,
so the report and a hand-written query cannot disagree.
