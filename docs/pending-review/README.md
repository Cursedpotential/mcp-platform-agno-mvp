# Pending documentation review

> _Byline: Codex · GPT-5 · 2026-08-18._

All documents in this tree were moved from `docs/` because they are not current entry
points. Their claims have **not** been freshly audited. Every item is `UNVERIFIED`,
regardless of a document’s own “complete/live” language.

| Category | Original path pattern | Fresh state | Promotion criteria |
|---|---|---|---|
| handoffs | `docs/HANDOFF-*.md`, session handoff | UNVERIFIED | Recheck referenced code, tests, deployment receipt, and acceptance gates |
| inventories | `docs/INVENTORY-*.md`, audit baseline | UNVERIFIED | Re-run scoped inventory and reconcile current git/deployment state |
| plans | dated plans, blueprints, proposals | UNVERIFIED | Owner confirms active status and reconcile with MASTER-TODO/canon |
| summaries | compact summaries | UNVERIFIED | Reconcile each claim against current canon/ledger |
| evaluations | evaluations and patch reports | UNVERIFIED | Re-run stated evaluation and preserve result with date/SHA |

Original relative paths are represented by category and filename. No document is promoted
to `docs/archive/verified/` without independent verification. Explicitly superseded or
design-only records may later move to `docs/archive/historical/`, with that decision recorded
in the master TODO. ADRs and `DECISION_LOG.md` remain in place.
