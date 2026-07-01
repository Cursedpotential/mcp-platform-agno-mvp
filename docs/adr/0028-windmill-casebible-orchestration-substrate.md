# ADR-0028: Windmill = CaseBible orchestration substrate (replaces FileFlows); execution layer under Agno
- Status: **Superseded by ADR-0029 (2026-06-23)** — Windmill is dead; CaseBible no longer runs on it. The replacement substrate is now decided: a dedicated persistent CaseBible resource on the Agno stack (ADR-0029).
- Date: 2026-06-14
- _Byline: Claude Code · Opus 4.8 · 2026-06-14 (deprecated 2026-06-20; superseded by ADR-0029 2026-06-23)_

> **⚠️ SUPERSEDED 2026-06-23 by [ADR-0029](0029-casebible-dedicated-ingestion-resource.md).** Windmill
> (the OVH-2 CaseBible orchestrator) is dead and is **no longer** the orchestration substrate. The
> replacement is a **dedicated persistent CaseBible resource on the Agno stack** (ADR-0029) — do not treat
> this ADR as current. The sub-decisions below remain sound and carry into ADR-0029 — **rclone** as the
> off-the-shelf mover/hasher, **DuckDB MD5 dedupe** (not raw R2 ETag), the **Postgres ledger**, the
> **non-destructive `_QUARANTINE_REVIEW`** safety rule, **rules-first + small-local-model** classification,
> and the **Agno-stays-the-brain** boundary. Only the Windmill *substrate* is retired. Supersession ADR TBD.

## Context
The **CaseBible** pipeline consolidates ~123k+ files from OneDrive / Google Drive / Takeout into
Cloudflare R2, dedupes them, and organizes survivors into 8 governed domains (Inbox · Evidence ·
Entities · Case Management · Legal · Platform · Legacy · Archive). Phase-2 classification/routing was
slated for **FileFlows** (visual rules → Executor → `rclone moveto`). Separately, the platform had a
hand-rolled tool **registry + facade + auto-discovery** to expose its parsers/extractors as callable,
schema'd units. Both are glue we'd otherwise keep building. We want one off-the-shelf substrate that
hosts custom logic, triggers it, queues it, gates it behind human approval, and audits every action —
without becoming the *reasoning* layer (that stays Agno) or the *stores* (Milvus/Neo4j/Postgres).

Usage is **strictly personal/internal** (no resale/managed-service), so Windmill's AGPLv3 Community
Edition is unrestricted and free — no commercial license needed. All boxes are **CPU-only (no GPU)**.

## Decision
Adopt **Windmill** (self-hosted CE, AGPLv3) as the **execution / orchestration substrate**, deployed by
**Coolify** onto **OVH-2** (51.81.83.191), domain `windmill.mitechconsult.com` (Traefik + LE auto-TLS).

- **Replaces FileFlows entirely** and also drives **Phase-1** (inventory → dedupe → copy → quarantine).
  The pipeline is **mount-less**: `rclone lsjson` → DuckDB dedupe → `rclone moveto`, gated by Windmill
  **approval/suspend steps**. FUSE mounts become optional (human eyeballing via Kasm only).
- **rclone is retained** as the off-the-shelf mover/hasher (baked into a dedicated `casebible` worker
  group image): it exports Google Docs to real bytes (`--drive-export-formats`), reads true source
  hashes (OneDrive QuickXorHash, GDrive MD5) and writes real MD5 into R2 object metadata, supports
  OneDrive (not a native Windmill integration), and does server-side R2→R2 moves. Windmill orchestrates
  rclone; it does not replace it. (Minimize-custom-code, per ADR-0021/0025.)
- **Dedupe uses the reliable hash, not the raw R2 ETag.** R2 multipart-upload ETags are not plain MD5,
  so large files would mis-/under-dedupe; rclone-sourced MD5 (in object metadata) is the dedupe key.
  DuckDB runs the two-tier GROUP BY (Tier-A structure-aware export packages; Tier-B size+hash+filename)
  over an R2 inventory table (DuckDB reads Parquet/Iceberg from R2 natively).
