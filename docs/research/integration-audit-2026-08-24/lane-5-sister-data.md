# Lane 5 — Sister Data Sources Inventory (Evidence-Only)

> _Byline: lane-5 agent · Sonnet · 2026-08-24_

Scope: read-only inventory of the four sister data sources named by the owner as merge
targets for platform adapters — Case Bible corpus, TraceIQ geo data, Legal-Workspace,
and the Agno workbenches. No writes performed. No recommendations. Every claim below is
cited to a path listing, `file:line`, or live probe. Anything not directly observed is
marked UNKNOWN.

---

## 1. Case Bible sorted vault

The canonical corpus (R2 `casebible-sorted`) was not probed directly (no R2 credentials
used, per the "local paths only" scoping in the task). Two local mirrors were inventoried
instead.

### 1a. `C:/Users/matts/OneDrive/Case Bible` (vault mirror)

**Evidence gap vs. the assumed taxonomy:** this mirror's top level is NOT the 8-domain
PascalCase v4 taxonomy. `ls -la` on the root shows ~30 freeform top-level entries (legacy
folders, some numbered duplicates like `wiki`/`wiki1`, `Motions_Filings`/`Motions_Filings1`,
`Takeout Data`/`Takeout Data1`) plus system dirs (`.claude`, `.obsidian`, `.review_hold`,
`_SWEPT`, `_system`). Command: `find "C:/Users/matts/OneDrive/Case Bible" -maxdepth 1 -type d`.

2-level dir/file counts per top-level folder (`find "$d" -type d|wc -l`, `find "$d" -type f|wc -l`):

| Folder | Dirs | Files | Dominant types (sampled) |
|---|---|---|---|
| Evidence | 913 | 24,827 | jpg (15,468), png (3,935), gif (1,826), mp4 (1,653), m4a (573) |
| Takeout | 452 | 56,221 | json (24,979), png (19,238), jpg (5,084), html (2,760), heic (1,454) |
| social backup | 405 | 6,102 | jpg (2,789), html (1,486), png (629), mp4 (388), json (285) |
| Triage | 98 | 4,529 | (not sampled) |
| KnowledgeBase | 160 | 2,145 | jpg (766), md (378), jpeg (226), mp4 (170), csv (119) |
| Legal_Knowledge_Base_Obsidian1 | 161 | 796 | (not sampled) |
| Person_Info_Backup_2026-03-12 | 56 | 583 | (not sampled) |
| people | 36 | 282 | (not sampled) |
| Takeout Data | 993 | 3,355 | (not sampled) |
| CaseManagement | 34 | 132 | docx (48), pdf (45), md (22), zip (8), xml (5) |
| wiki / wiki1 | 299 / 299 | 306 / 306 | (identical counts — likely duplicate copies) |
| timeline_analyzer | 302 | 119 | (not sampled) |
| context | 6 | 99 | (not sampled) |
| General_Code_&_Repos | 14 | 98 | (not sampled) |
| TECH_ASSETS_SW | 6 | 90 | (not sampled) |
| INBOX | 7 | 77 | (not sampled) |
| Obsidian Vault1 | 22 | 48 | (not sampled) |
| plans | 1 | 44 | (not sampled) |
| Recovered Files | 1 | 30 | (not sampled) |
| Clippings | 2 | 472 | (not sampled) |
| Person Enrichment Files | 1 | 7 | (not sampled) |
| Notes_Analysis | 2 | 5 | (not sampled) |
| Case Bible Backups | 3 | 6 | (not sampled) |
| Raw AI Chats | 1 | 12 | (not sampled) |
| plannotator | 1 | 14 | (not sampled) |
| Software Research & Reference | 1 | 4 | (not sampled) |
| Motions_Filings / Motions_Filings1 | 1 / 1 | 1 / 1 | (near-empty) |
| SMS_KK_Phone / SMS-KK-3592 | 1 / 1 | 1 / 1 | (near-empty) |

Root also contains loose OneDrive-recycled `$R*` files (mp3/json/csv/png/html/pdf/xlsx —
the local OneDrive recycle-bin cache, not vault content).

### 1b. `D:/casebible/vault-sorted` (IS the 8-domain v4 taxonomy)

