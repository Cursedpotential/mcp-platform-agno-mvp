# HANDOFF S1 — Docs & registers true-up

> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._
> _2026-08-09 · repo @ a68fabd · STATUS: READY once S4 task 4 allocates D-NNN ids · Depends: S4 task 4 · Blocks: none (do EARLY — everything downstream plans against these docs)_
> Inventory items: N5, N8(doc), FA(doc half), P1–P5, D1f–D4f(row), TD-JC, TR-1, TR-2, TR-5(commit half), R-6, OQ-5 closure.
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.

## Goal
Make every canonical doc true against the tree and the 2026-08-09 rulings, and make the two
self-checking registers (DEBT stub rule, traceability refs) mechanically verifiable.

## Tasks
1. [P1] README "Active plan: `plans/`" → `docs/BUILD_PLAN.md`; canon §6 `plans/logical-herding-forest.md`
   ref removed. Check: `grep -rn "plans/" README.md docs/PROJECT_CANON.md` → every hit resolves.
2. [P2] AGENTS.md:170 → `vendored/sbv/internal/custody.go`.
3. [P4] REPO_STRUCTURE.md: add `analytics/`, `deploy/`, `tool-skills/`, `database/` rows.
   `database/schema/00_analysis_graph.surql` noted "fate pending OQ-7 ruling — do not delete".
4. [P5] PROJECT_CANON re-sync: header → 2026-08-09 + edit trail; §4 data-tier hosts → ovh-files
   (100.91.190.107; cite commits 5e829ab/a68fabd); §5 SurrealDB → "RETIRED, zero callers" (matches
   server/core/session.py); §6 P4 → PR #18 universal import engine + SBV promotion (exact Phase-5a
   wording pends OQ-9 — leave a marked TODO if unruled).
5. [FA-doc] AGENTS.md:41 → disclosure_tier on working.normalized_record is **TEXT + CHECK**; the
   `ai.disclosure_horizon` enum lives on analysis.time_assertion/timeline_event only. Keep §1
   invariant text verbatim otherwise; add pointer to ADR-0045 (S4 draft) for the derivation
   amendment once signed.
6. [N5] Rewrite docs/DEBT.md:46 knowledge_filters row: **dict filters only on Weaviate**; FilterExpr
   lists silently dropped by agno 2.8.0 adapter (log_warning + filters=None). Cite AGENTS.md's own
   landmine paragraph ("verified in agno 2.8.0 source, 2026-08-02") as the source — NOT
   docs/reference/agno-memory-and-storage/02-knowledge-and-retrieval.md:1195, whose push-down table
   documents Milvus, not Weaviate. No doc in the repo may prescribe FilterExpr against
   Weaviate-backed Knowledge afterward — grep to confirm.
7. [D2f] docs/DEBT.md agno pin note → 2.8.0 (matches requirements.txt).
8. [D1f] STUB rule: scope to non-test code (`grep -rn "# STUB:" server docker evals scripts`) and
   re-tag tests/test_run_ledger.py:61 + tests/test_custody.py:19 markers as `# TEST-DOUBLE:`.
   Check: rule-vs-grep invariant holds mechanically.
9. [D3f/R-6] docs/DEBT.md dated stamp: "2026-08-09 audit — all resolved rows verified resolved;
   planned rows (pipeline population, CASES=(), backups→R2) verified open; rejection list 1–6
   re-reviewed and HELD (derivation-engine addition aside)."
10. [D4f] Parser-lane queue rows: item 1 (Go import-scoping) → LANDED PR #18 (cite D-NNN promotion
    entry from S4); item 2 → partial (SBV path has reconciliation gate; generic contract +
    evidence.raw_rejected writer open → S7); items 3–5 open → S7.
11. [TD-JC] docs/DEBT.md "justified custom" list += derivation engine (refresher + version pin + chain-hash
    attestation; no Agno-native equivalent) alongside NimEmbedder/NvidiaReranker.
12. [N8/OQ-5] One-line doc note (REPO_STRUCTURE or canon §9): case_id TEXT `'primary'` is canonical;
    legacy UUID case_id columns are historical, no migration planned (owner ruling 2026-08-09:
    never multi-case).
13. [TR-1/TR-2] CONVENTIONS.md: add citation convention (code cites `ADR-NNNN` for architecture,
    `D-NNN` for owner rulings). scripts/validate.sh: (a) every path cited in README/AGENTS.md/canon
    §9 exists; (b) every `ADR-\d{4}` / `D-\d{3}` reference in server/ sql/ docs/ resolves.
    No blanket annotation pass (TR-4).
14. [P3] Canon §9 + REPO_STRUCTURE.md: mark `dev-resources/Archives/*`, `Agno-MCP-Platform-alpha/
    chatminer`, and `dial-stack/…/Tether/` explicitly as WORKSPACE-ROOT-relative (outside this
    repo). `extracted-code/` + `MANIFEST.md`: strike or re-point per OQ-2 ruling; if unruled,
    leave a marked `TODO(OQ-2)` on the line.
15. [TR-5 commit half] Commit the S4-drafted DECISION_LOG entries (six-clock ratification, SBV
    promotion D-NNN, never-multi-case R-2 entry) into docs/DECISION_LOG.md once owner approves
    their text.

## Acceptance
`./scripts/validate.sh` (containerized: `docker compose run --rm agentos-api ./scripts/validate.sh`)
passes including the two new checks; grep spot-checks in tasks 1/6/8 clean; every edited doc
carries an updated byline.

## Constraints
Standing constraints per PLAN master (mandatory read). Doc edits only — no code behavior changes
in this segment. No secrets or credential-management content in any doc. Do not reopen §5 locked
decisions.
