"""Tests for server/analysis/chunking_policy.py — the KB↔chunking seam (D-046 / glittery-summit P6).

Byline: Claude Code · Opus 4.8 · 2026-08-11. Pins the original baseline and lane contract.
Byline: Codex · GPT-5 · 2026-08-13 (ADR-0053 five-lane alignment)
Byline: Codex · GPT-5 · 2026-08-16 (Chonkie is now the runtime default; Agno baseline is rollback)
"""

from __future__ import annotations

import pytest
from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.chunking.strategy import ChunkingStrategy

from server.analysis import chunking_policy as cp


def test_lanes_are_the_five_adr0053_lanes():
    assert cp.LANES == {
        "platform",
        "legal",
        "personal_history",
        "context",
        "evidence",
    }
    assert cp.TRANSCRIPT_LANES <= cp.LANES


@pytest.mark.parametrize("lane", sorted(cp.LANES - cp.TRANSCRIPT_LANES))
def test_knowledge_default_is_chonkie_recursive(lane):
    from server.analysis.chonkie_chunkers import ChonkieChunkingStrategy

    chunker = cp.lane_chunker(lane)
    assert isinstance(chunker, ChonkieChunkingStrategy)
    assert chunker.label == "chonkie.recursive@1.7.0:1500-chars"


def test_explicit_rollback_import_needs_no_chonkie():
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import sys
        sys.modules['chonkie'] = None  # any import of chonkie now raises ImportError
        from server.analysis.chunking_policy import lane_chunker
        from agno.knowledge.chunking.recursive import RecursiveChunking
        assert isinstance(lane_chunker('platform', tuned=False), RecursiveChunking)
        assert isinstance(lane_chunker('context', tuned=False), RecursiveChunking)
        print('OK')
        """
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_unknown_lane_raises():
    with pytest.raises(ValueError) as ei:
        cp.lane_chunker("timeline_relationship")  # old vocab -> must fail loudly
    assert "unknown lane" in str(ei.value)


@pytest.mark.parametrize("lane", sorted(cp.LANES))
def test_explicit_rollback_uses_agno_recursive(lane):
    assert isinstance(cp.lane_chunker(lane, tuned=False), RecursiveChunking)


@pytest.mark.parametrize("lane", sorted(cp.TRANSCRIPT_LANES))
def test_transcript_default_uses_chonkie_hybrid(lane):
    pytest.importorskip("chonkie")
    from server.analysis.chonkie_chunkers import TranscriptSemanticHybridChunking

    strat = cp.lane_chunker(lane)
    assert isinstance(strat, TranscriptSemanticHybridChunking)
    assert isinstance(strat, ChunkingStrategy)
