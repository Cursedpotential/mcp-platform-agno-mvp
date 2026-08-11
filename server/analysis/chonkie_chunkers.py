"""server/analysis/chonkie_chunkers.py — Chonkie chunkers wrapped as Agno ChunkingStrategy.

Byline: Claude Code · Opus 4.8 · 2026-08-10

WHY THIS EXISTS
---------------
Agno surfaces only two Chonkie chunkers (SemanticChunking → Chonkie SemanticChunker,
CodeChunking → Chonkie CodeChunker). The platform wants Chonkie's fuller specialty set built
directly into the Agno pipeline (owner directive 2026-08-10; DECISION_LOG D-046,
docs/planning/agno-chunking-strategy.md §8). This module wraps Chonkie chunkers as custom
`agno.knowledge.chunking.strategy.ChunkingStrategy` subclasses so they slot into any Agno reader
exactly like the native ones.

EXECUTION SPLIT (the load-bearing decision, D-046)
--------------------------------------------------
CPU-FRIENDLY (torch-free, run in-process here):
  Semantic (model2vec), Recursive, Sentence, Token, Fast, Code, Table.
REMOTE (heavy — routed to a GPU executor over MCP; NOT run locally on the CPU-only box):
  Neural (torch/BERT), Late (long-context embedder), Slumber (LLM).
The remote chunkers are represented here as explicit stubs that raise until the remote MCP
executor exists — they must never silently fall back to a local torch install.

Verified against: agno 2.8.6, chonkie 1.7.0 (torch-free install: chonkie[semantic,code,table]).
Chonkie 1.7.0 exports no standalone SDPMChunker — semantic double-pass lives inside SemanticChunker.
"""

from __future__ import annotations

from typing import Any, Callable

from agno.knowledge.chunking.strategy import ChunkingStrategy
from agno.knowledge.document.base import Document

# ---------------------------------------------------------------------------
# Adapter: turn any Chonkie chunker instance into an Agno ChunkingStrategy
# ---------------------------------------------------------------------------


class ChonkieChunkingStrategy(ChunkingStrategy):
    """Adapts a Chonkie chunker to Agno's ChunkingStrategy contract.

    A Chonkie chunker exposes ``.chunk(text) -> list[Chunk]`` where each Chunk has
    ``.text``, ``.start_index``, ``.end_index``, ``.token_count``. We map each Chunk to an
    Agno ``Document``, preserving the parent document's ``meta_data`` and adding chunk-level
    provenance so downstream stages (multipass classify → lane routing, ADR-0051 Stage 2) and
    retrieval can reason about chunk boundaries.

    The Chonkie chunker is built lazily via ``factory`` so importing this module never triggers a
    model download or a heavy backend load; construction happens on first ``chunk()`` call.
    """

    def __init__(self, factory: Callable[[], Any], *, label: str) -> None:
        self._factory = factory
        self._chunker: Any | None = None
        self.label = label

    def _get(self) -> Any:
        if self._chunker is None:
            self._chunker = self._factory()
        return self._chunker

    def chunk(self, document: Document) -> list[Document]:
        text = document.content or ""
        if not text.strip():
            return [document]
        chunks = self._get().chunk(text)
        out: list[Document] = []
        base_meta = dict(document.meta_data or {})
        base_name = document.name or "doc"
        for i, ck in enumerate(chunks):
            meta = {
                **base_meta,
                "chunker": self.label,
                "chunk_index": i,
                "chunk_start": getattr(ck, "start_index", None),
                "chunk_end": getattr(ck, "end_index", None),
                "chunk_tokens": getattr(ck, "token_count", None),
            }
            out.append(
                Document(
                    content=ck.text,
                    name=f"{base_name}-{i:04d}",
                    meta_data=meta,
                    embedder=document.embedder,
                )
            )
        return out


# ---------------------------------------------------------------------------
# CPU-friendly factories (torch-free) — transcript-sane defaults
# ---------------------------------------------------------------------------
# chunk_size units differ by chunker (Chonkie: tokens for most; Table: rows/chars).
# Defaults are starting points to tune per docs/planning/agno-chunking-strategy.md §4.


def recursive(chunk_size: int = 512, **kw: Any) -> ChonkieChunkingStrategy:
    def _f() -> Any:
        from chonkie import RecursiveChunker

        return RecursiveChunker(chunk_size=chunk_size, **kw)

    return ChonkieChunkingStrategy(_f, label="chonkie.recursive")


def sentence(chunk_size: int = 512, **kw: Any) -> ChonkieChunkingStrategy:
    def _f() -> Any:
        from chonkie import SentenceChunker

        return SentenceChunker(chunk_size=chunk_size, **kw)

    return ChonkieChunkingStrategy(_f, label="chonkie.sentence")


