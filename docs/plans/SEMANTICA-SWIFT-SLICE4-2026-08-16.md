# Semantica Swift Slice 4 — governed disposable extraction

> _Byline: Codex · GPT-5 · 2026-08-16_

STATUS: LOCAL DISPOSABLE SLICE IMPLEMENTED
BUILD_STATUS: FOCUSED TESTS, RUFF, FORMAT, AND FIRST-PARTY MYPY PASS; DATABASE/DEPLOYMENT PROOF UNKNOWN

## Slice card

- **Slice:** execute vendored Semantica on an immutable synthetic batch and emit reviewable candidates with provenance.
- **Sequential:** ORIENT → CLASSIFY → PREMORTEM → PLAN → REACT → REVISE → CLOSE.
- **Holds:** no live or scratch database write, worker deployment, custody write, promotion, provider call, Neo4j/Weaviate/Surreal/Graphiti write, or corpus execution.
- **BUILD_STATUS:** focused behavior is observed locally; physical PostgreSQL and deployment behavior remain UNKNOWN.

## Governing boundary

ADR-0043 controls this slice. Semantica is semantic intelligence, not custody or authority. The worker consumes an immutable, hash-attested snapshot of `working.normalized_record` rows and emits only entity, fact, and event candidates. It is deliberately horizon-blind: extraction forms no agent belief and receives no `HorizonContext`.

The public contracts import no Semantica, Agno, Graphiti, Surreal, provider, or persistence framework. The worker executes the real vendored Semantica pattern methods, then immediately converts their objects into platform-owned frozen contracts. Persistence is a separate host adapter with an exact four-table allowlist:

- `working.extraction_run`
- `working.candidate_entity`
- `working.candidate_fact`
- `working.candidate_event`

Every candidate remains `pending`. There is no promotion operation in this slice.

## Pre-mortem and resulting controls

The slice had failed because:

1. The adapter had reimplemented convenient regexes instead of running Semantica.
2. Semantica's last-resort adjacency fallback had fabricated `related_to` facts.
3. The extraction process had received database, custody, model-provider, or projection credentials.
4. Candidate rows had lost source hashes, offsets, quotes, extractor version, or configuration identity.
5. Per-record failures had been swallowed and a partial batch had been marked successful.
6. Relations had referenced entities that were filtered or never emitted.
7. A year such as `2024` had been promoted as a false precise timestamp.
8. Tests had proven configuration dictionaries rather than observed extraction and submission behavior.

The plan changed in response. The worker calls the vendored pattern implementations directly; never invokes `RelationExtractor`'s fallback chain; rejects `related_to`/`last_resort_adjacency`; imports no persistence or provider clients; attests every source and configuration; records failures; refuses failed batches at submission; links facts only to emitted identities; represents a bare year as `[January 1, next January 1)` with reduced temporal confidence; and runs an end-to-end synthetic fixture through a disposable table-shaped sink.

## Observed territory

`uv run python scripts/run_semantica_fixture.py` completed against two immutable fixture records and reported:

- extractor `vendored-0.3.0-alpha+1a0cd8577673864f`
- configuration SHA-256 `5d614b5121c2f0720e5e2ace2925f8a228986bc3ff9323795e8da52b8013d70f`
- 4 entity candidates
- 2 fact candidates: `founded_by`, `acquired_by`
- 1 `acquisition` event candidate
- 2 explicit non-identity-entity rejections
- 0 failures
- rows only in the four allowlisted `working.*` table-shaped collections

Verification run on 2026-08-16:

- `uv run pytest -q tests/test_semantica_phase1_worker.py tests/test_semantica_wiring.py` — **18 passed**
- focused Ruff check — **PASS**
- focused Ruff format check — **PASS**
- `uv run mypy server` — **PASS, 147 source files**

The vendored package reports `0.3.0-alpha` in package metadata but `0.2.7` in its `__init__`; the adapter therefore adds a digest of the exact imported method/event source files to the runtime version. Vendored Semantica remains outside the first-party typing boundary and carries upstream typing debt; the platform contracts and adapters remain checked.

## Remaining holds and next proof

No PostgreSQL row was written. A separately authorized disposable/scratch execution should inject a least-privilege engine limited to the four `working.*` tables, run the same fixture, verify pending candidates and provenance by readback, and prove that custody and projection writes are denied. Provider-backed extraction, SHACL validation, corpus execution, worker deployment, and all projection/promotion behavior remain later slices with their own authorization and pre-mortem.

This work does not modify or relax any R9/R12 Surreal activation hold.
