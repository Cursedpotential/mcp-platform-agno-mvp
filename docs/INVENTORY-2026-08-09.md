# Master Action Inventory — 2026-08-09
> Every task, gap, or debt mentioned or discovered in the 2026-08-09 audit + planning session.
> Each item maps to at least one handoff segment (column S; primary owner listed first).
> Verified by adversarial coverage pass 2026-08-09; 22 findings fixed same day.

## A. Audit findings (repo @ a68fabd)
| ID | Item | S |
|----|------|---|
| N1 | horizon_visible keyed on superseded knowledge_time — predicate inert | S6 |
| N2 | realized_at/acquired_at/realized_evidence/acquisition_id: zero writers; vw_record_disclosure derives NULL | S6 |
| N3 | disclosure_tier hardcoded contemporaneous everywhere; anti-leak guards dead | S6 |
| N4 | No enforcement: no RLS, predicate zero callers, inspect_routes bypass, unscoped DatabaseContextProvider | S6 |
| N5 | DEBT.md:46 prescribes FilterExpr on Weaviate (silent drop) | S1 |
| N6 | Graphiti add_memory sends no reference_time — mono-temporal belief lane | S6 |
| N7 | AI-chat context lane written without horizon axes (latent leak) | S6 |
| N8 | case_id TEXT vs UUID split — DEMOTED per owner ruling (never multi-case): document as legacy, no migration | S1 |
| FA | AGENTS.md:41 misstates disclosure_tier type; six-clock ruling unratified | S1+S4 |
| FC | schema_baseline.sql predates 0018 — bootstrap has no horizon layer | S3 |
| FD | Agent-layer pre-filter entirely unbuilt (state finding — resolved by S6 build) | S6 |
| F-B | 0004 disclosure_tier enum collision residue: none in code; replay recreates-then-drops (no action beyond S3 README note) | S3 |
| F-E | Predicate exists in two copies (SQL + test mirror) — unify into one derivation function | S6 |
| F-F | test_session_embedder unmarked integration (= T4) | S2 |
| F-G | Semantica extraction horizon-blind — COMPLIANT, preserve property in S8 build | S8 |
| S1f | Numbered chain can't bootstrap empty DB; 0014 silent no-op; README understates | S3 |
| S2f | evidence_hash 5-col vs 15-col divergence — 0019 bridge | S3 |
| S3f | Orphaned gen_validate_0008 scripts target renamed migration | S3 |
| S4f | walk_ledger HOLD rationale void (SurrealDB retired) — rewrite header → ADR-0045 | S3 |
| T1 | requirements.txt stale + grpcio/weaviate unsatisfiable → 7 failures; Dockerfile pymilvus (OQ-10) | S2 |
| T2 | test_sbv_demotion stale (superseded by 08-05 promotion); re-pin bodyless-retention + outbound-role vs _map_universal_record AND sms_xml.py; decide _map_message fate | S2 |
| T3 | test_semantica_wiring hardcodes retired IP — assert module default/env path instead | S2 |
| T4 | 3 live-Weaviate tests unmarked @pytest.mark.integration | S2 |
| T5 | evals/cases.py intentional stub — populate in S9, never flag as drift | S9 |
| P1 | README/canon plans/ + logical-herding-forest.md dead refs → docs/BUILD_PLAN.md | S1 |
| P2 | AGENTS.md custody.go path → vendored/sbv/internal/custody.go | S1 |
| P3 | extracted-code/+MANIFEST.md unresolvable (OQ-2 owner); sibling paths mark workspace-relative | S1 |
| P4 | analytics/ database/ deploy/ tool-skills/ undocumented; 00_analysis_graph.surql fate (OQ-7 owner) | S1 |
| P5 | Canon stale: header date, §4 hosts, §5 SurrealDB wording, §6 P4 pre-PR#18 | S1 |
| D1f | DEBT # STUB: rule self-violating (2 test doubles) | S1 |
| D2f | DEBT agno==2.6.9 pin note stale (actual 2.8.0) | S1 |
| D3f | Verified-open planned rows: stamp 2026-08-09 verification in DEBT.md | S1 |
| D4f | Parser-lane queue: item1 landed (close row), item2 partial, items 3,4,5 open | S1(row)+S7(work) |

