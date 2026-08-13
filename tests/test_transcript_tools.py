"""Registry + end-to-end tests for the chatminer-backed transcript tools (HA.2/HA.4).

Covers the wrapper glue, not the parsers themselves (chatminer parse_content
is exercised in test_parsers*.py): registration roster, substitution order
(whole-file fallback LAST), and a real file -> records pass per transport shape
(.json mapping tree, simple .jsonl, .md with role markers).

_Byline: Claude Code · Kimi K3 · 2026-08-12 (stale roster fix: count 13→14 for the
D-051 perplexity-contexts wrapper; de-numbered the test name so it stops rotting)_
_Byline: Codex · GPT-5 · 2026-08-13 (Gemini/custom-GPT Markdown parsers)_
"""

from __future__ import annotations

import json

import pytest

from server.tools.registry import load_builtin_tools, registry

CHATMINER_WRAPPER_IDS = {
    "transcripts.chatgpt-official",
    "transcripts.chatgpt-share",
    "transcripts.gemini-chrome",
    "transcripts.gemini-json",
    "transcripts.claude-md",
    "transcripts.claude-code",
    "transcripts.perplexity-gdpr",
    "transcripts.perplexity-plugin",
    "transcripts.perplexity-md",
    "transcripts.generic-md",
}

SPECIALTY_MARKDOWN_IDS = {
    "transcripts.chatgpt-custom-gpt-md",
    "transcripts.gemini-md",
}


@pytest.fixture(autouse=True)
def _builtins():
    load_builtin_tools()


def test_all_chatminer_wrappers_register():
    ids = {t.id for t in registry.all() if t.capability == "parse.transcript"}
    assert CHATMINER_WRAPPER_IDS <= ids
    # Kept for unique coverage (HA.4 amendment) + the whole-file fallback:
    assert {"transcripts.claude-ai-export", "transcripts.claude-code-jsonl", "transcripts.markdown"} <= ids
    # Retired duplicate (chatminer chatgpt_official covers the format):
    assert "transcripts.chatgpt-export" not in ids
    # D-051 (2026-08-12, 57ec156): Perplexity contexts parser is wrapper #14 —
    # the count below was stale at 13 (and the old `test_all_ten_...` name staler
    # still); renamed so a wrapper add can't silently rot the roster again.
    assert "transcripts.perplexity-contexts" in ids
    assert SPECIALTY_MARKDOWN_IDS <= ids
    assert len(ids) == 16


def test_whole_file_fallback_resolves_last_for_md():
    order = [t.id for t in registry.resolve("parse.transcript", media_hint="notes.md", size_bytes=1)]
    # The fallback never rejects a non-empty file; anything after it is dead code.
    assert order[-1] == "transcripts.markdown"
    assert set(order[:-1]) <= CHATMINER_WRAPPER_IDS | SPECIALTY_MARKDOWN_IDS


@pytest.mark.parametrize(
    ("tool_id", "body", "expected_source"),
    [
        (
            "transcripts.chatgpt-custom-gpt-md",
            "You asked:\n---\nHow should this work?\n\nChatGPT Replied:\n---\nUse ordered messages.",
            "chatgpt-custom-gpt-md",
        ),
        (
            "transcripts.gemini-md",
            "# Design chat\nExported on: 4/14/2026, 7:08:32 PM\n---\n**You:**\nQuestion\n**Gemini:**\nAnswer",
            "gemini-md",
        ),
    ],
)
def test_specialty_markdown_parsers_end_to_end(tmp_path, tool_id, body, expected_source):
    path = tmp_path / "chat.md"
    path.write_text(body, encoding="utf-8")
    tool = next(candidate for candidate in registry.all() if candidate.id == tool_id)
    result = tool.run({"path": str(path)})
    assert [record["source"] for record in result["records"]] == [expected_source, expected_source]
    assert [record["role"] for record in result["records"]] == ["user", "assistant"]


