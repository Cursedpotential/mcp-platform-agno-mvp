"""Post-chunk, multi-label classification for AI-chat knowledge routing.

Classification never emits ``evidence``: discussion about evidence is still an
AI-chat lead. Low-confidence and failed classifications remain searchable in
``context`` and enter selective human review.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from server.contracts.records import ChatChunk, ChatLane, LaneClassification

ROUTABLE_CHAT_LANES = (
    ChatLane.platform,
    ChatLane.legal,
    ChatLane.personal_history,
    ChatLane.context,
)

_KEYWORDS: dict[ChatLane, tuple[str, ...]] = {
    ChatLane.platform: (
        "api",
        "architecture",
        "branch",
        "chunk",
        "code",
        "commit",
        "database",
        "deploy",
        "docker",
        "embedding",
        "fastapi",
        "git",
        "migration",
        "model",
        "postgres",
        "python",
        "schema",
        "server",
        "sql",
        "vector",
        "weaviate",
    ),
    ChatLane.legal: (
        "affidavit",
        "appeal",
        "case law",
        "court",
        "custody",
        "discovery",
        "evidence rule",
        "filing",
        "friend of the court",
        "hearing",
        "judge",
        "mcl 722",
        "motion",
        "parenting time",
        "statute",
        "subpoena",
        "trial",
    ),
    ChatLane.personal_history: (
        "abuse",
        "afraid",
        "alcohol",
        "betrayal",
        "childhood",
        "coercive",
        "daughter",
        "family",
        "felt",
        "gaslight",
        "marriage",
        "mother",
        "narciss",
        "relationship",
        "son",
        "spouse",
        "therapy",
        "trauma",
    ),
}

_PATTERNS = {
    lane: tuple(re.compile(re.escape(keyword), re.IGNORECASE) for keyword in keywords)
    for lane, keywords in _KEYWORDS.items()
}


@dataclass(frozen=True)
class ClassificationPolicy:
    """Provisional thresholds, to be calibrated from owner corrections."""

    auto_accept: float = 0.78
    include_lane: float = 0.42
    ambiguity_margin: float = 0.12


def _lane_scores(text: str) -> dict[ChatLane, float]:
    counts = {lane: sum(len(pattern.findall(text)) for pattern in patterns) for lane, patterns in _PATTERNS.items()}
    total = sum(counts.values())
    if total == 0:
        return {ChatLane.context: 1.0}

    peak = max(counts.values())
    # A small density boost distinguishes a clear repeated topic from a single
    # incidental keyword without pretending keyword counts are probabilities.
    density = min(0.2, peak / max(10.0, len(text) / 120.0) * 0.08)
    scores = {lane: min(0.99, count / total + density) for lane, count in counts.items() if count}
    return scores or {ChatLane.context: 1.0}


def classify_chunk_keyword(
    chunk: ChatChunk,
    *,
    policy: ClassificationPolicy | None = None,
) -> list[LaneClassification]:
    """Return every plausible lane for one canonical chunk."""

    policy = policy or ClassificationPolicy()
    scores = _lane_scores(chunk.content)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_score = ordered[0][1]
    selected = [(lane, score) for lane, score in ordered if score >= policy.include_lane]
    if not selected:
        selected = [ordered[0]]

    ambiguous = len(ordered) > 1 and top_score - ordered[1][1] < policy.ambiguity_margin
    status = "auto_accepted" if top_score >= policy.auto_accept and not ambiguous else "pending_review"

    results = [
        LaneClassification(
            lane=lane,
            confidence=round(score, 4),
            review_status=status,
            rationale="keyword-v1",
        )
        for lane, score in selected
    ]

    if status == "pending_review" and all(item.lane is not ChatLane.context for item in results):
        results.append(
            LaneClassification(
                lane=ChatLane.context,
                confidence=1.0,
                review_status="pending_review",
                rationale="searchable fallback while classification awaits review",
            )
        )
    return results


def classification_failure(reason: str) -> list[LaneClassification]:
    """Fail open into searchable context and the review queue."""

    return [
        LaneClassification(
            lane=ChatLane.context,
            confidence=0.0,
            review_status="classification_failed",
            rationale=reason,
        )
    ]


def classify_chunks(
    chunks: Iterable[ChatChunk],
    *,
    mode: str = "keyword",
    policy: ClassificationPolicy | None = None,
) -> dict[str, list[LaneClassification]]:
    """Classify canonical chunks; keys are chunk content hashes.

    The deterministic CPU mode is the production baseline. Remote/LLM models
    can be added as challengers without changing the persistence contract.
    """

    if mode != "keyword":
        raise ValueError("only the calibrated keyword baseline is wired; remote classifiers are challengers")
    output: dict[str, list[LaneClassification]] = {}
    for chunk in chunks:
        try:
            output[chunk.content_hash] = classify_chunk_keyword(chunk, policy=policy)
        except Exception as exc:  # a bad chunk must never disappear
            output[chunk.content_hash] = classification_failure(str(exc))
    return output
