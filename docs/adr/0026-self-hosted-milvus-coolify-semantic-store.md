# ADR-0026: Self-hosted Milvus (Coolify) = shared semantic-search store; off managed EU Zilliz
- Status: Accepted
- Date: 2026-06-13
- _Byline: Claude Code · Opus 4.8 · 2026-06-13_

## Context
`claude-context` (code/knowledge semantic indexing) was backed by a **managed Zilliz
serverless cluster in `aws-eu-central-1`** — a data-residency + latency concern, and a
third-party dependency for what is core infrastructure. The same persistent vector store is
also needed for the **Case Bible** corpus (a separate, large body of material that badly
needs semantic search). `claude-context` speaks **only** Milvus/Zilliz — it cannot use our
SurrealDB vector layer (ADR-0024), so "get off EU" specifically means owning a Milvus.

## Decision
Stand up **self-hosted Milvus standalone** (Milvus + etcd + MinIO) on our **OVH** infra,
deployed and managed by **Coolify** (Ionos Coolify control plane → the two OVH servers).
It is the **shared semantic-search backend** for both the platform code/knowledge index and
the Case Bible corpus (isolated by separate Milvus databases/collections).

- **Deploy artifact:** a dedicated Git repo (`milvus-coolify`) holding a Coolify-friendly
  `docker-compose.yml` + `user.yaml`; Coolify deploys from the repo.
- **Volumes are mapped (bind-mount) host paths**, not named volumes (owner backup preference).
- **Traefik (h2c)** fronts Milvus's gRPC 19530, so `MILVUS_ADDRESS` is `https://<domain>` —
  same URL shape as the old Zilliz endpoint; the client swap is a 2-line `.env` change.
- **Auth on** (`authorizationEnabled`); default `root:Milvus` rotated on first boot.
- Embedder is unchanged: OpenRouter + `mistralai/codestral-embed-2505` (1536-d), ADR-0011 lineage.

## Consequences
- Vector data leaves managed EU; lives on a mapped volume we control and back up.
- We own a small infra stack (etcd/minio/milvus) — accepted: it's situation-specific (claude-context
  is Milvus-only) and Coolify-managed, so it does not violate minimize-custom (ADR-0025).
- Cutover step (post-deploy): edit `~/.context/.env` (`MILVUS_ADDRESS`/`MILVUS_TOKEN`),
  `/mcp` reconnect, re-index. The retired Zilliz EU cluster can be suspended/deleted after.
- **Does NOT** change ADR-0024: SurrealDB remains the store/session/Knowledge/memory layer
  for the *platform*; Graphiti stays cognition. Milvus serves the `claude-context`/Case-Bible
  semantic-search use case specifically.

## Alternatives considered
- **New Zilliz cluster in a US region** — quickest, but keeps the managed third-party dependency
  and data off-box; rejected for owned infra.
- **Drop claude-context, use Morph for code search only** — zero infra, but no persistent owned
  vector index and no Case Bible coverage; rejected (Case Bible needs the store).
- **Force claude-context onto SurrealDB** — not supported by the tool; rejected.
