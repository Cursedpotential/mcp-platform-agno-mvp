# HANDOFF — R3 Semantica VIP Integration (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: PARTIAL
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Governing decision | Semantica is a VIP component—integrate it fully and never fork around it; ADR-0043 governs how its outputs enter canonical platform knowledge |
| Current code | `server/analysis/semantica_wiring.py` emits configuration dictionaries only |
| Current tests | Configuration, environment override, dimension, database, and secret-name assertions exist |
| Missing runtime | No production worker, normalized input adapter, candidate submission path, or observed write is present |

## Findings / work done

- ADR-0043 is authoritative: PostgreSQL candidates/provenance are canonical; Neo4j and Weaviate are downstream projections.
- The later S8 handoff’s direct-Neo4j worker conflicts with ADR-0043 and must be corrected before implementation.
- Semantica remains the full horizon-blind semantic-intelligence/extraction service and receives immutable normalized batches, not arbitrary host paths.
- First slice remains NER, relation/event candidates, provenance, and SHACL validation with fabricated adjacency disabled.

## UNRESOLVED (mandatory)

- Exact pinned fork revision/image and dependency isolation strategy.
- Candidate/provenance schema details and gold-set thresholds.
- Whether model inference uses Portkey or an isolated provider route after structured-output probes.

## Pending owner decisions

- Preserve the governed canonical-write boundary — WHAT: Semantica exercises its full intelligence capabilities but submits provenance-rich findings for platform promotion · WHY: approval, lineage, and replay require one canonical path · APPROACH: result-submission API plus CDC projections · SHORTCOMINGS: additional service and projector work. Recommendation: approve.

## Next steps (work in order)

1. Correct S8 documentation drift.
2. Freeze batch/result/candidate/provenance contracts.
3. Build isolated worker image and synthetic fixture.
4. Validate zero custody/projection writes.
5. Establish gold extraction and failure/fallback reporting.
6. Add approval and idempotent projection stages.

## Owner working-style contract

- Extraction forms no beliefs; candidates never overwrite canonical evidence; verify observed behavior rather than accepted configuration.
