# DEBT / STUB Register

> _Byline: Claude Code · Sonnet 5 · 2026-08-09 (docs/registers true-up: knowledge_filters/Weaviate
> correction, agno pin correction, STUB-rule test scoping, parser-lane queue update, justified-custom
> addition, dated audit stamp)_

> **2026-08-09 audit** (docs/registers true-up pass): all "resolved" rows below re-checked
> against the tree and still verified resolved (parser/extractor modules present under
> `server/tools/parsers/{messaging,ai_chat,generic}/` + `server/tools/extractors/`; the
> `docker/tools/tools/facade.py` facade still `load_builtin_tools()`-backed — spot-checked,
> not exhaustively re-run). Planned rows re-verified open: "Evidence schemas populated by a
> real pipeline" (P2/P4), `evals/cases.py` still `CASES: tuple[Case, ...] = ()`, and Backups
> (pg_dump + neo4j dump → R2) still has no recurring implementation — `scripts/backup_ovhdata_hot.sh`
> exists but is a one-time host-retirement snapshot (Postgres/SurrealDB/Weaviate only, explicitly
> skips Neo4j/Milvus to a cold-copy phase), not the recurring R2 lane this row tracks. The
> session's rejection list (items 1–6, owner planning session 2026-08-09) was re-reviewed and
> HELD — no reversals — with one addition: the derivation engine joins the "justified custom"
> list below (see TD-JC).

**Rule:** No code ships incomplete-and-silent. Any unavoidable stub gets a
grep-able `# STUB:` marker in code AND a row here. **Scope: non-test code only**
(`server/`, `docker/`, `evals/`, `scripts/`) — `grep -rn "# STUB:" server docker
evals scripts` must match this table exactly. Keep this current as part of
every change. Test doubles (fake engines, stub clients, etc. used *by* tests
to isolate a unit) are a different thing — mark those `# TEST-DOUBLE:` in
`tests/`, not `# STUB:`; they don't belong in this register because they are
never incomplete-and-silent in production, they're deliberate test fixtures
(corrected 2026-08-09 — `tests/test_run_ledger.py:61` and
`tests/test_custody.py:19` were mistagged `# STUB:` and re-tagged
`# TEST-DOUBLE:` for exactly this reason).

## Active stubs (intentional, marked)

| Marker | File | What | Why deferred | Returns with |
|---|---|---|---|---|
| _(none)_ | | | | |

> 2026-06-12: the entire **Cloud Drive Cleanup agent** (not just `trash_cloud_file`)
> was removed from the active topology — owner decision: cloud cleanup is a separate
> future feature, not part of the evidence platform. It returns, fully toolled,
> with the Drive/OneDrive MCP integration. Empty `drive_*_tools` placeholders
> remain in `server/agents/providers.py` for that feature (still true as of this
> doc-sync pass, 2026-07-10).

> When a stub is added: add a `# STUB: <tag>` comment at the code site and a row above.
> When resolved: remove both.

## Known debt (tracked, scheduled in the plan)