`find D:/casebible/vault-sorted -maxdepth 1` shows exactly 8 named domains plus governance
files (`AGENTS.md`, `Dashboard.md`, `GLOSSARY.md`, `INDEX.md`, `MANIFEST.json`,
`Tag Guide.md`) and system dirs (`.agent_logs`, `.obsidian`, `_stale`, `_system`):

| Domain | Dirs (2-lvl) | Files (2-lvl, top only) | 2nd-level children observed |
|---|---|---|---|
| Archive | 6 | 4 | Case Management, Entities, Evidence, Legal, Platform |
| CaseManagement | 16 | 4 | _intake, _recovered, calendar, correspondence, discovery, drafts, exhibits, filings, financials, hearings, motions, orders, parenting-time, received, work-product |
| Code | 3 | 4 | _intake, _recovered |
| Entities | 8 | 4 | .recovered, .review, .staging, .to_be_deleted, .to_be_sorted, _intake, _recovered |
| EvidenceVault | 7 | 4 | _intake, _recovered, exports/{facebook, google-takeout, snapchat} |
| KnowledgeBase | 7 | 1 | _intake, _recovered, ai-chats (+ _derived), legal, personal-history |
| Recovered | 1 | 4 | (no subdirs) |
| Triage | 3 | 4 | documents, exports-bundles |

`D:/casebible` itself (parent of `vault-sorted`) also holds working artifacts: `casebible.duckdb`
(68MB), `casebible_work.sqlite` (2.5MB), `merge-plan.{csv,duckdb,xlsx}`, `backup-sort-plan.{csv,xlsx}`,
`backup-manifest-missing.csv` (30MB), `raw_hashes.txt`/`raw_sizehash.txt` (~77MB/80MB), and
`vault-sorted` itself — i.e. this is the working directory for the sort pipeline, not just a mirror.

**Reconciliation note (evidence, not inference):** the OneDrive mirror and the D: vault-sorted
tree are two different states of the same corpus — OneDrive still holds the legacy freeform
layout, D:/casebible/vault-sorted holds the already-sorted v4-taxonomy output. Both exist
locally; which one is the live mirror of the canonical R2 `casebible-sorted` bucket was not
verified in this pass (no R2 listing performed).

---

## 2. TraceIQ geo data

**Search roots and patterns used:** `find <root> -iname "*traceiq*" -o -iname "*trace-iq*" -o -iname "*trace_iq*"`
against `C:/Users/matts/OneDrive/Case Bible`, `D:/casebible`, `D:/Backup`, `E:/AI_Workspace`.

- **D:/casebible**: NOT FOUND. Zero matches.
- **C:/Users/matts/OneDrive/Case Bible**: found only inside `.review_hold/duplicates/swept/_SWEPT/AI_Chats/...`
  — these are AI-chat export `.md`/`.docx` documents *about* TraceIQ (dev-chat transcripts,
  schema-design docs), not TraceIQ data itself. No actual geo dataset present here.
- **D:/Backup**: found (a) more dev-chat docs (`Case Bible BACKUP 2026-03-12/_TO_BE_DELETED/chats/gemini/...`,
  `Court/Timeline ETL & Processor/...`), and (b) two real legacy project copies:
  `D:/Backup/Projects/TheBigOne/TraceIQ/` (a "Junkyard" of superseded source folders) and
  `D:/Backup/Projects/TheBigOne/MCP_Tool_Platform/.../TheBigOne_SAFE_COPY/01_Timeline_Forensics/`
  (an older archived copy). Both read as prior/legacy states, not the live project.
- **E:/AI_Workspace**: found the **current, canonical copy** at
  `Projects/the-platform-workspace/Projects/traceIQ/` — present identically inside every git
  worktree of this repo (`.claude/worktrees/*/Projects/traceIQ`), confirming it is a working-tree
  path of the `the-platform-workspace` repo itself (present in this session's own worktree at
  `E:/AI_Workspace/Projects/the-platform-workspace/.claude/worktrees/funny-benz-34106c/Projects/traceIQ`).
  Also found a *different*, older `TraceIQ/` (capital-T, no `Projects/` prefix) tree in three other
  worktrees (`ecstatic-tu-7c6c6c`, `pdf-page-deletion-tool-3a4414`, plus partial in `bold-swanson-911387`)
  containing a `Junkyard/` of superseded source folders (`Source_A_Root_Folder`, `Source_B_BigOne_Repo`,
  `Timeline_Tools_Backup_20260108_214802`) — this reads as an older, since-cleaned-up import,
  distinct from the current `Projects/traceIQ`.

