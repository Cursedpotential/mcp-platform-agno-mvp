# Byline: Codex · GPT-5 · 2026-08-03
# Byline: Codex · GPT-5.6 · 2026-08-29 (ContextForge publication cutover)
"""Policy-aware access to the ContextForge-published repair suite.

The Workbench never imports the repair implementation.  It calls the same
progressive-disclosure gateway agents use, so manual and automatic operation
have one registry, one contract, and one enforcement point.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.service.tools import ToolsError, call_tool

_SERVER = "platform-tools"
_MANUAL_ONLY = "manual_approval_required"


def _decode_result(raw: dict[str, Any]) -> Any:
    """Extract a Python value from either MCP or agno tool-result envelopes."""
    if raw.get("isError"):
        messages = [str(item.get("text", "")) for item in raw.get("content", [])]
        raise ToolsError("; ".join(filter(None, messages)) or "Repair tool failed", 422)
    structured = raw.get("structuredContent")
    if structured is not None:
        return structured.get("result", structured) if isinstance(structured, dict) else structured
    for item in raw.get("content", []):
        if item.get("type") != "text":
            continue
        text = item.get("text", "")
        try:
            value = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return text
        return value.get("result", value) if isinstance(value, dict) else value
    return raw


def _meta(name: str, arguments: dict[str, Any]) -> Any:
    return _decode_result(call_tool(_SERVER, name, arguments))


def _execute_atomic(tool_id: str, payload: dict[str, Any]) -> Any:
    """Execute a registry tool and unwrap its inline gateway envelope."""
    result = _meta("execute_tool", {"tool_id": tool_id, "payload": payload})
    if isinstance(result, dict) and result.get("inline") is True and "result" in result:
        audit = {
            "operation_id": result.get("operation_id"),
            "chain_head": result.get("audit_chain_head"),
        }
        value = result["result"]
        if isinstance(value, dict):
            return {**value, "_execution_audit": audit}
        return {"value": value, "_execution_audit": audit}
    return result


def list_repair_tools() -> list[dict[str, Any]]:
    """Return compact repair cards, including execution and side-effect policy."""
    result = _meta("search_tools", {"query": "repair", "limit": 100})
    cards = result if isinstance(result, list) else result.get("tools", [])
    return [card for card in cards if str(card.get("id", "")).startswith("repair.")]


def describe_repair_tool(tool_id: str) -> dict[str, Any]:
    if not tool_id.startswith("repair."):
        raise ToolsError("Only repair.* tools are available from this surface", 400)
    result = _meta("describe_tool", {"tool_id": tool_id})
    if not isinstance(result, dict):
        raise ToolsError(f"Invalid contract returned for {tool_id}", 502)
    return result


def execute_manual(tool_id: str, payload: dict[str, Any], approved: bool) -> dict[str, Any]:
    """Execute through the authenticated ContextForge-published repair door."""
    contract = describe_repair_tool(tool_id)
    policy = contract.get("execution_policy", "manual_or_auto")
    if policy == _MANUAL_ONLY and not approved:
        raise ToolsError(f"{tool_id} requires explicit operator approval", 409)
    operation_id = str(uuid4())
    started = datetime.now(UTC)
    from app.repo.spine_client import SpineError, spine_json

    try:
        envelope = spine_json(
            "POST",
            "/v1/repairs/execute",
            json={"tool_id": tool_id, "payload": payload, "approved": approved, "operation_id": operation_id},
        )
    except SpineError as exc:
        raise ToolsError(exc.detail, exc.status_code) from exc
    result: Any = envelope
    if isinstance(envelope, dict) and envelope.get("inline") is True and "result" in envelope:
        audit = {"operation_id": envelope.get("operation_id"), "chain_head": envelope.get("audit_chain_head")}
        value = envelope["result"]
        result = (
            {**value, "_execution_audit": audit}
            if isinstance(value, dict)
            else {
                "value": value,
                "_execution_audit": audit,
            }
        )
    return {
        "operation_id": operation_id,
        "mode": "manual",
        "tool_id": tool_id,
        "execution_policy": policy,
        "side_effect": contract.get("side_effect", "read_only"),
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "result": result,
    }


def automatic_assessment(path: str, fmt: str | None, sample_limit: int) -> dict[str, Any]:
    """Run every applicable read-only assessment step and recommend next actions.

    Automatic mode never writes a derived artifact, ledger entry, or quarantine
    copy.  Those operations remain available through the manual endpoint after
    the operator reviews this assessment and supplies explicit destinations.
    """
    operation_id = str(uuid4())
    started = datetime.now(UTC)
    base: dict[str, Any] = {"path": path, "_execution_mode": "automatic", "_operation_id": operation_id}
    steps: list[dict[str, Any]] = []

    def run(tool_id: str, payload: dict[str, Any]) -> Any:
        step_started = datetime.now(UTC)
        try:
            result = _execute_atomic(tool_id, payload)
        except Exception as exc:
            steps.append(
                {
                    "tool_id": tool_id,
                    "status": "failed",
                    "started_at": step_started.isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                    "error": str(exc),
                }
            )
            raise
        steps.append(
            {
                "tool_id": tool_id,
                "status": "completed",
                "started_at": step_started.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "result": result,
            }
        )
        return result

    detection = run("repair.detect", base)
    detected_format = fmt or (detection.get("detection", {}).get("fmt") if isinstance(detection, dict) else None)
    cloud_only = bool(detection.get("cloud_only")) if isinstance(detection, dict) else False
    preview: dict[str, Any] = {}
    if not cloud_only:
        preview_payload = {**base, "sample_limit": sample_limit}
        if detected_format:
            preview_payload["format"] = detected_format
        preview_result = run("repair.preview", preview_payload)
        preview = preview_result if isinstance(preview_result, dict) else {}
        if detected_format == "pdf" or path.lower().endswith(".pdf"):
            run("repair.pdf-inspect", base)

    report = preview.get("report", {}) if isinstance(preview, dict) else {}
    damaged = bool(
        report.get("chunks_failed") or report.get("repairs") or report.get("lossy") or report.get("truncated")
    )
    recommendations: list[dict[str, str]] = []
    if cloud_only:
        recommendations.append(
            {"action": "reacquire", "reason": "Source is a cloud-only placeholder; repair must not hydrate it."}
        )
    elif damaged:
        recommendations.extend(
            [
                {
                    "action": "repair.write-derived",
                    "reason": "Create a separately hashed candidate; never overwrite the custody original.",
                },
                {
                    "action": "repair.flag-damaged",
                    "reason": "Record the source hash and observed damage in the append-only ledger.",
                },
            ]
        )
    else:
        recommendations.append(
            {"action": "ingest-original", "reason": "No structural repair was required by the bounded assessment."}
        )

    return {
        "operation_id": operation_id,
        "mode": "automatic_assessment",
        "started_at": started.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "status": "completed",
        "steps": steps,
        "recommendations": recommendations,
        "write_performed": False,
    }
