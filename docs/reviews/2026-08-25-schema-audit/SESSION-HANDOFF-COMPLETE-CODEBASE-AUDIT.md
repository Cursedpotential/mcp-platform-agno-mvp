# Session Handoff — Complete Codebase Audit

Date: 2026-08-25

Status: repository audit and limited read-only live-parity pass completed 2026-08-26. Start with
`COMPLETE-CODEBASE-AUDIT.md` and `AUDIT-GAP-REGISTER.md`. No production execution is authorized by
this handoff.

The subsequent comprehensive path review is persisted in `COMPREHENSIVE-PATH-REVIEW.md`. It compares
the corrected R00-R14 direction with legacy code, records an 8/10 conditional-yes verdict, documents
the target-model corrections made during review, and gives proposed answers for CR-001 through
CR-006. Start there for the plain-English decision state; do not implement from the blocked unified
physical model until those closure items are ratified and designed.

Owner rulings D-082–D-085 subsequently fixed the AI-chat and timeline product path. AI chat is never
evidence; its typed outputs feed claims/investigation/observations/strategies/created works. The timeline
surface is a maintained Timesketch fork that displays both context candidates and evidence-approved
entries and supports governed individual/bulk edits. Every change to an approved entry returns as a
context amendment candidate for re-review/reconciliation; it never mutates approved history. Use
`TIMESKETCH-FORK-CURATION-HANDOFF.md` for that contract and `SEMANTIC-AGENT-WORK-PACKAGES.md` for the
current multi-agent TODO/dependency board.

## Owner request

Complete a genuinely exhaustive codebase audit and use it to verify, correct, and expand the existing whole-system reconciliation package. This must address all gaps between the intended controlled-replay product and the actual code, schemas, workflows, configuration, deployments and live runtime paths.

This is an audit/documentation task first. Do not begin broad implementation, migrations, deployment or cleanup without a separate approved execution step.

## Completed documentation baseline

Start at:

- `docs/reviews/2026-08-25-schema-audit/ENGINEERING-DOCUMENTATION-PACKAGE.md`

The baseline includes:

- whole-system conceptual and provisional physical models;
- system architecture and Mermaid diagrams;
- cross-domain contract matrix;
- reconciliation workstreams R00–R14;
- individual R00–R14 engineering guides and handoff checklists;
- reconciliation runbook;
- agent handoff protocol;
- Temporal/n8n workflow and gap analysis;
- D-069 through D-081 rulings incorporated into canon/decision documentation.

The baseline is a reconciliation blueprint, not yet a certified complete codebase audit.

## Audit objective

Produce a repository-wide, evidence-backed evaluation containing:

1. Complete file/module/service inventory.
2. Complete PostgreSQL relation, column, function, trigger, view, role and migration inventory.
3. Writer/reader/caller census for every canonical and derived relation.
4. API, agent/tool, workflow, Temporal activity, n8n and CLI entrypoint census.
5. Weaviate, Neo4j, SurrealDB, PostGIS, pgvector and pg_duckdb producer/consumer trace.
6. ADR/decision/canon-to-code traceability matrix.
7. Configuration, compose, deployment and live-service parity review.
8. Correctness, authority-boundary, security, horizon-leak, idempotency, retry, performance and maintainability evaluation.
9. Test coverage and live-integration verification matrix.
10. A deduplicated, severity-ranked gap register mapped to R00–R14, with exact file/line evidence, dependencies and acceptance criteria.
11. Amendments to the existing architecture guides wherever code evidence contradicts or refines them.

## Required discovery approach

- Use the existing CCC/CocoIndex repository index for broad structural and semantic discovery.
- Query the available DuckDB index/catalog for coverage, relations and dependency analysis.
- Use `rg` for exact symbol, caller, writer, SQL and configuration censuses.
- Inspect files directly for authoritative code context; do not treat search snippets as full proof.
- Compare repository truth with live database/service/runtime state where accessible.
- Use independent parallel audit lanes, with one final integrator responsible for deduplication and proof of coverage.

Do not mention repository-index tooling as part of the product architecture or proposed runtime design.

## Current access problem

Before reboot, every local PowerShell command failed with Windows `PermissionDenied` / error code 5, including `Get-Location`, file reads and skill reads. `apply_patch` still worked, and GitHub repository search/read connectors remained available.

The owner is rebooting the PC to restore local access.

After reboot, first verify:

```powershell
Get-Location
rg --files | Measure-Object
ccc --help
```

Then locate the DuckDB index/catalog and confirm it can be queried. Do not rebuild an existing index until its location, freshness and schema are understood.

## Skills selected

The audit clearly matches these local skills and their `SKILL.md` files must be read completely after access returns:

- `codebase-audit`
- `acquire-codebase-knowledge`
- `adr-code-traceability`

Skill reads were attempted before reboot but failed with Windows error 5.

## Initial audit lane split

Run these lanes in parallel after the contract/inventory freeze:

1. Canon, ADR and decision traceability.
2. PostgreSQL schema, migration, writer/reader and custody lifecycle.
3. Runtime entrypoints: API, agents/tools, Temporal, n8n, CLI and deployments.
4. Specialized stores and analysis: Semantica, Weaviate, Neo4j, SurrealDB, geo/modalities and walks.
5. Tests, security, reliability, idempotency, performance and live verification.
6. Final integration: coverage accounting, deduplication, severity ranking and R00–R14 amendments.

## Known high-priority gaps to reverify

- Ingestion currently creates evidence/custody before explicit context promotion.
- No implemented promotion-to-custody writer matching D-069/D-075/D-076.
- SBV raw H2/H3 and platform normalized-generation H2/H3 semantics are conflated in existing paths.
- Semantica candidate execution is unwired and has no governed candidate-to-fact lifecycle.
- Neo4j evidence projection is missing; current/legacy graph writers do not match target authority.
- Native Weaviate is structurally strong on pre-ranking filters but weak on promotion eligibility and exact original-span linkage; activation status must be rechecked live.
- SurrealDB production aggregation is fixture/proof oriented rather than a real PG-authorized projector.
- Walk derivation and evidence-search APIs are not proven to be bound into live agent execution.
- Current Workbench surfaces expose table/search plumbing rather than the paired-walk realization/deceit product.
- Database roles/RLS/immutability enforcement and production flags may be inert or bypassed.
- Legacy duplicate candidate, chat/message, case-identity, legal and geo relation families require a complete consumer census before disposition.

These are leads, not final conclusions. Each must be confirmed against current code and live state.

## Safety and repository rules

- Never use `rm` or permanently delete files or data.
- Approved retirement candidates go to `{project_dir}\to_be_deleted`; only the owner deletes them.
- Never edit an applied migration.
- Preserve user changes in a dirty worktree.
- Audit/read-only actions do not authorize production mutation.
- Live integration tests are mandatory before any later implementation is called complete.

## Next-session instruction

On the next session, tell the agent:

> Review `COMPLETE-CODEBASE-AUDIT.md`, `AUDIT-GAP-REGISTER.md`, and the amended R00-R14 guides.
> Preserve the owner correction that Agno is a replaceable runtime/orchestration adapter and owns
> no product truth. Do not begin implementation, migration, deployment, credential/role changes or
> cleanup without a separately approved execution scope. When execution is approved, work in the
> dependency order and stop gates recorded by the audit, with R14 live integration required before
> any production-complete claim.
