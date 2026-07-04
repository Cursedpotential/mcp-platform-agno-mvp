# E2 — Messaging + Court-Evidence Forensic Core (Extracted Table Inventory)

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Extraction task E2 of the forensic-db reconciliation. Scope = the messaging ingestion +
> court-evidence spine from the prior-iteration "Salem Forensic Trinity" schema corpus.

## Provenance (sources read)

| # | Source file (absolute) | What it contributes |
|---|---|---|
| S1 | `dev-resources/Archives/TheBigOne/TraceIQ/TraceIQ-fresh/00_Documentation/STACK_Deployment/n8n-local/supabase_production_schema.sql` | The *generic* (un-prefixed) production schema: `documents / conversations / messages / entities / entity_mentions / behaviors / evidence_items / factor_citations / timeline_events / mcl_factors / behavior_categories` + indexes, 3 views, 2 triggers. Has `content_lower` GENERATED column, `supports_factor` (supports/contradicts), `strength`. |
| S2 | `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/Case/COMPLETE_SCHEMA_PARSER_INVENTORY.md` (PARTS 1-2, 6) | The richer `messaging_*`-prefixed forensic schema (DDL excerpts), the 18 behavior categories, the 12 MCL factors, per-platform XML/HTML/TXT field maps, blocking-detection gotchas, deployment order (PART 6). |
| S3 | `dev-resources/Archives/TheBigOne/01_MCP_Tool_Platform_Repo/drizzle/production-message-schemas.ts` | Canonical Drizzle ORM port of the 900-line schema — authoritative column types/lengths for the `messaging_*` tables + 3 enums + relations. **Most complete `messaging_*` definition.** |
| S4 | `dev-resources/Archives/TheBigOne/01_MCP_Tool_Platform_Repo/drizzle/message-schemas.ts` | Per-platform flat tables (`sms_messages / facebook_messages / imessage_messages / email_messages / chatgpt_conversations`) with platform-specific columns + `preliminary_*` analysis lane + `conversation_cluster_id`. |
| S5 | `dev-resources/Archives/TheBigOne/01_MCP_Tool_Platform_Repo/CLAUDE.md` | Architectural intent: 6-pass NLP, cluster-ID format `PLAT_YYMM_TOPIC_iii`, preliminary→meta-analysis workflow, `meta_analyses`/`contradictions`/`audit_trail` tables (named, not DDL'd here). |
| — | `dev-resources/Archives/TheBigOne/01_MCP_Tool_Platform_Repo/drizzle/0001_remarkable_wendigo.sql` | Checked — **NOT messaging**; it is apiKeys/systemPrompts/workflowTemplates (MySQL). Excluded. |

**Three parallel iterations exist** and must be reconciled downstream:
- **Iteration A (generic, S1):** un-prefixed tables, `content`/`content_lower`, `entities`+`entity_mentions`, factor_citations carries supports/contradicts polarity. Simpler; no chain-of-custody acquirer fields on messages.
- **Iteration B (forensic, S2+S3):** `messaging_*` prefix, fuller chain-of-custody, denormalized forensic flags on the message row, `serial_number`, thread-linking pointers, `content_hash`. **B is the more advanced/intended target.**
- **Iteration C (per-platform, S4):** one flat table per platform feeding a preliminary-analysis lane; self-described as PLACEHOLDER/staging upstream of A/B.

---

## A. CHAIN-OF-CUSTODY / SOURCE LAYER

### `messaging_documents` (B; S3 authoritative) — source-file tracking + custody
| column | type | intent |
|---|---|---|
| id | uuid PK | doc id |
| filename | varchar(500) NOT NULL | original filename |
| file_hash | varchar(64) NOT NULL | **SHA-256 of source file — custody anchor / dedup** |
| file_size | int (BIGINT in SQL) | bytes |
| file_type | varchar(50) | `sms_xml`,`facebook_html`,`pdf`,`image`,`json`… |
| source_platform | varchar(50) | `android`,`ios`,`facebook`,`snapchat` |
| **acquired_by** | varchar(100) default 'Matt Salem' | custodian who acquired |
| **acquired_date** | timestamptz NOT NULL default now() | acquisition time |
| **acquisition_method** | text | how obtained (export, backup, subpoena…) |
| **verified_by** | varchar(100) | who verified |
| **verified_date** | timestamptz | verification time |
| storage_path | text | R2 bucket path |
| metadata | jsonb default '{}' | extras |

S1 generic `documents` adds processing-state fields absent from B: `status` (pending/processing/completed/failed), `processed_at`, `raw_text`, `page_count`, `source_device`, `date_range_start/end`, `record_count`, `created_at/updated_at`. Fold in on merge.

### `messaging_conversations` (B; S3) — thread grouping
| column | type | intent |
|---|---|---|
| id | uuid PK | |
| document_id | uuid FK→messaging_documents | provenance |
| platform | varchar(50) NOT NULL | `sms/facebook/snapchat/whatsapp/instagram` |
| platform_id | varchar(255) | external thread id; **UNIQUE(platform, platform_id)** |
| participants | text[] NOT NULL | all participants |
| participant_count | int NOT NULL | |
| primary_participant | varchar(255) | the "other party" |
| primary_participant_normalized | varchar(255) | **E.164** |
| started_at / ended_at | timestamptz | span |
| message_count | int default 0 | maintained by trigger |
| is_group | boolean default false | |
| behavior_summary | jsonb default '{}' | aggregated behavior counts |
| **is_evidence** | boolean default false | flagged for court |
| **exhibit_number** | varchar(50) | exhibit tag |
| **relevance_score** | decimal(3,2) | |

S1 generic `conversations` instead carries `title`, has `created_at/updated_at`, lacks normalized/evidence/exhibit fields.

---

## B. MESSAGE FORENSIC CORE — `messaging_messages` (B; S3 authoritative)

Central court record. UNIQUE(conversation_id, external_id).

**Identity / linkage**
- id uuid PK · conversation_id uuid NOT NULL FK · document_id uuid FK
- external_id varchar(200) — platform message id
- serial_number int — sequence-in-conversation
- previous_message_id / next_message_id text — **thread linking pointers**
- time_since_previous_seconds int — gap (drives clustering / burst detection)

**Time (forensic-grade)**
- timestamp timestamptz NOT NULL · timestamp_precision varchar(20) default 'exact' (enum exact/approximate/inferred)
- timezone varchar(50) · date_us text (MM/DD/YYYY) · time_12h text — human-render copies

**Participants**
- sender varchar(255) NOT NULL · sender_normalized (E.164) · sender_name
- recipient · recipient_normalized

**Content**
- body text · body_lower text (search; S1 uses GENERATED `content_lower AS LOWER(content) STORED`)
- word_count int · character_count int
- **content_hash varchar(64)** — SHA-256 of body (tamper / dedup at message level)
- raw_data text/jsonb — original record preserved verbatim

**Message metadata (forensic flags)**
- **direction** text NOT NULL — `inbound/outbound/unknown` (enum `direction`); blocking/initiation analysis
- message_type text default 'text' — text/mms/voice…
- status text — sent/delivered/read/failed; **status carries blocking indicators (SMS status=64 Failed, etc.)**
- is_read int
- has_attachments int default 0 · attachment_count int default 0

**Behavior denormalization (fast filter, populated from messaging_behaviors)**
- has_behaviors int default 0 · behavior_count int default 0
- behavior_categories text (JSON array) · max_severity text
- **contains_apology / contains_blame / contains_threat / contains_minimizing** int default 0 — quick boolean forensic flags

**Evidence tracking**
- is_evidence int default 0 · evidence_item_id text · is_redacted int default 0

> S1 generic `messages` is the trimmer cousin: `content`/`content_lower(GENERATED)`, `direction varchar(10)`, `has_behaviors boolean`, `behavior_count`, `max_severity`, `raw_data jsonb`; no content_hash / serial_number / thread pointers / contains_* flags. Merge target = B superset.

---

## C. ATTACHMENTS — `messaging_attachments` (B; S3)
message_id FK NOT NULL. Fields: filename, file_type NOT NULL, mime_type, **file_hash** (custody), file_size, storage_path, thumbnail_path, width, height, duration_seconds, **ocr_text** (screenshots / images), **transcription** (audio/video), contains_faces int, **is_screenshot** int, exif_data text/JSON (EXIF timestamps drive Google-Photos conversation reconstruction).

---

## D. BEHAVIOR DETECTION

### `messaging_behaviors` (B; S3) — per-match detection record
message_id FK NOT NULL · **category text FK→behavior_categories** · subcategory · matched_pattern · matched_text · start_char / end_char · context_before / context_after · confidence real NOT NULL · severity text NOT NULL (low/medium/high/critical) · detection_method text NOT NULL · rule_name · is_verified int · verified_by · verified_at. (S1 `behaviors` adds `verification_notes`, uses boolean/decimal types + `created_at`.)

### `behavior_categories` (reference) — **the 18**
PK id varchar(50) · name · description · severity_default default 'medium' · **mcl_factors varchar[]** (which MCL factors each maps to).
Full 18 (S2): `gaslighting, blame_shifting, minimizing, love_bombing, stonewalling, parental_alienation, coercive_control, financial_abuse, substance_weaponization, reactive_abuse, darvo, character_assassination, isolation, hoovering, triangulation, parenting_time, gatekeeping, special_needs`.
S1 seeded only the first 12 with explicit factor arrays, e.g. `gaslighting→{F,G,K}`, `parental_alienation→{J,K}`, `coercive_control→{F,K}`, `financial_abuse→{C,F,K}`, `darvo→{F,K}`, `blame_shifting→{F,J}`, `minimizing→{F,K}`, `love_bombing→{F}`, `stonewalling→{J}`, `substance_weaponization→{F,G}`, `reactive_abuse→{F,K}`, `character_assassination→{F,J}`. The remaining 6 (isolation/hoovering/triangulation/parenting_time/gatekeeping/special_needs) are list-only — need factor arrays assigned on load.

### `mcl_factors` (reference) — MCL 722.23 best-interest factors A–L
PK id varchar(2) · name · description · statutory_text. Seeded A–L (A Love/Affection, B Capacity to Provide, C Capacity for Necessities, D Home Environment, E Permanence of Family Unit, F Moral Fitness, G Mental/Physical Health, H Home/School/Community Record, I Child Preference, **J Willingness to Facilitate Relationship — KEY**, **K Domestic Violence — KEY**, L Other). Corpus also calls these "the 12 factors A–L".

---

## E. COURT-EVIDENCE SPINE

### `messaging_evidence_items` (B; S3)
id · message_id FK · exhibit_number varchar(50) · title · description · **mcl_factors text[]** · relevance_score int · verified_by · verified_at.
S1 generic `evidence_items` is far richer (court-prep): adds document_id FK, quote, context, evidence_type (communication/document/photo/record), category, evidence_date + date_precision, relevance_score decimal(3,2), is_exhibit, **is_authenticated**, **authentication_method**, **chain_of_custody text**, metadata jsonb, timestamps. → Merge: port S1's authentication/custody columns onto B.

### `messaging_factor_citations` (B; S3) — evidence↔factor link
id · evidence_item_id FK · factor_id varchar(2) FK→mcl_factors · supporting_text · relevance_explanation.
S1 `factor_citations` adds the legally-critical **supports_factor boolean (TRUE=supports / FALSE=contradicts)** + **strength** (weak/moderate/strong/decisive) + UNIQUE(evidence_id, factor_id). → Keep S1's polarity+strength.

### `messaging_timeline_events` (S2) / `timeline_events` (S1)
S2 minimal: id · event_type · event_date · description · evidence_ids uuid[] · mcl_factors text[].
S1 full: id · event_date NOT NULL + event_date_end · date_precision · title NOT NULL · description · event_type (communication/incident/filing/visit) · **message_ids[] / document_ids[] / evidence_ids[]** · location + lat/long · participants[] · mcl_factors varchar(2)[] · is_verified · is_disputed · metadata · timestamps. → S1 is merge target. (NB: a *different* `timeline_events` for Google-location data lives in E3 — keep distinct.)

### `entities` / `entity_mentions` (S1 only — absent from B)
`entities`: entity_type (person/location/organization/phone), name, normalized_name, aliases[], phone_numbers[], email_addresses[], address, lat/long, role (party/witness/child/attorney), is_party, UNIQUE(entity_type, normalized_name).
`entity_mentions`: message_id FK, entity_id FK, mention_text, start_char/end_char, confidence, extraction_method. → Overlaps Graphiti entity lane; covered more fully in E5.

---

## F. PER-PLATFORM HANDLING

### Per-platform staging tables (C; S4) — flat, one per platform
Common columns each: id, text NOT NULL, timestamp, sender, recipient, platform(default), **conversation_cluster_id** (`PLAT_YYMM_TOPIC_iii`), preliminary_{sentiment,severity 1-10,patterns jsonb[],confidence,analyzed_at,reasoning}, raw_data jsonb, file_source, **file_hash (custody)**, created_at.
Platform-specific extras:
- **sms_messages** — base only
- **facebook_messages** — thread_id, message_type (text/photo/video/audio), reactions jsonb[{emoji,user}]
- **imessage_messages** — is_from_me bool, chat_identifier, attachment_type
- **email_messages** — subject, cc[], bcc[], in_reply_to
- **chatgpt_conversations** — conversation_id, model, role (user/assistant/system)

### Per-platform raw field maps (S2 PART 1) — for parsers feeding the above
- **SMS/MMS** (SMS Backup&Restore XML): address, date (Java ms ÷1000), `type` 1=Recv/2=Sent/3=Draft/4=Outbox/5=Failed/6=Queued, body, readable_date, contact_name, read, **status -1/0/32/64 — status=64 = BLOCKING indicator**, locked, sub_id(SIM). MMS: msg_box 1/2, parts/part ct=text|image (base64 — skip on text-search), addrs type=137(from)/151(to). Call log: type 5=REJECTED/6=BLOCKED, presentation 2=RESTRICTED, duration=0 on outgoing = blocking.
- **Facebook** (HTML export): modern `_a6-g`(block)/`_a6-h`(sender)/`_a6-p`(content)/`_a72d`(ts); legacy `pam`/`_3-96`/`_3-94`. Multi-file per convo (message_1.html…); reactions/attachments in separate elements.
- **WhatsApp** (`_chat.txt`): `[MM/DD/YY, HH:MM:SS AM/PM] Sender: body`.
- **Snapchat / Instagram**: schema-supported (platform enum), same HTML-pattern approach as Facebook w/ different CSS selectors — defined, parser not built.
- **iMessage**: two-pass (PDF+embedded images→OCR; or text export→standard).
- **Email**: format TBD (Takeout / PST / EML).
- **Google Photos screenshots**: EXIF-timestamp sort → OCR-in-sequence → reconstruct timeline (feeds messaging_attachments.ocr_text/exif_data).
Recurring gotchas: Java-timestamp ÷1000, base64-skip on text search.

---

## G. DDL infra / deployment notes
Extensions: `uuid-ossp`, `pg_trgm` (trigram search on body_lower), `postgis` (timeline geo). Indexes (S1): messages(conversation_id, timestamp, sender_normalized), GIN trgm on content_lower, partial on has_behaviors=TRUE; behaviors(message_id,category,severity,is_verified); entities(type,name); evidence(date,type); timeline(date,type); factor_citations(evidence,factor). Views: `v_messages_analyzed`, `v_evidence_by_factor`, `v_daily_behavior_summary`. Triggers: `trg_behavior_insert`→recount/max_severity on message; `trg_message_insert`→recount on conversation. Deployment order (S2 PART 6): mcl_factors → behavior_categories → messaging_documents → messaging_conversations → messaging_messages → messaging_attachments → messaging_behaviors → messaging_evidence_items → messaging_factor_citations → timeline_events. Architectural lanes named but not DDL'd here (S5): `meta_analyses`, `contradictions`, `audit_trail` (immutable op log) — out of E2 scope, note for reconciliation.

## Reconciliation flags for downstream
1. **Two table families** (un-prefixed S1 vs `messaging_*` B) — pick `messaging_*` as canonical, port S1's richer evidence/timeline/entity columns + factor polarity (supports_factor/strength) onto it.
2. **content_hash + content_lower**: B has content_hash but lost S1's GENERATED content_lower — keep both.
3. **behavior_categories**: only 12 of 18 have seeded MCL-factor arrays; assign arrays for the 6 list-only categories.
4. **Custody asymmetry**: doc-level custody is strong (acquired/verified by/date), but message-level evidence authentication (is_authenticated/authentication_method/chain_of_custody) lives only on S1 evidence_items — promote.
5. **entities/entity_mentions** exist only in S1 and overlap the Graphiti entity lane — decide DB-vs-graph ownership (see E5).
