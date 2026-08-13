"""Atomic tool: Gemini markdown export -> NormalizedRecords.

Format: files with **You:** / **Gemini:** (or **Model:**) role markers,
optionally preceded by a YAML frontmatter header and `# Title` line.

Example:
    # Abusive Relationship: Seeking Honest Talk
    Exported on: 4/14/2026, 7:08:32 PM
    ---
    **You:**
    message text here
    **Gemini:**
    response text here
Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.contracts.records import NormalizedRecord, RecordType
from server.tools.registry import register
from server.tools._common import records_out

# Providers emit both ``**You:**`` (colon inside bold) and ``**You**:``.
_ROLE_RE = re.compile(r"^\*\*(You|Gemini|Model|Assistant|User)(?::\*\*|\*\*:)\s*$", re.IGNORECASE)
_TITLE_RE = re.compile(r"^#\s+(.+)$")
_EXPORT_DATE_RE = re.compile(r"^Exported on:\s*(.+)$", re.IGNORECASE)


def _parse_gemini_md(text: str) -> tuple[str, str | None, list[tuple[str, str]]]:
    """Parse Gemini markdown into (title, export_date, [(role, content)])."""
    lines = text.split("\n")
    title = None
    export_date = None
    messages: list[tuple[str, str]] = []
    current_role = None
    current_lines: list[str] = []

    for line in lines:
        # Check for title
        m = _TITLE_RE.match(line)
        if m:
            title = m.group(1).strip()
            continue

        # Check for export date
        m = _EXPORT_DATE_RE.match(line)
        if m:
            export_date = m.group(1).strip()
            continue

        # Skip frontmatter separator
        if line.strip() == "---" and title and not current_role:
            continue

        # Check for role marker
        m = _ROLE_RE.match(line)
        if m:
            # Flush previous message
            if current_role and current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    messages.append((current_role, content))
            role_raw = m.group(1).lower()
            current_role = "user" if role_raw == "you" else "assistant"
            current_lines = []
            continue

        # Accumulate content
        if current_role is not None:
            current_lines.append(line)

    # Flush last message
    if current_role and current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            messages.append((current_role, content))

    return title or "untitled", export_date, messages


def _parse_export_date(date_str: str | None) -> datetime | None:
    """Best-effort parse of 'Exported on: 4/14/2026, 7:08:32 PM'."""
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y, %I:%M:%S %p", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@register(
    id="transcripts.gemini-md",
    capability="parse.transcript",
    description="Gemini markdown export (**You:** / **Gemini:** markers) -> normalized message records",
    accept=lambda hint, size: hint.endswith((".md", ".txt")),
    provenance="new module (chat sample format detection)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    text = path.read_text(encoding="utf-8", errors="replace")

    # Quick rejection: must have role markers
    if not re.search(r"\*\*(You|Gemini|Model)(?::\*\*|\*\*:)", text, re.IGNORECASE):
        raise ValueError("not a Gemini markdown export (no **You:** / **Gemini:** markers)")

    title, export_date_str, messages = _parse_gemini_md(text)
    if not messages:
        raise ValueError("Gemini markdown parsed but found zero messages")

    export_dt = _parse_export_date(export_date_str)
    conv_id = f"gemini-md-{path.stem}"

    records: list[NormalizedRecord] = []
    for role, content in messages:
        records.append(
            NormalizedRecord(
                record_type=RecordType.message,
                source="gemini-md",
                conversation_id=conv_id,
                role=role,
                content=content,
                occurred_at=export_dt,
                attrs={"conversation_title": title},
            )
        )

    return records_out(records, conversation_count=1)
