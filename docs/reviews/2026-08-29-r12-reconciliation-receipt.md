# R12 Governed Legal Workbench — Reconciliation Receipt (Read-Only)

> **Assessment date:** 2026-08-29  
> **Mode:** Read-only. No edits, commits, deployments, or mutating commands.  
> **Sources:** AGENTS.md, HANDOFF-2026-08-27, RECONCILIATION-DOMAIN-WORKSTREAMS.md, R00/R02/R12/R14 guides, Workbench implementation files, git state.

---

## 1. Current Truth (Implemented vs. Documented)

| Area | Documented Intent | Actual Implementation | Evidence |
|------|-------------------|----------------------|----------|
| **Product naming** | "Evidence operations desk" / "Import source context" | ✅ Present in `unified-intake.tsx` | `workbench/web/src/components/unified-intake.tsx:45-52` |
| **Singleton case scope** | One owner, one personal case; intake blocked if ≠1 Matter | ✅ Enforced in UI | `unified-intake.tsx:119-128` |
| **Case Bible Sorted (R2)** | Default ingestion point via R2 bucket browser | ✅ Integrated via `listUIWSources` | `unified-intake.tsx:334-358` |
| **AI-chat promotion fence** | D-082: permanently denied | ✅ Local denial in `promote.py` + spine denial | `promote.py:133-151`; `server/evidence/custody.py:173-213`; `server/api/evidence_routes.py` |
| **Platform API auth** | OS_SECURITY_KEY bearer from mounted secret | ✅ Runtime read per request | `platform_api_auth.py:18-35`; `ingest_routes.py:28-40` |
| **Portkey inference** | x-portkey-api-key + config headers | ✅ Configured in `settings.py` + `chat_gateway.py` | `settings.py:89-95`; `chat_gateway.py` |
| **R2 SigV4** | OBJECT_STORE_* env vars via boto3 | ✅ In `deploy/workbench.yaml` + `settings.py` | `deploy/workbench.yaml:45-52`; `settings.py:70-78` |
| **Direct-store paths** | None from Workbench to evidence/custody | ✅ `promote.py` calls Platform API only | `promote.py:67-110` |
| **Graphiti client** | Read-only wrapper | ✅ No write operations | `graphiti_client.py:76-85` |

**Contradictions (R00 §Current implementation and gaps):**
- D-069 says intake is context-only, but `AGENTS.md:33` still describes "Evidence custody → parse → normalize" and `server/temporal/workflows.py:172-182,219-247` runs custody first
- D-070 retires Graphiti, but `server/agents/providers.py:194-212` still attaches writable Graphiti MCP tools when `GRAPHITI_MCP_URL` is set
- D-072 forbids new Matter/CourtCase, but `server/api/case_management_routes.py:68-82` and `server/case_management/repository.py:511-581` have active create routes/writers
- No universal immutable `ProjectionReceipt`/aggregation-manifest in PG (R00 §Missing shared contract)

---

## 2. Stale Assumptions (with File-Line Evidence)

| # | Stale Assumption | File / Line | Status |
|---|------------------|-------------|--------|
| 1 | Traefik/Authentik domain labels active for Workbench | `deploy/workbench.yaml:85-98` (COMMENTED OUT) | **Stale** — labels present but commented |
| 2 | `workbench/sprint` branch is production milestone target | `deploy/workbench.yaml:7` | **Stale** — still deployed on sprint, not main |
| 3 | Graphiti MCP URL configured and apps running | `deploy/workbench.yaml:58`; `deploy/data-graphiti.yaml:99-118` | **Stale** — D-070 retired Graphiti; apps still running |
| 4 | Matter/CourtCase creation dialogs are valid product surface | `matter-workspace.tsx:145-180` (CreateMatterDialog, CreateCourtCaseDialog) | **Stale** — D-072 forbids new; UI still has dialogs |
| 5 | Workbench direct Graphiti access is acceptable | `graphiti_client.py:76-85` calls Graphiti without authorization | **Stale** — bypasses governed retrieval |
| 6 | Agno agents have generic PG write access via shared tools | `server/agents/providers.py:147-158,192` | **Stale** — authority drift; exec-tier uses superuser `ai` |
| 7 | `RUNTIME_ENV=dev` in exec-tier is acceptable | `deploy/workbench.yaml:38` | **Stale** — production should not run dev flags |
| 8 | PG superuser `ai` used by exec-tier | `deploy/data-pg.yaml:40-48`; R14 audit snapshot | **Stale** — least privilege FALSE, RLS 0/143 tables |
| 9 | No live integration tests executed | `AGENTS.md:174` mandates `pytest -m integration` | **Stale** — only 2 integration-marked files exist, none run |
| 10 | Coolify Watch Paths are current | Many apps watch root `compose.*` paths | **Stale** — R14 audit: obsolete Watch Paths |
| 11 | Symbolic `HEAD` without matched deployment SHA is acceptable | All apps use `git_commit_sha=HEAD` | **Stale** — no fleet-wide SHA/manifest parity |

