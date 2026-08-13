"""Tests for server/analysis/chunking_policy.py — the KB↔chunking seam (D-046 / glittery-summit P6).

Byline: Claude Code · Opus 4.8 · 2026-08-11. Pins: baseline is Agno-native RecursiveChunking with
NO chonkie dependency; tuned transcript lanes use the Chonkie hybrid; unknown lanes fail loudly.
Byline: Codex · GPT-5 · 2026-08-13 (ADR-0053 five-lane alignment)
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


@pytest.mark.parametrize("lane", sorted(cp.LANES))
def test_baseline_is_recursive_for_every_lane(lane):
    # Baseline is Agno-native RecursiveChunking. (chonkie-independence is structural: the baseline
    # branch imports only agno; chonkie is imported lazily INSIDE the tuned transcript branch. A
    # sys.modules check can't prove it here because the shared pytest process imports chonkie in
    # test_chonkie_chunkers.py — see test_baseline_import_needs_no_chonkie for the real proof.)
    assert isinstance(cp.lane_chunker(lane), RecursiveChunking)


def test_baseline_import_needs_no_chonkie():
    # Prove chonkie-independence in a CLEAN subprocess: import the module + build a baseline
    # chunker with chonkie forced unavailable.
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import sys
        sys.modules['chonkie'] = None  # any import of chonkie now raises ImportError
        from server.analysis.chunking_policy import lane_chunker
        from agno.knowledge.chunking.recursive import RecursiveChunking
        assert isinstance(lane_chunker('platform'), RecursiveChunking)
        assert isinstance(lane_chunker('context'), RecursiveChunking)  # baseline even for transcript
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


@pytest.mark.parametrize("lane", ["platform", "legal", "personal_history", "evidence"])
def test_tuned_non_transcript_stays_recursive(lane):
    assert isinstance(cp.lane_chunker(lane, tuned=True), RecursiveChunking)


@pytest.mark.parametrize("lane", ["context"])
def test_tuned_transcript_lane_uses_chonkie_hybrid(lane):
    pytest.importorskip("chonkie")
    from server.analysis.chonkie_chunkers import TranscriptSemanticHybridChunking

    strat = cp.lane_chunker(lane, tuned=True)
    assert isinstance(strat, TranscriptSemanticHybridChunking)
    assert isinstance(strat, ChunkingStrategy)
