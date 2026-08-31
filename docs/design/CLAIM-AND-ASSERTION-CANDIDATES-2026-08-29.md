# Claim + Assertion candidates — phase 1 design (context side only)

> _Byline: Claude · Opus 5 · 2026-08-29 · owner-directed design session._
>
> **Scope boundary, owner-set:** this document designs the **context side only** — what a
> chat corpus yields when extracted. Evidence, promotion, custody binding, corroboration
> links, and evidence pointers are the **next phase** and are deliberately absent. No table
> here carries a promotion column. That omission is the design, not an oversight.

---

## 1 · Correction to ADR-0052 ruling Q6

Q6 (2026-08-12, D-054) resolved one collision and created another.

It correctly removed `artifact_candidate` because *artifact* reads, in owner usage, as a
**created work** — an AI chat, a generated document. It then renamed that row to
`working.claim_candidate` and described it as *"MCL 722.23 factors, case/court/docket
references, parties, motions, allegations, dates — the first legal-extractor schema."*

That description is a **legal-document extractor**. Owner ruling, 2026-08-29:

> "A legal artifact or document extractor gets extracted from chats. It would be one of the
> things that gets extracted, along with the timelines and the analysis. It's another
> production, it's another work product. But it's not a claim. It's kind of the farthest
> thing from a claim. It's a fucking document."

**Three distinct outputs were compressed into two names:**

| Output | What it is | Merge semantics | Table |
|---|---|---|---|
| **Claim** | A narrated assertion made inside a chat | Accumulates. Never merged, never rewritten. | `working.claim_candidate` — **this document** |
| **Entity** | A person, org, or thing referenced | Dedup-merged | existing layers; untouched here |
| **Created work** | A legal document, timeline, reference, or analysis *produced* inside a chat | Versioned as a work product | **deferred — not designed here** |

`working.claim_candidate` is hereby the narrated-assertion row. The ADR-0052 legal-document
extractor spec does **not** live at this name and needs its own table under a created-work
name in a later phase.

Q6's merge-semantics ruling — *entities dedup-merge, fact-claims accumulate and are NEVER
merged or rewritten* — survives intact and is the load-bearing rule of this design.

## 2 · Placement ruling

Owner, 2026-08-29: **"just land it next to it."**

The three existing candidate layers (`analysis.extraction_candidate`,
`analysis.entity_candidate`, `working.candidate_entity|fact|event`) are **not reconciled in
this phase**. New tables land beside them. Reconciliation is deferred and should be its own
change with its own ruling.

## 3 · What a claim is, and is not

Every row is an **assertion made in a chat**, not a record of anything that happened. The
corpus is permanently context-only (D-082, ADR-0053): AI chats can never become evidence.
Nothing in these tables is provable, citable, or filable on its own.

Consequences that drive the schema:

1. **`claim_class` is the most important column in the table.** It is the only thing
   separating degrees of unproven, and because claims are never rewritten, a row written
   without it is permanently unclassed.
2. **Redundancy is required.** The fortieth retelling of the same incident is a fortieth
   row. Deduplication destroys the variance between tellings, which is the analyzable
   signal. Clustering happens downstream, over the full set, and never by deletion.
3. **Nothing is inferred.** Relative dates stay relative. Hedges stay hedged. A claim
   carrying "I think it was around August" must never become a timestamp.
4. **Assistant text is never the subject's fact.** Enforced by CHECK, not by convention.

## 4 · `working.claim_candidate`

