# Byline: Codex · GPT-5 · 2026-08-03
"""Repair control-surface policy tests."""

from __future__ import annotations

import json

import pytest
from app.service import repairs
from app.service.tools import ToolsError


def _mcp(value):
    return {"content": [{"type": "text", "text": json.dumps(value)}]}


def test_lists_only_repair_cards(monkeypatch):
    servers: list[str] = []

    def fake_call(server, name, arguments):
        servers.append(server)
        return _mcp(
            [
                {"id": "repair.detect", "execution_policy": "manual_or_auto"},
                {"id": "parse.csv"},
            ]
        )

    monkeypatch.setattr(
        repairs,
        "call_tool",
        fake_call,
    )
    assert repairs.list_repair_tools() == [{"id": "repair.detect", "execution_policy": "manual_or_auto"}]
    assert servers == ["platform-tools"]


def test_manual_only_tool_requires_approval(monkeypatch):
    monkeypatch.setattr(
        repairs,
        "call_tool",
        lambda server, name, arguments: _mcp(
            {"id": "repair.quarantine-copy", "execution_policy": "manual_approval_required"}
        ),
    )
    with pytest.raises(ToolsError, match="explicit operator approval"):
        repairs.execute_manual("repair.quarantine-copy", {}, approved=False)


def test_approved_manual_tool_uses_operator_endpoint(monkeypatch):
    monkeypatch.setattr(
        repairs,
        "call_tool",
        lambda server, name, arguments: _mcp(
            {
                "id": "repair.write-derived",
                "execution_policy": "manual_approval_required",
                "side_effect": "derived_write",
            }
        ),
    )
    calls = []

    def fake_spine(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {
            "inline": True,
            "operation_id": kwargs["json"]["operation_id"],
            "audit_chain_head": "abc123",
            "result": {"derived": "/artifacts/repaired.json"},
        }

    monkeypatch.setattr("app.repo.spine_client.spine_json", fake_spine)
    result = repairs.execute_manual("repair.write-derived", {"path": "/evidence/source.json"}, approved=True)

    assert calls[0][0:2] == ("POST", "/v1/repairs/execute")
    assert calls[0][2]["json"]["approved"] is True
    assert result["result"]["_execution_audit"]["chain_head"] == "abc123"


def test_automatic_assessment_calls_applicable_read_only_tools(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake_call(server, name, arguments):
        calls.append((name, arguments))
        tool_id = arguments["tool_id"]
        if tool_id == "repair.detect":
            value = {"detection": {"fmt": "pdf"}, "cloud_only": False}
        elif tool_id == "repair.preview":
            value = {"report": {"chunks_failed": 1, "repairs": 2}}
        else:
            value = {"healthy": False}
        return _mcp({"tool_id": tool_id, "inline": True, "result": value})

    monkeypatch.setattr(repairs, "call_tool", fake_call)
    result = repairs.automatic_assessment("/evidence/damaged.pdf", None, 10)

    assert [args["tool_id"] for _, args in calls] == [
        "repair.detect",
        "repair.preview",
        "repair.pdf-inspect",
    ]
    assert result["write_performed"] is False
    operation_ids = {args["payload"]["_operation_id"] for _, args in calls}
    assert operation_ids == {result["operation_id"]}
    assert {item["action"] for item in result["recommendations"]} == {
        "repair.write-derived",
        "repair.flag-damaged",
    }


def test_automatic_assessment_never_opens_cloud_placeholder(monkeypatch):
    calls: list[str] = []

    def fake_call(server, name, arguments):
        calls.append(arguments["tool_id"])
        return _mcp(
            {
                "tool_id": "repair.detect",
                "inline": True,
                "result": {"detection": {"fmt": "unknown"}, "cloud_only": True},
            }
        )

    monkeypatch.setattr(repairs, "call_tool", fake_call)
    result = repairs.automatic_assessment("/cloud/export.json", None, 25)
    assert calls == ["repair.detect"]
    assert result["recommendations"][0]["action"] == "reacquire"
    assert result["write_performed"] is False


def test_repair_surface_rejects_non_repair_tool():
    with pytest.raises(ToolsError, match="Only repair"):
        repairs.describe_repair_tool("parse.csv")
