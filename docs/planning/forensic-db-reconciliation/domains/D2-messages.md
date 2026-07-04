# D2 — Messages, Conversations & Attachments (reconciled)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> Domain: the communication spine — conversations/threads, normalized messages, call/block
> logs, attachments, and the court-safe per-message classification surface (sentiment / intent /
> relational-function / cycle-phase).
>
> **Law (as-built, wins on conflict):** `extracted/E1_asbuilt_inventory.md`. **Prior art reconciled
> in:** `extracted/E2_messaging_core.md` (Salem Forensic Trinity messaging corpus). **Paper design
> adapted from:** `sections/03-canonical-data-model.md` §2. **Guardrails:** `discovery/CONTEXT_PACK.md`
> §6 + the reconciliation addendum.

---

## 1. The reconciliation in one paragraph

The live DB already has the right backbone: `evidence.evidence_hash` (raw custody anchor, agents
read-only) and `analysis.normalized_record` (the bitemporal record **every parser emits into**:
`occurred_at` valid-time, `knowledge_time`, a knowledge-horizon `disclosure_tier`). The prior
iteration (`messaging_documents / messaging_conversations / messaging_messages / messaging_attachments`,
E2 family B) carries the *forensic richness* the spine lacks — chain-of-custody acquirer fields,
per-thread linking, `content_hash`, direction/blocking indicators, message-level dedup, attachment OCR.
The paper design (`evidence.message`) added typed normalization + verbatim `raw_data` landing + the
balanced-cycle classification surface. **None of these is the whole answer; the reconciliation merges
all three under the as-built security boundary.**

The decision (see §3 for the merge rule): **keep `analysis.normalized_record` as the universal
record spine, and add typed forensic detail tables as PK-sharing subtypes** (`analysis.message`,
`analysis.call_log`) plus their children (`analysis.conversation`, `analysis.message_participant`,
`analysis.attachment`) and the multi-label HITL surface (`analysis.relational_classification`).
Per-platform quirks (FB reactions, iMessage `is_from_me`, email cc/bcc, ChatGPT role/model, SMS
`sub_id`) go in `platform_attrs jsonb`; the untouched export object goes in `raw_data jsonb`.

