# Hash taxonomy — one page, reconciled against source

> _Byline: Claude · Opus 5 · 2026-08-29._
>
> Written because the count differs depending on which document you read: ADR-0034 says
> three levels, `sql/0048` defines five `hash_kind` values, and the owner has referred to
> four. This page reconciles what is actually on disk. It is a **reference reconciliation,
> not a ruling** — where a question remains open it is marked open rather than filled in.

## The two families are separate on purpose

D-088 / D-089: **context integrity fingerprints (R02) are DISTINCT from custody hashes
(R04).** This is intentional, not drift. A context fingerprint is never labeled H1/H2/H3.

| Family | When | Purpose |
|---|---|---|
| **Context fingerprints** | at intake, pre-parse | integrity of what landed; not custody |
| **Custody hashes** | at governed promotion | court-facing chain of custody |
| **Normalized digests** | after normalization | integrity of derived records |

Everything ingests as context and is fingerprinted. Custody begins only at promotion.
Conflating the families is the error this separation exists to prevent.

## Custody family — three levels (`vendored/sbv/CUSTODY.md`, authoritative)

Owner ruling, 2026-08-27, and the spec agrees:

| Level | Tag | Definition |
|---|---|---|
| **H1** | `h1-rawbytes-v1` | SHA-256 of the exact original source bytes |
| **H2** | `h2-rawelement-v1` | SHA-256 of the exact raw logical record/span bytes, **before** any decoding or normalization |
| **H3** | `h3-chain-sbv-genesisempty-v1` | order-sensitive left fold over ordered H2 digests |

Ordering contract: **H1 → H2 → H3 → only then normalize.** Every hash is over original bytes
before field decoding, base64 transcoding, phone normalization, or record mapping. That
ordering is what lets the hashes prove the source is unaltered.

H3 construction: `chain_0 = prevChain` (`""` for a fresh batch);
`chain_i = hex(SHA-256(chain_{i-1} + "\n" + H2_i))`. H1 never enters the fold.

### The tag question is closed

`h3-chain-v1` was ambiguous — the Case Bible vault writes a different, equally valid H3
(genesis = H1, `sha256(prev_hex + h2_hex)`) under the same name. **Resolved 2026-08-11:**
`custodyhash.CanonH3 = "h3-chain-sbv-genesisempty-v1"`, with
`custodyhash.CanonH3Legacy = "h3-chain-v1"` retained read-only. Computation unchanged; only
the label gained precision. Legacy rows are disambiguated by writer and never relabelled.

Any statement that this collision is still open is stale.

## Context fingerprint family — three kinds (`sql/0048`)

| `hash_kind` | `construction` |
|---|---|
| `context_source_fingerprint` | `context-source-fingerprint-v1` |
| `context_raw_record_fingerprint` | `context-rawrecord-fingerprint-v1` / `context-rawspan-fingerprint-v1` |
| `context_raw_generation_fingerprint` | `context-rawgen-fingerprint-chain-v1` |

Structurally parallel to H1/H2/H3 — source, record, generation-fold — deliberately **named
differently** so a fingerprint is never mistaken for custody.

## Normalized family — two kinds (`sql/0048`)

| `hash_kind` | `construction` |
|---|---|
| `normalized_record_digest` | `normalized-record-postgresql18-jsonb-text-utf8-sha256-v1` |
| `normalized_generation_manifest_digest` | `normalized-generation-ordered-digests-lengthframed-sha256-v1` |

Same record / generation-fold shape a third time.

## The recurring shape

Every family is the same three positions:

| | source | record | generation fold |
|---|---|---|---|
| Custody | H1 | H2 | H3 |
| Context | source fingerprint | raw record fingerprint | raw generation fingerprint |
| Normalized | — (derives from raw) | record digest | generation manifest digest |

`context.hash_receipt` carries **five** `hash_kind` values: the three context fingerprints
plus the two normalized digests. The three custody hashes live on the evidence side and are
not `hash_receipt` rows.

## ADR-0034 is stale, not wrong

ADR-0034 (2026-06-25) states "three SHA-256 levels." That is correct **for the custody
family**, which was the only family that existed when it was written. It predates both the
context-fingerprint split (D-088/D-089) and the normalized generation layer. It should be
read as scoped to custody, not as a whole-system count.

## Open

**Which four does "four hashes" name?** Not resolvable from source. The defensible readings:

- **A — four record-addressable digests:** H1 source, H2 raw record, normalized record
  digest, and the fold. Manifest digest is a rollup of the same position, not a level.
- **B — four families:** context fingerprint, custody, normalized record, normalized
  manifest.

Both fit the artifacts. One line in `CUSTODY.md` or `PROJECT_CANON.md` naming the four
closes this permanently, and it is the owner's to write — this page deliberately does not
guess.

## Not applicable to claims

`working.claim_candidate`, `claim_temporal_edge`, and `claim_assertion` (ADR-0062) carry
**no custody hash of any kind**. They are context extraction output from AI chats, which are
permanently context-only (D-082). `content_sha256` on those tables is a dedup key, not a
custody construction, and must never be described as one.
