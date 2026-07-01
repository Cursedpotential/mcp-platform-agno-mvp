# GAP & STALENESS CRITIC — Verification of the Drafted Forensic-DB Design

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Mandate: does the draft (sections 01–21) actually ADDRESS the gaps/blind-spots in `discovery/GAP_AND_STALENESS_REPORT.md`, and does it AVOID silently inheriting stale decisions (ADR-0003/0013 DuckDB conflict, SurrealDB-as-unratified, stale manifests)?
> Verdict: **The design is sound on every named staleness trap and on the five headline corrections. The residual misses are specific salvaged-asset omissions and one un-spec'd evidence class — not architectural regressions.**

---

## A. STALENESS — clean. No stale decision is silently inherited.

| Stale trap (from gap report) | Inherited? | Where corrected |
|---|---|---|
| **ADR-0003 (PG18 pgvector-only, NO DuckDB)** treated as live | **NO** | §04 ¶0/¶8, §01 N7, §21 §2.2, §15 R-ST-1 all state it is *superseded*, not a live conflict. |
| **Standalone DuckDB blessed** | **NO** | §04 ¶0 explicit: "DuckDB is NOT a standalone deployable… pg_duckdb-embedded wins; standalone DuckDB is *not* blessed." Repeated §01 N7, §11, §19, §21. The local `casebible.duckdb` is correctly excluded from the server tier. |
| **ADR-0003 README "Accepted" label** copied forward | **NO** | Design *recommends fixing it* ("Superseded by 0013/0014/0027") in §21 §4-#6, §19 §9, §15 R-ST-1, §15 Q-11 — never re-asserts it. |
| **SurrealDB framed as new/unratified** | **NO — actively corrected** | §07 status banner + §21 §2.2: ratified (ADR-0024) but undeployed (Phase D); the master prompt's "new/unratified" framing is explicitly called wrong. §07 still independently rules adopt-vs-defer → DEFER (conditional). |
| **Stale `Workspace_Manifest_*.json` (78 files)** | **NO** | §15 R-ST-4: "last-resort lookup only"; resolve paths via `extracted-code/MANIFEST.md`. |
| **Dead absolute paths / TheBigOne / osgrep** | **NO** | §15 R-ST-4; MANIFEST is the resolver. |
| **Stale planning docs (PG16, pgvector-hybrid, `uuid_generate_v4`)** | **NO** | §15 R-ST-2; design uses PG18 + native `uuidv7()` throughout. |
| **Jan reports' Supabase/Chroma/LanceDB/pgvector stack** | **NO** | Re-targeted to PG(+pg_duckdb+PostGIS)/Milvus/R2 in every adopting section; §15 R-ST-3. |

The five Appendix "biggest corrections" are all folded in: standalone-DuckDB-not-blessed ✓, `positive_behaviors.ttl` adopt-don't-invent ✓ (§01 G8, §04 §3.4, §10 §1.3, §11 P14, §13 §3.7, §21 §5), call-logs/blocked-call/AI-chat/XLSX/schema-resolver lanes ✓ (XLSX flagged as still-open gap), crosswalk anchored on `extracted-code/MANIFEST.md` ✓, timestamp-precision class ✓ (added everywhere as a genuine new requirement).

**Conclusion on staleness: no contamination. The design treats every superseded resource as inventory-only and cites the live ADR instead.**

---

## B. GAP COVERAGE — strong, with specific residual misses.

Well-covered AVAILABLE-but-was-not-HAVE items now mapped: call-logs & blocked-call type 5/6 (§10 §2.1 → `message_kind`), AI-chat-export logs (§10 §2.2, quarantined to inferred/analytical), `schema-resolver.ts` for unknown formats (§10 §3), `normalized_messages` raw-JSON landing (§04 §3.2/§7, §10 §3), all the behavioral ontologies + 256/303-pattern libs + DARVO + hurtlex (§10 §1.3, §11 P14, §13 §3.7), doc-intelligence approvals/sections/chunks/spans (§04 §3.5, §10 §2.9, §19 table), Snapchat-source & Instagram & XLSX explicitly flagged as open gaps (§10 §5).

