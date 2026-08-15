# Platform Runtime Migration — Master Plan

> _Byline: Codex · GPT-5 · 2026-08-15_

## Decision summary

The target is a deliberately polyglot platform whose domain contracts are independent of any agent framework.

- Go remains the primary parser for every format it covers, at every file size.
- Python owns evidence-domain services, Semantica, temporal truth, durable approvals, and the AG2 coordination spike.
- TypeScript owns the custom Workbench, AI SDK adapters, streaming UX, and OpenCode control.
- PostgreSQL is authoritative. Neo4j/Graphiti and Weaviate are rebuildable projections.
- AG2 is a coordination candidate, not an approved replacement. It must pass a bounded bake-off behind an `OrchestrationPort`.
- Portkey remains the governed gateway. OpenCode supplements it for subscription, OAuth, and local model access.
- Graphiti is the derived belief graph; an append-only PostgreSQL belief-event ledger is the replay authority.

## Governing invariants

1. Extraction is horizon-blind; agent experience is horizon-bound.
2. The ignorant agent and hindsight agent never share a belief namespace.
3. Model/provider changes take effect only at the next invocation, turn, or durable workflow checkpoint.
4. No future fact may enter retrieval, prompts, handoffs, coordination WALs, Graphiti, summaries, observations, or traces before activation.
5. Engine selection is coverage-based, never size-based.
6. Every side effect is idempotent, audited, and resumable.
7. No framework object crosses a public/domain contract.
8. Nothing is permanently deleted; superseded material moves to `to_be_deleted` for owner review.

## Work waves

| Wave | Outcome | Gate |
|---|---|---|
| 0 | Preserve and independently audit the dirty Wave-1 tree | Owner accepts defect register; no migrations applied |
| 1 | Complete the Go streaming/parser contract | Sequential/parallel custody and output equivalence |
| 2 | Repair realization and immutable horizon manifests | Old runs replay after later ingestion |
| 3 | Freeze framework-neutral ports and schemas | Contract tests pass without Agno, AG2, AI SDK, or Graphiti imports |
| 4 | Integrate the Semantica VIP as the semantic-intelligence service | Full Semantica capability preserved; governed candidate/provenance boundary into canonical knowledge; no custody authority |
| 5 | Establish belief ledger and functional Graphiti projection | Temporal, isolation, contamination, backup/restore gates pass |
| 6 | Implement live provider routing and Workbench selector | Concurrent routes do not bleed; actual route is visible |
| 7 | Run AG2-versus-Agno coordination bake-off | HITL, recovery, idempotency, and horizon gates pass |
| 8 | Deploy persistent OpenCode workspace and isolated execution | Restart persistence and workspace isolation pass |
| 9 | Complete custom Workbench product surface | Intake-to-delta-to-export E2E passes |
| 10 | Shadow cutover and Agno retirement | Capability parity, owner approval, rollback proof |

## Public contracts

- `OrchestrationPort`: start, resume, dispatch, handoff, pause, finish, cancel, stream, inspect.
- `HandoffPacket`: objective, scope, references, horizon binding, completed work, unresolved questions, output schema, tools, route, termination conditions.
- `ProviderRegistry`: catalog, resolve, validate, create adapter, health, credential status, record outcome.
- `ModelRoute`: stable alias, candidates, capabilities, fallback, billing, data, context, health, audit, version.
- `BeliefMemoryPort`: append event, project, search current/as-of, trace provenance, communities, observations, delete run, health.
- `HorizonContextPort`: create run, advance step, materialize manifest, retrieve, replay, rewalk, rebatch, compare.
- `ExtractionPort`: issue immutable batch, accept candidates/provenance, inspect status, retry, dead-letter.
- `WorkspacePort`: create, start, stop, restart, fork, attach session, execute isolated job, export work product.

## Required review packets

The execution source of truth is the nine dated HANDOFF v2 documents R0–R8 plus:

- `PRODUCT-BLUEPRINT-2026-08-15.md`
- `ARCHITECTURE-BLUEPRINT-2026-08-15.md`
- `TASK-DISTRIBUTION-2026-08-15.md`
- `MIGRATION-DIAGRAMS-2026-08-15.md`

## Cutover rule

AgentOS/Agno remains available while adapters are shadow-tested. Retirement is agent-by-agent and capability-by-capability. Superseded code is quarantined only after counts, checksums, session/memory migration, and rollback artifacts are owner-approved.
