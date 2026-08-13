"""server/analysis/chunking_policy.py — per-lane chunker selection (the KB↔chunking seam).

Byline: Claude Code · Opus 4.8 · 2026-08-10
Byline: Codex · GPT-5 · 2026-08-13 (ADR-0053 five-lane alignment)

WHY THIS EXISTS — lane alignment
--------------------------------
The five-lane KB structure (create_knowledge, lane→handle registry, evidence retrieval) is owned by
ADR-0053. CHUNKING is a separate concern
(Phase 6). This module is the clean seam between them: the KB code imports `lane_chunker(lane)` and
gets the right `ChunkingStrategy` for that lane — so chunking policy lives here, not scattered
inside `create_knowledge`, and neither lane edits the other's files.

PLAN-FAITHFUL DEFAULT (glittery-summit Phase 6): the BASELINE is Agno-native `RecursiveChunking`
on every reader — deterministic, zero embed cost, and **no chonkie dependency** (so the KB lane can
adopt this today without touching requirements.txt). The semantic+fixed turn-aware hybrid (Chonkie,
`chonkie_chunkers.TranscriptSemanticHybridChunking`) is a GATED opt-in for the transcript lanes,
enabled by `tuned=True` once chonkie is in the lockfile and the A/B in evals/ justifies it
(docs/planning/agno-chunking-strategy.md §6).

Lane→chunker rationale: context is the conversational corpus. Relationship material is a topic
within personal_history, not a separate destination; chat chunks are classified only after their
message-safe boundaries are formed.
"""

from __future__ import annotations

from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.chunking.strategy import ChunkingStrategy

#: The lane whose source material is normally conversational (turn-structured).
TRANSCRIPT_LANES: frozenset[str] = frozenset({"context"})

#: All five ADR-0053 lanes (kept here so a bad lane name fails loudly at the seam).
LANES: frozenset[str] = frozenset({"platform", "legal", "personal_history", "context", "evidence"})

# Baseline sizes (characters) — glittery-summit Phase 6 / agno-chunking-strategy.md §4.
_BASELINE_CHUNK_CHARS = 1500
_BASELINE_OVERLAP_CHARS = 150

# Transcript hybrid knobs (tokens / char-cap) — agno-chunking-strategy.md §4.
_TRANSCRIPT_SEMANTIC_TOKENS = 400
_TRANSCRIPT_HARD_CAP_CHARS = 2000


def lane_chunker(lane: str, *, tuned: bool = False, embedder=None) -> ChunkingStrategy:
    """Return the ChunkingStrategy for a lane.

    Args:
        lane: one of the five ADR-0053 lanes.
        tuned: False (default) -> Agno-native RecursiveChunking baseline (no chonkie dep).
               True -> transcript lanes get the Chonkie semantic+fixed hybrid; non-transcript
               lanes still get the recursive baseline (semantic tuning for those is future work).
        embedder: passed to the semantic chunker when tuned (should be the lane's storage embedder,
               so boundaries live in the storage vector space — agno-chunking-strategy.md §5).

    Raises:
        ValueError: on an unknown lane (fail loudly at the seam, never silently mis-route).
    """
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {sorted(LANES)}")

    if tuned and lane in TRANSCRIPT_LANES:
        # Import lazily: only the tuned transcript path needs chonkie installed.
        from server.analysis.chonkie_chunkers import TranscriptSemanticHybridChunking

        kw = {"embedder": embedder} if embedder is not None else {}
        return TranscriptSemanticHybridChunking(
            semantic_chunk_tokens=_TRANSCRIPT_SEMANTIC_TOKENS,
            hard_cap_chars=_TRANSCRIPT_HARD_CAP_CHARS,
            **kw,
        )

    return RecursiveChunking(chunk_size=_BASELINE_CHUNK_CHARS, overlap=_BASELINE_OVERLAP_CHARS)