### Current TraceIQ project structure (`Projects/traceIQ/`, this worktree)

```
Projects/traceIQ/
├── traceiq-rebuild/        # empty in this worktree — no files present
├── TraceIQ_Backups/        # 11 PostgreSQL pg_dump custom-format (-Fc) backups
└── TraceIQ_Evidence/       # 2 JSON files, named by sha256
```

**TraceIQ_Backups/ (`ls -la`):** 11 files, all dated 2026-07-24, milestone-tagged, sizes
287KB–13.5MB (schema-init-testload=287KB smallest; pre-single-file-cleanup=13.53MB largest),
total ≈103MB. Filenames: `milestone-analytics-suite`, `milestone-full-radar-import`,
`milestone-geodata-linkage`, `milestone-k-export-ingested`,
`milestone-knownplace-locregistry-typeviews`, `milestone-lite-cache-import`,
`milestone-locationkeys-legacycache`, `milestone-schema-init-testload`,
`milestone-working-layer-wave1`, `pre-single-file-cleanup`, `single-file-clean`.
Format confirmed as PostgreSQL custom-format dump by cross-reference:
`Agno-MCP-Platform/sql/_manual/20260801_clear_case_data.sql:16-17` records a `pg_dump -Fc`
backup set taken 2026-08-01 that explicitly names `traceiq (12M)` alongside `ai (2.6M)`,
`postgres`, and `globals` — i.e., TraceIQ runs as a live PostgreSQL database on the same
Postgres server as the platform's own `ai` database, and is routinely included in that
server's backup rotation.

**TraceIQ_Evidence/ (sampled 1 of 2 files, `376e58d0...json`, first 2KB):** JSON, matching
Google Takeout "Semantic Location History" format — top-level `semanticSegments` array,
each with `startTime`/`endTime` (ISO-8601 with UTC offset, e.g.
`"2017-09-20T16:00:00.000-04:00"`) and a `timelinePath` array of `{point, time}` pairs where
`point` is a string `"<lat>°, <lon>°"` (e.g. `"43.0762317°, -83.6604617°"`) and `time` is
per-point ISO-8601. Earliest timestamp observed in the sample: 2017-09-20. Row/segment count
not fully enumerated (file not parsed beyond first 2KB, per the ≤10-sample-file cap).