| Item | Status | Where |
|---|---|---|
| Backend atomic tools (parsers/extractors) attached | **resolved 2026-07-10** — real chatminer-backed parsers exist under `server/tools/parsers/{messaging,ai_chat,generic}/` + `server/tools/extractors/`, registry populated | P2 — `server/tools/registry.py` |
| Evidence schemas populated by a real pipeline | planned | P2/P4 — `server/evidence/*` |
| `tools-facade` populated (was `PORTED={}`) | **resolved 2026-07-10** — `load_builtin_tools()`-backed, real registry + SBV proxy surface | P2 — `docker/tools/tools/facade.py` |
| Evals populated (was `CASES=()`) | planned (still `CASES: tuple[Case, ...] = ()` as of 2026-07-10) | P5 — `evals/cases.py` |
| Backups (pg_dump + neo4j dump → R2) | planned | P5 |
| Self-hosted evidence vector store (Qdrant/Milvus) | **resolved 2026-07-11** — Milvus is the locked platform-wide vector substrate (ADR-0026/ADR-0027), self-hosted + LIVE on the `data-vector` Coolify app; the "Qdrant" framing was stale. Evidence-text-embeddings *ingestion* at scale is still future work, tracked as "Evidence schemas populated by a real pipeline" above. | future → `docs/adr/0026-self-hosted-milvus-coolify-semantic-store.md`, `docs/adr/0027-milvus-platform-wide-vector-substrate.md` |
| Part 2 multi-pass analysis engine | next round | future |
| V2 slim Graphiti image; multi-user auth | deferred | future |
| Knowledge text embedder (`nvidia/nv-embed-v1`) calls NVIDIA NIM **direct**, not through the Portkey gateway | owner decision 2026-08-01: direct for now, Portkey later | `server/core/session.py` — see the TODO above `_EMBED_TEXT_BASE_URL`; target config already exists and is verified live at `docker/gateway/portkey/configs/embed.json` (reused as-is by Graphiti's own Portkey cutover) |

## Agno-native audit (2026-06-11) — STOP reinventing; use native (no code written yet)

~~Pinned `agno==2.6.9`; latest is 2.6.13~~ — **corrected 2026-08-09: `requirements.txt` currently
pins `agno==2.8.7`** (verified by grep against the live file; not the `2.8.0` other docs — AGENTS.md,
CONVENTIONS.md, canon §8 — still cite as current, itself a drift this pass did not chase down
further; flag for a follow-up sync). Audit below was verified against the 2.6.9 wheel + skill
references at the time it was written and has not been re-run against 2.8.7; treat the specific
API surfaces named as needing re-verification, not as stale in spirit. **Reinvented /
about-to-reinvent things Agno provides natively — switch before building P1–P5:**

| We built/planned | Native Agno (use this instead) |
|---|---|
| Custom `approval_request` table + `/v1/approval-requests` routes | `@approval(type="required")` decorator (`agno.approval.decorator`) + auto-mounted **`/approvals`** router (list/resolve/count/status/delete) + `PostgresDb.create_approval/get_approvals/update_approval` + agents `/continue` w/ `require_approval_resolved`. **Recorded, queryable, blocking approval — exactly our HITL intent. DROP the custom table+routes.** |
| Domain-separated knowledge via custom per-domain plumbing (ADR-0020) | `knowledge_filters` + `enable_agentic_knowledge_filters` on Agent. **Dict filters ONLY on Weaviate** (the locked platform vector substrate, ADR-0040) — `Knowledge.search(filters={"domain": "legal_strategy", "disclosure_tier": ...})`. Corrected 2026-08-09: ~~`Knowledge.search(filters=[EQ("domain","legal_strategy")])` (`agno.filters` `FilterExpr` list)~~ — agno's Weaviate adapter SILENTLY DROPS `FilterExpr` lists (`log_warning` + `filters=None`); source = `AGENTS.md`'s own Weaviate-specific landmine paragraph ("verified in agno 2.8.0 source, 2026-08-02"), not `docs/reference/agno-memory-and-storage/02-knowledge-and-retrieval.md:1195` (that push-down table documents Milvus, a different adapter with different filter support). Metadata tags + dict filters; agents can pick dict filter *values* agentically (`enable_agentic_knowledge_filters`), never a `FilterExpr`. |
| Custom DAG executor for evidence workflows (ADR-0017) | `agno.workflow` `Step/Steps/Parallel/Condition/Loop/Router`. **Router = agent re-composition on failure; Loop = retry; Condition = branch; `Step(executor=fn)` = arbitrary code.** Registry can stay; orchestration is native. |
| Bespoke tool registry / `tools-facade` | `Toolkit` (`agno.tools.toolkit`) + `MCPToolbox` (`agno.tools.mcp`, DB-fleet tool filtering). Atomic tools = Toolkits/MCP. |
| Custom eval harness (P5) | `agno.eval`: `AccuracyEval`, `AgentAsJudgeEval`, `ReliabilityEval` (tool-call assertions), `PerformanceEval`. |

**Justified custom (NO native equivalent — keep):** `db/embedder.py` NimEmbedder (no native NVIDIA
embedder; query/passage), `db/reranker.py` NvidiaReranker (no native NVIDIA reranker; Cohere leaks).
(Now `server/core/embedder.py` / `server/core/reranker.py` — ADR-0033 `db/` → `server/core/`.)
Added 2026-08-09: the **checkpoint-derivation engine** (ADR-0045, Decision B) — the sole
grant-locked refresher that materializes version-pinned derived-pass checkpoints from the one
canonical factual store, one predicate, two schedules (as-lived incremental / hindsight
on-prompt), every derivation hash-attested to `ops.audit_ledger`. No Agno-native equivalent
exists for version-pinned, hash-attested, single-writer derivation of bitemporal knowledge-horizon
checkpoints — this is the platform's own knowledge-horizon mechanism (`AGENTS.md` §"WHY THIS
EXISTS"), not a generic capability an off-the-shelf component provides.

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
| `apply_db_modification` was `NotImplementedError` | Real write: executes ONE statement against an allowlisted schema (`DB_WRITE_SCHEMAS` env, default `analysis`; `evidence` hard-denied regardless of config), search_path pinned to the validated target, rejects `evidence.*` references, rolls back on error (`agents/factory.py`; allowlist added 2026-07-29) | 2026-06-12 |
| `trash_cloud_file` stub + Cloud Drive Cleanup agent | Removed from active topology entirely (owner decision) — separate future feature | 2026-06-12 |

## Parser-lane follow-ups (from the 2026-08-02 gap review — owner: "ensure these go on a list")

Source: docs/HANDOFF-2026-08-02-sbv-chatminer-parser-gap-review.md (phases + acceptance criteria there).

1. ~~**Go-side import-scoping (review Phase 1):** SBV upload returns
   `{job_id, import_id}`; messages/calls carry import_id; add
   `GET /api/imports/:id/activity`; bind progress + hashes to the same id;
   custody reconciliation becomes mandatory for the forensic tier. This is the
   restore condition for the 2026-08-02 SBV demotion (DECISION_LOG).~~
   **LANDED — PR #18 (`aacf21c`, merged 2026-08-06).** `server/tools/_sbv_client.py`
   is import-scoped throughout (`import_id` on `import_detail`/`import_records`/
   `import_rejections`/`import_attachments`/`hashes`, verified 2026-08-09).
   This is the basis for **SBV's promotion back to primary** (owner directive
   2026-08-05; D-040, `docs/DECISION_LOG.md`).
