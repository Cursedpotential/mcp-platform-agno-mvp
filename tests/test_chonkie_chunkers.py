"""Tests for server/analysis/chonkie_chunkers.py (Chonkie → Agno ChunkingStrategy wrappers).

Byline: Claude Code · Opus 4.8 · 2026-08-10. Pins the D-046 contract:
CPU chunkers run torch-free in-process; heavy chunkers RAISE (never a silent local fallback).
"""

from __future__ import annotations

import pytest
from agno.knowledge.document.base import Document

# chonkie is a torch-free authoring dep not yet in the prod lockfile (D-046; the wrappers
# lazy-import it). Skip the whole module where chonkie isn't installed so CI stays green until
# requirements.txt is regenerated with chonkie[semantic,code,table].
pytest.importorskip("chonkie")

from server.analysis import chonkie_chunkers as cc

_TRANSCRIPT = (
    "[2024-01-12 10:00 AM] Matt: We should use SBV as the universal parser for everything.\n"
    "[2024-01-12 10:01 AM] Katrina: I disagree, the custody chain matters more here.\n"
    "[2024-01-12 10:02 AM] Matt: Both — custody tier is the only branch in the pipeline.\n"
) * 6


def _doc() -> Document:
    return Document(content=_TRANSCRIPT, name="conv-test", meta_data={"lane": "context", "source": "unit"})


def test_recursive_returns_agno_documents_with_provenance():
    out = cc.cpu_chunker("recursive", 128).chunk(_doc())
    assert len(out) > 1
    assert all(isinstance(d, Document) for d in out)
    d0 = out[0]
    assert d0.content
    assert d0.meta_data["chunker"] == "chonkie.recursive"
    assert d0.meta_data["chunk_index"] == 0
    assert d0.meta_data["source"] == "unit"  # parent meta preserved
    assert "chunk_tokens" in d0.meta_data


def test_empty_document_passthrough():
    empty = Document(content="   ", name="empty", meta_data={})
    assert cc.cpu_chunker("recursive").chunk(empty) == [empty]


def test_cpu_registry_names():
    assert set(cc.CPU_FRIENDLY) == {"recursive", "sentence", "token", "semantic", "code", "table"}


def test_transcript_hybrid_caps_runaway():
    # A runaway single "turn" with no sentence breaks -> semantic can't split -> cap must fire.
    runaway = Document(content="x" * 7000, name="runaway", meta_data={})
    out = cc.TranscriptSemanticHybridChunking(hard_cap_chars=2000).chunk(runaway)
    assert len(out) >= 4
    assert all(len(d.content) <= 2000 for d in out)
    assert any(d.meta_data.get("hard_capped") for d in out)


@pytest.mark.parametrize("name", ["neural", "late", "slumber"])
def test_remote_chunkers_raise_never_silent(name):
    with pytest.raises(NotImplementedError) as ei:
        cc.REMOTE[name]().chunk(_doc())
    assert "remote GPU executor" in str(ei.value)


def test_semantic_is_torch_free_and_chunks():
    # model2vec static embeddings — no torch. Model is cached from the install-verify step.
    out = cc.semantic(chunk_size=256).chunk(_doc())
    assert len(out) >= 1
    assert out[0].meta_data["chunker"] == "chonkie.semantic"
    import sys

    assert "torch" not in sys.modules, "semantic path must not import torch"
