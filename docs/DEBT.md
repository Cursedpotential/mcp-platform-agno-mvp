# DEBT / STUB Register

**Rule:** No code ships incomplete-and-silent. Any unavoidable stub gets a
grep-able `# STUB:` marker in code AND a row here. `grep -rn "# STUB:"` must
match this table exactly. Keep this current as part of every change.

## Active stubs (intentional, marked)

| Marker | File | What | Why deferred | Returns with |
|---|---|---|---|---|
| _(none)_ | | | | |

> 2026-06-12: the entire **Cloud Drive Cleanup agent** (not just `trash_cloud_file`)
> was removed from the active topology — owner decision: cloud cleanup is a separate
> future feature, not part of the evidence platform. It returns, fully toolled,
> with the Drive/OneDrive MCP integration. Empty `drive_*_tools` placeholders
> remain in `agents/providers.py` for that feature.

> When a stub is added: add a `# STUB: <tag>` comment at the code site and a row above.
> When resolved: remove both.

## Known debt (tracked, scheduled in the plan)

| Item | Status | Where |
|---|---|---|
| Backend atomic tools (parsers/extractors) attached | planned | P2 — `evidence/registry.py` |
| Evidence schemas populated by a real pipeline | planned | P2/P4 — `evidence/*` |
| `tools-facade` populated (was `PORTED={}`) | planned | P2 — `docker/tools/tools/facade.py` |
| Evals populated (was `CASES=()`) | planned | P5 — `evals/cases.py` |
| Backups (pg_dump + neo4j dump → R2) | planned | P5 |
| Self-hosted evidence vector store (Qdrant/Milvus) | deferred (at scale) | future |
| Part 2 multi-pass analysis engine | next round | future |
| V2 slim Graphiti image; multi-user auth | deferred | future |

## Agno-native audit (2026-06-11) — STOP reinventing; use native (no code written yet)

Pinned `agno==2.6.9`; **latest is 2.6.13** (patch-only, same module structure → low-risk upgrade).
Audit verified against the 2.6.9 wheel + skill references. **Reinvented / about-to-reinvent things
Agno provides natively — switch before building P1–P5:**

| We built/planned | Native Agno (use this instead) |
|---|---|
| Custom `approval_request` table + `/v1/approval-requests` routes | `@approval(type="required")` decorator (`agno.approval.decorator`) + auto-mounted **`/approvals`** router (list/resolve/count/status/delete) + `PostgresDb.create_approval/get_approvals/update_approval` + agents `/continue` w/ `require_approval_resolved`. **Recorded, queryable, blocking approval — exactly our HITL intent. DROP the custom table+routes.** |
| Domain-separated knowledge via custom per-domain plumbing (ADR-0020) | `knowledge_filters` + `enable_agentic_knowledge_filters` on Agent; `Knowledge.search(filters=[EQ("domain","legal_strategy")])` (`agno.filters`). Metadata tags + native filters; agents can pick filters agentically. |
| Custom DAG executor for evidence workflows (ADR-0017) | `agno.workflow` `Step/Steps/Parallel/Condition/Loop/Router`. **Router = agent re-composition on failure; Loop = retry; Condition = branch; `Step(executor=fn)` = arbitrary code.** Registry can stay; orchestration is native. |
| Bespoke tool registry / `tools-facade` | `Toolkit` (`agno.tools.toolkit`) + `MCPToolbox` (`agno.tools.mcp`, DB-fleet tool filtering). Atomic tools = Toolkits/MCP. |
| Custom eval harness (P5) | `agno.eval`: `AccuracyEval`, `AgentAsJudgeEval`, `ReliabilityEval` (tool-call assertions), `PerformanceEval`. |

**Justified custom (NO native equivalent — keep):** `db/embedder.py` NimEmbedder (no native NVIDIA
embedder; query/passage), `db/reranker.py` NvidiaReranker (no native NVIDIA reranker; Cohere leaks).

**Under-used native worth adopting:** `output_schema` (Pydantic) for normalized/analysis records;
`tool_hooks` for custody/audit wrapping; native Knowledge readers/chunkers for ingestion.

**Action:** ~~upgrade to 2.6.13~~ ✅ — ~~rewrite P1 to native `@approval` + `/approvals`~~ ✅ (2026-06-12);
base P2/P3 workflows on native Workflow; P5 evals on `agno.eval`. Updates ADR-0017/0020/0021.

## Resolved (kept for provenance)

| Item | Resolution | Date |
|---|---|---|
| Embedding query/passage mismatch | `db/embedder.py` NimEmbedder — passage default, query-path override | 2026-06-11 |
| Ephemeral pg_duckdb R2 secret | `ensure_duckdb_r2_secret()` runs at API startup (survives DB recreate) | 2026-06-11 |
| HITL row persist + decision→continue (P1) | NATIVE: agno upgraded 2.6.9→2.6.13; `apply_db_modification` = `@approval` + `@tool(requires_confirmation=True)` — pause persists a pending row (`agno.run.approval`), `POST /approvals/{id}/resolve` records the decision, run-continue is gated by `require_approval_resolved`. Custom `approval_request` table+routes removed (`app/main.py`); legacy tables marked in `sql/0002_schema.sql` | 2026-06-12 |
| `apply_db_modification` was `NotImplementedError` | Real write: executes ONE statement against the `analysis` schema (search_path pinned), rejects `evidence.*` references, rolls back on error (`agents/factory.py`) | 2026-06-12 |
| `trash_cloud_file` stub + Cloud Drive Cleanup agent | Removed from active topology entirely (owner decision) — separate future feature | 2026-06-12 |