2. **Streaming/batch ingestion contract (review Phase 2) — PARTIAL, open item
   tracked in S7:** the **SBV path** now has its own import-scoped
   reconciliation (item 1, landed) — but the **generic/cross-parser**
   contract this row originally scoped is still open: iterator/batch parser
   protocol with backpressure; a real `evidence.raw_rejected` WRITER (the
   table + indexes exist since sql/0012 and `server/tools/parsers/messaging/
   sms_xml.py` + `server/tools/repair/types.py` reference the table by name,
   but no code path currently `INSERT`s into it — verified 2026-08-09, zero
   writers found); `record_count_claimed` capture; claimed = accepted +
   rejected + accounted-duplicate gate; replace the in-memory multipart
   upload for non-SBV parsers.
3. **Registry priority/quality metadata (review Phase 3) — open, S7:** explicit
   `priority` / `quality_tier` / `streaming` / `custody_capabilities` /
   `max_safe_size` on the tool contract; golden corpora per format;
   primary/fallback equivalence tests; SBV shadow-comparison harness.
4. **ChatMiner hardening (review Phase 4) — open, S7:** rename `message_hash` →
   `content_fingerprint` (full digest, never custody); deterministic IDs from
   (artifact H1, parser version, source indices); tz-aware UTC timestamps;
   bounded detection probes instead of whole-file reads.
5. **Repair-layer wiring — open, S7:** adopt `server/tools/repair/` one format
   at a time (SMS XML first, then CSV) only AFTER the ledger/rejection/
   reconciliation writers of item 2 exist — the observability contract is the
   acceptance criterion. Coordinate with the repair-layer chat (their branch:
   feat/stream-repair-layer — landed in part via PR #18's governed repair
   slice, item 1 above; item 2's generic writer is still the gate for
   adopting `server/tools/repair/` beyond SBV).