- **Ledger → Postgres.** The CaseBible audit ledger moves from SQLite into a second database `casebible`
  on Windmill's bundled Postgres (one-time import from `ledger.sqlite`), avoiding SQLite's single-writer
  lock under parallel workers. The bundled Postgres is **dedicated** to Windmill, not the platform DB
  (Postgres IS Windmill's job queue — kept isolated).
- **Classification = rules-first, small-local-model for the ambiguous tail.** Deterministic routing
  (provenance prefix, extension, export-package patterns in `dedupe_patterns.txt`) handles the bulk and
  is auditable. A **small CPU-runnable model (≤4B; e.g. Granite-small)** classifies the residue via the
  **LiteLLM gateway (ADR-0015) + provider-agnostic factory (ADR-0008)** — model choice is a config swap,
  not infra. **Governance:** cloud/Colab escalation only on NON-sensitive signals (metadata); anything
  that reads file *content* stays on the local model + human review (child-PII risk). Specific model pick
  **deferred** (sub-4B space moves weekly). See memory `hardware-cpu-only-model-constraint`.
- **Agno boundary:** Windmill = execution substrate; **Agno stays the reasoning/agent brain** (teams,
  memory, legal analysis). Agno consumes Windmill scripts as tools via Windmill's **MCP server**
  (HTTP-streamable, scoped token) — Phase-2 wiring.

## Consequences
- Deletes the custom registry/facade/auto-discovery glue: a Windmill script's typed signature *is* its
  JSON-schema form + webhook + flow step + MCP tool. We inherit queue, retries, concurrency, secrets,
  RBAC, versioning-by-hash, and **per-job immutable audit logs** (a chain-of-custody asset).
- One more managed stack on OVH-2 (~2–4 GB): bundled Postgres + server + default/native/casebible
  workers. Coolify-managed, bind-mounted (owner backup preference). Fits once Milvus vacates OVH-2.
- **Implements, does not supersede,** the intent of ADR-0016 (tool containers/sandbox), ADR-0017
  (polyglot evidence orchestration mesh), and ADR-0023 (universal API/MCP exposure). A later pass may
  formally fold those into "Windmill is the mesh." Does not change ADR-0024 (SurrealDB) or 0026/0027
  (Milvus vector substrate).
- **Reversible bet:** step code is plain Python/TS/Bash that runs anywhere after leaving Windmill;
  OpenFlow spec is Apache-2.0.
- **Safety (enforced in scripts, never in tool names):** losers → `_QUARANTINE_REVIEW` via server-side
  `rclone moveto`, never delete/purge/rmdirs; never keep a 0-byte file; Takeout hard-excluded; human
  approval before every move batch. (The quarantine name is deliberately non-destructive — an agent once
  pattern-matched a delete-ish name and destroyed files.)

## Alternatives considered
- **FileFlows (original plan)** — visual, but a separate watcher/Executor with weaker audit and no
  schema→tool/MCP story; rejected (Windmill subsumes it and Phase-1 too).
- **n8n for the pipeline** — already deployed, but connector-oriented and JS-centric; weaker for
  code-first DuckDB/rclone steps and multi-language tool hosting; stays for SaaS-glue, not this.
- **Drop rclone, use Windmill-native S3 + Google Drive integration** — loses Google-Docs export, reliable
  source hashing, and OneDrive support; reintroduces custom Graph/Drive glue; rejected.
- **Dedupe on raw R2 ETag** — breaks on multipart large files; rejected for correctness.
- **Keep ledger in SQLite** — single-writer lock contention under parallel workers; rejected.
- **24B+ local model for classification** — not CPU-viable (no GPU); rejected, cloud/Colab-only for big.
