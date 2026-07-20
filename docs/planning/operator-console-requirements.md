# Operator Console — requirements (owner-driven, discussion of 2026-07-20)

> _Byline: Claude Code · Fable 5 · 2026-07-20_
> Source: owner rejection of Workbench v1 ("blind upload→promote") + follow-up
> discussion. This is the requirements ledger for the C-series rebuild; the
> workbench app (`workbench/`, Coolify :8020) is rebuilt in place. Supersedes
> the v1 upload/promote UX. Sprint plan lineage: workbench P0–P4 (delivered),
> then C0…C5 below.

## Owner intent (verbatim spirit)
Drive the pipeline, don't feed a black box. See every stage: custody hashes,
parser/schema recognition, PG tables, Milvus chunks/entities. Verify parsing
quality (semantics, splitting; summaries/sentiment when the analysis lane
exists). Verify hashes actively. Curate (labels/tags/titles). Pull up and
browse knowledge. Manual access to registered tools/workflows is table stakes
("they're registered — it shouldn't be hard").

## Locked decisions
- **Drive model**: per-run `supervised` toggle — gated step-through (native
  HITL @approval pauses) vs fire-and-watch live telemetry.
- **Surface**: rebuild the existing workbench app in place (keep container,
  R2/LanceDB staging, :8020). G1 shell remains the eventual home; console must
  stay embeddable (own origin, no auth assumptions).
- **Reads vs writes**: console reads stores DIRECTLY read-only (PG, Milvus,
  Graphiti); ALL writes go through spine APIs (single-writer preserved).
- **Drive scope v1**: evidence workflows + bulk pours + agents/teams/workflows
  + **Tool Explorer** (schema-generated forms over agentos-mcp :8001 and
  ContextForge :4444/mcp Bearer CF_MCP_CLIENT_TOKEN — both verified live).
  Copilot lane (OpenCode :4096 via SDK) = C2.5; `opencode-ops` skill + `oc`
  CLI built separately.
- **Knowledge views**: Milvus (hybrid /knowledge/search) + Graphiti pane
  (entities/facts) both in v1 scope (C4).
- **First light**: Run Console — real chat export watched stage-by-stage.

## Stage telemetry (C0 ledger: analysis.workflow_run + workflow_run_stage)
Typed per-stage outputs written AS stages execute:
custody {sha256, artifact_id, duplicate, blob path} · parse {parser_id,
attempts, schema_recognized, record_count, sample_records, parse_stats,
alt_parse} · store {rows_stored, table} · knowledge {docs_ingested, domain,
skipped}.

## Addenda (2026-07-20, post-kickoff)
1. **Parse-quality review is a first-class purpose**: C3 adds a full per-run
   record browser (paged normalized_record view: split boundaries/turns,
   roles, timestamps, attrs) to verify splitting + semantics by eye.
   Summaries/sentiment = Part-2 analysis stages; the stage rail must surface
   them as inspectable stages when they exist (NOT claimable before).
2. **Hash verification (active)**: custody drawer "Verify" action → spine
   endpoint re-fetches blob, recomputes sha256, and for evidence-tier runs
   walks the H1/H2/H3 chain (H3 = sha256(prev_hex + h2_hex), genesis = H1),
   returns intact/broken + failing link. Verification logic lives spine-side.
   **Two-tier custody (owner decision 2026-07-20)**: knowledge-lane pours
   (platform docs, AI-chat story) need ONLY whole-file sha256 + R2 blob copy
   — integrity ("whole thing made it in") + dedupe; no evidence-schema chain
   rows. Full H1/H2/H3 stays mandatory for evidence verticals (sms-xml etc.).
   Implement as `custody_tier: full|light` on workflows (C2); Verify UI
   states which tier it asserts. Escape hatch: pristine blob + sha256 always
   retained, so story material can be re-run through FULL custody later if it
   becomes evidentially relevant — light tier never forecloses evidence-grade
   treatment.
