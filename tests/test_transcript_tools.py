"""Registry + end-to-end tests for the chatminer-backed transcript tools (HA.2/HA.4).

Covers the wrapper glue, not the parsers themselves (chatminer parse_content
is exercised in test_parsers*.py): registration roster, substitution order
(whole-file fallback LAST), and a real file -> records pass per transport shape
(.json mapping tree, simple .jsonl, .md with role markers).
"""

from __future__ import annotations

import json

import pytest

from server.evidence.registry import load_builtin_tools, registry

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


@pytest.fixture(autouse=True)
def _builtins():
    load_builtin_tools()


def test_all_ten_chatminer_wrappers_register():
    ids = {t.id for t in registry.all() if t.capability == "parse.transcript"}
    assert CHATMINER_WRAPPER_IDS <= ids
    # Kept for unique coverage (HA.4 amendment) + the whole-file fallback:
    assert {"transcripts.claude-ai-export", "transcripts.claude-code-jsonl", "transcripts.markdown"} <= ids
    # Retired duplicate (chatminer chatgpt_official covers the format):
    assert "transcripts.chatgpt-export" not in ids
    assert len(ids) == 13


def test_whole_file_fallback_resolves_last_for_md():
    order = [t.id for t in registry.resolve("parse.transcript", media_hint="notes.md", size_bytes=1)]
    # The fallback never rejects a non-empty file; anything after it is dead code.
    assert order[-1] == "transcripts.markdown"
    assert set(order[:-1]) <= CHATMINER_WRAPPER_IDS


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