---

## 3. Exact Acceptance Blockers (Mapped to STOP Gates)

### R12 STOP Gates (R12-legal-workbench.md:204-211)

| Gate | Blocker | Evidence |
|------|---------|----------|
| **STOP-R12-1** | Healthy Workbench container ≠ governed legal use proof | R12 audit: "healthy front ends do not prove governed authorization/export" |
| **STOP-R12-2** | AgentOS auth, singleton scope, least-privilege DB, direct-store denial, privilege/redaction, citation resolution unproven live | R12 audit: "High security/authority gap: UI health does not prove governed retrieval or least privilege" |
| **STOP-R12-3** | External filing/service/messaging/delivery disabled absent explicit authorization | R12 §Out of scope; no separate authorization documented |
| **STOP-R12-4** | Generic Agno database writes not removed/denied; mutations don't pass through authenticated Workbench domain commands with PG receipts | R12 audit: "Critical authority drift: drafting/runtime agents can potentially bypass typed citations, review, and export receipts" (`providers.py:147-158,192`) |
| **STOP-R12-5** | AI-chat input can reach evidence import/custody; created work/Timesketch rows can masquerade as facts | R12 audit: "Critical live/product violation (GAP-023/GAP-032): D-082 permanently forbids AI-chat promotion" — Coolify deploy + live negative test still open |

### R14 STOP Gates (R14-migration-cutover-integration.md:256-266)

| Gate | Blocker | Evidence |
|------|---------|----------|
| **STOP-R14-1** | Fleet-wide immutable SHA/rendered-manifest parity proof missing | R14 audit: "many applications point at `/deploy/*.yaml` but still watch obsolete root `compose.*` paths... no fleet-wide immutable SHA/rendered-manifest parity proof" |
| **STOP-R14-2** | Exec-tier superuser, unverified AgentOS bearer, `RUNTIME_ENV=dev`, direct agent/store paths, Graphiti write capability block cutover | R14 audit: "exec still uses superuser `ai`; RLS was enabled on 0 of 143 tables... Graphiti write capability" |
| **STOP-R14-2A** | Agno boundary: generic write access to canonical PG | R14 audit: "STOP/critical: Agno has a path to write the canonical store outside governed domain commands" |
| **STOP-R14-3** | Service health/schema/unit tests ≠ live receipts/reconciliations | R14 §STOP-R14-3: "none substitutes for live receipts and reconciliations" |
| **STOP-R14-4** | Derived stores cutover blocked until PG manifests, receipts, counts/hashes, horizon traps, rebuilds, rollback pass | R14 §STOP-R14-4: Weaviate native, Neo4j, Surreal, Timesketch all lack rebuild/rollback proof |
| **STOP-R14-5** | n8n count zero, absent Temporal crash/replay proof, absent governed Workbench export proof | R14 audit: "n8n workflow count is zero; no live durability probe... Workbench healthy but no governed export proof" |
| **STOP-R14-6** | Receipt backed only by process-local execution; multiplicative retry loops without observable budget | R14 audit: "acknowledgement is not durable completion and attempt semantics are not controlled" (16× DB transactions possible) |
| **STOP-R14-7/8/9** | Timesketch authority/edit/operations gates unmet | R14 §STOP-R14-7/8/9: no deployed fork, no writer denials, no rebuild/rollback proof |

---

## 4. Satisfied Checklist Items (with File-Line Evidence)