```sql
CREATE TABLE working.claim_candidate (
    id                   UUID PRIMARY KEY DEFAULT uuidv7(),
    extraction_run_id    UUID NOT NULL REFERENCES working.extraction_run(id) ON DELETE CASCADE,
    window_id            UUID NOT NULL REFERENCES working.extraction_window(id) ON DELETE CASCADE,

    -- Provenance. Anchored to the platform's own chat spine (ADR-0053 §2), not to a
    -- free-floating turn index. chunk_id is nullable because extraction may run over
    -- messages before or independently of chunking.
    chat_conversation_id UUID NOT NULL REFERENCES working.chat_conversation(id) ON DELETE RESTRICT,
    chat_message_id      UUID NOT NULL REFERENCES working.chat_message(id) ON DELETE RESTRICT,
    chat_chunk_id        UUID REFERENCES working.chat_chunk(id) ON DELETE RESTRICT,
    message_ordinal      BIGINT NOT NULL CHECK (message_ordinal >= 0),
    span_start           INT CHECK (span_start IS NULL OR span_start >= 0),
    span_end             INT CHECK (span_end IS NULL OR span_end >= span_start),

    -- WHO. speaker_role is denormalized from the message on purpose: it is decisive for
    -- claim_class and must not require a join to enforce.
    speaker_role         TEXT NOT NULL CHECK (speaker_role IN ('human','assistant','system','unknown')),
    claim_class          TEXT NOT NULL CHECK (claim_class IN (
                             'SELF_ACCOUNT',      -- subject's own statement of fact/recollection
                             'SELF_ALLEGATION',   -- subject's claim about another party
                             'REPORTED_SPEECH',   -- what someone else is said to have said
                             'DOCUMENT_QUOTE',    -- text quoted from an actual document
                             'AI_PROPOSAL',       -- originates in an assistant turn
                             'UNKNOWN')),

    -- WHAT. claim_type is table-driven, not a CHECK list: the vocabulary is expected to
    -- grow and must not require a migration to do so.
    claim_type_slug      TEXT NOT NULL REFERENCES reference.claim_type(slug) ON DELETE RESTRICT,
    title                TEXT NOT NULL CHECK (length(btrim(title)) > 0),
    body                 TEXT NOT NULL CHECK (length(btrim(body)) > 0),

    -- Verbatim is required. Paraphrase in this column is a defect.
    verbatim             TEXT NOT NULL CHECK (length(verbatim) BETWEEN 1 AND 300),
    hedged               BOOLEAN NOT NULL,
    hedge_terms          TEXT[] NOT NULL DEFAULT '{}',

    -- WHEN, unresolved by design. occurred_at/validity stay NULL on this table; a claim
    -- about a date is not an event. relative_time_anchor_id is the seam to the anchor
    -- system and stays NULL until an anchor is proposed and reviewed there.
    date_raw             TEXT,
    date_relative_to     TEXT,
    relative_time_anchor_id UUID REFERENCES context.relative_time_anchor(id) ON DELETE RESTRICT,

    participant_codes    TEXT[] NOT NULL DEFAULT '{}',

    -- Clustering inputs. fingerprint is a cheap blocking key only; it is not an identity
    -- and MUST NOT be made unique — identical fingerprints across mentions are expected
    -- and are the point.
    fingerprint          TEXT NOT NULL CHECK (length(btrim(fingerprint)) > 0),
    content_sha256       BYTEA NOT NULL CHECK (octet_length(content_sha256) = 32),

    extractor            TEXT NOT NULL,
    extractor_version    TEXT NOT NULL,
    model_id             TEXT,
    confidence           DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),

    review_state         TEXT NOT NULL DEFAULT 'pending'
                         CHECK (review_state IN ('pending','approved','rejected','needs_info','superseded')),
    reviewed_by          TEXT,
    reviewed_at          TIMESTAMPTZ,
    review_note          TEXT,

    attrs                JSONB NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(attrs) = 'object'),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- THE CONTAMINATION GUARD. Assistant text is an AI proposal, full stop; and an
    -- AI_PROPOSAL cannot be attributed to a human turn. Both directions enforced.
    CONSTRAINT claim_candidate_assistant_is_proposal
        CHECK ((speaker_role = 'assistant') = (claim_class = 'AI_PROPOSAL')),

    -- A hedge list without the flag, or a flag with no evidence in the verbatim, is a
    -- dropped qualifier. Cheap to assert, expensive to lose.
    CONSTRAINT claim_candidate_hedge_consistency
        CHECK (hedged OR cardinality(hedge_terms) = 0),

    CONSTRAINT claim_candidate_review_is_attributed
        CHECK (review_state IN ('pending') OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);

-- Deliberately NOT unique. Re-emission of the same span by the SAME run at the SAME
-- version is a bug; the same span emitted by a different run or version is a new
-- observation and must be kept.
CREATE UNIQUE INDEX claim_candidate_run_span_key
    ON working.claim_candidate (extraction_run_id, chat_message_id, content_sha256);

CREATE INDEX claim_candidate_fingerprint_idx ON working.claim_candidate (fingerprint);
CREATE INDEX claim_candidate_class_idx       ON working.claim_candidate (claim_class);
CREATE INDEX claim_candidate_conversation_idx ON working.claim_candidate (chat_conversation_id, message_ordinal);
```

**No promotion columns.** `working.candidate_fact` carries
`promoted_to_table / promoted_to_id / promoted_at`. This table has none, because a claim
extracted from an AI chat has nowhere to be promoted to. The phase boundary is structural.

**Append-only on content.** Content columns (`verbatim`, `body`, `title`, `claim_class`,
`hedged`, `date_raw`) take an UPDATE guard following the `sql/0017_append_only_guards.sql`
pattern. Review columns remain mutable. A correction is a new row with
`review_state='superseded'` on the old one — never an edit. This is Q6's never-rewritten
rule enforced rather than intended.

## 5 · `reference.claim_type`

