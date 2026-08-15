# HANDOFF — R4 Graphiti/Zep Belief Memory (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: COMPLETE
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Repository integration | Case client writes text episodes to one fixed group and Workbench reads facts, nodes, and episodes |
| Missing request fields | Current case client does not pass `reference_time`, custom types, or per-run groups |
| Projection acknowledgement | Local code treats queued `add_memory` as completion without verifying materialization/episode provenance |
| Deployment truth | Documentation and current compose/image claims conflict; live version and tool inventory remain unverified |

## Findings / work done

- Retain Graphiti as a derived, per-run semantic/temporal belief projection.
- Make append-only PostgreSQL `belief_event` the deterministic replay authority.
- Namespace every run/role as `belief:{case}:{workflow}:{run}:{role}`; ignorant and hindsight runs never share groups.
- Graphiti OSS supplies temporal edges, contradiction invalidation, custom types, communities, hybrid search/reranking, provenance, and direct triplets, but the project uses only a subset.
- Zep mainly adds managed context assembly, observations, governance, logs, scale, and proprietary models. Self-hosted functional approximations are possible; managed SLA/compliance parity is not turnkey.

## UNRESOLVED (mandatory)

- Live Graphiti/MCP/core/Neo4j versions, tools, indices, write freshness, and invalidation behavior.
- Native `graphiti-core` adapter versus richer MCP wrapper.
- Ontology and lifecycle rules for belief groups, observations, and communities.

## Pending owner decisions

- Adopt PG belief ledger + Graphiti projection — WHAT: separate authority from semantic projection · WHY: court-defensible replay · APPROACHES: Graphiti-only, PG-only, or hybrid · SHORTCOMINGS: hybrid needs a projector. Recommendation: hybrid.
- Defer Zep hosted — WHAT: benchmark only with synthetic/redacted corpus after the memory port exists · WHY: avoid sensitive-data/vendor lock-in before comparable tests · SHORTCOMINGS: delays access to managed features. Recommendation: defer.

## Next steps (work in order)

1. Probe live deployment read-only and reconcile version docs.
2. Specify `BeliefMemoryPort` and `belief_event`.
3. Add per-run groups, reference time, upstream UUID, and materialization acknowledgements.
4. Test temporal invalidation, as-of search, isolation, and contamination.
5. Enable custom ontology, communities, search recipes, observations, and context assembly.
6. Add metrics, backup/restore, orphan repair, and golden upgrade tests.

## Owner working-style contract

- Graphiti is belief state, not evidence truth; group IDs are namespaces, not authorization; no sensitive Zep trial without explicit approval.
