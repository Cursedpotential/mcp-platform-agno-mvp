"""parse_content tests for the remaining chat-export formats.

Completes parser coverage: chatgpt_share, gemini_chrome, perplexity_plugin,
perplexity_gdpr (claude_code/generic_md/chatgpt_official/claude_md/gemini_json/
perplexity_md are in test_parsers.py). Focus: role assignment, assistant
relabeling per source, metadata extraction, verbatim content.
"""

from __future__ import annotations

import json

from chatminer.core.types import MessageRole
from chatminer.parsers.chatgpt_share import ChatGptShareParser
from chatminer.parsers.gemini_chrome import GeminiChromeParser
from chatminer.parsers.perplexity_gdpr import PerplexityGdprParser
from chatminer.parsers.perplexity_plugin import PerplexityPluginParser


def _roles(conv):
    return {m.sender_role for m in conv.messages}


def test_perplexity_plugin_query_answer_pairs():
    content = (
        "# What is hearsay?\n\n"
        "Hearsay is an out-of-court statement offered for its truth.\n\n"
        "## Sources\n1. [Cornell](https://law.cornell.edu/x)\n"
    )
    [conv] = PerplexityPluginParser().parse_content(content, source_file="p.md")
    assert conv.title == "What is hearsay?"
    assert conv.message_count == 2
    assert _roles(conv) == {MessageRole.USER, MessageRole.ASSISTANT}
    asst = [m for m in conv.messages if m.sender_role is MessageRole.ASSISTANT][0]
    assert asst.sender == "Perplexity"
    assert "out-of-court statement" in asst.content


def test_gemini_chrome_header_and_messages():
    content = (
        "# Google Gemini\n"
        "Exported on: 05/17/2022, 5:29:42 PM\n"
        "Total Messages: 2\n\n"
        "👤 You\nWhat is pgvector?\n\n"
        "🤖 Assistant\nA Postgres extension for vector search.\n"
    )
    [conv] = GeminiChromeParser().parse_content(content, source_file="g.md")
    assert conv.message_count == 2
    assert conv.metadata["total_messages_expected"] == 2
    assert conv.metadata.get("exported_at", "").startswith("2022-05-17")

    user, asst = conv.messages
    assert user.sender_role is MessageRole.USER and user.content == "What is pgvector?"
    assert asst.sender_role is MessageRole.ASSISTANT
    assert asst.sender == "Gemini"
    assert "vector search" in asst.content


def test_perplexity_gdpr_answers_become_assistant_messages():
    export = {
        "conversations": [
            {
                "title": "hearsay question",
                "answers": [
                    {
                        "content": "Hearsay is an out-of-court statement.",
                        "created_at": "2022-05-17T17:29:42Z",
                        "citations": [{"url": "https://example.com/x"}],
                    }
                ],
            }
        ]
    }
    [conv] = PerplexityGdprParser().parse_content(json.dumps(export), source_file="pg.json")
    assert conv.title == "hearsay question"
    assistants = [m for m in conv.messages if m.sender_role is MessageRole.ASSISTANT]
    assert assistants and assistants[0].sender == "Perplexity"
    assert "out-of-court statement" in assistants[0].content


def test_chatgpt_share_header_metadata_and_pair():
    content = (
        "**User:** Matt (matt@example.com)\n"
        "Created: 5/17/2022 17:29\n"
        "https://chatgpt.com/c/abc123\n\n"
        "What is hearsay?\n\n"
        "**Response:**\nHearsay is an out-of-court statement.\n"
    )
    [conv] = ChatGptShareParser().parse_content(content, source_file="c.md")
    assert conv.metadata["user_email"] == "matt@example.com"
    assert conv.metadata["chatgpt_url"].endswith("abc123")
    assert _roles(conv) == {MessageRole.USER, MessageRole.ASSISTANT}
    asst = [m for m in conv.messages if m.sender_role is MessageRole.ASSISTANT][0]
    assert asst.sender == "ChatGPT"
    assert "out-of-court statement" in asst.content
