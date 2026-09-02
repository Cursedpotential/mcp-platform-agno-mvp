# Reconciliation domain engineering guides

This directory contains executable engineering guides for workstreams R00 through R14. The master
dependency and ownership map is [RECONCILIATION-DOMAIN-WORKSTREAMS.md](../RECONCILIATION-DOMAIN-WORKSTREAMS.md).
The whole-system diagrams are in [SYSTEM-ARCHITECTURE.md](../SYSTEM-ARCHITECTURE.md).
Open audit findings and their acceptance gates are maintained in the
[audit gap register](../AUDIT-GAP-REGISTER.md). Each guide links the gaps assigned to its lane.

Per [D-072](../../../DECISION_LOG.md), the product is permanently one owner and one personal case.
Existing Matter/CourtCase identifiers and `case_id='primary'` are compatibility scaffolding only;
the guides do not authorize a Matter-to-CourtCase hierarchy, new scope-binding architecture, or
identifier proliferation.

## Navigation

| ID | Domain | Guide | Primary handoff |
|---|---|---|---|
| R00 | Canon and contract freeze | [R00](R00-canon-contract-freeze.md) | Contract/vocabulary registry |
| R01 | PG backbone, CDC and receipts | [R01](R01-pg-backbone-cdc-receipts.md) | Universal event/job/receipt envelope |
| R02 | Context ingest and parser boundary | [R02](R02-context-ingest-parser-boundary.md) | Parse-generation manifest |
| R03 | Normalization, messages and clocks | [R03](R03-normalization-messages-clocks.md) | Sealed normalized generation |
| R04 | Hashing, custody and promotion | [R04](R04-hashing-custody-promotion.md) | Custody/promotion manifest |
| R05 | Weaviate search | [R05](R05-weaviate-search.md) | Search projection receipt |
| R06 | Semantica and Neo4j | [R06](R06-semantica-neo4j.md) | Candidate and graph receipts |
| R07 | Governed facts and realizations | [R07](R07-governed-facts-realizations.md) | Governed-fact event |
| R08 | PostGIS and modalities | [R08](R08-postgis-modalities.md) | Geo/modality fact manifest |
| R09 | Cross-store reconciliation | [R09](R09-cross-store-reconciliation.md) | Surreal aggregation manifest |
| R10 | Surreal aggregation | [R10](R10-surreal-aggregation.md) | Reconciled Surreal generation |
| R11 | Walks and paired delta | [R11](R11-walks-paired-delta.md) | Walk/delta manifest |
| R12 | Legal and Workbench | [R12](R12-legal-workbench.md) | Governed work-product revision |
| R13 | Temporal and n8n | [R13](R13-temporal-n8n-execution.md) | Durable execution/correlation contract |
| R14 | Migration and final integration | [R14](R14-migration-cutover-integration.md) | Production sign-off packet |

## Assignment procedure

1. Assign exactly one numbered domain and name the guide version/commit.
2. Read R00 plus every upstream domain named by the guide.
3. Complete the guide's discovery inventory before implementation.
4. Record cross-domain gaps as dependencies; never silently change another domain's authority.
5. Produce all required tests, receipts and the handoff manifest.
6. R09 validates projection domains; R14 validates the complete lifecycle and production cutover.

## No-dropped-bits accounting

At every boundary:

```text
expected = accepted + quarantined + superseded_or_revoked + explicitly_rejected
```

Every non-accepted item retains its source locator and reason code. Count equality alone is
insufficient; ordered membership and content hashes must also reconcile.
