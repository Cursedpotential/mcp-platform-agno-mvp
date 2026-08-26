"""Executable proof of the custody-hash canon — the anti-h2-filebound-v1 test.

Byline: Claude Code · Opus 5 · 2026-08-24

Why this file exists: `h2-filebound-v1` was a hash recipe that lived only in
running code in an agent scratchpad. The session died; the recipe died; ~1.5M
candidate serializations later it is PERMANENTLY unrecoverable (see
`docs/reference/CUSTODY-HASH-CANON.md`, entry 4). Prose descriptions
underdetermine bytes. Only an executable recipe with pinned vectors survives.

So every ACTIVE canon here is implemented *from its documented recipe text
alone* — deliberately independent of `server/` and the Go package — and
asserted against the registry's test vectors. Three consequences:

  1. If the doc's recipe wording drifts from what these functions do, a human
     reading both will catch the mismatch (the functions mirror the doc line
     by line).
  2. If anyone edits a vector or a recipe, this suite goes red.
  3. The recipe can never again exist in only one place: it is in the live
     `public.canon_registry`, in `docs/reference/CUSTODY-HASH-CANON.md`, and
     executable here — and CI re-derives it on every run.

Rule enforced by convention: any NEW hash construction gets a canon row, a doc
entry, and a vector test HERE before its first production use.
"""

from __future__ import annotations

import hashlib

# ---------------------------------------------------------------------------
# Recipes, implemented verbatim from docs/reference/CUSTODY-HASH-CANON.md
# ---------------------------------------------------------------------------


def h1_rawbytes_v1(raw: bytes) -> str:
    """h1-rawbytes-v1: sha256(raw file bytes)."""
    return hashlib.sha256(raw).hexdigest()


def h2_canonical_v2(
    file_hash_hex: str,
    sequence_number: int,
    role: str,
    occurred_at_utc_iso: str,
    content: str,
) -> str:
    """h2-canonical-v2: sha256(utf8(file_hash|seq|role|occurred_at_utc_iso|content)).

    occurred_at_utc_iso format: YYYY-MM-DD HH:MM:SS+00:00
    """
    canonical = f"{file_hash_hex}|{sequence_number}|{role}|{occurred_at_utc_iso}|{content}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def h3_entry_v1(previous_hash_hex: str, h2_hash_hex: str) -> str:
    """h3-chain-v1: entry = sha256(utf8(previous_hash_hex || h2_hash_hex)).

    Genesis previous_hash = the H1 file hash. (The SBV lane's separate
    construction, h3-chain-sbv-genesisempty-v1, uses genesis "" and an
    LF fold — covered by the Go package's own tests, not conflated here.)
    """
    return hashlib.sha256((previous_hash_hex + h2_hash_hex).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# The pilot anchor vector shared by every canon below
# ---------------------------------------------------------------------------

PILOT_H1 = "8173f2d3977e2dd7920e7fef4284b0ea6a292db00ff921f4dab638e056c69f71"


def test_h2_canonical_v2_reproduces_registry_vector():
    got = h2_canonical_v2(
        file_hash_hex=PILOT_H1,
        sequence_number=0,
        role="them",
        occurred_at_utc_iso="2019-01-01 00:00:00+00:00",
        content="hello",
    )
    assert got == "b6b3b4a557d4d02c60168a00d8edc233b68f3a1c14b514b545faddef2904ff46", (
        "h2-canonical-v2 no longer reproduces its canon vector — the recipe, "
        "this implementation, or the vector has drifted. Reconcile against "
        "docs/reference/CUSTODY-HASH-CANON.md before ANY new ingest."
    )


def test_h3_chain_v1_reproduces_both_registry_vectors():
    # vector 1: the (lost) h2-filebound-v1 pilot hash folded onto the H1 genesis
    assert (
        h3_entry_v1(PILOT_H1, "bcd2b404aa3838e9eb1024a6708e56e6cd8185b271e1e8b29acba42472b167cb")
        == "bc6538b346c192af04f5cdf2f0f42b766f2a95070307fc2aa0f495462ad34016"
    )
    # vector 2: the h2-canonical-v2 vector folded onto the same genesis
    assert (
        h3_entry_v1(PILOT_H1, "b6b3b4a557d4d02c60168a00d8edc233b68f3a1c14b514b545faddef2904ff46")
        == "676bd4e40eb3556d052ac03782854e5018819aecca855a9664e60eceb9351ca9"
    )


def test_h3_chain_composes_end_to_end_from_h2():
    """The full pipeline property: content -> H2 -> chained onto H1 genesis."""
    h2 = h2_canonical_v2(PILOT_H1, 0, "them", "2019-01-01 00:00:00+00:00", "hello")
    head = h3_entry_v1(PILOT_H1, h2)
    assert head == "676bd4e40eb3556d052ac03782854e5018819aecca855a9664e60eceb9351ca9"


def test_h1_is_plain_sha256():
    assert h1_rawbytes_v1(b"") == hashlib.sha256(b"").hexdigest()
    assert h1_rawbytes_v1(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_lost_h2_filebound_v1_vectors_are_preserved_not_reproducible():
    """h2-filebound-v1 is LOST — its recipe is unknown. What we CAN assert
    forever: its surviving vectors still chain correctly under h3-chain-v1,
    which is exactly the tamper-evidence the canon doc promises. And the
    obvious v2-style recipe provably does NOT reproduce it (guarding anyone
    from 'reconstructing' it wrongly)."""
    lost_vector = "bcd2b404aa3838e9eb1024a6708e56e6cd8185b271e1e8b29acba42472b167cb"
    # still chains:
    assert h3_entry_v1(PILOT_H1, lost_vector) == ("bc6538b346c192af04f5cdf2f0f42b766f2a95070307fc2aa0f495462ad34016")
    # and is NOT what h2-canonical-v2 yields for the same record:
    naive = h2_canonical_v2(PILOT_H1, 0, "them", "2019-02-21 22:03:00+00:00", "Oh haaaay.")
    assert naive != lost_vector, (
        "If this ever PASSES as equal, the lost recipe has been found — "
        "celebrate, then update the canon registry and doc immediately."
    )
