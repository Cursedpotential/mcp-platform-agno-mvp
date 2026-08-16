"""server/analysis/chunking_policy.py — per-lane chunker selection (the KB↔chunking seam).

Byline: Claude Code · Opus 4.8 · 2026-08-10
Byline: Codex · GPT-5 · 2026-08-13 (ADR-0053 five-lane alignment)
Byline: Codex · GPT-5 · 2026-08-16 (D-046 Chonkie runtime activation)

WHY THIS EXISTS — lane alignment
--------------------------------
The five-lane KB structure (create_knowledge, lane→handle registry, evidence retrieval) is owned by
ADR-0053. CHUNKING is a separate concern
(Phase 6). This module is the clean seam between them: the KB code imports `lane_chunker(lane)` and
gets the right `ChunkingStrategy` for that lane — so chunking policy lives here, not scattered
inside `create_knowledge`, and neither lane edits the other's files.

D-046 RUNTIME DEFAULT: knowledge lanes use Chonkie RecursiveChunker and transcript lanes use the
semantic+fixed hybrid. Both are torch-free. The former Agno-native recursive policy remains an
explicit ``tuned=False`` rollback only; it is not the production default.

Lane→chunker rationale: context is the conversational corpus. Relationship material is a topic
within personal_history, not a separate destination; chat chunks are classified only after their
message-safe boundaries are formed.
"""

from __future__ import annotations

from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.chunking.strategy import ChunkingStrategy

#: Lanes whose source material is normally conversational (turn-structured).
TRANSCRIPT_LANES: frozenset[str] = frozenset({"context", "evidence"})

#: All five ADR-0053 lanes (kept here so a bad lane name fails loudly at the seam).
LANES: frozenset[str] = frozenset({"platform", "legal", "personal_history", "context", "evidence"})

# Baseline sizes (characters) — glittery-summit Phase 6 / agno-chunking-strategy.md §4.
_BASELINE_CHUNK_CHARS = 1500
_BASELINE_OVERLAP_CHARS = 150

# Transcript hybrid knobs (tokens / char-cap) — agno-chunking-strategy.md §4.
_TRANSCRIPT_SEMANTIC_TOKENS = 400
_TRANSCRIPT_HARD_CAP_CHARS = 2000


def lane_chunker(lane: str, *, tuned: bool = True, embedder=None) -> ChunkingStrategy:
    """Return the ChunkingStrategy for a lane.

    Args:
        lane: one of the five ADR-0053 lanes.
        tuned: True (default) activates Chonkie. False is the explicit Agno-native rollback.
        embedder: retained for call compatibility. Direct Chonkie semantic chunking deliberately
               uses its pinned model2vec model rather than an Agno framework object.

    Raises:
        ValueError: on an unknown lane (fail loudly at the seam, never silently mis-route).
    """
    if lane not in LANES:
        raise ValueError(f"unknown lane {lane!r}; expected one of {sorted(LANES)}")

    if not tuned:
        return RecursiveChunking(chunk_size=_BASELINE_CHUNK_CHARS, overlap=_BASELINE_OVERLAP_CHARS)

    if lane in TRANSCRIPT_LANES:
        # Import lazily: only the tuned transcript path needs chonkie installed.
        from server.analysis.chonkie_chunkers import TranscriptSemanticHybridChunking

        return TranscriptSemanticHybridChunking(
            semantic_chunk_tokens=_TRANSCRIPT_SEMANTIC_TOKENS,
            hard_cap_chars=_TRANSCRIPT_HARD_CAP_CHARS,
        )

    from server.analysis.chonkie_chunkers import cpu_chunker

    return cpu_chunker("recursive")
