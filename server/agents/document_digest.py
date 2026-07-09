"""agents/document_digest.py — Gemini long-context specialist agent builder.

Provides ``build_document_digest(db, knowledge)`` which returns a configured
Agno ``Agent`` when ``GOOGLE_API_KEY`` is set, or ``None`` otherwise.

The agent uses Gemini 2.5 Pro (1M+ token context) to produce structured
digests of very large documents: summaries, section maps, extracted
decisions, entity lists.

Guardrails:
- Deterministic evidence operations (hashing, custody, normalization) stay in
  the platform pipeline. This agent SUMMARIZES; it is never the chain of custody.
- Outputs feed the same approval gates as everything else.
"""

from __future__ import annotations

from os import getenv
from typing import Any, Optional

from agno.agent import Agent


def build_document_digest(db: Any, knowledge: Any = None) -> Optional[Agent]:
    """Build the Document Digest agent (conditional on ``GOOGLE_API_KEY``).

    Parameters
    ----------
    db:
        Agno operational DB instance.
    knowledge:
        Agno Knowledge instance (optional).

    Returns
    -------
    Agent | None
        A configured Agent when ``GOOGLE_API_KEY`` is set, otherwise ``None``.
    """
    api_key = getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    from agno.models.google import Gemini

    return Agent(
        id="document-digest",
        name="Document Digest",
        role=("Read very large documents/transcripts and produce structured digests."),
        model=Gemini(
            id=getenv("GOOGLE_MODEL_ID", "gemini-2.5-pro"),
            api_key=api_key,
        ),
        db=db,
        knowledge=knowledge,
        add_history_to_context=True,
        num_history_runs=5,
        instructions=[
            "You are the long-context reader. Given a large document, transcript, "
            "or export, produce: (1) a faithful structured summary, (2) section/topic "
            "map, (3) extracted decisions, action items, and named entities, "
            "(4) anything anomalous worth human review.",
            "Quote sparingly but precisely; always note where in the document each "
            "finding came from (section, page, or timestamp).",
            "You never perform evidence custody operations (hashing, normalization, "
            "storage) — flag content for the platform pipeline instead.",
        ],
        markdown=True,
    )
