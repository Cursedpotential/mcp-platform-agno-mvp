# ADR-0029: CaseBible execution substrate = a dedicated persistent resource on the Agno stack (supersedes Windmill)
- Status: **Accepted (2026-06-23)** — supersedes ADR-0028 (the "replacement substrate TBD" it left open)
- Date: 2026-06-23
- _Byline: Claude Code · Opus 4.8 · 2026-06-23_
- _Handoff 2026-06-25: drafted by the CaseBible ingestion workstream; ownership/maintenance transferred to the platform workstream (owner of this repo). File stays in place; revise as you see fit._

## Context
ADR-0028 deprecated Windmill as the CaseBible orchestration substrate and left the replacement
**undecided**. CaseBible still needs an execution layer that reads the sorted corpus, runs the
evidence vertical (custody → parse → store → knowledge, ADR-0017), and (next) drives entity
extraction (ADR-0014/0031) — **without** re-introducing heavy glue and **without** disturbing the
shared `exec-tier` Agno stack (agentos-api/mcp/gateway/platform-tools/sandbox), which a second
workstream actively deploys to. Verified this session: editing/redeploying `exec-tier` collides with
that workstream; the empty `/r2` mount on `exec-tier` is a stray local volume, and the sandbox is
deliberately R2-isolated — so CaseBible cannot ride those containers.

## Decision
Run CaseBible ingestion as a **dedicated, separately-deployable Coolify resource** — its own
container (reusing the existing `agentos:latest` image so it shares the evidence/knowledge code),
**joined to the Agno docker network** (`rz41…_agentos`) for DB/Milvus/Graphiti reachability, with
**`casebible-sorted` rclone-mounted read-only** (ADR-0030). It executes the evidence vertical against
the platform's shared evidence spine (`evidence.evidence_hash`, `working.normalized_record`) and an
**isolated CaseBible knowledge collection** (own Milvus collection, ADR-0026/0027). It **never mutates
the `exec-tier` stack**. Carry-forward of ADR-0028's still-sound sub-decisions: rclone as the
off-the-shelf mover/hasher, DuckDB MD5 dedupe (not raw R2 ETag), Postgres ledger, the non-destructive
quarantine rule, and **Agno stays the brain** (this resource is execution, not reasoning).

Knowledge is **append-only and accessible anywhere**: once ingested it is never destroyed, and any
agent can query it through the platform Milvus/Neo4j substrate.

## Consequences
- CaseBible ingestion is isolated and independently modifiable; ingesting needs **no `exec-tier`
  redeploy**. Validated end-to-end this session (custody/hash → parse → normalized_record → knowledge
  → hybrid search → dedup → integrity re-verify) on real `casebible-sorted` output, non-disruptively.
- Obligation: a **writable** CaseBible evidence-blob destination for custody write-once (a
  `casebible-evidence` bucket), **not** the read-only source `casebible-sorted`.
- Obligation: decide CaseBible isolation on the shared evidence spine (own schema/DB vs shared) before
  bulk ingest; knowledge collection is already isolated.

## Alternatives considered
- **Edit/redeploy `exec-tier`** to add the mount — rejected: disrupts the other workstream's stack and
  couples CaseBible to it.
- **Repurpose the `/r2` (nexus) mount** to `casebible-sorted` — rejected: hijacks the platform landing
  zone (ADR-0007).
- **Revive a Windmill-style orchestrator** — rejected: ADR-0028 already retired it; a dedicated Agno
  resource reuses existing code (ADR-0021 no-stub / minimize-custom).
