"""Dynamic Go/Python parser routing for AI-chat exports.

This module owns parsing only. Storage, chunking, classification, and
projection live in ``context_chat_ingest``.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.contracts.records import NormalizedRecord
from server.tools.registry import load_builtin_tools, registry

VALID_ENGINES = ("auto", "python", "go")


def _with_source_meta(
    parsed: tuple[list[NormalizedRecord], str, list[dict[str, Any]]],
    source_meta: dict[str, Any] | None,
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    """Attach archive/member provenance regardless of which parser ran."""

    if not source_meta:
        return parsed
    records, parser_id, attempts = parsed
    enriched = [record.model_copy(update={"attrs": {**source_meta, **record.attrs}}) for record in records]
    return enriched, parser_id, attempts


def parse_chat_export(
    path: Path | str,
    source_meta: dict[str, Any] | None = None,
    *,
    engine: str = "auto",
    format: str | None = None,
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    """Parse with strict explicit overrides and Go-primary auto routing."""

    path = Path(path)
    if engine not in VALID_ENGINES:
        raise ValueError(f"unknown engine {engine!r} (expected one of {VALID_ENGINES})")
    if not path.is_file():
        raise FileNotFoundError(path)

    if format is not None:
        from server.analysis.format_router import resolve_format_override

        engaged, go_id, python_id = resolve_format_override(format, engine)
        if engaged == "go":
            from server.analysis.sbv_transcript import parse_via_sbv

            return _with_source_meta(parse_via_sbv(path, format=go_id, source_meta=source_meta), source_meta)
        assert python_id is not None
        return _with_source_meta(_parse_via_pinned_tool(path, source_meta, python_id), source_meta)

    if engine == "go":
        from server.analysis.sbv_transcript import parse_via_sbv

        return _with_source_meta(parse_via_sbv(path, format=None, source_meta=source_meta), source_meta)
    if engine == "python":
        return _with_source_meta(_parse_via_registry(path, source_meta), source_meta)

    from server.analysis.format_router import detect_format

    detected = detect_format(path)
    if detected.format_id and detected.engine == "go":
        from server.analysis.sbv_transcript import parse_via_sbv

        try:
            return _with_source_meta(
                parse_via_sbv(path, format=detected.parse_format, source_meta=source_meta), source_meta
            )
        except Exception:
            pass
    if detected.python_parser_id:
        try:
            return _with_source_meta(
                _parse_via_registry(path, source_meta, preferred_tool_id=detected.python_parser_id), source_meta
            )
        except Exception:
            pass
    return _with_source_meta(_parse_via_registry(path, source_meta), source_meta)


def _parse_via_registry(
    path: Path,
    source_meta: dict[str, Any] | None = None,
    *,
    preferred_tool_id: str | None = None,
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    load_builtin_tools()
    candidates = registry.resolve(
        "parse.transcript",
        media_hint=path.name.lower(),
        size_bytes=path.stat().st_size,
    )
    if preferred_tool_id:
        candidates = sorted(candidates, key=lambda tool: tool.id != preferred_tool_id)
    if not candidates:
        raise ValueError(f"no parse.transcript tool accepts {path.name!r}")

    attempts: list[dict[str, Any]] = []
    for tool in candidates:
        try:
            result = tool.run({"path": str(path), "source_meta": source_meta or {}})
            attempts.append({"tool": tool.id, "ok": True})
            return [NormalizedRecord.model_validate(row) for row in result["records"]], tool.id, attempts
        except Exception as exc:
            attempts.append({"tool": tool.id, "ok": False, "error": str(exc)})
    raise ValueError(f"all parse.transcript candidates failed for {path.name!r}: {attempts}")


def _parse_via_pinned_tool(
    path: Path,
    source_meta: dict[str, Any] | None,
    tool_id: str,
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    load_builtin_tools()
    try:
        tool = registry.get(tool_id)
    except KeyError:
        known = sorted(tool.id for tool in registry.all() if tool.capability == "parse.transcript")
        raise ValueError(f"unknown python parser {tool_id!r}; registered parse.transcript tools: {known}") from None
    if tool.capability != "parse.transcript":
        raise ValueError(f"tool {tool_id!r} is not a parse.transcript tool")
    try:
        result = tool.run({"path": str(path), "source_meta": source_meta or {}})
    except Exception as exc:
        raise ValueError(
            f"parser {tool_id!r} rejected {path.name!r} under the explicit format override (no fallback): {exc}"
        ) from exc
    records = [NormalizedRecord.model_validate(row) for row in result["records"]]
    return records, tool.id, [{"tool": tool.id, "ok": True}]


def filter_conversations(
    records: list[NormalizedRecord],
    conversation_ids: set[str] | None,
) -> list[NormalizedRecord]:
    if conversation_ids is None:
        return records
    return [record for record in records if (record.conversation_id or "") in conversation_ids]
