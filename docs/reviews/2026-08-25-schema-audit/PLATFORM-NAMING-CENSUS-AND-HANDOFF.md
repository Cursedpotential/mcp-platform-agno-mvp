# PLATFORM-NAMING-CENSUS-AND-HANDOFF — PARTIAL RECOVERY

> _Recovery note: this file's creation (`Add File`) was never captured by any `apply_patch` call across every rollout in `C:\Users\matts\.codex\sessions\2026\08\{25,26,27,28}\` — the file already existed live by the time the earliest `Update File` hunk below was issued, so it was created through some other mechanism (a full-file write, or a session/date genuinely outside this recovery task's scope). **This is therefore a PARTIAL recovery: the document's base structure, headings, and any untouched passages could not be reconstructed.** What follows is every located, accepted `apply_patch` hunk that touched this file, in chronological order, shown as unified-diff-style fragments (`-` = text the fragment replaced, `+` = text it introduced, ` ` = unchanged context) — all verbatim from the session transcripts. Reconstructed 2026-09-02 by Claude Code · Sonnet (recovery lane C)._

D-086 in `docs/DECISION_LOG.md` cites this document as authoritative for the platform naming census. Two accepted `apply_patch` calls were located (both from 2026-08-27), which together add a substantial, coherent D-091/D-092 addendum (fresh `platform` database/role scheme, `agno_app` correction, and receipt-log entry). The base census document (N00-N06 packet definitions, the full owned-name inventory table, sections before 2026-08-27) predates this recovery's scan window and could not be located.

**2 accepted hunk(s) recovered, none of which is a file-creation event.**

---

### Fragment 1 — 2026-08-27T09:05:43.980Z (`Update File`, call `call_ouVAcWnw6mqmUVslg0ea4sDN`, session `rollout-2026-08-27T04-49-40-01a04269-1c37-74a3-8ee5-71106bce4eea.jsonl`)

```diff
@@
 > **Authority:** owner-approved canonical scheme (`PLATFORM-NAMING-MIGRATION-PROPOSAL.md`, 2026-08-26),
 > recorded as **D-086** in `docs/DECISION_LOG.md` and in `docs/PROJECT_CANON.md` §5.
+> **2026-08-27 owner addendum (D-091/D-092):** fresh application database = `platform`;
+> migration/admin = `platform_admin`; runtime = `platform_runtime`; narrow capability roles remain
+> domain-named. Legacy `ai`/`agno_app` stays untouched as source inventory. Migration 0036 is held
+> and must never target `ai`. Canonical content is not redacted; explicit court-export preparation
+> creates a separate derived output only.
@@
 | Owned environment variables | `PLATFORM_*` |
 | Owned Python/DB identifiers | `platform_*` (snake) / `platform-*` (kebab, infra) |
+| Fresh application database | `platform` |
+| Migration/admin identity | `platform_admin` |
+| Runtime identity | `platform_runtime` |
+| Domain capability identities | capability-specific, for example `context_import_writer` |
 | Legacy Agno/AgentOS owned names | compatibility alias only; removal gated by N06 |
@@
 No new branded product name is invented. No replacement public DNS name is *invented* here;
 the registry proposes one and the owner confirms it at the N03 gate (§6, UC-1).
+
+### 1.1.1 Database replacement boundary (D-091)
+
+This is a fresh-database cutover, not a database or role rename in place:
+
+| Existing legacy/source resource | Fresh application resource | Rule |
+|---|---|---|
+| database `ai` | database `platform` | Preserve `ai` untouched through preservation review; never deploy new application migrations into it. |
+| superuser/login `ai` | migration/admin `platform_admin` | `platform_admin` is for administration and migrations, not ordinary runtime. |
+| application role `agno_app` | runtime `platform_runtime` | Create a fresh least-privilege login; do not rename or repurpose the legacy role in place. |
+| legacy mixed grants | domain roles such as `context_import_writer` | Keep each capability role narrow and explicit. |
+
+Migration 0036 is unapplied and held. It may be reconciled into the consolidated fresh baseline and
+target `platform` only after the preservation, role/grant, cutover, tooling, and rollback gates pass.
@@
-> **Note on `agno_app`.** The PostgreSQL application role `agno_app` (165 refs, incl.
-> `sql/0033_chunk_classification_drafts.sql:45` GRANT) is **OWNED** — we created it — but a
-> role rename touches grants across applied migrations and the live connection string.
-> It is assigned to **N05**, not to a naming packet, because it is a live-database change
-> with the same blast radius as the framework swap.
+> **2026-08-27 correction on `agno_app`.** The PostgreSQL role `agno_app` (165 census refs,
+> including grants in applied legacy migrations) remains part of database `ai`'s legacy/source
+> inventory. It is not renamed and is not the fresh application's runtime identity. D-091 creates
+> `platform_runtime` in database `platform`; migration/admin uses `platform_admin`; capability roles
+> stay domain-specific. N05 still owns actual Agno framework/package retirement, but it does not
+> authorize deleting or repurposing `ai`, `agno_app`, or `ai.agno_*` history.
@@
 ### 7.1 Receipt log
 
-_(empty — no packet has executed. N00/N01 completed by this document.)_
+- **2026-08-27 scoped N04 current-truth addendum:** database and role registry reconciled to D-091;
+  legacy `ai` preserved; 0036 explicitly held; D-092 no-canonical-redaction boundary recorded.
+  Documentation only—no database, role, migration, service, DNS, environment variable, branch,
+  Coolify resource, or repository path changed.
```

### Fragment 2 — 2026-08-27T09:12:40.293Z (`Update File`, call `call_eqUdO4gpJf4GND2ldv7ssQzS`, session `rollout-2026-08-27T04-49-40-01a04269-1c37-74a3-8ee5-71106bce4eea.jsonl`)

```diff
@@
-| `ai.agno_*` PostgreSQL tables: `agno_approvals`, `agno_component_configs`, `agno_component_links`, `agno_components`, `agno_eval_runs`, `agno_knowledge`, `agno_learnings`, `agno_memories`, `agno_metrics`, `agno_schedule_runs`, `agno_schedules`, `agno_schema_versions`, `agno_service_accounts`, `agno_sessions`, `agno_spans`, `agno_traces` | 16 tables; 228 refs in `sql/bootstrap/schema_baseline.sql` | Created and owned by the agno library. Renaming breaks the running app and is **not** in scope for any naming packet. They disappear with N05. |
+| `ai.agno_*` PostgreSQL tables: `agno_approvals`, `agno_component_configs`, `agno_component_links`, `agno_components`, `agno_eval_runs`, `agno_knowledge`, `agno_learnings`, `agno_memories`, `agno_metrics`, `agno_schedule_runs`, `agno_schedules`, `agno_schema_versions`, `agno_service_accounts`, `agno_sessions`, `agno_spans`, `agno_traces` | 16 tables; 228 refs in `sql/bootstrap/schema_baseline.sql` | Created and owned by the agno library inside legacy database `ai`. Renaming is **not** in scope. D-091 requires preserving `ai` untouched through preservation review; N05 may retire framework callers but does not authorize table deletion. |
@@
-- **Must not:** be started as part of the naming program, and must never be reported as complete
-  because a service was renamed.
+- **Must not:** be started as part of the naming program, must never be reported as complete
+  because a service was renamed, and must not delete or repurpose legacy database `ai`, role
+  `agno_app`, or any `ai.agno_*` table. D-091's preservation review is a separate prerequisite.
```
