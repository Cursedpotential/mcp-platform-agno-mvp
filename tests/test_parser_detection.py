"""Unit tests for chatminer parser auto-detection.

``get_parser_for_file`` is the routing brain of chatminer: it scores every
registered parser's ``can_parse`` and picks the best one above a 0.5 threshold.
Mis-routing here silently corrupts the forensic record, so the routing and the
threshold both need coverage.
"""

from __future__ import annotations

import json

from chatminer.parsers import PARSER_REGISTRY, get_parser_for_file


def _detect(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return get_parser_for_file(str(p), content=content)


def test_registry_specific_before_generic():
    # The generic markdown fallback must be last so specific formats win ties.
    names = [c.__name__ for c in PARSER_REGISTRY]
    assert names[-1] == "GenericMdParser"


def test_detects_claude_code_jsonl(tmp_path):
    content = "\n".join(
        json.dumps({"role": role, "content": f"msg {i}", "timestamp": "2026-01-01T00:00:00Z"})
        for i, role in enumerate(["user", "assistant", "user", "assistant"])
    )
    parser = _detect(tmp_path, "conv.jsonl", content)
    assert parser is not None
    assert parser.SOURCE_NAME == "claude_code"


def test_detects_chatgpt_official_json(tmp_path):
    content = json.dumps([{"title": "A chat", "create_time": 1700000000.0, "mapping": {"root": {}}}])
    parser = _detect(tmp_path, "conversations.json", content)
    assert parser is not None
    assert parser.SOURCE_NAME == "chatgpt_official"


def test_detects_generic_markdown_fallback(tmp_path):
    # 'Person'/'Bot' bold markers are matched ONLY by the generic parser, not by
    # the Claude-specific markdown parser — isolates the fallback path.
    content = "\n\n".join(f"**Person**: question {i}\n\n**Bot**: answer {i}" for i in range(7))
    parser = _detect(tmp_path, "mystery.md", content)
    assert parser is not None
    assert parser.SOURCE_NAME == "generic_md"


def test_unknown_content_returns_none(tmp_path):
    parser = _detect(tmp_path, "random.txt", "just some prose with no chat markers at all")
    assert parser is None


def test_below_threshold_returns_none(tmp_path):
    # Two exchanges -> generic score 0.3, under the 0.5 floor -> no parser.
    content = "**Person**: hi\n\n**Bot**: hello"
    parser = _detect(tmp_path, "tiny.md", content)
    assert parser is None


def test_missing_file_returns_none(tmp_path):
    # No content passed and the file can't be read -> None, not a crash.
    assert get_parser_for_file(str(tmp_path / "does-not-exist.md")) is None
