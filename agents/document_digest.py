"""
Document Digest Agent — Gemini long-context specialist (owner decision 2026-06-10)
==================================================================================

Swallows large documents/transcripts (Gemini 2.5 Pro, 1M+ token context) and
produces structured digests: summaries, parsed structure, extracted decisions,
entity lists — the pre-processing step before knowledge ingestion or analysis.

Guardrails (locked):
  - Deterministic evidence work (hashing, custody, normalization) stays in the
    MCP tools / platform pipeline. This agent SUMMARIZES; it is never the
    chain of custody.
  - Outputs feed the same approval gates as everything else; no direct writes.
"""

from os import getenv

from agno.agent import Agent


def build_document_digest(db, knowledge=None) -> Agent | None:
    """Gemini-backed long-context digest agent. Returns None when no key set."""
    api_key = getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    from agno.models.google import Gemini

    return Agent(
        id="document-digest",
        name="Document Digest",
        role="Read very large documents/transcripts and produce structured digests.",
        model=Gemini(id=getenv("GOOGLE_MODEL_ID", "gemini-2.5-pro"), api_key=api_key),
        db=db,
        knowledge=knowledge,
        add_history_to_context=True,
        num_history_runs=5,
        instructions=[
            "You are the long-context reader. Given a large document, transcript, or "
            "export, produce: (1) a faithful structured summary, (2) section/topic map, "
            "(3) extracted decisions, action items, and named entities, (4) anything "
            "anomalous worth human review.",
            "Quote sparingly but precisely; always note where in the document each "
            "finding came from (section, page, or timestamp).",
            "You never perform evidence custody operations (hashing, normalization, "
            "storage) — flag content for the platform pipeline instead.",
            "Output clean markdown ready for knowledge ingestion or human review.",
        ],
        markdown=True,
    )
