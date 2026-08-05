# Open tasks — consolidated 2026-07-27

> _Byline: Claude Code · Fable 5 · 2026-07-27_
> Sources: SESSION-HANDOFF-2026-07-13.md (claude.ai export recovered from Downloads),
> July 21–27 session logs, owner directives 2026-07-27. Supersedes the STILL-TO-DO
> section of the 07-13 handoff where they conflict.

## Highest value next (per 07-13 handoff, still true)
1. **Detection matcher fix** (`server/analysis/detection.py`) — Unicode-apostrophe canonicalization w/ offset map, word boundaries, dry-run diff acceptance test; add `deflection_of_accountability` category. Cheap, measurable, gates cycle detection.
2. **Vector substrate decision** — now ADR-0040 (Weaviate leading vs pgvector vs keep-Milvus). Needs: owner's Milvus symptom list, Weaviate RAM check, migration plan, researched gains/losses breakdown (still owed from 07-13 chat).

## Deployed 2026-07-27 ✅
- **data-weaviate LIVE** on ovh-data: uuid `h5hrvmcs84no9g1ubl0jr0pw`, host **:8081** REST (8080 is coolify-proxy's) + :50051 gRPC, `/v1/.well-known/ready` = 200, healthy. Fixes en route: CLUSTER_ADVERTISE_ADDR=127.0.0.1 (single-node memberlist), host-port move 8080→8081. Compose: `deploy/data-weaviate.yaml` @ `infra/data-weaviate-memgql`.
- **data-memgql LIVE** on ovh-data: uuid `is1z1b0v0j6s842gggak5iew`, Bolt **:7688** open, multi-connection mode. Compose: `deploy/data-memgql.yaml` @ same branch.
- Next: MemGQL connector attach (data-pg/Neo4j/DuckDB) · Milvus→Weaviate 4096-d vector export · Weaviate auth hardening (currently anonymous, tailnet-only) · pin Weaviate image tag (running 1.39.0-rc.0 via :latest — pin a stable tag) · DozerDB swap prep (backup first) · merge `infra/data-weaviate-memgql` → main when settled.

## New direction (owner, 2026-07-27)
- **Memgraph temporal GraphRAG layer** — ADR-0041 (additive; Neo4j/DozerDB and all current storage stays). Evaluate **Memgraph Zero** (federated zero-ETL over PG/DuckDB/Neo4j) first; fall back to classic-Memgraph projection. Orchestration: LangGraph + LangChain or LlamaIndex (pick at first retrieval-tool build).
- Memgraph official skills installed user-level (`~/.memgraph-skills` → junctions in `~/.claude/skills/memgraph-*`). ✅ done 07-27.

## New (owner, 2026-07-27 session close)
- **TraceIQ → Agno knowledge base tie-in** — the Agno knowledge layer (Graphiti/vectors/AgentOS) currently has ZERO awareness of TraceIQ data (documented in traceiq ADR-0015). Wire TraceIQ-derived facts (home bases, patterns, labels) into the knowledge layer with provenance pointers back to deterministic rows + "prove it landed" node-count gate. This is the Evidence → Analysis → **Legal Team** tier.
- **AgentOS UI: knowledge + memory features broken** — on first open of AgentOS, many features (specifically knowledge and memory surfaces) weren't working. Diagnose and fix; likely config/wiring between AgentOS UI and the knowledge/memory backends. Owner-reported, unscoped — needs a repro pass first.

## Carried blockers (07-13 handoff)
- **ContextForge transport check** — Streamable HTTP vs SSE-only upstream; closes ADR-0037 blocker (Graphiti auth door, retire no-auth nginx :8071).
- **Identity-spine verification** — does resolution stamp entity keys onto `working.normalized_record` at write time? Read `normalize.py` + entity tables.

## Housekeeping
- Commit ADR drafts **0036–0041** + SESSION-HANDOFF-2026-07-13.md (all uncommitted on `docs/adr-graphiti-memory`).
- ~~**ADR-0034 stranded** on unmerged `docs/adr-0033-0034-evidence-model` — merge or re-home.~~
  **DONE 2026-08-05:** merged to `main`. 0034 kept its number (it was a real gap
  in the ledger); the sibling ADR became **0044** to clear a number collision.
- Verify traceIQ PR push landed (repo slimmed 3.4 GB→276 MB, push in flight 07-27 ~10:04).
- Standing rotations: Coolify API token, OS_SECURITY_KEY.

## TraceIQ lane (separate repo)
- Distance-weighted agreement matrix / conflation resolution (designed, unbuilt; 543 same-sec collisions, 16 >1000 mph pairs).
- UI build (pre-UI; mockups + build brief committed; ADR-0015 hybrid agent-brain).

## Analysis roadmap (unchanged)
① Antecedent reconstruction → ② cycle detection (provocation→reaction→selective-capture; frequency = intent) → ③ documentation-gap detection. Memgraph layer (ADR-0041) is the compute engine candidate for ② .
