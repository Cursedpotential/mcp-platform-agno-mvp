# HANDOFFS — agent-executable task units

> _Byline: Claude Code · Opus 4.8 · 2026-06-13_
> **Authoritative for:** the forward build, broken into SMALL self-contained units a cheaper /
> smaller-context agent can pick up and finish **without re-deriving context**. Entry point:
> `PROJECT_CANON.md` (§0). Companion: `BUILD_PLAN.md` (phase narrative).
>
> **How an agent uses one unit:** read (a) `PROJECT_CANON.md`, (b) the unit's *Refs*, (c) `CONVENTIONS.md`.
> Then do *Steps*, satisfy *Accept*, respect *HITL*. One unit = one PR-sized change. Don't exceed scope.
> **Tier:** `S` = small/cheap model ok · `J` = needs judgment (Opus/owner). **All writes are HITL-gated.**

## DONE this session (the ~70% — don't redo)
SSOT docs (canon/merge-map/build-plan/repo-structure/conventions/ADR_RECONCILIATION) · vendored
`chatminer/` (10 parsers + segmenter + artifacts) · `TopicTag` + `RELATIONSHIP_HISTORY` · segmenter
generalized + `_load_case_terms()` (config-load) · `case_terms.example.yaml` + gitignored real file ·
infra (new OVH VPS `51.81.83.191` docker host; gateways topology; VIPs; claude-context embedder = OpenRouter `codestral-embed`).

## VIPs — never overwrite (integrate around)
Agno (+ native chat/AgentOS UI) · **custom Graphiti** · Semantica · **IBM ContextForge** · **forked SBV** · CopilotKit. Keep: LiteLLM (model gateway), OpenCode, agent-sandbox, persistent Kasm.

---

## TRACK 0 — CANONICAL SCHEMAS (the crux; blocks A-normalize, B, D). Schemas already inventoried — see `EVIDENCE_MERGE_MAP.md` §2.2/§2.6/§7-8 and the source files cited per unit.

### H0.1 — `Entity` schema + canonical model `[S]`
- **Goal:** one pydantic `Entity` consolidating every donor entity schema.
- **Refs:** dial-stack `drizzle/schema.ts::documentEntities` (entityType, entityValue, normalizedValue, occurrenceCount, firstOccurrence, confidence, extractorModel) · Chat Parser v2.0 `entities.jsonl` (types person/org/project/tech/location/concept, aliases) · Salem Ontology v3 entities · `server/mcp/storage/graphiti-client.ts::Entity` (mclFactors) · ChatMiner `core/types.py::ArtifactType.ENTITY`.
- **Steps:** create `evidence/schemas/__init__.py` + `evidence/schemas/entity.py` — fields: `id, type, value, normalized_value, aliases[], confidence, first_occurrence, occurrence_count, source_refs[], mcl_factors[], attrs`.
- **Accept:** pydantic model imports; round-trip `to_dict/from_dict` test in `evals/`.
- **HITL:** none (schema only). **Tier S.**

### H0.2 — `Relationship` schema (bitemporal) `[S]`
- **Refs:** `graphiti-client.ts::Relationship` (valid_from/valid_to, mclFactors) · Salem edges.
- **Steps:** `evidence/schemas/relationship.py` — `id, from_entity, to_entity, type, valid_from, valid_to, confidence, mcl_factors[], source_refs[]`.
- **Accept:** model + test. **Tier S.**

### H0.3 — `Event` + relationship-timeline schema `[J]`
- **Refs:** Chat Parser v2.0 `events.jsonl` (subtypes milestone|decision|meeting|incident|change|memory|upcoming; temporal historical|current|future) · `timeline-generator.ts::TimelineEvent` + cycle-of-abuse phases · Salem incidents/statements · `NormalizedRecord` (occurred_at/knowledge_time/disclosure_tier).
- **Steps:** `evidence/schemas/event.py` — `id, event_type, temporal_class, occurred_at, knowledge_time, disclosure_tier, participants[](entity ids), related_entities[], summary, source_refs[], mcl_factors[]`. A **relationship timeline** = ordered Events filtered to a pair/among entities.
- **Accept:** model + a test building a 3-event timeline for two entities. **Tier J** (the crux — judgment on the model).

### H0.4 — Storage tables migration `[J]`
- **Refs:** dial-stack `drizzle/production-message-schemas.ts` + `drizzle/schema.ts` (documents→sections→chunks→spans→summaries→entities, evidenceChains, **mclFactors (12)**, behavior categories, exhibit numbers) · `migrations/004_chain_of_custody.sql` (Ed25519) · spine `sql/0002`, `sql/0003`.
- **Steps:** `sql/0004_entities_events_relationships.sql` — tables for entities, relationships, events (in `analysis` schema), + mcl_factors reference table; FKs to evidence rows; indexes on entity value/type, event occurred_at.
- **Accept:** migration applies clean on the VPS PG18; `\d` shows tables. **HITL:** schema write → owner approve. **Tier J.**

### H0.5 — Entity-extraction atomic tool `[J]`
- **Refs:** `server/python-tools/nlp_runner.py` (spaCy `en_core_web_lg` NER, aliases, confidence) · Chat Parser v2.0 entity design (first-mention, mention counts).
- **Steps:** `evidence/tools/extract_entities.py` — `@register(capability="extract.entities")`; input text/records → `Entity[]` (H0.1) with aliases/confidence/first-mention.
- **Accept:** runs on a sample transcript, emits ≥1 person entity w/ confidence + first_occurrence. **HITL:** none (read-only extract). **Tier J** (entity extraction = crux).

---

## TRACK A — PARSER CORE (most done; storage-agnostic)