**traceiq-rebuild/**: directory exists but is empty in this worktree (`find traceiq-rebuild`
returns only the directory itself) — either gitignored working data not materialized here, or
an in-progress/scaffolded rebuild with no files yet. Not resolvable further without a live
listing of what should populate it.

---

## 3. Legal-Workspace

**Location:** `E:/AI_Workspace/Projects/the-platform-workspace/Legal-Workspace/` (confirmed
git repo — `.git/` present). Two decoys ruled out: `Legal-desktop/LEGAL-WORKSPACE-BUILD-GUIDE-2026-08-17.md`
is a doc-only file, not a repo; `node_modules/legal-workspace-web` is an installed npm
package, not the source repo.

### API surface — route table

FastAPI app defined in `api/legal_workspace/api/main.py:149-154` (title "Legal Workspace API"),
with `ContextForgeAuthMiddleware` (`main.py:93-130`) gating every route except `/health` behind
a Context Forge JWT bearer token (`CF_JWT_SECRET_KEY`), unless `LEGAL_WORKSPACE_BYPASS_AUTH=true`.

Routes defined directly in `main.py`:

| Method | Path | Purpose (from code) | file:line |
|---|---|---|---|
| GET | /health | liveness | main.py:337 |
| POST | /v1/token | mint CF JWT — **STUB, returns 501** (see code comment) | main.py:184-204 |
| GET | /v1/agno/status | probe Agno (evidence platform) reachability | main.py:349 |
| GET | /v1/matter | matter home/dashboard aggregate | main.py:360 |
| GET | /v1/authorities | list curated authorities | main.py:396 |
| GET/POST | /v1/research | research questions | main.py:401,406 |
| POST | /v1/research/{id}:status | update research status | main.py:411 |
| GET/POST | /v1/currency-flags | authority currency flags | main.py:424,429 |
| GET/POST | /v1/strategy | strategy notes | main.py:437,442 |
| PUT | /v1/strategy/{note_id} | patch strategy note | main.py:447 |
| GET/POST | /v1/redteam | red-team runs | main.py:456,460 |
| GET/POST | /v1/todos | case todos | main.py:466,470 |
| POST | /v1/todos/{id}:status | update todo status | main.py:475 |
| PUT | /v1/todos/{id} | patch todo | main.py:483 |
| GET/POST | /v1/reviews | review decisions | main.py:492,496 |
| GET/POST | /v1/releases | release manifests / build candidate | main.py:507,511 |
| POST | /v1/legal-source-packages:import | import a `LegalSourcePackage` | main.py:516 |
| GET | /v1/factors | factor entries | main.py:528 |
| POST | /v1/factors/{letter}/citations | link citation to factor | main.py:532 |
| GET/POST | /v1/agent-runs | agent run log | main.py:543,547 |
| GET | /v1/filing-readiness | filing gate status | main.py:552 |
| POST | /v1/filing-overrides | override a filing check | main.py:557 |
| GET/POST/DELETE | /v1/docket-events | docket events | main.py:566,571,575 |
| GET/POST | /v1/exhibits | exhibit candidates | main.py:585,589 |
| POST | /v1/exhibits/{id}:bates | assign bates number | main.py:597 |
| GET/POST | /v1/investigations | investigation requests | main.py:606,610 |
| GET/POST | /v1/discovery | discovery requests | main.py:616,620 |
| POST | /v1/discovery/{id}:status | update discovery status | main.py:625 |
| GET | /v1/templates | drafting template catalog | main.py:636 |
| POST | /v1/templates:instantiate | instantiate a template into a draft | main.py:640 |
| GET/POST | /v1/drafts | draft sections | main.py:658,649 |
| POST | /v1/drafts/{id}:gate | citation-gate check on a draft | main.py:663 |
| GET | /v1/drafts/{id}/support-map | support map for a draft | main.py:673 |
| PUT | /v1/drafts/{id} | edit draft | main.py:684 |
| POST | /v1/citation-resolutions:batch | batch citation gate | main.py:693 |
| POST | /v1/privilege:scan | keyword privilege first-pass scan | main.py:704 |
| GET/PUT | /v1/settings | app settings | main.py:773,778 |
| GET/PUT | /v1/confidential | confidential-mode toggle | main.py:792,797 |
| POST | /v1/redactions | content-stream PDF redaction upload | main.py:802 |
| POST | /v1/bates:stamp | PDF bates-stamp upload | main.py:822 |
| POST | /v1/events:apply | apply a revocation/event envelope | main.py:841 |
| GET | /v1/export/json | full workspace JSON export (flag-gated) | main.py:857 |
| GET | /v1/surface-context | per-path UI surface context | main.py:767 |

Additional routers mounted at `main.py:898-905`:

| File | Routes |
|---|---|
| source_routes.py | GET /v1/sources (line 20), GET /v1/sources/{id}/search (line 25) |
| routing_routes.py | GET /v1/routing (20), GET /v1/routing/resolve (25), PUT /v1/routing (33) |
| ops_routes.py | GET /v1/audit (27), GET /v1/triggers (32) |
| automation_routes.py | GET /v1/automations/jobs (18), GET /v1/automations/playbooks (23), POST /v1/automations/playbooks/{id}:run (28) |
| citation_routes.py | POST /v1/citations:parse (25) |
| calendar_routes.py | POST /v1/calendar/deadlines/calculate (130), GET /v1/calendar/events (148), POST /v1/calendar/events (154), DELETE /v1/calendar/events/{id} (163) |
| factor_routes.py | GET/POST/PUT /v1/issues (53,59,67), POST /v1/issues/{id}/elements (77), POST /v1/factors/{letter}/notes (87), GET /v1/factors/{letter}/analysis (97) |
| privilege_routes.py | GET /v1/providers (40), POST /v1/gateway:invoke (46) |

### Database

`db/engine.py:1-2` — "SQLite locally; PostgreSQL on the platform." `get_engine()`
(`db/engine.py:18-45`) branches on URL scheme: `sqlite://` → SQLite with WAL + foreign_keys
pragmas (NullPool, `check_same_thread=False`); `postgresql://` → plain SQLAlchemy engine.
Default (dev) URL comes from `default_sqlite_url()` → `sqlite:///<store_dir>/legal.sqlite`
(`db/engine.py:60-67`). `config.py:32` wires `database_url` from `default_sqlite_url` by
default, overridable via settings.

`db/models.py` defines SQLAlchemy models mirroring a schema-prefixed Postgres design
(comment at `db/models.py:1-5`: "Table names use schema prefixes... because SQLite does not
support CREATE SCHEMA. When the app moves to PostgreSQL, the prefixes can be remapped to real
schemas with no model changes."). Table groups observed:

- `legal_core_*` (models.py:93-260): app_settings, matter_ref, court_case_ref,
  source_package, source_package_omission, docket_event, todo, discovery_request,
  investigation_request, exhibit_annotation, agent_run, filing_override
- `legal_research_*` (models.py:267-311): authority, currency_flag, question
- `legal_work_product_*` (models.py:319-409): draft_section, work_product,
  work_product_version, strategy_note, red_team_run, review_decision, release_manifest
- `legal_audit_*` (models.py:417-439): event_outbox, consumed_event

### Integration points toward Agno

- `services/agno_client.py` (byline: Grok, 2026-08-18) — "Read-only Evidence Platform
  client. Agno is truth; never clone evidence." Calls, via `httpx`:
  `GET {evidence_platform_base_url}/health` (`probe_health`, lines 130-144),
  `GET {evidence_platform_base_url}/v1/matters` (`list_matters`, lines 147-162, projects
  only `id`/`matter_id` + `title`/`display_name` — "Identity only. Evidence bytes, spans,
  and hashes stay on Agno"), `POST {evidence_platform_base_url}/v1/verify/{sha256}`
  (`verify_sha256`, lines 180-219, custody verdict only).
- `config.py:26,30` — `evidence_platform_service` default `"evidence-platform"`,
  `evidence_platform_base_url` default `"http://evidence-platform:8000"`. **No literal
  `agno`/`agentos`/`100.72.*` string appears in this repo's code** — `config.py:15,40-54`
  actively enforces a `no_embedded_ips` validator that raises `ValueError` if any configured
  service URL contains a dotted-quad IP, forcing service-name-only wiring (consistent with
  the module docstring "Tailnet IPs are forbidden," `config.py:1`).
  Auth toward Agno/ContextForge is a bearer token (`CF_GATEWAY_TOKEN`,
  `services/agno_client.py:89-90`); auth *into* this API from callers is a separate
  ContextForge JWT (`CF_JWT_SECRET_KEY`, `main.py:93-130`).
- This confirms the integration doorway is HTTP + service-DNS (`evidence-platform:8000`),
  not a hardcoded tailnet address — matching the platform-side pattern seen in workbench.yaml
  (§4 below) where the *workbench* app, unlike Legal-Workspace, does use the literal tailnet
  IP `100.72.169.40` for `AGENTOS_API_URL`. The two apps take different addressing strategies
  toward the same Agno backend.

---

## 4. Workbenches (Agno-MCP-Platform repo)

### knowledge-workbench

`deploy/workbench.yaml` (single Coolify app, `deploy/workbench.yaml:1-158`). Builds from
`./workbench` (Dockerfile) → image `agno-knowledge-workbench:latest`, container
`knowledge-workbench`, published on `${BIND_IP:-127.0.0.1}:8020:8020` (tailnet-only, line 47).

Backends it talks to (all env-driven, `deploy/workbench.yaml:48-127`):

| Env var | Default | Purpose |
|---|---|---|
| AGENTOS_API_URL | `http://100.72.169.40:8000` | agentos-api ingestion spine (literal tailnet IP) |
| AGENTOS_API_TOKEN | (unset) | bearer for `/knowledge/*` + `/v1/runs` |
| EVIDENCE_OPERATOR_SECURITY_KEY | (unset) | owner-only bounded evidence search, distinct from agent-issued keys |
| MCP_SERVERS | `[]` | Tool Explorer — ContextForge virtual servers, `agentos` entry now points at agentos-api's mounted `/mcp` (:8000) per agno 2.8 door migration (comment, lines 64-83) |
| PORTKEY_BASE_URL / PORTKEY_* | `http://100.72.169.40:8787/v1` | LLM gateway (self-hosted Portkey) |
| GRAPHITI_MCP_URL | `http://100.91.190.107:8071/mcp` | knowledge-graph memory (read-only, no auth, tailnet-only) |
| OPENCODE_URL | `http://100.72.169.40:4096` | Ops Copilot (exec-gateway app, headless OpenCode server) |
| OBJECT_STORE_* (R2_*) | — | S3-agnostic staging object store (R2 today) |

Storage: bind-mounted LanceDB (`/data/agno/volumes/workbench/lancedb:/data/lancedb`) for
staged uploads; per the file header comment (lines 23-27) it "stages uploads locally
(LanceDB whole-file store) and promotes them through the EXISTING ingestion spine
(agentos-api). It never writes Milvus/Postgres directly."

### Operator console

No separate `deploy/operator-console.yaml` exists — searched `deploy/*.yaml` (25 files
listed) and found none named for it. `docs/planning/operator-console-requirements.md:1-9`
states explicitly this is the SAME app: "the workbench app (`workbench/`, Coolify :8020) is
rebuilt in place" and under "Locked decisions" (lines 12-16): "**Surface**: rebuild the
existing workbench app in place (keep container, R2/LanceDB staging, :8020)." Access-pattern
rule stated in the same doc (lines 17-19): "**Reads vs writes**: console reads stores
DIRECTLY read-only (PG, Milvus, Graphiti); ALL writes go through spine APIs (single-writer
preserved)." I.e. "knowledge-workbench" (deploy/workbench.yaml) and "operator console" are
the same deployed container at :8020, at different points in its build history — not two
apps.

---

## Summary (8 lines)

1. **Case Bible**: two divergent local states exist — OneDrive mirror still has the legacy
   freeform ~30-folder layout (Evidence/Takeout/social backup dominate by file count, mostly
   jpg/png/json); `D:/casebible/vault-sorted` already holds the true 8-domain v4 taxonomy
   (Archive, CaseManagement, Code, Entities, EvidenceVault, KnowledgeBase, Recovered, Triage).
   Adapter doorway: the sorted tree's per-domain folders, once its relationship to the
   canonical R2 `casebible-sorted` bucket is confirmed live.
2. **TraceIQ**: not a document corpus — a live PostgreSQL database (confirmed via
   `sql/_manual/20260801_clear_case_data.sql:17`, `traceiq (12M)` in the same pg_dump backup
   set as the platform's own `ai` DB) backed by JSON evidence files in Google
   Semantic-Location-History format (lat/lon + ISO-8601 timestamps back to 2017) and 11
   milestone `pg_dump -Fc` snapshots (~103MB total) living at
   `Projects/traceIQ/{TraceIQ_Backups,TraceIQ_Evidence}` inside this very repo's working
   tree. Adapter doorway: restore/point at the live TraceIQ Postgres DB directly (schema
   already Postgres-native), not the JSON evidence files.
3. **Legal-Workspace**: a FastAPI service (`Legal-Workspace/api/legal_workspace/api/main.py`
   + 8 routers, ~45 routes) with its own SQLite-dev/Postgres-prod SQLAlchemy schema
   (`legal_core_*`/`legal_research_*`/`legal_work_product_*`/`legal_audit_*`, ~20 tables) that
   already talks to Agno as a read-only "Evidence Platform" client
   (`services/agno_client.py`: `/health`, `/v1/matters`, `/v1/verify/{sha256}`) via
   service-name DNS, never tailnet IPs. Adapter doorway: this client is already the seam —
   extending it (or its ContextForge-JWT-gated inbound API) is the natural merge point.
4. Workbenches: "knowledge-workbench" and "operator console" are one and the same Coolify
   app (`deploy/workbench.yaml`, :8020) — the console is the workbench rebuilt in place, not
   a second deployment — and it is already the adapter doorway into agentos-api, Portkey,
   Graphiti, and OpenCode via literal tailnet-IP env vars.