| # | Item | File / Line | Verified |
|---|------|-------------|----------|
| 1 | Workbench product naming: "Evidence operations desk" / "Import source context" | `unified-intake.tsx:45-52` | ✅ |
| 2 | Singleton case scope: intake blocked if ≠1 Matter | `unified-intake.tsx:119-128` | ✅ |
| 3 | Case Bible Sorted as default R2 browser source | `unified-intake.tsx:334-358` | ✅ |
| 4 | AI-chat promotion permanently denied locally in `promote.py` (D-082 fence) | `promote.py:133-151` (`_promote_chat_export` returns denial) | ✅ |
| 5 | Platform API bearer read from mounted file at runtime | `platform_api_auth.py:18-35`; `ingest_routes.py:28-40` | ✅ |
| 6 | Portkey inference routing configured with saved gateway config | `settings.py:89-95`; `chat_gateway.py` | ✅ |
| 7 | R2 SigV4 via OBJECT_STORE_* env vars | `deploy/workbench.yaml:45-52`; `settings.py:70-78` | ✅ |
| 8 | No direct-store paths from Workbench to evidence/custody | `promote.py:67-110` calls Platform API only | ✅ |
| 9 | Graphiti client is read-only wrapper | `graphiti_client.py:76-85` (search_memory_facts, search_nodes, get_episodes only) | ✅ |

---

## 5. Missing Tests / Live Proof (Explicit Gaps)

| # | Missing Proof | Blocked By |
|---|---------------|------------|
| 1 | Live singleton-scope governed product creation/export observed | STOP-R12-2 |
| 2 | Blocked unsupported export / revoked access / AI-only assertion / unanchored delta tests live | STOP-R12-2, STOP-R12-5 |
| 3 | Immutable export receipt reproduction hash observed | STOP-R12-2, ACCEPT-R12 |
| 4 | Live negative test proving AI-chat promote/promote-all paths disabled (GAP-032) | STOP-R12-5, WP-C01 |
| 5 | Live test proving direct Graphiti client disabled/denied | STOP-R12-4, STOP-R14-2A |
| 6 | Live test proving Agno generic PG write access denied | STOP-R14-2A |
| 7 | Live test proving least-privilege DB roles in production | STOP-R14-2 |
| 8 | Live test proving RLS enabled on evidence/working/analysis tables (143 tables) | STOP-R14-2 |
| 9 | Temporal crash/replay proof | STOP-R14-5, STOP-R14-6 |
| 10 | Timesketch fork deployed/proven | STOP-R14-7/8/9 |
| 11 | Paired-walk leakage trap test | STOP-R14-4, STOP-R14-8 |
| 12 | Rollback drill executed | STOP-R14-4, STOP-R14-9 |
| 13 | Fleet-wide SHA/manifest parity verification | STOP-R14-1 |

---

## 6. Next Non-Overlapping Implementation Packets (Priority-Ordered, Exact Files)

### Packet 1 — AI-Chat Promotion Fence + Live Negative Tests
**Unblocks:** STOP-R12-5, GAP-032, WP-C01  
**Files to verify/modify:**
1. `workbench/api/app/service/promote.py:133-151` — verify `_promote_chat_export` denial logic
2. `workbench/api/app/service/detect.py:17-31` — verify `chat_export` classification (ChatGPT `mapping`, claude.ai `chat_messages`, Claude Code `.jsonl`)
3. `server/evidence/custody.py:1-13,173-213` — verify `ingest_artifact()` AI-chat denial before any write
4. `server/api/evidence_routes.py` — verify `workflow=chat-transcript` denial at spine
5. `deploy/workbench.yaml` — push to trigger Coolify deploy on `workbench/sprint`
6. `tests/integration/test_ai_chat_promotion_denial.py` — **NEW** live negative test: POST AI-chat export → verify 0 evidence/custody rows, 0 `/v1/evidence/import` calls

### Packet 2 — Disable Direct Graphiti Path from Workbench
**Unblocks:** STOP-R12-4, STOP-R14-2A  
**Files to verify/modify:**
1. `workbench/api/app/repo/graphiti_client.py` — remove or gate behind feature flag (e.g., `ENABLE_GRAPHITI_CLIENT=false`)
2. `workbench/api/app/service/graphiti.py` — if exists, remove
3. `deploy/workbench.yaml:58` — remove `GRAPHITI_MCP_URL` or set `MCP_DIRECT_BYPASS_ALLOWED=false`
4. Live test: Verify Workbench cannot call Graphiti MCP tools (network/role boundary)

### Packet 3 — Enforce Least-Privilege PG Roles + RLS
**Unblocks:** STOP-R14-1, STOP-R14-2, STOP-R14-2A  
**Files to verify/modify:**
1. `sql/NNNN_restricted_roles.sql` — **NEW** migration for restricted roles (per `deploy/data-pg.yaml:40-48`)
2. `sql/NNNN_rls_evidence_tables.sql` — **NEW** migration enabling RLS on 143 evidence/working/analysis tables
3. `server/core/session.py` — DB session factory using least-privilege role (not superuser `ai`)
4. Deploy + verify exec-tier no longer uses superuser `ai`
5. Verify RLS enabled on all 143 tables via `pg_catalog.pg_class.relrowsecurity`

