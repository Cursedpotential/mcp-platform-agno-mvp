"""Tests for the detection router (server/analysis/format_router.py) + the
Perplexity-contexts parser — the "detect once, don't fail-through" design.
"""

from __future__ import annotations

import json

import pytest

from server.analysis.format_router import SIGNATURES, detect_format
from server.tools.registry import load_builtin_tools, registry


@pytest.fixture(autouse=True)
def _builtins():
    load_builtin_tools()


def _write(tmp_path, name, obj):
    f = tmp_path / name
    f.write_text(json.dumps(obj), encoding="utf-8")
    return f


def test_detect_chatgpt_is_go_primary(tmp_path):
    f = _write(tmp_path, "conversations.json", [{"title": "t", "create_time": 1, "mapping": {"root": {}}}])
    det = detect_format(f)
    assert det.format_id == "chatgpt-official"
    assert det.engine == "go"  # Go-primary: a Go decoder exists for this format
    assert det.parse_format == "chatgpt-official-json"
    assert det.python_parser_id == "transcripts.chatgpt-official"  # python fallback available


def test_detect_claude_is_python(tmp_path):
    f = _write(
        tmp_path,
        "conversations.json",
        [{"uuid": "c", "name": "n", "chat_messages": [{"sender": "human", "text": "hi"}]}],
    )
    det = detect_format(f)
    assert det.format_id == "claude-ai-export"
    assert det.engine == "python"


def test_detect_perplexity_contexts_is_python(tmp_path):
    f = _write(
        tmp_path,
        "conversations.json",
        {"conversations": [{"context_uuid": "x", "context_title": "t", "entries": [{"query": "q", "answer": "a"}]}]},
    )
    det = detect_format(f)
    assert det.format_id == "perplexity-contexts"
    assert det.engine == "python"
    assert det.python_parser_id == "transcripts.perplexity-contexts"


def test_detect_unknown_returns_none(tmp_path):
    f = _write(tmp_path, "weird.json", {"something": "else"})
    det = detect_format(f)
    assert det.format_id is None
    assert det.engine == "python"  # caller falls back to the full mesh


def test_every_signature_names_a_registered_parser():
    ids = {t.id for t in registry.all()}
    for sig in SIGNATURES:
        assert sig.python_parser_id in ids, f"{sig.format_id} -> unregistered parser {sig.python_parser_id}"


# ---------------------------------------------------------------------------
# Perplexity-contexts parser
# ---------------------------------------------------------------------------


def test_perplexity_contexts_parser_maps_query_and_answer(tmp_path):
    from server.tools.parsers.ai_chat.perplexity_contexts import parse

    f = _write(
        tmp_path,
        "conversations.json",
        {
            "conversations": [
                {
                    "context_uuid": "ctx-1",
                    "context_title": "pickup",
                    "mode": "COPILOT",
                    "entries": [
                        {
                            "entry_uuid": "e1",
                            "query": "when is pickup",
                            "answer": "6pm",
                            "created_at": "2026-01-01T00:00:00Z",
                            "query_status": "COMPLETED",
                        },
                    ],
                }
            ]
        },
    )
    out = parse({"path": str(f)})
    recs = out["records"]
    assert len(recs) == 2  # query + answer
    assert recs[0]["role"] == "user" and recs[0]["content"] == "when is pickup"
    assert recs[1]["role"] == "assistant" and recs[1]["content"] == "6pm"
    assert recs[0]["source"] == "perplexity-contexts"
    assert recs[0]["conversation_id"] == "ctx-1"
    assert recs[0]["attrs"]["conversation_title"] == "pickup"


def test_perplexity_contexts_parser_rejects_other_formats(tmp_path):
    from server.tools.parsers.ai_chat.perplexity_contexts import parse

    f = _write(tmp_path, "conversations.json", [{"uuid": "c", "chat_messages": []}])  # claude shape
    with pytest.raises(ValueError):
        parse({"path": str(f)})
