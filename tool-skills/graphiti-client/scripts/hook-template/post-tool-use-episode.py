#!/usr/bin/env python3
"""
TEMPLATE — PostToolUse hook that writes a Graphiti episode via `grc add`.

DESIGN ONLY. Not registered in any plugin's hooks.json/settings.json. A plugin
author copies this into their own hooks/ dir, tightens _should_record(), and
wires it in `hooks/hooks.json` matched to the specific tool(s) worth recording.

Contract: Claude Code invokes PostToolUse hooks with a JSON payload on stdin,
e.g. {"tool_name": "...", "tool_input": {...}, "tool_response": {...}, ...}.
This script must ALWAYS exit 0 (fail soft) — a Graphiti outage or a bug here
must never block or fail the tool call that just happened.

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
NAME_PREFIX = os.environ.get("GRC_HOOK_NAME_PREFIX", "hook:")


def _should_record(tool_name: str, tool_input: dict, tool_response: dict) -> bool:
    """PLACEHOLDER heuristic — replace with a real, plugin-specific filter
    before wiring this in. Default: only fires for Write/Edit and only if the
    resulting content looks non-trivial (crude length check) — deliberately
    permissive so the template is visibly a starting point, not a real gate.
    """
    if tool_name not in ("Write", "Edit"):
        return False
    content = json.dumps(tool_input)
    return len(content) > 80


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001 — fail soft, always exit 0
        sys.stderr.write(f"[graphiti-hook] failed to parse stdin: {e}\n")
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    tool_response = payload.get("tool_response", {})

    if not _should_record(tool_name, tool_input, tool_response):
        return 0

    file_path = tool_input.get("file_path", "unknown")
    name = f"{NAME_PREFIX} {tool_name} on {file_path}"
    body = (
        f"Tool {tool_name} was called on {file_path}. "
        f"Auto-recorded by the graphiti-client PostToolUse hook template — "
        f"tighten _should_record() before relying on this in production."
    )

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
