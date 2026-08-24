# Ingestion readiness — 2026-08-23

> _Byline: Claude Code · Opus 5 · 2026-08-23_
>
> Written for tonight: what is live, the exact commands to start ingesting knowledge, and what
> is blocked. Plain English. Everything below was probed or verified this session — nothing is
> assumed from docs.

## What is live right now (probed 2026-08-23 ~22:4x ET)

| Service | Check | Result |
|---|---|---|
| AgentOS API | `GET http://100.72.169.40:8000/health` | `{"status":"ok"}` — up, restarted today |
| Weaviate | `GET http://100.91.190.107:8081/v1/.well-known/ready` | `200` — ready |
| Postgres (PG18) | direct connect, migrations introspected | up; **all migrations 0026-0030 applied** |
| Neo4j | tcp `100.91.190.107:7687` | open |
| Workbench | `http://100.72.169.40:8020/` | alive but `401` (auth) — and the deployed build is stale; do not rely on it tonight |

Schema state: near-empty and ready — `working.context_record` 1,741 rows (the 08-12 test ingest),
`working.normalized_record` 11, `evidence.evidence_hash` 3, `analysis.evidence_item` 0.

## The two ingest paths that work TONIGHT, zero code changes

### Path A — AI-chat export ZIPs (ChatGPT / Claude / Perplexity) → the RICH path

This is the good path: conversation modeling, lane classification, per-lane Weaviate projection.
It is CLI-only (no HTTP route yet). **Proven live on 2026-08-12: 1,617 Claude rows + 124 ChatGPT
rows landed end-to-end with this exact method.**

Run it inside the live container on ovh-app (avoids local env drift entirely):

```bash
# 1. copy the export zip into the running container
ssh ovh-app 'docker cp /path/on/vps/your-export.zip \
  $(docker ps -qf name=agentos-api):/app/_ingest_test/'

# 2. ingest (context lane — knowledge, NOT evidence)
ssh ovh-app 'docker exec -w /app $(docker ps -qf name=agentos-api) \
  python scripts/ingest_context_chat.py /app/_ingest_test/your-export.zip --engine auto'
```

**Convention (owner, 2026-08-23): database-touching work runs on the VPS, inside the container.**
There is no "override" on that path — the config's `DB_HOST=agentos-db` resolves natively where
production runs, which is the whole point. Running a DB script from the desktop is the exception,
not a supported path; the address override that requires is the tell that the work is standing in
the wrong place. If a desktop run is ever genuinely unavoidable, that is what
`DB_HOST=100.91.190.107` is for — and it should feel like the workaround it is.

### Path B — markdown / text / text-layer PDFs → the HTTP path

```bash
curl -s -X POST "http://100.72.169.40:8000/v1/ingest" \
  -H "Authorization: Bearer $OS_SECURITY_KEY" \
  -F "file=@/path/to/document.pdf" \
  -F 'lane=context'
# returns 202 + receipt_id; poll:
curl -s "http://100.72.169.40:8000/v1/knowledge/items" -H "Authorization: Bearer $OS_SECURITY_KEY"
```

The bearer is the API security key from the platform `.env` on the VPS. Path B produces FLAT
records (no conversation modeling) — fine for documents, wrong for chat exports; chat ZIPs
should always go through Path A.

## Verify it landed (run after any ingest)

```sql
-- rows by source, newest ingest visible immediately
SELECT source, count(*), max(created_at) FROM working.context_record GROUP BY source;
-- projection status: NULL = not yet pushed to Weaviate (the drain is best-effort/deferred)
SELECT count(*) FILTER (WHERE weaviate_synced_at IS NULL) AS pending,
       count(*) FILTER (WHERE weaviate_synced_at IS NOT NULL) AS synced
FROM working.context_record;
```

Connect with `DB_HOST=100.91.190.107`, db `ai` (or the new non-superuser role `agno_app`).

## Blocked tonight — do not fight these, route around them

| Blocker | Effect tonight | Fix (later) |
|---|---|---|
| `docling` not in requirements.txt | **DOCX / PPTX / XLSX / HTML uploads FAIL** with receipt status `failed` | add the `document-ai` extra to the deployed image (weigh its local-model download against the CPU-only box); tracked as URGENT-TODO 17 |
| OCR extras not installed | **Scanned/image-only PDFs ingest as empty text**, silently | install `ocr` extra on the VPS image; URGENT-TODO 18 |
| Evidence lane blocks documents | a PDF cannot be ingested with `lane=evidence` at all | by design pending ADR-0044 review; URGENT-TODO 19 |
| Custody flag unset (`SBV_CUSTODY_ENABLED`) | message-transcript ingests skip custody reconciliation | owner ruled mandatory-at-capture; standalone hashing process must land first (the plan's custody item) — until then, keep evidence-lane message ingests OFF |
| Workbench build stale | no UI-driven ingest tonight | redeploy workbench (also a prerequisite of the Temporal approval work, D-067) |

**Tonight's rule of thumb: everything goes in as knowledge/context. Nothing touches the evidence
lane until the hashing process lands.** That matches the promotion architecture — ingest workable
now, promote to evidence deliberately later; the promotion guard (live since tonight, migration
0030) will hash-check anything you promote.

## The single next command

If you have a Claude or ChatGPT export ZIP ready, Path A step 1+2 is the whole thing. First run
should be a SMALL export; verify with the SQL above; then batch the rest.