## B. Tech-debt additions beyond audit rows
| ID | Item | S |
|----|------|---|
| TD-E7 | No recurring backups pg_dump+neo4j→R2; existing script is one-time, skips neo4j; include baseline regen in cycle | S9 |
| TD-EV | Horizon-leak eval = highest-value assertion; planted-future-fact canary | S9 |
| TD-JC | Add derivation engine to DEBT "justified custom" list (next to NimEmbedder/NvidiaReranker) | S1 |

## C. System-design decisions (Stage D design session)
| ID | Item | S |
|----|------|---|
| SD-1 | HorizonContext frozen object, server-side construction only | S6 |
| SD-2 | Clock insight: visible_from = COALESCE(realized_at, occurred_at); acquired_at = custody metadata only; knowledge_time frozen as ingest audit clock | S4(ADR)+S6(impl) |
| SD-3 | Fail-closed: missing context → zero rows + raise; hindsight = explicit grant, never default | S6 |
| SD-4 | Weaviate: visible_from_epoch axes; wire-payload-level regression test (never count-based) | S6 |
| SD-5 | Graphiti: reference_time = party-knowledge time; group_id=(case,pass) belief state legitimate | S6 |
| SD-6 | Pass runner: agno.workflow Loop; delta computed between snapshots in plain code | S6 |
| SD-7 | Planted-future-fact runtime canary promoted from 0018 test | S9 |
| SD-8 | Transaction-scoped set_config (pooling-safe) | S6 |
| SD-9 | Multi-case/multi-user/Memgraph "revisit" — VOIDED by owner ruling (never multi-case/multi-user); R-2 DECISION_LOG entry records it | S4 |

## D. Checkpoint-derivation architecture (owner-driven amendment)
| ID | Item | S |
|----|------|---|
| DA-1 | Canonical factual layer (ingestion+Semantica) write-once; pass corpora DERIVED, never authored | S4(ADR)+S6 |
| DA-2 | As-lived corpus derived incrementally per walk step; hindsight derived on prompt; ONE predicate function, two schedules | S6 |
| DA-3 | Refresher = only writer of pass tables (grant-enforced INSERT); agents SELECT own pass corpus only | S6 |
| DA-4 | Every derivation hash-attested to audit ledger; checkpoint records base-store version | S6 |
| DA-5 | Walk pins to base version at start; mid-walk ingestion → next run; runs citable ("Pass 1 run #3, base X") | S6 |
| DA-6 | Walk-ledger = as-lived derivation log, chain-hashed (prev_hash), Postgres working.* — CLOSES OQ-1 | S4+S6 |
| DA-7 | Per-pass Weaviate collections materialized at checkpoint; vectors copied, no re-embed | S6 |
| DA-8 | Cross-lane checkpoint consistency: PG+Weaviate cut from same base version in one op | S6 |
| DA-9 | Canon §1 amendment: parallel AUTHORED stores forbidden; version-pinned derived materializations sanctioned | S4 |
| DA-10 | Semantica assertions carry visible_from of source record; entity nodes = identity anchors only | S8 |
| DA-11 | Analysis/observation tables append-only with (pass,run,base-version) attribution | S6 |

## E. MCP lens
| ID | Item | S |
|----|------|---|
| M-1 | D9: MCP doors are a 5th read lane — evidence-reading tools resolve server-side HorizonContext; never accept client-supplied horizon; hindsight = credential grant; fail-closed | S6 |
| M-2 | ADR-0046: universal MCP exposure contract (pays canon §5 item 11 "needs ADR"): progressive disclosure, subnamespacing, annotations, pagination, horizon-binding rule | S4 |
| M-3 | Facade tool grooming: readOnlyHint/destructiveHint annotations, actionable errors, pagination on evidence reads | S7 |
| M-4 | MCP-style eval pattern (independent/read-only/string-verifiable) composes with horizon canary | S9 |

