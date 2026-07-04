# Forensic-DB Reconciliation — STATUS (complete)

> _Byline: Claude Code · Opus 4.8 · 2026-06-30 ~09:45 EDT_

## Done
| Phase | Output | State |
|---|---|---|
| Architecture draft (91k words) | `…/scratchpad/forensic-db-arch/FORENSIC_DB_ARCHITECTURE_DRAFT.md` | session scratchpad (paper draft) |
| Durable addendum | `docs/planning/forensic-db-extension-and-reconciliation-addendum.md` | committed to repo tree |
| Extract (as-built + prior schemas + behavioral ontology) | `extracted/E1–E5` | done |
| Reconciled schema | `RECONCILED_SCHEMA.sql` (93 tables, evidence/analysis/public) | done |
| Final reconciliation report | `FINAL_RECONCILIATION_REPORT.md` | done |
| Domain/store/review detail | `domains/` (8) · `stores/` (3) · `review/` (2) | done |
| **Live introspection** (Tailscale→ovh3-data) | `live-introspection/` (PG dump + Neo4j/Surreal/Milvus + summary) | done |
| **Live diff + migration** | `LIVE_DIFF_AND_MIGRATION.md` + `migrations/0005_forensic_reconciliation.sql` | done |

## ✅ APPLIED to live PG — 2026-06-30 ~09:55 EDT (owner approved "apply")
`migrations/0005_forensic_reconciliation.sql` run against the live `agno-postgres:18-duckdb` (DB `ai`) over Tailscale → **psql exit 0, zero errors**. Pre-apply rollback snapshot: `live-introspection/PG_pre_0005.sql`. Apply log: `migrations/0005_apply_log.txt`. Acceptance: `migrations/0005_acceptance.txt`. Verified: 4 drifted extensions installed; types created incl. `sensitivity_tier` (disclosure_tier fix); `entity_type` extended; `evidence.evidence_hash` +8 cols; tables now evidence=9 / analysis=75 / public=15; views present.
**Still data-empty / next:** `analysis.behavior_category` exists but 0 rows — needs the 18-category + detection-pattern SEED load from the behavioral ontology. Per-store (Milvus forensic collections, Neo4j/Semantica, SurrealDB) NOT yet created — separate step.

## ✅ BEHAVIOR SEED APPLIED — 2026-06-30 (migration 0006)
`migrations/0006_behavior_seed.sql` = **strictly-additive UNION of 9 fragment sources** (G1 analyzer-app, G2 seed-patterns.ts, G3 dial TTL, G4 detection_patterns.py+E4, G5 agno-alpha classifiers, G6 behavioral_patterns_dataset/temp_patterns+unsloth, G7 zep_salem ontology v3, G8 conversation logs, G9 OneDrive+D: drives). Per-source tally in `behavior-seed/MERGED_behavior_seed.md`. Applied --single-transaction, psql exit 0. **Live counts:** detection_pattern_set=1, behavior_category=153 (124 neg/13 pos/8 linguistic_marker/8 neutral), detection_pattern=512, pattern_lexicon=51 (12 sealed/37 restricted/2 public), behavior_category_mcl=225 (104 critical J/K). Apply log: `migrations/0006_apply_log.txt`.
**Court-safety:** every detection_pattern is a HYPOTHESIS (bias_caution=true, authored_perspective='single_party_complainant' + symmetric-application caveat citing Kubicki v. Sharpe); ZERO real PII in git — child/party/personal identifiers are SEALED-lexicon REDACTED placeholders, real values load out-of-band.
**Fix applied during seed:** custom enum types live in the `ai` schema (0004 was applied under search_path "$user"=ai during 0005) — 0006 search_path set to `analysis, ai, public`. Quirk noted; types are functional where they are.

## Verdict
Migration is **additive / low-risk**: 91 of 93 tables greenfield; 2 existing tables get additive `ADD COLUMN`s; 4 drifted-absent extensions + the never-applied `0004` types get created; **no destructive DDL** (verified: 0 uncommented DROP/TRUNCATE/DELETE). Safe to apply pending owner sign-off; run by hand on the live volume (not docker-entrypoint).

## NOT done (needs owner) — deliberately stopped here
- **No DDL executed against the live DB.** `0005` is a reviewable draft.
- 8 `TODO(human):` decisions in `RECONCILED_SCHEMA.sql` / migration (incl. the `knowledge_horizon` column rename).
- **BLOCKING for court output:** child-name seed-routing / redaction (court-safety finding #1).
- Verify the 4 contrib extensions are baked into the `pg_duckdb` image before applying (else the migration aborts at step 0).

## To apply (when owner approves) — read-only verify first
1. `psql … -f migrations/0005_forensic_reconciliation.sql` (idempotent; STEP 0/1 = extensions+types in autocommit before table DDL).
2. Acceptance checks in `LIVE_DIFF_AND_MIGRATION.md` §6 (`\dx \dn \dT \dt evidence.* analysis.*`; Milvus `list_collections`; Neo4j `db.labels`; Surreal `INFO FOR DB`).
3. Rollback = drop the new tables + the additive columns (documented §7).
