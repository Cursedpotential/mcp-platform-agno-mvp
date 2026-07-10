"""Unit tests for evidence.store.render_conversations_markdown.

The renderer turns normalized records into the per-conversation markdown the
knowledge engine chunks/embeds. It's pure (no DB), but it's the shape agents
ultimately read, so grouping/ordering/titling matter.
"""

from __future__ import annotations

from datetime import datetime, timezone

from server.contracts.records import NormalizedRecord
from server.evidence.store import render_conversations_markdown


def _rec(conv_id, role, content, *, when=None, title=None):
    attrs = {"conversation_title": title} if title else {}
    return NormalizedRecord(
        source="chat",
        conversation_id=conv_id,
        role=role,
        content=content,
        occurred_at=when,
        attrs=attrs,
    )


def test_groups_by_conversation():
    docs = render_conversations_markdown(
        [
            _rec("A", "user", "hi A"),
            _rec("A", "assistant", "hello A"),
            _rec("B", "user", "hi B"),
        ]
    )
    assert set(docs) == {"A", "B"}
    assert "hi A" in docs["A"] and "hello A" in docs["A"]
    assert "hi B" in docs["B"]


def test_orders_by_time_and_renders_roles():
    later = _rec("A", "assistant", "second", when=datetime(2026, 1, 2, tzinfo=timezone.utc))
    earlier = _rec("A", "user", "first", when=datetime(2026, 1, 1, tzinfo=timezone.utc))
    [md] = render_conversations_markdown([later, earlier]).values()
    # Chronological order regardless of input order.
    assert md.index("first") < md.index("second")
    assert "**USER" in md and "**ASSISTANT" in md


def test_untitled_when_no_conversation_id():
    docs = render_conversations_markdown([_rec(None, "user", "orphan")])
    assert "untitled" in docs


def test_uses_conversation_title_attr():
    docs = render_conversations_markdown([_rec("A", "user", "x", title="Custody Dispute Thread")])
    assert docs["A"].startswith("# Custody Dispute Thread")


def test_empty_input():
    assert render_conversations_markdown([]) == {}