**Schema homing (security boundary, as-built law):** the raw export *file* + its SHA-256 stays in
`evidence` (`evidence.evidence_hash`, append-only, read-only to agents). Every *normalized/parsed*
row — conversations, messages, calls, attachments, classifications — is parser **output** = derived,
so it lives in `analysis` (writeable only after recorded approval). This is exactly the existing
`analysis.normalized_record.artifact_id → evidence.evidence_hash(id)` contract, extended. We do **not**
introduce `core/raw/geo/legal` top-level schemas (the paper's mistake); message text is a readable
derived artifact in `analysis`, the immutable source bytes are in `evidence`.

---

## 2. The disclosure_tier bug (fixed here)

Per E1 §5.1 the name `disclosure_tier` is defined two incompatible ways. Resolution applied in this
domain's DDL:

- **Keep** `analysis.normalized_record.disclosure_tier` as the substantive **knowledge-horizon**
  (`TEXT CHECK ('contemporaneous','hindsight','discovered')`) — values unchanged, no destructive cast.
- **Rename** the `0004` enum `disclosure_tier('public','restricted','sealed')` → **`sensitivity_tier`**
  (access classification), and add an optional `sensitivity_tier sensitivity_tier` column where an
  access tier is needed. Names are now disjoint; the foot-gun (someone `ALTER … TYPE disclosure_tier`)
  is gone.

---

## 3. The big call: normalized-spine vs typed-message tables (merge rule)

**Decision: spine + PK-sharing subtype, not "either/or."**

- `analysis.normalized_record` stays the **supertype spine** and the parser-emission target (honors
  as-built law — we do *not* demote it to a maintained projection). It holds the fields common to
  **all** record types (`message`/`call`/`event`/`media`): canonical `content`, `participants`,
  `occurred_at` (valid time), `knowledge_time`, the knowledge-horizon, `role`, `source`, provenance,
  tier, review. We extend it with `conversation_ref`, `ts_precision`, `sensitivity_tier`,
  `provenance_id`, `data_tier`, `review_status`, `safe_for_legal_use`.
- `analysis.message` is a **subtype sharing the PK** (`message.id REFERENCES normalized_record(id)`).
  It holds only message-specific forensic columns (direction, blocking/status, serial, thread
  pointers, sender/recipient normalization, `content_sha256`, denormalized behavior fast-filters,
  embedding ref, `platform_attrs`, `raw_data`). `analysis.call_log` is a sibling subtype for
  `record_type='call'`.

**Merge rule, precisely:** a message is one logical row split across two physical tables sharing a
UUIDv7 — the spine row (common + bitemporal + content) and the subtype row (forensic detail). The
parser writes the spine row first, then the subtype. No field is stored twice **except** two
deliberate denormalizations on `analysis.message` for forensic hot-paths: `conversation_id` (enables
the legally-important within-thread dedup `UNIQUE(conversation_id, external_id)`) and `ts_utc` (mirror
of `spine.occurred_at`, enabling the `(conversation_id, ts_utc)` ordering index entirely on one
table). Both mirrors are app/trigger-kept-equal to the spine and are documented as such.

**Why not pure-typed (drop the spine):** would contradict the as-built ("every parser emits into
normalized_record") and break cross-store `id_xref` + the Part-2 knowledge-horizon replay that scans
the spine across record types. **Why not pure-spine (JSONB-only):** loses typed forensic constraints,
dedup uniqueness, and indexable direction/blocking — the prior art's whole point.

---

## 4. Reconciled DDL

```sql
-- ===========================================================================
-- D2 — Messages / Conversations / Attachments  (schema: analysis + evidence)
-- Reuses as-built custom types from sql/0004. Adds shared lane enums (created
-- once, cross-domain). PG18 native uuidv7(). Vectors -> Milvus (embedding refs
-- only; NO pgvector columns, ADR-0027).
-- ===========================================================================

-- ---- 0. Shared lane enums (created once; also used by timeline/geo/analysis) ----
DO $$ BEGIN CREATE TYPE evidence_tier AS ENUM
  ('raw','extracted','inferred','analytical','legal_conclusion');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE precision_class AS ENUM
  ('exact','approximate','inferred','uncertain');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE strength_class AS ENUM
  ('none','weak','moderate','strong','conclusive');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE review_state AS ENUM
  ('unreviewed','in_review','approved','rejected','needs_more_evidence');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE conduct_party AS ENUM
  ('user','partner','child','third_party','institution','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE cycle_phase AS ENUM
  ('calm','tension_building','conflict','repair','reconciliation',
   'love_bombing','withdrawal','escalation','de_escalation','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Fix the disclosure_tier double-definition: rename the 0004 access enum.
-- (Guarded: the 0004 types may or may not be applied on the live volume.)
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname='disclosure_tier' AND typtype='e') THEN
    ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
-- If 0004 was never applied, create sensitivity_tier directly:
DO $$ BEGIN CREATE TYPE sensitivity_tier AS ENUM ('public','restricted','sealed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
-- Reused 0004 types assumed present: confidence(numeric(4,3)), source_system,
-- match_method, mcl_factor, source_ref(composite). Do NOT redefine.

-- ---- 1. analysis.normalized_record  (EXTEND the as-built spine) -------------
-- Existing cols (0003) kept verbatim: id, artifact_id, record_type, source,
-- conversation_id(TEXT external key), role, participants, content, occurred_at,
-- knowledge_time, disclosure_tier(TEXT knowledge-horizon), attrs, created_at.
ALTER TABLE analysis.normalized_record
  ADD COLUMN IF NOT EXISTS conversation_ref   uuid,            -- FK below
  ADD COLUMN IF NOT EXISTS ts_precision        precision_class NOT NULL DEFAULT 'exact',
  ADD COLUMN IF NOT EXISTS sensitivity_tier    sensitivity_tier,       -- access class (nullable)
  ADD COLUMN IF NOT EXISTS data_tier           evidence_tier NOT NULL DEFAULT 'extracted',
  ADD COLUMN IF NOT EXISTS review_status       review_state  NOT NULL DEFAULT 'unreviewed',
  ADD COLUMN IF NOT EXISTS safe_for_legal_use  boolean       NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS provenance_id       uuid;          -- FK -> provenance.provenance (added when that domain lands)
-- disclosure_tier (knowledge-horizon) UNCHANGED: TEXT CHECK
--   ('contemporaneous','hindsight','discovered').

-- ---- 2. analysis.conversation  (thread / document grouping) ----------------
-- Merges E2 messaging_conversations (B) + the richer generic `conversations`(S1).
CREATE TABLE IF NOT EXISTS analysis.conversation (
  id                       uuid PRIMARY KEY DEFAULT uuidv7(),
  source_artifact_id       uuid NOT NULL REFERENCES evidence.evidence_hash(id), -- doc-level custody
  platform                 text NOT NULL,                 -- sms/fb/imessage/gvoice/snapchat/instagram/whatsapp/gchat/email
  external_thread_key      text,                          -- platform thread/conversation id
  title                    text,
  participants             jsonb NOT NULL DEFAULT '[]'::jsonb, -- raw + resolved tokens
  participant_count        integer,
  primary_participant      text,                          -- the "other party"
  primary_participant_e164 text,
  is_group                 boolean NOT NULL DEFAULT false,
  started_at               timestamptz,
  ended_at                 timestamptz,
  message_count            integer NOT NULL DEFAULT 0,     -- maintained by trigger
  is_evidence              boolean NOT NULL DEFAULT false, -- flagged for court
  exhibit_number           text,
  relevance                confidence,                    -- 0.000-1.000 (0004 domain)
  behavior_summary         jsonb NOT NULL DEFAULT '{}'::jsonb, -- aggregated behavior counts (hint, not fact)
  data_tier                evidence_tier NOT NULL DEFAULT 'extracted',
  review_status            review_state  NOT NULL DEFAULT 'unreviewed',
  platform_attrs           jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw_data                 jsonb,                          -- verbatim source (C11)
  provenance_id            uuid,                           -- FK -> provenance.provenance (deferred)
  created_at               timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_conversation_thread UNIQUE (platform, external_thread_key)
);
CREATE INDEX IF NOT EXISTS idx_conv_source   ON analysis.conversation(source_artifact_id);
CREATE INDEX IF NOT EXISTS idx_conv_platform ON analysis.conversation(platform);
CREATE INDEX IF NOT EXISTS idx_conv_primary  ON analysis.conversation(primary_participant_e164);
CREATE INDEX IF NOT EXISTS idx_conv_attrs    ON analysis.conversation USING gin(platform_attrs);

-- wire the spine -> conversation now that the table exists
ALTER TABLE analysis.normalized_record
  ADD CONSTRAINT fk_normrec_conv
  FOREIGN KEY (conversation_ref) REFERENCES analysis.conversation(id);
CREATE INDEX IF NOT EXISTS idx_normrec_convref_time
  ON analysis.normalized_record(conversation_ref, occurred_at);
-- FTS + fuzzy on the canonical body (lives on the spine):
CREATE INDEX IF NOT EXISTS idx_normrec_fts
  ON analysis.normalized_record
  USING gin (to_tsvector('english', coalesce(content,'')));
CREATE INDEX IF NOT EXISTS idx_normrec_trgm
  ON analysis.normalized_record
  USING gin (content gin_trgm_ops);

-- ---- 3. analysis.message  (forensic subtype; shares PK with the spine) -----
-- E2 family-B `messaging_messages` superset + S1 richness + paper typed cols.
CREATE TABLE IF NOT EXISTS analysis.message (
  id                    uuid PRIMARY KEY
                          REFERENCES analysis.normalized_record(id) ON DELETE CASCADE,
  conversation_id       uuid NOT NULL REFERENCES analysis.conversation(id), -- mirror of spine.conversation_ref (dedup + local queries)
  ts_utc                timestamptz,                       -- mirror of spine.occurred_at (hot-path ordering)
  platform              text NOT NULL,
  external_id           text,                              -- platform message id
  serial_number         bigint GENERATED ALWAYS AS IDENTITY, -- stable in-thread order (TraceIQ serial_id)
  prev_message_id       uuid REFERENCES analysis.message(id),
  next_message_id       uuid REFERENCES analysis.message(id),
  time_since_prev_s     integer,                           -- burst/cluster detection
  -- participants (verbatim + normalized; resolution -> entity domain) ---------
  sender_raw            text,                              -- verbatim token before resolution
  sender_e164           text,
  sender_entity_id      uuid,                              -- FK -> entity.person (deferred)
  recipient_raw         text,
  recipient_e164        text,
  -- forensic metadata --------------------------------------------------------
  direction             text CHECK (direction IN ('inbound','outbound','unknown')),
  message_type          text NOT NULL DEFAULT 'text',      -- text/mms/voice/sticker/...
  delivery_status       text,                              -- sent/delivered/read/failed
  status_code           integer,                           -- raw SMS status (e.g. 64 = Failed/blocked)
  is_blocked            boolean NOT NULL DEFAULT false,     -- derived from status/type 5/6
  -- time (forensic-grade; precision/horizon on the spine) --------------------
  raw_ts                text,                              -- verbatim timestamp string (never discarded)
  tz                    text,
  ts_earliest           timestamptz,
  ts_latest             timestamptz,
  temporal_confidence   confidence,
  relative_time_refs    jsonb NOT NULL DEFAULT '[]'::jsonb, -- "last night"/"that weekend" -> temporal domain
  -- content integrity --------------------------------------------------------
  word_count            integer,
  char_count            integer,
  content_sha256        bytea CHECK (content_sha256 IS NULL OR octet_length(content_sha256)=32),
  language              text,
  -- single-valued extraction HINTS (multi-label lives in relational_classification)
  surface_sentiment     text,                              -- surface tone ONLY
  inferred_intent       text,                              -- distinct from surface tone
  topic                 text,
  domain_type           text,                              -- parenting/finance/logistics/legal
  relevance             text,
  custody_relevance     text,
  evidence_strength     strength_class,
  extraction_confidence confidence,
  -- review / sensitivity gates ----------------------------------------------
  is_private            boolean NOT NULL DEFAULT false,     -- TraceIQ is_private -> review gate
  is_redacted           boolean NOT NULL DEFAULT false,
  -- denormalized fast-filters (HINTS; authoritative labels in behavioral D4) --
  has_attachments       boolean NOT NULL DEFAULT false,
  attachment_count      integer NOT NULL DEFAULT 0,
  has_behaviors         boolean NOT NULL DEFAULT false,
  behavior_count        integer NOT NULL DEFAULT 0,
  max_behavior_severity text,
  screenshot_attachment_id uuid,                            -- FK set after attachment table (below)
  -- vectors & payload --------------------------------------------------------
  body_embedding_ref    text,                              -- Milvus PK (ADR-0027); NO vector in PG
  platform_attrs        jsonb NOT NULL DEFAULT '{}'::jsonb, -- FB reactions / iMessage is_from_me / email cc,bcc / ChatGPT role,model / SMS sub_id
  raw_data              jsonb,                             -- verbatim export object (normalized_messages landing)
  CONSTRAINT uq_message_thread_extid UNIQUE (conversation_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_msg_conv_time ON analysis.message(conversation_id, ts_utc);
CREATE INDEX IF NOT EXISTS idx_msg_ts        ON analysis.message(ts_utc);
CREATE INDEX IF NOT EXISTS idx_msg_sender    ON analysis.message(sender_e164);
CREATE INDEX IF NOT EXISTS idx_msg_type      ON analysis.message(message_type);
CREATE INDEX IF NOT EXISTS idx_msg_chash     ON analysis.message(content_sha256);
CREATE INDEX IF NOT EXISTS idx_msg_attrs     ON analysis.message USING gin(platform_attrs);
CREATE INDEX IF NOT EXISTS idx_msg_raw       ON analysis.message USING gin(raw_data);
CREATE INDEX IF NOT EXISTS idx_msg_blocked   ON analysis.message(id) WHERE is_blocked;
CREATE INDEX IF NOT EXISTS idx_msg_private   ON analysis.message(id) WHERE is_private; -- review queue

-- ---- 4. analysis.message_participant  (recipients + third parties, M:N) -----
CREATE TABLE IF NOT EXISTS analysis.message_participant (
  id               uuid PRIMARY KEY DEFAULT uuidv7(),
  message_id       uuid NOT NULL REFERENCES analysis.message(id) ON DELETE CASCADE,
  entity_id        uuid,                                   -- FK -> entity.person (deferred)
  participant_raw  text,
  participant_e164 text,
  role             text NOT NULL CHECK (role IN ('from','to','cc','bcc','group','third_party')),
  conduct_party    conduct_party,                          -- whole-record (both-parties) analysis
  CONSTRAINT uq_msg_part UNIQUE (message_id, role, participant_raw)
);
CREATE INDEX IF NOT EXISTS idx_msgpart_msg    ON analysis.message_participant(message_id);
CREATE INDEX IF NOT EXISTS idx_msgpart_entity ON analysis.message_participant(entity_id);

-- ---- 5. analysis.attachment  (message attachments; OCR/transcription) -------
-- E2 messaging_attachments + paper multimodal linkage (full media -> D7).
CREATE TABLE IF NOT EXISTS analysis.attachment (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  message_id         uuid NOT NULL REFERENCES analysis.message(id) ON DELETE CASCADE,
  source_artifact_id uuid REFERENCES evidence.evidence_hash(id),  -- attachment-file custody
  media_asset_id     uuid,                                  -- FK -> multimodal.media_asset (deferred, D7)
  filename           text,
  attachment_type    text,                                  -- image/video/audio/document/voice
  mime_type          text,
  file_sha256        bytea CHECK (file_sha256 IS NULL OR octet_length(file_sha256)=32),
  file_size          bigint,
  object_uri         text,                                  -- R2 (r2://nexus/... or casebible-*)
  thumbnail_uri      text,
  width              integer,
  height             integer,
  duration_s         numeric,
  is_screenshot      boolean NOT NULL DEFAULT false,
  contains_faces     boolean NOT NULL DEFAULT false,        -- detection HINT -> HITL in D7
  ocr_text           text,                                  -- extracted tier
  transcription      text,                                  -- extracted tier (audio/video)
  exif               jsonb,                                 -- EXIF (drives Google-Photos reconstruction)
  ocr_confidence     confidence,
  embedding_ref      text,                                  -- Milvus PK (OCR/transcript vector)
  data_tier          evidence_tier NOT NULL DEFAULT 'extracted',
  review_status      review_state  NOT NULL DEFAULT 'unreviewed',
  platform_attrs     jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw_data           jsonb,
  provenance_id      uuid,                                  -- FK -> provenance.provenance (deferred)
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_att_msg     ON analysis.attachment(message_id);
CREATE INDEX IF NOT EXISTS idx_att_type    ON analysis.attachment(attachment_type);
CREATE INDEX IF NOT EXISTS idx_att_exif    ON analysis.attachment USING gin(exif);
CREATE INDEX IF NOT EXISTS idx_att_ocr_fts ON analysis.attachment
  USING gin (to_tsvector('english', coalesce(ocr_text,'')||' '||coalesce(transcription,'')));
CREATE INDEX IF NOT EXISTS idx_att_shot    ON analysis.attachment(id) WHERE is_screenshot;

-- deferred self-ref now that attachment exists
ALTER TABLE analysis.message
  ADD CONSTRAINT fk_msg_screenshot
  FOREIGN KEY (screenshot_attachment_id) REFERENCES analysis.attachment(id);

-- ---- 6. analysis.call_log  (call & block log; record_type='call' subtype) ---
-- sms_backup_parser blocked-call type 5/6; shares PK with the spine like message.
CREATE TABLE IF NOT EXISTS analysis.call_log (
  id                 uuid PRIMARY KEY
                       REFERENCES analysis.normalized_record(id) ON DELETE CASCADE,
  source_artifact_id uuid NOT NULL REFERENCES evidence.evidence_hash(id),
  conversation_id    uuid REFERENCES analysis.conversation(id),
  from_raw           text,
  from_e164          text,
  from_entity_id     uuid,                                  -- FK -> entity.person (deferred)
  to_raw             text,
  to_e164            text,
  to_entity_id       uuid,                                  -- FK -> entity.person (deferred)
  call_type          text NOT NULL CHECK (call_type IN
                       ('incoming','outgoing','missed','rejected',
                        'blocked_incoming','blocked_outgoing','voicemail')),
  direction          text CHECK (direction IN ('inbound','outbound','unknown')),
  started_at         timestamptz,
  ts_precision       precision_class NOT NULL DEFAULT 'exact',
  duration_s         integer,                               -- 0 on outgoing can indicate blocking
  is_blocked         boolean NOT NULL DEFAULT false,        -- type 5/6 or presentation RESTRICTED
  presentation       text,                                  -- RESTRICTED/etc.
  data_tier          evidence_tier NOT NULL DEFAULT 'extracted',
  platform_attrs     jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw_data           jsonb,
  provenance_id      uuid
);
CREATE INDEX IF NOT EXISTS idx_call_started ON analysis.call_log(started_at);
CREATE INDEX IF NOT EXISTS idx_call_type    ON analysis.call_log(call_type);
CREATE INDEX IF NOT EXISTS idx_call_conv    ON analysis.call_log(conversation_id);

-- ---- 7. analysis.relational_classification  (court-safe multi-label surface) -
-- sentiment / intent / relational-function / cycle-phase. Polymorphic subject
-- (message/event/call); MULTIPLE rows per subject = multi-label; HITL-gated.
-- Adopts paper §8.1; positive/repair categories seeded from positive_behaviors.ttl
-- so the model is NOT one-sidedly negative (both-parties / full-cycle guardrail).
CREATE TABLE IF NOT EXISTS analysis.relational_classification (
  id                          uuid PRIMARY KEY DEFAULT uuidv7(),
  subject_type                text NOT NULL CHECK (subject_type IN ('message','event','call')),
  subject_id                  uuid NOT NULL,                -- = normalized_record/message/event id
  event_category              text,   -- positive/neutral/ambiguous/negative/repair_attempt/
                                       -- love_bombing/cycle_transition/escalation/de_escalation
  surface_sentiment           text,
  emotional_tone              text,
  relational_function         text,
  cycle_phase                 cycle_phase,
  cycle_transition_type       text,
  love_bombing_indicator      boolean,
  repair_attempt_indicator    boolean,
  cooperation_indicator       boolean,
  neutral_context_indicator   boolean,
  precedes_concerning_event   boolean,
  follows_concerning_event    boolean,
  temporal_proximity_to_conflict_s bigint,
  changes_nearby_interpretation boolean,                    -- may spawn a temporal.interpretation_version (D?)
  corroborated                boolean,
  conduct_party               conduct_party,                -- whose conduct (user/partner/...)
  pattern_relevance           text,
  mcl_factor_hint             mcl_factor,                   -- reuse 0004 enum (a-l); HINT only
  classified_by               text CHECK (classified_by IN ('rule','model','human')),
  confidence                  confidence,
  detector_provenance_id      uuid,                         -- which detector lib/version
  requires_human_review       boolean NOT NULL DEFAULT true,
  review_status               review_state  NOT NULL DEFAULT 'unreviewed',
  safe_for_legal_use          boolean NOT NULL DEFAULT false,
  data_tier                   evidence_tier NOT NULL DEFAULT 'analytical',
  provenance_id               uuid,
  created_at                  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_relcls_subject  ON analysis.relational_classification(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_relcls_category ON analysis.relational_classification(event_category);
CREATE INDEX IF NOT EXISTS idx_relcls_phase    ON analysis.relational_classification(cycle_phase);
CREATE INDEX IF NOT EXISTS idx_relcls_review   ON analysis.relational_classification(review_status)
  WHERE requires_human_review;
```

---

## 5. Decision table

| Table / field | Decision | Source | Note |
|---|---|---|---|
| `analysis.normalized_record` (spine) | **adopt + extend** | as-built 0003 | Stays the universal parser-emission spine; +`conversation_ref`,`ts_precision`,`sensitivity_tier`,`data_tier`,`review_status`,`safe_for_legal_use`,`provenance_id`. |
| `normalized_record.disclosure_tier` (TEXT horizon) | **adopt unchanged** | as-built 0003 | The substantive bitemporal knowledge-horizon; values `contemporaneous/hindsight/discovered` kept. |
| `0004` enum `disclosure_tier` → `sensitivity_tier` | **adapt (rename)** | as-built 0004 / E1 §5.1 | Fixes the double-definition; now access classification only. |
| `confidence`,`source_system`,`match_method`,`mcl_factor`,`source_ref` | **reuse** | as-built 0004 | Not redefined; `confidence` used on every score, `mcl_factor` as classification hint. |
| `evidence_tier/precision_class/strength_class/review_state/conduct_party/cycle_phase` | **adopt (new, shared)** | paper §0.1 | Cross-domain lane enums; created once (idempotent). |
| `analysis.conversation` | **merge** | E2 `messaging_conversations`(B) + generic `conversations`(S1) | B's evidence/exhibit/normalized fields + S1's processing/title fields; `source_artifact_id`→`evidence.evidence_hash`. |
| `analysis.message` | **merge → subtype** | E2 `messaging_messages`(B superset) + S1 + paper `evidence.message` | Family-B superset is canonical; PK-shares with the spine. |
| `message.content_sha256` | **adopt** | E2 B `content_hash` | Message-level tamper/dedup; 32-byte CHECK (sha256 = canonical identity). |
| `message.direction`,`status_code`,`is_blocked` | **adopt** | E2 B + S2 field maps | SMS status=64 / call type 5/6 blocking indicators preserved. |
| `message.conversation_id` + `ts_utc` (denormalized) | **adapt** | reconciliation | Two deliberate mirrors of the spine for dedup unique + hot-path ordering. |
| `message.serial_number` | **adopt** | TraceIQ `serial_id` / E2 `serial_number` | `GENERATED ALWAYS AS IDENTITY`. |
| `prev/next_message_id`,`time_since_prev_s` | **adopt** | E2 B thread pointers | Burst/cluster detection; typed self-FK (was TEXT). |
| `message.body_lower` (GENERATED) | **deprecate → expression index** | E2 §181 / S1 | Dropped the stored col; FTS+trgm GIN built on `spine.content` instead. |
| `message.has_behaviors`/`behavior_count`/`max_behavior_severity`/`contains_*` | **adapt (hint only)** | E2 D denormalized flags | Kept as fast-filters; authoritative labels live in behavioral domain D4 behind HITL (court-safe). |
| `surface_sentiment`,`inferred_intent` (inline) | **adopt** | paper §2.1 (MP 470/456/1589-90) | Single-valued hints only; multi-label normalized out. |
| `message.is_private` | **adopt** | TraceIQ V4.1 | → judicial/sensitive-review gate (partial index). |
| `body_embedding_ref` (text) | **adapt** | ADR-0027 | Vector in Milvus, not PG (pgvector legacy/dropped). |
| `platform_attrs jsonb` | **adopt** | E2 family-C per-platform extras | FB reactions / iMessage `is_from_me` / email cc,bcc / ChatGPT role,model / SMS `sub_id`. |
| `raw_data jsonb` | **adopt** | `normalized_messages` landing (A3 §60) / C11 | Verbatim export object; byte-faithful. |
| Per-platform flat tables (`sms_messages`,`facebook_messages`,…) | **deprecate** | E2 family-C (S4) | Self-described staging/placeholder; folded into `message.platform_attrs`. |
| `analysis.message_participant` | **adopt** | E2 sender/recipient + paper `message_recipient` | M:N recipients + third parties; `conduct_party` for balance. |
| `analysis.attachment` | **merge** | E2 `messaging_attachments` + paper `multimodal` | OCR/transcription = extracted; binary in R2; vector in Milvus; full media → D7. |
| `analysis.call_log` | **adopt → subtype** | E2 §165 sms_backup_parser / paper `evidence.call_log` | `record_type='call'`; blocked-call type 5/6. |
| `analysis.relational_classification` | **adopt** | paper §8.1 (MP 404-497) + `positive_behaviors.ttl` | Court-safe, multi-label, HITL surface for sentiment/intent/relational-function/cycle-phase. |
| `messaging_evidence_items`,`factor_citations`,`timeline_events` | **defer** | E2 §E | Court-evidence spine + MCL factor citation → **legal domain (D-legal)**, not D2. |
| `entities`/`entity_mentions` | **defer** | E2 §147 / S1 | Identity resolution → **entity domain (D-entity)**; D2 keeps soft `*_entity_id` refs. |
| `behaviors`/`behavior_categories`/`mcl_factors` | **defer** | E2 §D | 18-category detector + MCL ref tables → **behavioral domain (D4)**. |

---

## 6. Migration notes (live DB → reconciled)

Apply in order; all idempotent. **Acceptance step first (verify-before-claiming):** diff against the
live `agno-postgres:18-duckdb` (`\dt analysis.*`, `\dT+ public.*`, `\d analysis.normalized_record`) to
confirm what's actually present before running anything — `0004` types may or may not be applied on the
live volume.

1. **Shared enums** — run §4 step 0 (`evidence_tier`, `precision_class`, `strength_class`,
   `review_state`, `conduct_party`, `cycle_phase`). Idempotent-guarded.
2. **disclosure_tier fix** — run the guarded `ALTER TYPE disclosure_tier RENAME TO sensitivity_tier`
   (only if the `0004` enum exists), else `CREATE TYPE sensitivity_tier`. The `normalized_record`
   TEXT column is **untouched** — no data migration, no cast.
3. **Extend spine** — `ALTER TABLE analysis.normalized_record ADD COLUMN IF NOT EXISTS …` (§4 step 1).
   Then create `analysis.conversation` (step 2) and add the `fk_normrec_conv` FK + the
   `(conversation_ref, occurred_at)` / FTS / trgm indexes on the spine.
4. **Create** `analysis.message`, `analysis.message_participant`, `analysis.attachment`,
   `analysis.call_log`, `analysis.relational_classification` (§4 steps 3-7), then the deferred
   `fk_msg_screenshot` FK.
5. **Backfill** — for existing `analysis.normalized_record` rows where `record_type='message'`:
   (a) upsert `analysis.conversation` from `(source/conversation_id)`; (b) set
   `normalized_record.conversation_ref`; (c) insert the matching `analysis.message` subtype row
   (PK = the spine `id`), hydrating typed columns from `attrs`/`raw_data`. Same for `record_type='call'`
   → `analysis.call_log`. ETL, not a single SQL statement.
6. **Deferred FKs** — add `provenance_id → provenance.provenance(id)` and `*_entity_id → entity.person(id)`
   FKs (and a NOT NULL on `message`/`attachment.provenance_id`) once those domains land. Tracked as
   open items, not applied now.
7. **Grants / boundary** — confirm the read-only agent role keeps `evidence.*` RO and `analysis.*`
   read-allowed/write-after-approval (existing `readonly_engine` model). New `analysis.*` tables inherit
   the analysis-schema grants; verify the approval-gated writer role owns them.
8. **Triggers (follow-up)** — `conversation.message_count` recount on message insert; keep
   `message.conversation_id`/`ts_utc` equal to `spine.conversation_ref`/`occurred_at` (mirror-guard
   trigger) — port from E2 `trg_message_insert`/`trg_behavior_insert`.

---

## 7. Needs human review / open items

1. **Polymorphic FK** `relational_classification.(subject_type,subject_id)` and
   `message_participant.entity_id` trade declarative integrity for flexibility — enforce via
   per-target partial FK or trigger when entity/timeline domains land (acceptable for v1).
2. **Denormalization mirrors** (`message.conversation_id`/`ts_utc`) must be trigger-guarded equal to the
   spine; if a mirror-guard trigger isn't added, treat them as app-maintained and document the invariant.
3. **Behavior labels are HYPOTHESES** — the `has_behaviors`/`behavior_count` hints here must never be
   read as findings; court output gates on D4 + `review_status='approved' AND safe_for_legal_use`.
4. **`provenance_id` nullable for now** — court-safety wants NOT NULL on derived rows; enforce once the
   provenance domain exists (migration note 6).
5. **6 of 18 behavior categories** still lack MCL-factor arrays (E2 §182) — a D4 concern, but the
   `mcl_factor_hint` here depends on it.
6. **No raw forensic/abuse evidence to cloud extractors** — `provenance.model_version` must record local
   ≤4B models for any column populated by extraction (CONTEXT_PACK §4).
