# Architecture Blueprint — Polyglot, Framework-Neutral Platform

> _Byline: Codex · GPT-5 · 2026-08-15 · ADR-0059 amendment Codex · GPT-5 · 2026-08-18_

## Component ownership

| Layer | Technology | Owns | Must not own |
|---|---|---|---|
| Ingestion data plane | Go/SBV | Streaming decode, custody hashes, rejection accounting, format repair | Beliefs, horizon filtering, agent orchestration |
| Domain/control plane | Python/FastAPI | Evidence services, manifests, approvals, Semantica jobs, durable workflows | Browser UX, provider secrets in clients |
| Coordination adapter | AG2 candidate / Agno legacy | Runtime turns, handoffs, timeouts, coordination events | Canonical state, model policy, horizon policy |
| Experience/UI | TypeScript/Next.js/AI SDK | Workbench, SSE/AG-UI translation, route picker | Evidence writes or policy evaluation |
| Coding workspace | OpenCode | Persistent coding sessions and provider access | Direct host/container control or case-store access |
| Canonical storage | PostgreSQL + R2 | Evidence, manifests, approvals, beliefs, runs, audit, work products | Approximate semantic ranking |
| Belief projection | Graphiti/Neo4j memory DB | Run-scoped semantic/temporal belief recall | Evidence truth or cross-run authorization |
| Evidence graph | Neo4j evidence DB | Approved factual projection | Agent belief state |
| Retrieval projection | Weaviate | Horizon-filtered similarity/hybrid search | Canonical data or post-filter-only enforcement |
| Curated analytical/walk projection | SurrealDB candidate | Separate derived first-party/acquired-third-party messages, plural realization links, chunks, checkpoints, terminal snapshots, linked rewalks | Authored evidence truth, invented third-party participants, or sealed-state fallback |

## Go parallel ingestion design

The source decoder stays ordered. It assigns sequence numbers and exact raw-record hashes. Bounded workers may normalize or repair independent records. A bounded reorder buffer feeds one ordered committer that folds H3 and writes results in source order. Backpressure prevents unbounded memory growth.

Parallel imports require per-import progress and idempotency. The current global import mutex is a temporary safety mechanism, not the target concurrency model.

## Runtime anti-corruption boundary

Public requests use stable platform IDs and neutral schemas. The selected coordination adapter translates these into AG2 or Agno objects. Model routes are resolved before adapter invocation. Tool results and handoffs are normalized before persistence.

## Temporal memory design

PostgreSQL `belief_event` is authoritative. A Graphiti projector writes only agent-visible beliefs into `belief:{case}:{workflow}:{run}:{role}`. Hindsight and ignorant runs never share a group. `group_id` is a namespace, not an authorization boundary; the gateway enforces allowed group IDs.

Canonical normalized messages are authored once. Derived first-party source availability equals
occurrence; acquired-third-party availability equals acquisition and its participant set excludes
the owner. Zero-to-many realization links remain independent. Derived chunks inherit the source
boundary. A healthy checkpoint resumes the same walk only on exact reconciliation; terminal
integrity failure seals immutable state and requires an attested linked rewalk.

## Model route semantics

Hard policy filters first. Then the most specific authorized override wins: next call/stage, run/session, agent, workflow, deployment. Capability, health, context, billing, and data policy are evaluated before fallback. Changes during a stream or pending tool call are queued or rejected.

## Semantica boundary

Semantica is a VIP: the platform integrates its full semantic-intelligence and extraction capabilities and never replaces, dilutes, or forks around it. It receives immutable normalized batches and returns governed findings/candidates plus provenance through a scoped API. “Candidate” names the canonical-write boundary, not the service. Semantica does not acquire custody authority; approved results are projected downstream through governed CDC/outbox consumers.

## Deployment posture

- Self-host Next.js/Node with AI SDK; do not claim to self-host Vercel Functions or Vercel Sandbox.
- Self-host the persistent OpenCode service on existing infrastructure.
- Execute untrusted code in isolated child jobs with no host socket, secrets, or evidence mounts.
- Pin fast-moving Graphiti, AG2, OpenCode, and provider-adapter versions and validate upgrades against golden corpora.
