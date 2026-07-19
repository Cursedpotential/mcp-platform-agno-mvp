#!/usr/bin/env python3
"""
TEMPLATE — Stop hook that writes ONE Graphiti episode summarizing the session,
via `grc add`. Lower-noise alternative to per-tool-call hooks (see
post-tool-use-episode.py) — better fit for plugins whose durable unit is a
whole task, not an individual tool call.

DESIGN ONLY. Not registered in any plugin's hooks.json/settings.json.

Contract: Claude Code invokes Stop hooks with a JSON payload on stdin,
e.g. {"transcript_path": "...", "hook_event_name": "Stop", ...}. This script
must ALWAYS exit 0 (fail soft) — a Graphiti outage must never break Stop.

# Byline: Claude Code · Sonnet · 2026-07-19
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

GRC_PATH = os.environ.get(
    "GRC_PATH", r"C:/Users/matts/.claude/skills/graphiti-client/scripts/grc.py"
)
GROUP = os.environ.get("GRC_HOOK_GROUP", "platform")
NAME_PREFIX = os.environ.get("GRC_HOOK_NAME_PREFIX", "session:")


def _build_summary(payload: dict) -> tuple[str, str] | None:
    """PLACEHOLDER — replace with real summarization before wiring this in.

    Options for a real implementation:
    - Read payload['transcript_path'], extract the last assistant message or
      a structured "what I did" block the plugin's own prompts produce.
    - Have the plugin set an env var (e.g. GRC_HOOK_SUMMARY) earlier in the
      session with a one-paragraph summary, and just read that here — avoids
      re-parsing the transcript in the hook itself.

    Returns (name, body) or None to skip (e.g. nothing durable happened).
    """
    summary = os.environ.get("GRC_HOOK_SUMMARY")
    if not summary:
        return None  # default: skip unless the plugin explicitly set one
    session_id = payload.get("session_id", "unknown-session")
    name = f"{NAME_PREFIX} {session_id}"
    return name, summary


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001 — fail soft, always exit 0
        sys.stderr.write(f"[graphiti-hook] failed to parse stdin: {e}\n")
        return 0

    built = _build_summary(payload)
    if built is None:
        return 0
    name, body = built

    try:
        subprocess.run(
            [sys.executable, GRC_PATH, "add", name, body, "--group", GROUP, "--source", "text"],
            check=False,
            timeout=20,
            capture_output=True,
        )
    except Exception as e:  # noqa: BLE001 — fail soft, always exit 0
        sys.stderr.write(f"[graphiti-hook] grc add failed: {e}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