```sql
CREATE TABLE reference.claim_type (
    slug        TEXT PRIMARY KEY
                CHECK (slug = lower(slug) AND slug ~ '^[a-z0-9]+(?:_[a-z0-9]+)*$'),
    label       TEXT NOT NULL CHECK (length(label) > 0),
    description TEXT NOT NULL,
    parent_slug TEXT REFERENCES reference.claim_type(slug),
    retired_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Seed set — expected to grow without migration:

`event` · `condition` · `statement` · `authority` · `strategy` · `decision` · `exposure` ·
`person_detail` · `open_question` · `artifact_reference` · `other`

`artifact_reference` is a claim that *names* a document existing in the world. It is a
pointer, and pointers are a next-phase concern — the type exists now so those claims are
findable later rather than re-extracted.

## 6 · `working.extraction_window`

Windowed extraction with overlap produces duplicates rather than gaps, which is the correct
failure direction. Coverage must be queryable, not a footnote.

```sql
CREATE TABLE working.extraction_window (
    id                   UUID PRIMARY KEY DEFAULT uuidv7(),
    extraction_run_id    UUID NOT NULL REFERENCES working.extraction_run(id) ON DELETE CASCADE,
    chat_conversation_id UUID NOT NULL REFERENCES working.chat_conversation(id) ON DELETE RESTRICT,
    ordinal_range        INT4RANGE NOT NULL,
    read_mode            TEXT NOT NULL
                         CHECK (read_mode IN ('full','targeted_retrieval','partial_truncated')),
    claims_emitted       INT NOT NULL DEFAULT 0 CHECK (claims_emitted >= 0),
    ordinals_no_claims   INT[] NOT NULL DEFAULT '{}',
    truncated            BOOLEAN NOT NULL DEFAULT false,
    note                 TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (extraction_run_id, chat_conversation_id, ordinal_range)
);
```

`read_mode` exists because of an observed real case: an existing Opus extraction covered
turns 0–26 in full and 27–76 by targeted retrieval only. That distinction determines whether
a conversation needs re-reading, and it is currently recoverable only from prose.

## 7 · `working.claim_assertion` — the AI/analysis layer

This has **no precedent anywhere in the schema**. `analysis.record_observation` is the
nearest neighbour and is built for classifier output (sentiment, tone, topic): it has an
`observer` and a review gate — both right instincts — but no way to express *which claims
this is about* or *what argument it serves*.

An assertion is: **N claims + an asserted relationship + a significance grade + who
asserted it + what it is for.**

```sql
CREATE TABLE working.claim_assertion (
    id                 UUID PRIMARY KEY DEFAULT uuidv7(),
    assertion_kind     TEXT NOT NULL CHECK (assertion_kind IN (
                           'connection',   -- two or more claims are one thing
                           'significance', -- this claim matters more than it looks
                           'decision',     -- a settled choice, not to be re-litigated
                           'exposure',     -- an adverse fact and how it is answered
                           'gap',          -- something asked and never answered
                           'correction')), -- an earlier assertion was wrong
    statement          TEXT NOT NULL CHECK (length(btrim(statement)) > 0),
    rationale          TEXT NOT NULL CHECK (length(btrim(rationale)) > 0),

    -- WHO asserted it. Never collapsible: an owner decision and a model's framing are
    -- different objects with different weight.
    asserted_by_kind   TEXT NOT NULL CHECK (asserted_by_kind IN ('owner','model')),
    asserted_by        TEXT NOT NULL CHECK (length(btrim(asserted_by)) > 0),
    asserted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    salience           TEXT CHECK (salience IN ('hot','good','warm')),
    argument_targets   TEXT[] NOT NULL DEFAULT '{}',

    -- The owner's verdict. 'parked' carries a reason; an assertion held back deliberately
    -- is different from one never looked at.
    owner_disposition  TEXT NOT NULL DEFAULT 'unreviewed'
                       CHECK (owner_disposition IN ('unreviewed','accepted','rejected','parked','superseded')),
    disposition_reason TEXT,
    disposition_at     TIMESTAMPTZ,

    source_ref         TEXT,   -- originating analysis document, if harvested from one
    supersedes_id      UUID REFERENCES working.claim_assertion(id) ON DELETE RESTRICT,
    attrs              JSONB NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(attrs) = 'object'),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT claim_assertion_parked_has_reason
        CHECK (owner_disposition <> 'parked' OR disposition_reason IS NOT NULL),
    CONSTRAINT claim_assertion_disposition_dated
        CHECK (owner_disposition = 'unreviewed' OR disposition_at IS NOT NULL)
);

