"""Unit tests for parser parse_content — the actual transcript-to-record step.

Detection is covered in test_parser_detection; this exercises the parsing
itself, where silent mis-parsing would corrupt the forensic record. Verbatim
content preservation is the contract that matters most (ParsedMessage.content
is "NEVER summarized").
"""

from __future__ import annotations

import json
from datetime import timezone

from chatminer.core.types import ContentType, MessageRole
from chatminer.parsers.claude_code import ClaudeCodeParser
from chatminer.parsers.generic_md import GenericMdParser


def test_claude_code_parses_roles_timestamps_and_code():
    content = "\n".join(
        [
            json.dumps({"role": "user", "content": "hello", "timestamp": "2026-01-02T03:04:05Z"}),
            "",  # blank line — skipped
            "this is not json",  # malformed — skipped, not fatal
            json.dumps(
                {
                    "role": "assistant",
                    "content": "```python\nprint(1)\n```",
                    "timestamp": "2026-01-02T03:04:06Z",
                    "model": "claude-x",
                }
            ),
            json.dumps({"role": "user", "content": ""}),  # empty content — skipped
        ]
    )

    [conv] = ClaudeCodeParser().parse_content(content, source_file="c.jsonl")
    assert conv.message_count == 2

    user_msg, asst_msg = conv.messages

    assert user_msg.sender_role is MessageRole.USER
    assert user_msg.sender == "You"
    assert user_msg.content == "hello"  # verbatim
    assert user_msg.content_type is ContentType.TEXT
    assert user_msg.timestamp is not None
    assert user_msg.timestamp.tzinfo is not None  # Z normalized to +00:00
    assert user_msg.timestamp.astimezone(timezone.utc).year == 2026

    assert asst_msg.sender_role is MessageRole.ASSISTANT
    assert asst_msg.sender == "Claude"
    assert asst_msg.content_type is ContentType.CODE
    assert asst_msg.language == "python"
    # Non-core keys land in metadata; role/content/timestamp are stripped out.
    assert asst_msg.metadata.get("model") == "claude-x"
    assert "role" not in asst_msg.metadata
    assert "content" not in asst_msg.metadata


def test_claude_code_treats_human_as_user():
    content = json.dumps({"role": "human", "content": "hi"})
    [conv] = ClaudeCodeParser().parse_content(content, source_file="c.jsonl")
    assert conv.messages[0].sender_role is MessageRole.USER


def test_generic_md_preserves_content_and_roles():
    content = "**Person**: what is X?\n\n**Bot**: X is Y.\n\n**Person**: thanks\n\n**Bot**: you're welcome"
    [conv] = GenericMdParser().parse_content(content, source_file="g.md")

    assert conv.message_count >= 2
    roles = {m.sender_role for m in conv.messages}
    assert MessageRole.USER in roles
    assert MessageRole.ASSISTANT in roles
    # Verbatim assistant content survives parsing.
    joined = " ".join(m.content for m in conv.messages)
    assert "X is Y" in joined


def test_parsers_stamp_source_format():
    content = json.dumps({"role": "user", "content": "hi"})
    [conv] = ClaudeCodeParser().parse_content(content, source_file="c.jsonl")
    assert conv.messages[0].source_format == "claude_code"