def token(chunk_size: int = 512, **kw: Any) -> ChonkieChunkingStrategy:
    def _f() -> Any:
        from chonkie import TokenChunker

        return TokenChunker(chunk_size=chunk_size, **kw)

    return ChonkieChunkingStrategy(_f, label="chonkie.token")


def semantic(chunk_size: int = 512, **kw: Any) -> ChonkieChunkingStrategy:
    """SemanticChunker on model2vec (static, torch-free). Downloads a small potion model once."""

    def _f() -> Any:
        from chonkie import SemanticChunker

        return SemanticChunker(chunk_size=chunk_size, **kw)

    return ChonkieChunkingStrategy(_f, label="chonkie.semantic")


def code(chunk_size: int = 1500, **kw: Any) -> ChonkieChunkingStrategy:
    def _f() -> Any:
        from chonkie import CodeChunker

        return CodeChunker(chunk_size=chunk_size, **kw)

    return ChonkieChunkingStrategy(_f, label="chonkie.code")


def table(**kw: Any) -> ChonkieChunkingStrategy:
    def _f() -> Any:
        from chonkie import TableChunker

        return TableChunker(**kw)

    return ChonkieChunkingStrategy(_f, label="chonkie.table")


#: CPU-friendly chunkers, addressable by short name (for a registry / config).
CPU_FRIENDLY: dict[str, Callable[..., ChonkieChunkingStrategy]] = {
    "recursive": recursive,
    "sentence": sentence,
    "token": token,
    "semantic": semantic,
    "code": code,
    "table": table,
}


# ---------------------------------------------------------------------------
# Transcript hybrid — semantic primary + fixed char hard-cap guardrail
# ---------------------------------------------------------------------------


class TranscriptSemanticHybridChunking(ChunkingStrategy):
    """Transcript-tuned hybrid (docs/planning/agno-chunking-strategy.md §3/§6):
      1) Chonkie SemanticChunker (model2vec, torch-free) groups meaning-coherent turns.
      2) A deterministic CHARACTER hard-cap re-splits any runaway chunk (a long monologue where
         similarity never drops) so an untuned threshold can't emit an oversized chunk.

    The cap is the seatbelt, not a substitute for tuning similarity — see §6.
    """

    def __init__(self, semantic_chunk_tokens: int = 400, hard_cap_chars: int = 2000, **semantic_kw: Any) -> None:
        self._semantic = semantic(chunk_size=semantic_chunk_tokens, **semantic_kw)
        self.hard_cap_chars = hard_cap_chars

    def _cap(self, doc: Document) -> list[Document]:
        text = doc.content or ""
        if len(text) <= self.hard_cap_chars:
            return [doc]
        pieces: list[Document] = []
        for j in range(0, len(text), self.hard_cap_chars):
            seg = text[j : j + self.hard_cap_chars]
            pieces.append(
                Document(
                    content=seg,
                    name=f"{doc.name}-cap{j // self.hard_cap_chars:02d}",
                    meta_data={**(doc.meta_data or {}), "hard_capped": True},
                    embedder=doc.embedder,
                )
            )
        return pieces

    def chunk(self, document: Document) -> list[Document]:
        out: list[Document] = []
        for sem_doc in self._semantic.chunk(document):
            out.extend(self._cap(sem_doc))
        return out


# ---------------------------------------------------------------------------
# REMOTE (heavy) chunkers — explicit stubs, never a local torch fallback (D-046)
# ---------------------------------------------------------------------------

_REMOTE_MSG = (
    "{name} is a HEAVY chunker (needs {backend}) and must run on the remote GPU executor over MCP, "
    "not on this CPU-only box (DECISION_LOG D-046). The remote executor is not wired yet — "
    "see docs/planning/agno-chunking-strategy.md §8.3 step 3."
)


class _RemoteChunkerStub(ChunkingStrategy):
    def __init__(self, name: str, backend: str) -> None:
        self.name = name
        self.backend = backend

    def chunk(self, document: Document) -> list[Document]:
        raise NotImplementedError(_REMOTE_MSG.format(name=self.name, backend=self.backend))


def neural() -> _RemoteChunkerStub:
    return _RemoteChunkerStub("NeuralChunker", "torch/transformers")


def late() -> _RemoteChunkerStub:
    return _RemoteChunkerStub("LateChunker", "a long-context embedder")


def slumber() -> _RemoteChunkerStub:
    return _RemoteChunkerStub("SlumberChunker", "an LLM")


#: Heavy chunkers, addressable by short name (all raise until the remote MCP executor lands).
REMOTE: dict[str, Callable[[], _RemoteChunkerStub]] = {
    "neural": neural,
    "late": late,
    "slumber": slumber,
}