CREATE TABLE working.claim_assertion_member (
    assertion_id       UUID NOT NULL REFERENCES working.claim_assertion(id) ON DELETE CASCADE,
    claim_candidate_id UUID NOT NULL REFERENCES working.claim_candidate(id) ON DELETE RESTRICT,
    member_role        TEXT NOT NULL DEFAULT 'constituent'
                       CHECK (member_role IN ('constituent','supports','contradicts','context')),
    member_ordinal     INT NOT NULL CHECK (member_ordinal >= 0),
    note               TEXT,
    PRIMARY KEY (assertion_id, claim_candidate_id),
    UNIQUE (assertion_id, member_ordinal)
);
```

### Two generations, and a hard depth cap

Owner ruling, 2026-08-29:

> "We're going to be extracting a lot of conversations that involve the same thing, and
> different versions of the analysis. As long as it's not an analysis of an analysis, but
> the synthesis of the same first-generation analysis just based on a different iteration,
> we can maybe get a complete idea of everything."

This is the distinction the schema has to carry, because both look identical from the
outside and only one of them is legitimate.

| | Generation 1 — **assertion** | Generation 2 — **synthesis** |
|---|---|---|
| Members | `claim_candidate` rows only | generation-1 assertions only |
| Minimum | 1 member | 2 members |
| Grounded in | what a person said | independent readings of the same material |
| Allowed to cite a synthesis | n/a | **never** |

`assertion_generation` is `1` or `2`. There is no `3`. A synthesis whose member is itself a
synthesis is the failure mode this cap exists to prevent — that is analysis of analysis, the
chain stops reaching anything a person actually said, and confidence inflates with every
hop while evidence stays constant.

The legitimate case is the opposite shape: several first-generation passes read the *same*
conversations at different times, with different prompts, or by different models. Each saw
part of it. The synthesis is the union of what all of them found, and it is worth more than
any single pass — that is the "complete idea of everything."

### Synthesis preserves variance; it does not resolve it

Same rule as claims. When two generation-1 assertions about the same material **disagree**,
the synthesis records the disagreement as a first-class fact. It does not pick a winner, and
it does not average them.

Divergence between independent readings is signal: it marks where the underlying material is
genuinely ambiguous, where a pass was under-informed, or where one iteration saw something
the others missed. Collapsing it silently is the same defect as deduplicating claims.

`agreement_state` on each synthesis member records `concurs` / `diverges` / `extends`, and a
synthesis carrying any `diverges` member must state the divergence in its own `statement`.
Adjudication is an owner act recorded as a *new* assertion, never an edit to the synthesis.

```sql
CREATE TABLE working.claim_assertion_synthesis_member (
    synthesis_id     UUID NOT NULL REFERENCES working.claim_assertion(id) ON DELETE CASCADE,
    member_assertion_id UUID NOT NULL REFERENCES working.claim_assertion(id) ON DELETE RESTRICT,
    agreement_state  TEXT NOT NULL
                     CHECK (agreement_state IN ('concurs','diverges','extends')),
    divergence_note  TEXT,
    member_ordinal   INT NOT NULL CHECK (member_ordinal >= 0),
    PRIMARY KEY (synthesis_id, member_assertion_id),
    UNIQUE (synthesis_id, member_ordinal),
    CHECK (synthesis_id <> member_assertion_id),
    CONSTRAINT synthesis_divergence_is_explained
        CHECK (agreement_state <> 'diverges' OR divergence_note IS NOT NULL)
);
```

Generation and member-kind agreement is enforced by trigger, because a CHECK cannot reach
across rows: a generation-1 row must have ≥1 `claim_assertion_member` and zero synthesis
members; a generation-2 row must have ≥2 synthesis members, zero claim members, and every
member must itself be generation 1.

`supersedes_id` is how any assertion is revised — never by editing `statement`.

## 8 · What this deliberately does not do

Deferred to the evidence phase, by owner instruction:

- Promotion of anything to anywhere. No promotion columns exist on any table above.
- Evidence pointers, evidence needs, acquisition targets.
- Corroboration links between a claim and an evidence item.
- Custody binding, hash-level citation, construction tags.
- Reconciliation of the three pre-existing candidate layers.
- The created-work / legal-document extractor that ADR-0052 Q6 mistakenly named
  `claim_candidate`.

`relative_time_anchor_id` and the `artifact_reference` claim type are the two seams left
open on purpose: both are nullable, both are inert now, and both let the next phase attach
without rewriting rows that by rule can never be rewritten.

## 9 · Open, for the next session

1. Migration number. `0049`–`0051` exist on disk uncommitted; this needs a clean number
   against a settled tree, not a guess against a dirty one.
2. Whether `working.extraction_run` (0016) is reused as-is or needs a chat-corpus variant.
3. Seed content for `reference.claim_type` beyond the eleven above.
4. `argument_targets` — free text now. Whether it becomes a controlled reference table
   determines whether coverage-by-argument is computable.
5. Whether the three existing Opus analysis documents get harvested into
   `claim_assertion` before or after the first extraction run.
