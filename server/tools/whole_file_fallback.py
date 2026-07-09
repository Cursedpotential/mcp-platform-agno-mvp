"""Atomic tool: plain .md/.txt transcript -> one whole-file NormalizedRecord.

The deliberate FALLBACK unit: when no structured parser fits, the whole file
becomes one record (the knowledge engine chunks it downstream).
Provenance: new module (deliberate design, not a port).

NAMING IS LOAD-BEARING: auto-discovery imports server.tools modules
alphabetically and registration order = substitution preference, so this
module is named to sort AFTER every structured parse.transcript parser
(was markdown_transcript.py, which sorted before the perplexity wrappers
and would have swallowed their .md inputs — this tool never rejects a
non-empty file, so it must be the LAST candidate tried).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.evidence.normalize import NormalizedRecord, RecordType
from .registry import register
from ._common import records_out


@register(
    id="transcripts.markdown",
    capability="parse.transcript",
    description="Plain .md/.txt transcript -> one whole-file record (fallback)",
    accept=lambda hint, size: hint.endswith((".md", ".txt")),
    provenance="new module (deliberate whole-file fallback)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        raise ValueError("empty file — nothing to parse")
    rec = NormalizedRecord(
        record_type=RecordType.message,
        source="markdown-transcript",
        conversation_id=path.stem,
        role="transcript",
        participants=["owner"],
        content=text,
        attrs={"original_name": path.name},
    )
    return records_out([rec])