### Packet 4 — Fleet-Wide Deployment Parity
**Unblocks:** STOP-R14-1  
**Files to verify/modify:**
1. All Coolify app configs — update Watch Paths to scoped paths (e.g., `workbench/**`, `server/**`, not root `compose.*`)
2. Verify `git_commit_sha` matches deployed manifest for all apps (not symbolic `HEAD`)
3. Record branch/SHA/config hashes in integration manifest (JSON)

### Packet 5 — Integration Test Suite Execution (Mandatory per AGENTS.md)
**Unblocks:** STOP-R14-3, ACCEPT-R14  
**Files to verify/modify:**
1. `uv run pytest -m integration` — mandatory live integration tests
2. `tests/integration/` — add service-specific live integration tests per R00-R13
3. Document receipts, evidence pointers, owners, last-verified timestamps in `docs/integration-receipts/`

---

## 7. Questions for Owner Resolution

1. **Graphiti removal priority:** Packet 2 (Graphiti) and Packet 1 (AI-chat fence) are independent. Which first?
2. **Least-privilege migrations:** Packet 3 requires new SQL migrations. Exact migration numbers/names needed?
3. **Live proof standard:** Run negative tests against deployed `workbench/sprint` on ovh-app (100.72.169.40:8020) or local?
4. **Timesketch fork:** R14 STOP-R14-7/8/9 gate on Timesketch. In scope for this reconciliation or separate R14 workstream?
5. **R12-PHASE1 pre-mortem:** Include failure matrix comparison in receipt, or only R12/R14 guides?

---

## 8. Appendix: Key File Inventory

| File | Purpose | Status |
|------|---------|--------|
| `AGENTS.md` | Universal entry point, stack, knowledge-horizon | Current |
| `docs/HANDOFF-2026-08-27-platform-development-takeover.md` | PARTIAL status, dirty worktree, UNRESOLVED | Current |
| `docs/reviews/2026-08-25-schema-audit/RECONCILIATION-DOMAIN-WORKSTREAMS.md` | R00-R14 dependency map | Current |
| `docs/reviews/.../R00-canon-contract-freeze.md` | Frozen lifecycle, contradictions | Current |
| `docs/reviews/.../R02-context-ingest-parser-boundary.md` | Critical boundary violations | Current (WP-C01 correction noted) |
| `docs/reviews/.../R12-legal-workbench.md` | Owned surfaces, gaps, STOP/ACCEPT gates | Current (WP-C01 correction noted) |
| `docs/reviews/.../R14-migration-cutover-integration.md` | Integration invariants, audit snapshot, STOP gates | Current |
| `deploy/workbench.yaml` | Coolify deployment, env, volumes, commented Traefik | Current (sprint branch) |
| `workbench/api/app/service/promote.py` | Doc vs chat_export paths, D-082 fence | Current (fenced) |
| `workbench/api/app/service/detect.py` | Chat_export classification | Current |
| `workbench/api/app/repo/graphiti_client.py` | Read-only Graphiti wrapper | Current (should be removed) |
| `workbench/api/app/config/platform_api_auth.py` | Runtime bearer from mounted secret | Current |
| `workbench/web/src/components/unified-intake.tsx` | Singleton scope, Case Bible Sorted R2 browser | Current |
| `workbench/web/src/components/matter-workspace.tsx` | Matter/CourtCase hierarchy UI (stale dialogs) | Current |
| `workbench/api/app/config/settings.py` | Pydantic settings, MCP/PORTKEY/Graphiti config | Current |
| `server/api/main.py` | AgentOS entrypoint, OS_SECURITY_KEY bearer | Current |
| `server/api/ingest_routes.py` | _authorize function, OS_SECURITY_KEY validation | Current |
| `server/evidence/custody.py` | ingest_artifact AI-chat denial | Current (fenced) |
| `server/api/evidence_routes.py` | Evidence import route denial | Current (fenced) |
| `server/agents/providers.py` | Generic PG write provider, Graphiti MCP tools | Current (authority drift) |

---

**End of Receipt**  
*Generated read-only. No mutations performed.*