The remaining misses are below (Section C).

---

## C. TOP UNADDRESSED / WEAKLY-ADDRESSED ITEMS

1. **Email is not a first-class evidence source type.** Gap report 1.5-#4 named "Email parser (format TBD)" as an open item, and §01 G1 lists "emails" in ingest scope — but §10 (per-source extraction ontology) has **no Email subsection** (EML/MBOX/PST headers, threading, attachments, sender-auth/SPF/DKIM). Email appears only incidentally (a `depicts_kind=email` screenshot, a court-doc attachment). A whole evidence class has no extraction contract.

2. **Alpha forensic-DB table survivors are flagged "re-verify" but never actually mapped.** Gap report 1.3 listed `bertConfigs, severityWeights, schemaResolvers, forensicResults, patternCategories, hurtlexTerms/Categories`, plus the Drizzle `production-message` schema and the SQL deployment files (`agno-alpha-schema.sql`, `Salem_SMS_Tables_Complete_Deployment`). The draft only re-flags "verify which exist; map survivors" (§04 §11, RE-VERIFY list) — it never maps them. Notably `severityWeights` is the natural donor for §13's 10-axis scoring yet §13 builds the band/weights model from scratch without citing it; `schemaResolvers` (alpha table) is distinct from the `schema-resolver.ts` tool and is unmapped.

3. **The SBV SMS-Backup&Restore cluster and the 4GB-capable streaming-XML ingest design are dropped.** Gap report 1.1 listed the `extracted-code/sbv/` cluster (Go upstream + TS client + ingestor + MCP) and the streaming `SmsXmlReader`/`xml-sms-parser.ts` (4GB-capable). The draft names `enhanced-xml-chunker.py` / `sms_backup_parser` but carries **no streaming/large-dump ingest design** — a real forensic SMS backup can be multi-GB, so the in-memory parser assumption is an unaddressed scalability/robustness gap. Off-the-shelf SBV pipeline reuse (minimize-custom-code rule) is not considered.

4. **The `normalized_messages` (raw-JSON landing) vs TraceIQ typed `messages` conflict is deferred, not resolved.** The gap report flagged this as a partial conflict needing an explicit decision. The draft proposes "both: raw landing → typed projection" (§04 §3.2, §10 §3, §21 §4-#3) but every instance ends in **needs-human-review** rather than locking field-merge rules (esp. platform-hop reconstruction + blocked-call type 5/6). This is the one known data-model conflict the design leaves open rather than deciding.

5. **No as-deployed DDL verification — the entire design is paper-only against an unverified live stack.** Gap report 1.5-#1 named this the biggest cross-cutting blind spot ("the current architecture is answered by ADRs + live probes, NOT reports"). The draft *correctly and repeatedly flags* it (§11 open items, §15 R-ST-5/R-ST-6, §19) but does not reconcile any schema against the running `agno-postgres:18-duckdb` / Milvus / Neo4j DDL. Acknowledged-but-unclosed: nothing here is verified against the live boxes, and `claude-context` is unindexed for the workspace root, so even a code-level confirmation pass was not run.

### Lesser notes (not in top 5)
- Doc-intelligence `summaries` and `keywords` tables (gap 1.3) were dropped from the adopted set (§04 §3.5 keeps section/chunk/span/entity/finding/approval only).
- Semantica's *conflict-detection* model (997-line pipeline) is referenced as a writer but its conflict/PROV-O schema is mapped only loosely (§11 P15) — A4's note that A3 "never mapped its model" is only partially closed.
- R5's two byte-identical copies are flagged for dedupe (§15 R-ST-3/Q-12) but the dedupe + data-model extraction is left as a to-do, so R5's richest data model has not actually been extracted yet.
