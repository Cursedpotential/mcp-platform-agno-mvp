# Evidence Custody Inspection — Pre-Mortem (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

STATUS: BUILT LOCALLY, VERIFIED, UNCOMMITTED, UNDEPLOYED

## Intended outcome

A Matter operator can reopen any promoted evidence item and inspect the exact
canonical normalized record, its H1 custody hash, source acquisition state,
optional file-node coordinates, and promotion provenance. A reviewer cannot
record a decision unless that Matter-scoped detail has loaded successfully.

## Pre-mortem failures and controls

| Failure | Consequence | Planned control | Residual risk |
|---|---|---|---|
| A reviewer decides from a quote card alone | The decision is not grounded in the complete canonical record | Review dialog loads the exact record and custody detail before enabling submission | Human review can still be mistaken; rationale remains mandatory |
| Matter A requests Matter B's item | Cross-matter evidence disclosure | One fail-closed join begins with both item ID and Matter ID; missing or broken scope returns 404 | Named-principal Matter grants remain future work |
| A row survives while its promotion/custody joins drift | UI presents internally inconsistent provenance | Join requires item, promotion, normalized record, H1 hash, source, and optional file node to agree | Full deployed baseline proof remains held |
| A non-H1 or noncanonical hash appears trustworthy | Weak or derived hashes are mistaken for custody anchors | Require H1, SHA-256, 32-byte digest, and `h1-rawbytes-v1` | Legacy alternate canon versions need a deliberate adapter later |
| Internal paths or storage metadata leak through the API | Operator surface exposes infrastructure details | Explicit response fields; exclude local paths, object-store keys, and raw metadata; source pointer is allowlisted | Authenticated owner still sees necessary source references |
| Stale detail from a prior item remains visible | A review is recorded against the wrong displayed provenance | Clear detail on open/error and bind successful state to the current Matter/item request | Browser smoke must prove exact request ordering |
| Detail load fails but decision remains enabled | Review bypasses the inspection requirement | Fail closed: disable submission until exact detail loads | An explicit offline-review workflow would require a separate decision |
| Review approval is mistaken for authentication | Unsafe evidence advances to export | Preserve unauthenticated/unsafe labels; this slice adds no authentication or release mutation | Authentication/redaction/court-readiness remain separate gates |

## Release boundary

- No migration is needed; the read side uses the existing held 0030 relations.
- This code must not be deployed ahead of migrations 0026–0030 and Workbench
  key provisioning.
- People/Timeline scope migration remains design-only until its ownership model
  is separately approved.

## Validation evidence

- Root Ruff, format, and mypy: **PASS**.
- Full root suite: **721 passed / 24 skipped**.
- Workbench API Ruff and format: **PASS**; full suite: **88 passed**.
- Frontend ESLint and TypeScript: **PASS**; production build: **PASS** with
  15 static routes.
- Headless Matter journey: **1 passed**; exact detail loaded before review and
  the request log contained one Matter-scoped evidence-detail GET.
- Real PostgreSQL 18.4 rollback proof: **PASS**, including a file-node/member H1
  digest different from the container source SHA and a foreign-Matter 404;
  zero net writes. The disposable server was stopped and port 55439 is closed.