### HA.1 — ChatMiner→NormalizedRecord adapter `[J]`
- **Refs:** `chatminer/core/types.py` (ParsedMessage/ParsedConversation) · `evidence/normalize.py` (NormalizedRecord).
- **Steps:** `evidence/tools/_chatminer_adapter.py` — map ParsedMessage→NormalizedRecord (content→content, sender_role→role, timestamp→occurred_at, source_format→source, conversation_id, everything else→attrs incl. message_hash, content_type, artifacts, segment topic_tag).
- **Accept:** unit test: a 2-message ParsedConversation → 2 NormalizedRecords with occurred_at set. **Tier J.**

### HA.2 — Per-format `@register` wrappers (10 tiny units) `[S]`
- **Skeleton** (one file per format under `evidence/tools/`, e.g. `chatgpt_official.py`):
  ```python
  from __future__ import annotations
  from evidence.registry import register
  from evidence.tools._chatminer_adapter import to_normalized_records
  from chatminer.parsers.chatgpt_official import ChatGptOfficialParser
  @register(id="transcripts.chatgpt-official", capability="parse.transcript",
            description="ChatGPT official JSON export -> NormalizedRecords",
            accept=lambda hint, size: hint.endswith(".json"),
            provenance="vendored: chatminer/parsers/chatgpt_official.py")
  def run(payload: dict) -> dict:
      result = ChatGptOfficialParser().parse_file(payload["path"])
      return {"records": [r.model_dump() for r in to_normalized_records(result)]}
  ```
- **The 10 (one sub-unit each):** chatgpt_official, chatgpt_share, gemini_chrome, gemini_json, claude_md, claude_code, perplexity_gdpr, perplexity_plugin, perplexity_md, generic_md.
- **Accept:** `load_builtin_tools()` registers all under `parse.transcript`; each parses its sample. **Tier S** (identical pattern — ideal for a small agent, one file at a time).

### HA.3 — Populate `evidence/config/case_terms.yaml` `[owner]`
Copy `case_terms.example.yaml` → `case_terms.yaml`; fill real names/places/child name per `TopicTag`. **HITL:** owner-only (PII). **Tier owner.**

### HA.4 — Retire 4 placeholders + registry smoke test `[S]`
Delete `evidence/tools/{chatgpt_export,claude_ai_export,claude_code_jsonl,markdown_transcript}.py`; run a smoke that `load_builtin_tools()` count == 10 + asserts no import errors. **Tier S.**

### HA.5 — Deploy + VPS smoke test `[J]` (RUNBOOK below)
Sync to VPS, rebuild image (chatminer + pyyaml + sentence-transformers deps), parse a real export end-to-end. **HITL:** deploy = owner go. **Tier J.**

---

## TRACK B-E + PART 2/3 (compact stubs — expand when reached; each becomes its own small-unit set)

- **B — Knowledge ingestion + domain routing (bootstrap loop) `[J]`:** route segmented records into domains (`platform_design`/`legal_strategy`/`timeline_relationship`/`personal_history`) by segment tag; ingest design+legal history first so Builder agents can answer "what did we decide". Refs: canon §3.
- **C — IBM ContextForge gateway + serve agents `[J]`:** stand up ContextForge (off-the-shelf) as the MCP tool gateway; register spine + dial-stack tools; serve our agents via Agno MCP-server/A2A/AG-UI. Refs: canon §5 topology.
- **D — Bitemporal substrate + SurrealDB decision `[J]`:** keep **custom Graphiti** (VIP) for cognition; decide **SurrealDB** as store/session/Knowledge/memory consolidation (Agno-native); wire two-pass (multi-pass-classifier=Pass1, forensic-workflow shape on Agno). Refs: canon §10, EVIDENCE_MERGE_MAP §2.6/§8.
- **E — Forensic verticals `[J]`:** **forked SBV** (VIP) + SMS/FB/iMessage parsers + sqlite-WAL deleted-message recovery + Ed25519 custody hardening + harness tests + R2 backups. Refs: EVIDENCE_MERGE_MAP §2.1/§2.7/§8.
- **Part 2 — Behavioral `[J]`:** wrap **Tether** (`dial-stack/utilities/apps/ml-nlp/Tether`, HF models) + ConflictAnalysisApp RuleEngine + pattern-analyzer (~25 MCL modules) as MCP services; map to mcl_factors. Deferred per owner until here.
- **Part 3 — AI LAW FIRM build-out `[J]`:** port the owner's **Gemini Gems personas** to Agno as a third agent family — strategy / motions / filings / discovery agents — using the **MCL 722.23 ontology** + imported Michigan legal skills + the evidence/knowledge/timeline outputs. Refs: canon §2 (Part 3), `ontologies/mcl_722_23.ttl`. (Inventory the Gemini Gems personas as the first sub-unit.)

## DEPLOY RUNBOOK (every Track-A/B/E unit ends here)
```
# from Agno-MCP-Platform/ — sync to VPS, rebuild, restart, verify
tar czf /tmp/sync.tgz chatminer evidence sql requirements.txt
scp -i ~/.ssh/ovh /tmp/sync.tgz debian@40.160.5.19:/tmp/
ssh -i ~/.ssh/ovh debian@40.160.5.19 'cd ~/agno-mvp && tar xzf /tmp/sync.tgz && \
  docker compose --profile tools up -d --build agentos-api && \
  docker compose exec agentos-api python -m evidence smoke'   # smoke = registry load + sample parse
```
(`requirements.txt` must add: `chatminer` deps — sentence-transformers, scikit-learn, pyyaml — and rebuild the image, not just restart.)

## NOT NOW — future brainstorm
**Workflows** (the named `agno.workflow` verticals A/B/C, orchestration, agent-to-agent flows): a **dedicated brainstorming session** with the owner — output gets added here as new units or built directly. Do not design workflows ahead of that session.
