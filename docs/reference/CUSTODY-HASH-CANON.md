# Custody-hash canon — durable backup of `public.canon_registry`

> _Byline: Claude Code · Opus 5 · 2026-08-24_
> _Byline: Claude Code · Fable 5.1 · 2026-09-05 — naming sweep D-137..D-141; see `docs/NAMING.md`._
>
> **Why this file exists (owner instruction, 2026-08-24):** until tonight these recipes lived in
> exactly ONE place — a table in the live database, created by no migration, read by no code,
> present in no doc. If that database were lost, the definition of how every custody hash was
> computed would be lost with it. This file is the verbatim capture. A numbered migration to make
> the table reproducible is the follow-up; this file is the record either way.
>
> Source: `public.canon_registry`, dumped live from `100.91.190.107:5432` db `ai`, 2026-08-24.
> All four rows `established_at 2026-07-03`. **If this file and the live table ever disagree, say
> so loudly and reconcile — do not silently trust either.**

## The four canons

### 1. `h1-rawbytes-v1` — file identity (ACTIVE)

- **Recipe:** `sha256(raw file bytes)`, streaming.
- **Role:** custody identity — dedupe key, blob path, the `evidence.evidence_hash` row.
- **Reference implementations:** `server/evidence/custody.py::_sha256_file`; case-bible plugin
  `tools/cb_custody_chain.py`.
- **Test vector:** pilot iMessage `+18108532989 index.html` (325,065 bytes) →
  `8173f2d3977e2dd7920e7fef4284b0ea6a292db00ff921f4dab638e056c69f71`

### 2. `h2-canonical-v2` — per-record hash (ACTIVE — the canon for ALL new ingests)

- **Recipe:**
  `sha256(utf8(file_hash_hex || '|' || sequence_number || '|' || role || '|' || occurred_at_utc_iso || '|' || content))`
  with `occurred_at_utc_iso` formatted `YYYY-MM-DD HH:MM:SS+00:00`.
- **Property:** fully recomputable from record content + H1.
- **Reference implementation:** case-bible plugin `tools/cb_custody_chain.py::h2_canonical_v2`.
- **Test vector:** file_hash `8173f2d3…c69f71`, seq `0`, role `them`,
  occurred `2019-01-01 00:00:00+00:00`, content `hello` →
  `b6b3b4a557d4d02c60168a00d8edc233b68f3a1c14b514b545faddef2904ff46`

### 3. `h3-chain-v1` — the chain (ACTIVE)

- **Recipe:** `entry_hash = sha256(utf8(previous_hash_hex || h2_hash_hex))`;
  **genesis `previous_hash` = the H1 file hash**; the final entry is the chain head, sealed in
  `evidence_hash.meta.chain_head`.
- **Reference implementation:** case-bible plugin `tools/cb_custody_chain.py::h3_entry`.
- **Proof:** 2026-07-02, reverse-engineered against pilot data — **1,918/1,918 links recomputed,
  head matches the sealed value.**
- **Test vectors** (both from previous_hash `8173f2d3…c69f71`):
  - h2 `bcd2b404…b167cb` → `bc6538b346c192af04f5cdf2f0f42b766f2a95070307fc2aa0f495462ad34016`
  - h2 `b6b3b4a5…04ff46` → `676bd4e40eb3556d052ac03782854e5018819aecca855a9664e60eceb9351ca9`
- **⚠ Naming caution:** the SBV/~~universal-import~~ **proffer** (renamed D-140, 2026-09-05) lane uses a DIFFERENT construction with
  genesis `""` under the tag `h3-chain-sbv-genesisempty-v1` (`server/evidence/custody.py:374-384`).
  Two valid constructions once collided under the bare tag `h3-chain-v1`; rows are never
  relabelled — always name the exact construction.

### 4. `h2-filebound-v1` — **LOST** (the loss that motivated the registry)

- **Recipe: UNKNOWN.** Pilot doc says "sha256 of the canonical message including the file hash";
  the exact serialization is irrecoverable — **~1.5M candidate serializations exhausted
  2026-07-02.**
- **How it was lost:** the code ran from an agent scratchpad (`bestoffort-v2-2026-06-26`) and
  died with the session. No reference implementation survives.
- **Status of pilot H2s:** still tamper-evident via `h3-chain-v1` + the sealed head — but they
  **cannot be recomputed.**
- **Test vectors kept for any future reconstruction attempt:**
  - seq 0, role `them`, content `Oh haaaay.`, occurred `2019-02-21 22:03:00+00:00`
    (original `2019-02-21 05:03 PM`), file_hash `8173f2d3…c69f71` →
    `bcd2b404aa3838e9eb1024a6708e56e6cd8185b271e1e8b29acba42472b167cb`
  - seq 4, role `them`, content `756 yes`, occurred `2019-02-21 22:26:00+00:00` →
    `c4e570c4d23442a2edff311a590015b70d73b97db975cfd48d9ab174792a0874`

## The lesson this table encodes

**This loss was carelessness, not bad luck** (owner ruling, 2026-08-24). The standing discipline
— everything persists, always; work gets a durable home the same session it is created; a second
copy is baseline practice, not extra credit — applies to CODE exactly as it applies to data.
`h2-filebound-v1` computed production custody hashes from code that had no durable home and no
second copy anywhere. When the session died, the recipe died, permanently: prose descriptions
("sha256 of the canonical message") underdetermine bytes, and ~1.5M serialization guesses could
not rediscover one delimiter choice. Any single one of the three persistence forms would have
saved it.

That is why every canon here carries its recipe, its reference implementation path, AND test
vectors; why this file exists in git; and why `tests/test_custody_canon_vectors.py` rebuilds
every active recipe from this document's prose alone on every test run. **Any new hash
construction gets a row in `canon_registry`, an entry here, and a vector test, before its first
production use — the scratchpad path to production is closed.**