## F. Traceability lens
| ID | Item | S |
|----|------|---|
| TR-1 | Convention: code cites ADR-NNNN (architecture) + D-NNN (owner rulings), grep-able | S1(doc)+all(practice) |
| TR-2 | validate.sh: every ADR-/D- reference and doc path resolves | S1 |
| TR-3 | Retroactive citations ONLY: 0018 predicate → ADR-0045; _sbv_enabled → promotion D-NNN | S6+S2 |
| TR-4 | No blanket annotation pass | all |
| TR-5 | New DECISION_LOG entry for SBV promotion (08-05) + six-clock ruling | S1+S4 |

## G. Owner rulings (this session — embed as constraints)
| ID | Ruling | S |
|----|--------|---|
| R-1 | Audit-everything VIP: every decision/action/modification/READ audited, hash-chained, retrievable on demand | S5 (+hooks in S6,S7,S8) |
| R-2 | NEVER multi-case / multi-user: drop case_id migration (N8→doc note), drop multi-user auth everywhere, single horizon_agent role | all |
| R-3 | SBV rewrite ~complete → live testing is the next SBV step | S7 |
| R-4 | Graph/Semantica lane: vendored+configured but NOT wired — build it (explicit phase) | S8 |
| R-5 | Checkpoint-derivation architecture sanctioned (conditions DA-1..8) | S4/S6 |
| R-6 | Rejection list reviewed and HELD (1-6), with derivation engine added to justified-custom | S1 |

## H. Open questions — disposition
| ID | State | S |
|----|-------|---|
| OQ-1 | CLOSED: walk-ledger = derivation log, Postgres | S4 records closure |
| OQ-2 | OPEN (owner): extracted-code/ fate | S4 rulings sheet |
| OQ-3 | OPEN (verify): graphiti-mcp reference_time support — live probe via grc | S6 task |
| OQ-4 | RECOMMENDATION READY: COALESCE(realized_at,occurred_at) — sign in ADR-0045 | S4 |
| OQ-5 | CLOSED by R-2: case_id stays TEXT 'primary'; UUID families = legacy note | S1 |
| OQ-6 | FOLDED into ADR-0045 (ratification + tier type target) | S4 |
| OQ-7 | OPEN (owner): 00_analysis_graph.surql fate | S4 rulings sheet |
| OQ-8 | OPEN (owner): who may emit hindsight/discovered (HITL-only vs trusted lanes) | S4 rulings sheet |
| OQ-9 | OPEN (owner): PR#18 = Phase 5a shipped? | S4 rulings sheet |
| OQ-10 | OPEN (owner): Milvus cutover verified → pymilvus fate | S4 rulings sheet |
| OQ-11 | OPEN (owner): D-008 sign-off (RESTART-0001 schema) — gates S9 population | S4 rulings sheet |

## I. Standing constraints (embed verbatim-critical in every handoff)
- Never delete — move to _stale/; owner-only removal
- Containerized-only (docker compose; never host venv)
- NEVER edit an applied migration; add NNNN files
- SURREALDB_URL default stays as-is (parked container) — do NOT consistency-fix
- agent-ui+browser+hotfix branch KILLED — never resurrect
- No secrets in command lines/transcripts; no real PII in git
- Dict filters ONLY on Weaviate; extraction horizon-blind; evidence schema append-only, custody.py sole writer
- VIP components (Agno, custom Graphiti, Semantica, ContextForge, SBV fork, CopilotKit): never overwrite/reinvent/fork around
- HITL-first: every write pauses for recorded approval where canon requires
- Locked decisions PROJECT_CANON §5: cite, never reopen
