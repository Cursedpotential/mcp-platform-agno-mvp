"""CPU semantic challenger for post-chunk AI-chat lane classification.

This is deliberately a challenger, not an oracle. It compares bounded text
windows with several human-readable prototypes per lane using a small Sentence
Transformer. Semantic-only assignments remain pending review until owner
labels calibrate the model and thresholds. The optional dependency is loaded
lazily so the API and parser containers remain lightweight.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Protocol, Sequence

from server.contracts.records import ChatChunk, ChatLane, LaneClassification

DEFAULT_CPU_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_CPU_BACKEND = "onnx"

_PROTOTYPES: dict[ChatLane, tuple[str, ...]] = {
    ChatLane.platform: (
        "software architecture, databases, APIs, deployment, infrastructure, and code",
        "technical design decisions, implementation, debugging, testing, and developer operations",
        "AI agents, retrieval, embeddings, schemas, workflows, and platform configuration",
    ),
    ChatLane.legal: (
        "law, court procedure, legal research, motions, hearings, discovery, and litigation strategy",
        "child custody, parenting time, statutes, case law, subpoenas, and evidence rules",
        "drafting or reviewing legal documents and preparing arguments for court",
    ),
    ChatLane.personal_history: (
        "personal history, family relationships, marriage, childhood, and lived experiences",
        "relationship conflict, coercive control, abuse, fear, trauma, feelings, and therapy",
        "events involving family members, partners, children, and significant personal experiences",
    ),
    ChatLane.context: (
        "general conversation, planning, miscellaneous background, and uncategorized context",
        "material that is ambiguous or does not clearly belong to a specialized knowledge domain",
    ),
}


class SentenceEncoder(Protocol):
    """Small protocol implemented by SentenceTransformer and test doubles."""

    def encode(self, sentences: Sequence[str], **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class CpuSemanticPolicy:
    """Uncalibrated semantic thresholds; every result remains reviewable."""

    include_lane: float = 0.52
    relative_margin: float = 0.035
    max_lanes: int = 2
    max_window_chars: int = 1400
    batch_size: int = 16


def load_cpu_encoder(model_id: str | None = None, backend: str | None = None) -> SentenceEncoder:
    """Load the optional CPU encoder without importing it at module discovery."""

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError('CPU classification is unavailable; install the "classification" extra') from exc
    return SentenceTransformer(
        resolve_cpu_model_id(model_id),
        backend=backend or os.getenv("CPU_CLASSIFIER_BACKEND", DEFAULT_CPU_BACKEND),
        device="cpu",
    )


def resolve_cpu_model_id(model_id: str | None = None) -> str:
    """Resolve explicit configuration before environment and default values."""

    return model_id or os.getenv("CPU_CLASSIFIER_MODEL") or DEFAULT_CPU_MODEL


def _windows(text: str, max_chars: int) -> list[str]:
    """Bound encoder inputs so a 512-position model cannot silently truncate a chunk."""

    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    windows: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = [paragraph[index : index + max_chars] for index in range(0, len(paragraph), max_chars)] or [""]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip() if current else piece
            if current and len(candidate) > max_chars:
                windows.append(current)
                current = piece
            else:
                current = candidate
    if current:
        windows.append(current)
    return windows or [""]


def _as_vectors(values: Any) -> list[list[float]]:
    if hasattr(values, "tolist"):
        values = values.tolist()
    return [[float(component) for component in vector] for vector in values]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _assign_scores(
    scores: dict[ChatLane, float],
    *,
    model_id: str,
    policy: CpuSemanticPolicy,
) -> list[LaneClassification]:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_score = ordered[0][1]
    selected = [
        (lane, score)
        for lane, score in ordered
        if score >= policy.include_lane and top_score - score <= policy.relative_margin
    ][: policy.max_lanes]
    if not selected:
        return [
            LaneClassification(
                lane=ChatLane.context,
                confidence=1.0,
                review_status="pending_review",
                rationale=f"cpu-semantic-v1:{model_id}; every domain score below inclusion threshold",
            )
        ]

    results = [
        LaneClassification(
            lane=lane,
            confidence=round(max(0.0, min(1.0, score)), 4),
            review_status="pending_review",
            rationale=f"cpu-semantic-v1:{model_id}; uncalibrated challenger",
        )
        for lane, score in sorted(selected, key=lambda item: item[1], reverse=True)
    ]
    if all(result.lane is not ChatLane.context for result in results):
        results.append(
            LaneClassification(
                lane=ChatLane.context,
                confidence=1.0,
                review_status="pending_review",
                rationale="searchable fallback while CPU semantic assignment awaits review",
            )
        )
    return results


def classify_chunks_cpu(
    chunks: Sequence[ChatChunk],
    *,
    encoder: SentenceEncoder,
    model_id: str = DEFAULT_CPU_MODEL,
    policy: CpuSemanticPolicy | None = None,
) -> dict[str, list[LaneClassification]]:
    """Batch windows and encode lane prototypes once for the entire run."""

    policy = policy or CpuSemanticPolicy()
    lanes = tuple(_PROTOTYPES)
    prototypes = [prototype for lane in lanes for prototype in _PROTOTYPES[lane]]
    all_windows: list[str] = []
    spans: list[tuple[int, int]] = []
    for chunk in chunks:
        start = len(all_windows)
        all_windows.extend(_windows(chunk.content, policy.max_window_chars))
        spans.append((start, len(all_windows)))
    vectors = _as_vectors(
        encoder.encode(
            [*all_windows, *prototypes],
            normalize_embeddings=True,
            batch_size=policy.batch_size,
            show_progress_bar=False,
        )
    )
    prototype_vectors = vectors[len(all_windows) :]
    output: dict[str, list[LaneClassification]] = {}
    for chunk, (start, stop) in zip(chunks, spans, strict=True):
        window_vectors = vectors[start:stop]
        scores: dict[ChatLane, float] = {}
        offset = 0
        for lane in lanes:
            count = len(_PROTOTYPES[lane])
            lane_vectors = prototype_vectors[offset : offset + count]
            offset += count
            scores[lane] = max(_dot(window, prototype) for window in window_vectors for prototype in lane_vectors)
        output[chunk.content_hash] = _assign_scores(scores, model_id=model_id, policy=policy)
    return output


def classify_chunk_cpu(
    chunk: ChatChunk,
    *,
    encoder: SentenceEncoder,
    model_id: str = DEFAULT_CPU_MODEL,
    policy: CpuSemanticPolicy | None = None,
) -> list[LaneClassification]:
    """Single-chunk convenience wrapper around the batched implementation."""

    return classify_chunks_cpu([chunk], encoder=encoder, model_id=model_id, policy=policy)[chunk.content_hash]
