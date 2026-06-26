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
from chatminer.parsers.chatgpt_official import ChatGptOfficialParser
from chatminer.parsers.claude_code import ClaudeCodeParser
from chatminer.parsers.claude_md import ClaudeMdParser
from chatminer.parsers.gemini_json import GeminiJsonParser
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


def test_chatgpt_official_walks_mapping_tree():
    # Official export: a node tree under "mapping"; system + empty nodes drop out,
    # user/assistant survive in tree order.
    export = [
        {
            "title": "Custody timeline",
            "create_time": 1_700_000_000.0,
            "model": "gpt-4",
            "id": "conv-123",
            "mapping": {
                "root": {"parent": None, "children": ["sys"], "message": None},
                "sys": {
                    "parent": "root",
                    "children": ["u1"],
                    "message": {"author": {"role": "system"}, "content": {"parts": ["be helpful"]}},
                },
                "u1": {
                    "parent": "sys",
                    "children": ["a1"],
                    "message": {"author": {"role": "user"}, "content": {"parts": ["hi there"]}},
                },
                "a1": {
                    "parent": "u1",
                    "children": ["empty"],
                    "message": {"author": {"role": "assistant"}, "content": {"parts": ["```python\nprint(1)\n```"]}},
                },
                "empty": {
                    "parent": "a1",
                    "children": [],
                    "message": {"author": {"role": "user"}, "content": {"parts": []}},
                },
            },
        }
    ]

    [conv] = ChatGptOfficialParser().parse_content(json.dumps(export), source_file="conversations.json")
    assert conv.title == "Custody timeline"
    assert conv.metadata["model"] == "gpt-4"
    assert conv.created_at is not None

    # system node skipped, empty-parts node skipped -> exactly user + assistant.
    assert conv.message_count == 2
    user_msg, asst_msg = conv.messages
    assert user_msg.sender_role is MessageRole.USER
    assert user_msg.content == "hi there"
    assert asst_msg.sender_role is MessageRole.ASSISTANT
    assert asst_msg.content_type is ContentType.CODE
    assert asst_msg.language == "python"


def test_claude_md_parses_human_assistant_markers():
    content = (
        "My Claude Chat\n\n"
        "Human: What is the custody schedule?\n\n"
        "Assistant: The schedule alternates weekly.\n\n"
        "Human: thanks\n\n"
        "Assistant: you're welcome"
    )
    [conv] = ClaudeMdParser().parse_content(content, source_file="claude.md")
    assert conv.message_count >= 2
    roles = {m.sender_role for m in conv.messages}
    assert MessageRole.USER in roles
    assert MessageRole.ASSISTANT in roles
    assert "alternates weekly" in " ".join(m.content for m in conv.messages)


def test_gemini_json_maps_model_to_assistant():
    export = {
        "title": "Gemini Q",
        "messages": [
            {"author": "user", "content": "explain pgvector"},
            {"author": "model", "content": "```sql\nCREATE EXTENSION vector;\n```"},
            {"author": "user", "content": ""},  # empty -> skipped
        ],
    }
    [conv] = GeminiJsonParser().parse_content(json.dumps(export), source_file="gemini.json")
    assert conv.title == "Gemini Q"
    assert conv.message_count == 2

    user_msg, model_msg = conv.messages
    assert user_msg.sender_role is MessageRole.USER and user_msg.content == "explain pgvector"
    assert model_msg.sender_role is MessageRole.ASSISTANT  # "model" -> assistant
    assert model_msg.sender == "Gemini"
    assert model_msg.content_type is ContentType.CODE
    assert model_msg.language == "sql"
