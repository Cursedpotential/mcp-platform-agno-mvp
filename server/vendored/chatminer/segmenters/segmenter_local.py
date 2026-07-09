"""
Local Topic Segmenter — runs on your 2GB Quadro GPU
====================================================

Uses sentence-transformers (all-MiniLM-L6-v2, ~80MB) to create
embeddings, then cosine-similarity-based sliding window to detect
topic shifts.

Requirements:
    pip install sentence-transformers scikit-learn numpy

Memory: ~150MB RAM + 80MB model. Fits comfortably in 2GB VRAM.

Usage:
    from server.vendored.chatminer.segmenters import LocalSegmenter

    segmenter = LocalSegmenter()
    segments = segmenter.segment(messages)

    for seg in segments:
        print(f"{seg.topic_tag.value}: {seg.message_count} msgs, "
              f"confidence={seg.topic_confidence:.2f}")
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import numpy as np

from server.vendored.chatminer.core.types import ParsedMessage, TopicSegment, TopicTag

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Topic classification keywords (used for labeling after segmentation).
# GENERIC ONLY — no case-specific names/places here (owner decision 2026-06-13).
# Case-specific terms (real names, places, child name, etc.) are merged in at runtime
# from a gitignored config via _load_case_terms() — keeps PII out of the codebase.
_TOPIC_KEYWORDS = {
    TopicTag.RELATIONSHIP_HISTORY: [
        "relationship",
        "marriage",
        "married",
        "divorce",
        "separated",
        "custody",
        "child",
        "children",
        "daughter",
        "son",
        "kid",
        "baby",
        "family",
        "parenting",
        "visitation",
        "partner",
        "spouse",
        "ex",
        "boyfriend",
        "girlfriend",
        "anniversary",
        "moved",
        "apartment",
        "house",
        "trip",
        "visit",
        "argument",
        "fight",
        "apology",
        "promise",
        "incident",
        "timeline",
        "happened",
        "when",
    ],
    TopicTag.PERSONAL_LEGAL: [
        "court",
        "legal",
        "attorney",
        "lawyer",
        "motion",
        "filing",
        "affidavit",
        "deposition",
        "hearing",
        "trial",
        "settlement",
        "subpoena",
        "strategy",
        "case",
        "litigation",
        "plaintiff",
        "defendant",
        "judge",
        "testimony",
        "mcl",
        "factor",
        "petition",
        "order",
        "custody hearing",
        "foc",
    ],
    TopicTag.DEVELOPMENT: [
        "code",
        "parser",
        "server",
        "mcp",
        "api",
        "database",
        "schema",
        "docker",
        "typescript",
        "python",
        "javascript",
        "react",
        "agno",
        "agent",
        "tool",
        "function",
        "implement",
        "build",
        "deploy",
        "repository",
        "github",
        "commit",
        "merge",
        "refactor",
        "debug",
        "architecture",
        "component",
        "module",
        "pipeline",
        "ingestion",
        "embedding",
        "vector",
        "search",
        "index",
        "chunk",
        "segment",
        "test",
        "unit test",
        "integration",
        "coverage",
    ],
    TopicTag.EMOTIONAL: [
        "feel",
        "feeling",
        "emotion",
        "hurt",
        "pain",
        "trauma",
        "angry",
        "sad",
        "scared",
        "anxious",
        "depressed",
        "stressed",
        "overwhelmed",
        "exhausted",
        "tired",
        "burnout",
        "frustrated",
        "cry",
        "crying",
        "tears",
        "heart",
        "broken",
        "healing",
        "therapy",
        "therapist",
        "counseling",
        "support",
        "help",
        "lonely",
        "isolated",
        "betrayed",
        "confused",
        "lost",
    ],
    TopicTag.EVIDENCE: [
        "screenshot",
        "photo",
        "picture",
        "video",
        "recording",
        "voicemail",
        "text message",
        "email",
        "log",
        "document",
        "record",
        "metadata",
        "hash",
        "chain of custody",
        "exhibit",
        "proof",
        "timestamp",
    ],
}

_CASE_TERMS_LOADED = False


def _load_case_terms() -> None:
    """Merge case-specific terms (names/places/child name) into the keyword map at runtime.

    Source: YAML at $CHATMINER_CASE_TERMS, else ./server/evidence/config/case_terms.yaml.
    Keeps PII OUT of the codebase (owner decision 2026-06-13). Idempotent; safe if the
    file or pyyaml is absent (segmenter still works on generic keywords).
    Config shape:  relationship_history: ["<name>", "<place>"]\n  personal_legal: [...]
    """
    global _CASE_TERMS_LOADED
    if _CASE_TERMS_LOADED:
        return
    _CASE_TERMS_LOADED = True
    path = os.environ.get("CHATMINER_CASE_TERMS", "server/evidence/config/case_terms.yaml")
    try:
        import pathlib
        import yaml  # optional dep; skip silently if missing

        p = pathlib.Path(path)
        if not p.exists():
            return
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for tag_name, terms in data.items():
            try:
                tag = TopicTag(tag_name)
            except ValueError:
                logger.warning("case_terms: unknown TopicTag %r — skipped", tag_name)
                continue
            bucket = _TOPIC_KEYWORDS.setdefault(tag, [])
            for term in terms or []:
                t = str(term).strip().lower()
                if t and t not in bucket:
                    bucket.append(t)
        logger.info("case_terms: merged case-specific terms from %s", path)
    except Exception as e:  # never let config break segmentation
        logger.warning("case_terms: could not load %s (%s) — using generic keywords", path, e)


@dataclass
class SegmenterConfig:
    """Configuration for the local segmenter."""

    model_name: str = "all-MiniLM-L6-v2"  # 80MB, fits in 2GB
    window_size: int = 3  # Messages to compare
    similarity_threshold: float = 0.65  # Below this = topic shift
    min_segment_size: int = 2  # Minimum messages per segment
    max_segment_size: int = 50  # Maximum messages per segment
    device: str = "auto"  # "cuda", "cpu", or "auto"
    batch_size: int = 32  # Embedding batch size


class LocalSegmenter:
    """
    Topic segmenter using sentence-transformers on local GPU.

    Strategy:
        1. Embed each message using sentence-transformer
        2. Compute cosine similarity between consecutive windows
        3. Where similarity drops below threshold → topic boundary
        4. Classify each segment by keyword matching
        5. Return TopicSegment objects with confidence scores
    """

    def __init__(self, config: Optional[SegmenterConfig] = None):
        self.config = config or SegmenterConfig()
        self._model: Optional["SentenceTransformer"] = None
        _load_case_terms()  # merge case-specific terms (gitignored config) into the keyword map

    def _load_model(self) -> "SentenceTransformer":
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            device = self.config.device
            if device == "auto":
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading sentence-transformer model: {self.config.model_name} on {device}")
            self._model = SentenceTransformer(self.config.model_name, device=device)

        return self._model

    def segment(self, messages: list[ParsedMessage]) -> list[TopicSegment]:
        """
        Segment messages into topic-coherent chunks.

        Args:
            messages: List of ParsedMessage objects (chronological)

        Returns:
            List of TopicSegment objects
        """
        if len(messages) < self.config.min_segment_size:
            # Too few messages — return as single segment
            return [self._create_segment(messages, 0, len(messages))]

        # Step 1: Create embeddings
        embeddings = self._embed_messages(messages)

        # Step 2: Compute similarities between sliding windows
        similarities = self._compute_similarities(embeddings)

        # Step 3: Find topic boundaries
        boundaries = self._find_boundaries(similarities, len(messages))

        # Step 4: Create segments from boundaries
        segments: list[TopicSegment] = []
        start = 0
        for end in boundaries + [len(messages)]:
            if end - start >= self.config.min_segment_size:
                seg = self._create_segment(messages, start, end)
                segments.append(seg)
            start = end

        # Merge tiny segments if needed
        segments = self._merge_small_segments(segments)

        return segments

    def _embed_messages(self, messages: list[ParsedMessage]) -> np.ndarray:
        """Create embeddings for all messages."""
        model = self._load_model()
        texts = [m.content[:512] for m in messages]  # Truncate long messages
        embeddings = model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return embeddings

    def _compute_similarities(self, embeddings: np.ndarray) -> list[tuple[int, float]]:
        """
        Compute cosine similarity between consecutive sliding windows.

        For each position i, we compare the window [i-w+1, i] with
        [i+1, i+w] where w is the window size. Low similarity = topic shift.
        """
        from sklearn.metrics.pairwise import cosine_similarity

        n = len(embeddings)
        w = self.config.window_size
        similarities = []

        for i in range(w, n - w):
            left = embeddings[i - w : i].mean(axis=0).reshape(1, -1)
            right = embeddings[i : i + w].mean(axis=0).reshape(1, -1)
            sim = cosine_similarity(left, right)[0, 0]
            similarities.append((i, float(sim)))

        return similarities

    def _find_boundaries(self, similarities: list[tuple[int, float]], total: int) -> list[int]:
        """Find topic shift points where similarity drops below threshold."""
        boundaries = []
        threshold = self.config.similarity_threshold

        for idx, sim in similarities:
            if sim < threshold:
                boundaries.append(idx)

        # Merge boundaries that are too close
        merged: list[int] = []
        min_gap = self.config.min_segment_size
        for b in sorted(boundaries):
            if not merged or b - merged[-1] >= min_gap:
                merged.append(b)

        return merged

    def _create_segment(self, messages: list[ParsedMessage], start: int, end: int) -> TopicSegment:
        """Create a TopicSegment from a range of messages."""
        seg_messages = messages[start:end]

        # Combine all content for keyword classification
        combined_text = " ".join(m.content.lower() for m in seg_messages)

        # Classify by keyword matching
        topic_tag, confidence = self._classify_topic(combined_text)

        # Extract keywords
        keywords = self._extract_keywords(combined_text, topic_tag)

        # Get timestamps
        timestamps = [m.timestamp for m in seg_messages if m.timestamp]
        start_time = min(timestamps) if timestamps else None
        end_time = max(timestamps) if timestamps else None

        return TopicSegment(
            segment_id=str(uuid.uuid4()),
            messages=seg_messages,
            topic_tag=topic_tag,
            topic_confidence=confidence,
            start_time=start_time,
            end_time=end_time,
            keywords=keywords,
        )

    def _classify_topic(self, text: str) -> tuple[TopicTag, float]:
        """Classify topic by keyword matching."""
        scores: dict[TopicTag, float] = {}

        for topic, keywords in _TOPIC_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text)
            scores[topic] = matches / len(keywords) if keywords else 0

        if not scores:
            return TopicTag.UNKNOWN, 0.0

        best_topic = max(scores, key=lambda t: scores.get(t, 0.0))
        best_score = scores[best_topic]

        # Check if it's mixed (multiple topics have significant scores)
        significant = [t for t, s in scores.items() if s > 0.1 and t != best_topic]
        if len(significant) > 0 and best_score < 0.3:
            return TopicTag.MIXED, best_score

        # Normalize confidence
        confidence = min(best_score * 3, 1.0)  # Scale up

        if confidence < 0.15:
            return TopicTag.UNKNOWN, confidence

        return best_topic, confidence

    def _extract_keywords(self, text: str, topic: TopicTag) -> list[str]:
        """Extract matching keywords for the topic."""
        keywords = _TOPIC_KEYWORDS.get(topic, [])
        found = [kw for kw in keywords if kw in text]
        # Return top 5 most frequent
        from collections import Counter

        counts = Counter(found)
        return [kw for kw, _ in counts.most_common(5)]

    def _merge_small_segments(self, segments: list[TopicSegment]) -> list[TopicSegment]:
        """Merge segments that are too small with neighbors."""
        if not segments:
            return segments

        merged: list[TopicSegment] = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            if seg.message_count < self.config.min_segment_size and merged:
                # Merge with previous
                prev = merged[-1]
                prev.messages.extend(seg.messages)
                # Re-classify
                combined_text = " ".join(m.content.lower() for m in prev.messages)
                prev.topic_tag, prev.topic_confidence = self._classify_topic(combined_text)
                prev.keywords = self._extract_keywords(combined_text, prev.topic_tag)
            else:
                merged.append(seg)
            i += 1

        return merged