def test_chatgpt_official_wrapper_end_to_end(tmp_path):
    export = [
        {
            "id": "orig-1",
            "title": "pickup dispute",
            "create_time": 1767409445,
            "mapping": {
                "root": {"parent": None, "children": ["n1"], "message": None},
                "n1": {
                    "parent": "root",
                    "children": ["n2"],
                    "message": {
                        "author": {"role": "user"},
                        "create_time": 1767409445,
                        "content": {"content_type": "text", "parts": ["she blocked the exchange again"]},
                    },
                },
                "n2": {
                    "parent": "n1",
                    "children": [],
                    "message": {
                        "author": {"role": "assistant"},
                        "create_time": 1767409500,
                        "content": {"content_type": "text", "parts": ["Document the time and place."]},
                    },
                },
            },
        }
    ]
    f = tmp_path / "conversations.json"
    f.write_text(json.dumps(export), encoding="utf-8")

    out = registry.get("transcripts.chatgpt-official").run({"path": str(f)})
    assert out["stats"]["record_count"] == 2
    [user, asst] = out["records"]
    assert user["content"] == "she blocked the exchange again"  # verbatim
    assert user["role"] == "user" and asst["role"] == "assistant"
    assert user["source"] == "chatgpt-official"
    assert user["occurred_at"] is not None
    assert user["attrs"]["message_hash"]


def test_claude_code_wrapper_parses_simple_jsonl(tmp_path):
    lines = [
        json.dumps({"role": "user", "content": "hello", "timestamp": "2026-01-02T03:04:05Z"}),
        json.dumps({"role": "assistant", "content": "hi there", "timestamp": "2026-01-02T03:04:06Z"}),
    ]
    f = tmp_path / "claude_session.jsonl"
    f.write_text("\n".join(lines), encoding="utf-8")

    out = registry.get("transcripts.claude-code").run({"path": str(f)})
    assert out["stats"]["record_count"] == 2
    assert out["records"][0]["source"] == "claude-code"


def test_real_session_jsonl_falls_through_to_claude_code_jsonl(tmp_path):
    # REAL Claude Code session events (type/message/sessionId) — chatminer's
    # simple-format detector must hard-fail, the session parser must succeed:
    # the substitution mesh in miniature.
    lines = [
        json.dumps(
            {
                "type": "user",
                "sessionId": "s-1",
                "uuid": "u-1",
                "timestamp": "2026-01-02T03:04:05Z",
                "message": {"content": [{"type": "text", "text": "run the ingest"}]},
            }
        ),
        json.dumps(
            {
                "type": "assistant",
                "sessionId": "s-1",
                "uuid": "u-2",
                "timestamp": "2026-01-02T03:04:06Z",
                "message": {"content": [{"type": "text", "text": "ingest complete"}]},
            }
        ),
    ]
    f = tmp_path / "session.jsonl"
    f.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(ValueError):
        registry.get("transcripts.claude-code").run({"path": str(f)})

    out = registry.get("transcripts.claude-code-jsonl").run({"path": str(f)})
    assert out["stats"]["record_count"] == 2
    assert out["records"][0]["conversation_id"] == "s-1"


def test_generic_md_wrapper_needs_role_alternation(tmp_path):
    chat = tmp_path / "chat.md"
    chat.write_text("User: did she reply?\nAssistant: Not yet — log it.\n", encoding="utf-8")
    out = registry.get("transcripts.generic-md").run({"path": str(chat)})
    assert out["stats"]["record_count"] == 2
    assert out["records"][0]["role"] == "user"

    plain = tmp_path / "notes.md"
    plain.write_text("# Meeting notes\njust prose, no chat markers\n", encoding="utf-8")
    with pytest.raises(ValueError, match="detection confidence"):
        registry.get("transcripts.generic-md").run({"path": str(plain)})
    # ...which is exactly when the whole-file fallback picks it up.
    out = registry.get("transcripts.markdown").run({"path": str(plain)})
    assert out["stats"]["record_count"] == 1


def test_wrappers_reject_wrong_shape_for_substitution(tmp_path):
    # A claude.ai export is NOT a ChatGPT mapping tree: the chatgpt-official
    # wrapper must raise (so resolve() order moves on to claude-ai-export).
    f = tmp_path / "conversations.json"
    f.write_text(
        json.dumps([{"uuid": "c1", "name": "t", "chat_messages": [{"sender": "human", "text": "hi"}]}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        registry.get("transcripts.chatgpt-official").run({"path": str(f)})
    out = registry.get("transcripts.claude-ai-export").run({"path": str(f)})
    assert out["stats"]["record_count"] == 1
