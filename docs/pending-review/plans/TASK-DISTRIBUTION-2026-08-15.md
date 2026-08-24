# Task Distribution and Context Boundaries

> _Byline: Codex · GPT-5 · 2026-08-15_

## Coordination rule

Specialists research and implement within one bounded domain. They exchange typed references and HANDOFF v2 packets, not full conversation histories. The integration architect alone reconciles cross-domain decisions and updates shared ADRs/contracts.

## Lane ownership

| Lane | Responsibility | Primary output | Must not edit |
|---|---|---|---|
| R0 Audit | Wave-1 truth and defect register | Review addendum and salvage map | Migrations or runtime code |
| R1 Go ingestion | SBV streaming, formats, custody, concurrency | Go contract and benchmark report | Python horizon/agent code |
| R2 Horizon | Realization, manifests, replay, delta | Temporal API/schema specification | Parser implementations |
| R3 Semantica VIP | Full semantic intelligence, governed extraction, and provenance | VIP integration contract, capability map, and eval results | Forking/replacing Semantica or giving it canonical custody authority |
| R4 Memory | Belief ledger, Graphiti/Zep parity | BeliefMemoryPort and parity report | Canonical evidence policy |
| R5 Coordination | AG2/Agno bake-off | Orchestration adapter report | Provider registry or domain stores |
| R6 Providers | Portkey/OpenCode/AI SDK routing | ProviderRegistry and GUI semantics | Agent coordination logic |
| R7 Workspace | OpenCode persistence and sandbox | WorkspacePort and isolation report | Model-policy decisions |
| R8 Workbench | Custom visual product surface | UX/API integration specification | Domain rules or DB access |
| Integration | Reconcile all packets | ADRs, frozen contracts, rollout order | Specialist-owned implementation before handoff |

## Minimum cold-start context

Every lane receives:

1. Root `AGENTS.md`.
2. `docs/PROJECT_CANON.md` section 1.
3. This task-distribution document.
4. Its own dated HANDOFF.
5. Only the ADRs and source paths named by that HANDOFF.
6. Current `git status` and explicit file ownership.

## Handoff packet contract

Each packet includes objective, verified state, inputs-by-reference, findings, work completed, remaining work, decisions, shortcomings, acceptance tests, exact owned files, and unresolved questions. `BUILD_STATUS` is `UNKNOWN` unless the named checks were actually executed.

## Dependency graph

- R0 precedes any Wave-1 implementation.
- R1 and R3 may proceed after their contracts are frozen.
- R2 precedes R4 agent-belief projection and R5 contamination testing.
- R6 precedes R5 hot-switch tests and R8 route-picker integration.
- R7 can proceed after R6 defines credential and billing policy.
- R8 integrates only versioned APIs.
- Integration/cutover begins only after all relevant packets are `COMPLETE` or explicitly owner-waived.

## Pre-mortem requirement

After each task, the owner review surface records: likely failure modes, what evidence would falsify success, tests run, failures observed, rollback/quarantine path, production-apply status, and push status.