3. **Curation actions**: label/tag/retitle from the record browser and
   knowledge views — analysis/metadata lane ONLY (normalized_record.attrs,
   knowledge doc metadata) via spine PATCH routes. Evidence blobs + hashes
   immutable, always. Sensitivity/redaction stays label-not-switch.

4. **Model Compare bench (owner idea 2026-07-20)**: side-by-side comparison of
   how different MODELS handle LLM-driven knowledge transformations. NOT the
   parse stage (deterministic parsers — nothing to compare); applies to
   segmentation-by-meaning, summaries, sentiment, entity extraction, and
   Part-2 analysis passes. Design: pick input (staged file / record set) +
   task template + 2–4 models → run via Portkey (model swap = x-portkey-config
   header) → diff panes; runs tagged in the ledger as eval runs. Doubles as
   the evidence base for model selection per analysis stage and feeds the
   ground-truth labeling workflow (compare against gold labels). Boundary:
   eval bench ONLY — outputs never write to knowledge (single-writer intact);
   results inform which model the spine adopts. Build with the `evaluation`
   skill when implementing.

5. **Extraction lane (owner 2026-07-20; design pre-seeded by DECISION_LOG
   D-034 + the chat-sample facet maps in docs/planning/chat-sample-analysis/,
   local/gitignored)**: the raw early dump IS C1–C5 (pour everything now;
   blobs immutable, records re-processable). Extraction = D-series post-store
   passes over analysis.normalized_record (never file re-parses), one facet
   per workflow, each a ledger-tracked run visible in the console:
   - code extraction: fenced-block + tree-sitter/AST (smart-explore engine)
     → code knowledge collection (codestral-embed lane)
   - legal/strategy extraction: drafted motions/letters/strategy discussion
     → legal_strategy domain + Case Bible vault routing
   - artifact extraction: tables, drafted docs, embedded exports → typed
     artifacts w/ provenance to source record + hash
   - ordering: deterministic passes (grep/AST) first and always; LLM passes
     behind them, models auditioned via the C4.5 Model Compare bench before
     being wired in.

6. **Corroboration flags (owner 2026-07-20)**: flag events/claims as "needs
   corroborating evidence" while reviewing. Rationale: the AI chats are the
   owner's STORY, not evidence — flags operationalize the story→evidence map.
   Shape: analysis-lane annotation {target record/event/doc, claim summary,
   claim date(s), evidence type wanted (sms/photo/call-log/financial/witness),
   status open|partial|corroborated|unobtainable, linked corroborating
   artifact ids + hashes once found}. Surfaces: (a) flag action in every
   review view (C3 curation family); (b) Corroboration queue page — the
   evidence-gathering worklist, filterable by claim date + evidence type;
   feeds discovery requests (what to subpoena/RFP). D-series: LLM pass
   auto-suggests flags (accept/reject → gold labels; models via C4.5 bench).
   Long-range: flag status maps onto bitemporal knowledge horizons (claim vs
   corroborated fact) for Part-2 passes. Immutability: flags are metadata,
   never mutate evidence.

## Sequencing
C0 ledger+runs API → C1 Run Console fire-and-watch + Tools page + Intake
(FIRST LIGHT) → C2 supervised gates + retry-stage → C2.5 Copilot lane
(OpenCode) → C3 inspectors: record browser, hash verify, curation +
corroboration flags, raw PG/Milvus schema views → C4 knowledge browser +
Graphiti pane + corroboration queue → C4.5 Model Compare bench (addendum 4)
→ C5 bulk pours + agent/team forms → D-series extraction lane + flag
auto-suggestion (addenda 5–6).

## Standing blockers (at time of writing)
- Milvus `platform_knowledge` recreate (1024-d→4096-d) — owner-gated; blocks
  the knowledge stage going green.
- Rotations queued: Coolify API token, OS_SECURITY_KEY (transcript exposure).
