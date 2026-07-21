# Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.7: detect_type_with_evidence added)
"""Detect whether a staged upload is a generic doc or a chat export.

Chat exports take a different promote path (POST /v1/evidence/import) than
plain docs (POST /knowledge/content) — see service/promote.py. New in the
workbench; no donor equivalent (the donor kit had no chat-export concept).
"""

from __future__ import annotations

import json

DOC = "doc"
CHAT_EXPORT = "chat_export"


def detect_type(filename: str, sample: bytes | str) -> str:
    """Return "doc" or "chat_export" based on filename + a content sample.

    `sample` may be the first N bytes of the file (non-JSON formats) or the
    full extracted text (JSON/JSONL formats, already capped upstream at 2MB
    by service/upload.py) — only JSON-family files are ever sniffed.
    """
    lower = filename.lower()
    text = sample.decode("utf-8", errors="replace") if isinstance(sample, bytes) else sample

    if lower.endswith(".jsonl"):
        return CHAT_EXPORT if _looks_like_claude_code_session(text) else DOC
    if lower.endswith(".json"):
        return CHAT_EXPORT if _looks_like_chat_export(text) else DOC
    return DOC


def _looks_like_claude_code_session(text: str) -> bool:
    """Sniff the first non-empty JSONL line for a Claude Code session shape."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return False
        if not isinstance(obj, dict):
            return False
        # Claude Code session lines carry a "type" plus one of these keys.
        return "type" in obj and any(key in obj for key in ("sessionId", "message", "uuid"))
    return False


def detect_type_with_evidence(filename: str, sample: bytes | str) -> tuple[str, str]:
    """Like detect_type(), but also returns a human-readable reason for the
    call — powers the Intake "Analyze" action (C2.7 owner scope addition:
    let the operator see WHAT a file is, and why, before running it).

    Deliberately re-implements the same branching as detect_type() rather
    than refactoring it to share code, so the original (already-shipped,
    already-relied-on-by-promote) function's behavior can't regress as a
    side effect of this additive change.
    """
    lower = filename.lower()
    text = sample.decode("utf-8", errors="replace") if isinstance(sample, bytes) else sample
    ext = lower.rsplit(".", 1)[-1] if "." in lower else "(no extension)"

    if lower.endswith(".jsonl"):
        if _looks_like_claude_code_session(text):
            return (
                CHAT_EXPORT,
                "filename ends .jsonl and the first JSONL line has a Claude Code "
                "session shape ('type' key plus one of sessionId/message/uuid)",
            )
        return (
            DOC,
            "filename ends .jsonl but the first line isn't valid JSON, isn't an "
            "object, or doesn't match the Claude Code session shape",
        )
    if lower.endswith(".json"):
        if _looks_like_chat_export(text):
            return (
                CHAT_EXPORT,
                "filename ends .json and the parsed head object has a 'mapping' "
                "(ChatGPT) or 'chat_messages' (claude.ai) key",
            )
        return (
            DOC,
            "filename ends .json but is unparseable, empty, or has neither a "
            "'mapping' nor a 'chat_messages' key at the head",
        )
    return DOC, f"extension '.{ext}' is not .json/.jsonl — only those are sniffed, everything else defaults to doc"


def _looks_like_chat_export(text: str) -> bool:
    """Detect a ChatGPT export ("mapping" per conversation) or a claude.ai
    export ("chat_messages") by parsing just the head of the JSON."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        return False

    head = data[0]
    if not isinstance(head, dict):
        return False
    return "mapping" in head or "chat_messages" in head
