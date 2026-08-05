# Byline: Codex · GPT-5 · 2026-08-03
"""Repair registry adapters and execution-policy regression tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from server.tools.gateway.toolfinder import execute_tool
from server.tools.registry import load_builtin_tools, registry

REPAIR_TOOL_IDS = {
    "repair.capabilities",
    "repair.audit-verify",
    "repair.detect",
    "repair.flag-damaged",
    "repair.pdf-derived",
    "repair.pdf-inspect",
    "repair.preview",
    "repair.quarantine-copy",
    "repair.quarantine-plan",
    "repair.write-derived",
}


def test_all_repair_adapters_are_registry_discoverable_with_policy() -> None:
    load_builtin_tools()
    manifest = {row["id"]: row for row in registry.manifest()}
    assert REPAIR_TOOL_IDS <= manifest.keys()
    assert manifest["repair.detect"]["execution_policy"] == "manual_or_auto"
    assert manifest["repair.detect"]["side_effect"] == "read_only"
    assert manifest["repair.write-derived"]["side_effect"] == "derived_write"
    assert manifest["repair.write-derived"]["execution_policy"] == "manual_approval_required"
    assert manifest["repair.flag-damaged"]["execution_policy"] == "manual_approval_required"
    assert manifest["repair.quarantine-copy"]["execution_policy"] == "manual_approval_required"


def test_gateway_writes_and_verifies_execution_audit(tmp_path: Path) -> None:
    from server.tools.gateway.content_store import ContentStore

    source = tmp_path / "sample.csv"
    source.write_text("name,value\na,1\n", encoding="utf-8")
    store = ContentStore(tmp_path / "gateway")
    result = execute_tool("repair.detect", {"path": str(source), "_execution_mode": "automatic"}, store=store)

    ledger = store.root / "audit" / "tool-executions.jsonl"
    verified = registry.get("repair.audit-verify").run({"ledger_path": str(ledger)})
    assert result["operation_id"]
    assert result["audit_chain_head"] == verified["chain_head"]
    assert verified["valid"] is True
    assert verified["entries"] == 2


def test_execution_audit_detects_tampering(tmp_path: Path) -> None:
    from server.tools.gateway.execution_audit import append_event, verify_ledger

    ledger = tmp_path / "audit.jsonl"
    append_event(ledger, {"operation_id": "one", "status": "started"})
    append_event(ledger, {"operation_id": "one", "status": "completed"})
    text = ledger.read_text(encoding="utf-8")
    ledger.write_text(text.replace('"status":"started"', '"status":"altered"'), encoding="utf-8")
    result = verify_ledger(ledger)
    assert result["valid"] is False
    assert any("event hash mismatch" in error for error in result["errors"])


def test_detect_and_preview_are_callable_through_registry(tmp_path: Path) -> None:
    load_builtin_tools()
    source = tmp_path / "broken.xml"
    source.write_text("<records><message>one<message>two</records>", encoding="utf-8")

    detection = registry.get("repair.detect").run({"path": str(source)})
    assert detection["detection"]["fmt"] == "xml"
    preview = registry.get("repair.preview").run({"path": str(source), "sample_limit": 2})
    assert preview["report"]["chunks_ok"] >= 1
    assert len(preview["samples"]) <= 2


def test_derived_repair_is_confined_to_artifact_root(tmp_path: Path) -> None:
    load_builtin_tools()
    source = tmp_path / "source.ndjson"
    source.write_text('{"ok": 1}\n', encoding="utf-8")
    root = tmp_path / "artifacts"
    with pytest.raises(ValueError, match="artifact_root"):
        registry.get("repair.write-derived").run(
            {
                "path": str(source),
                "artifact_root": str(root),
                "dest": str(tmp_path / "escape.ndjson"),
                "approved": True,
                "_execution_mode": "manual",
            }
        )


def test_quarantine_copy_requires_approval_and_retains_original(tmp_path: Path) -> None:
    load_builtin_tools()
    source = tmp_path / "source.xml"
    source.write_text("<broken>", encoding="utf-8")
    tool = registry.get("repair.quarantine-copy")
    payload = {
        "path": str(source),
        "dest": str(tmp_path / "to_be_deleted" / "source.xml"),
        "size": source.stat().st_size,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "ledger_path": str(tmp_path / "ledger.jsonl"),
    }
    with pytest.raises(PermissionError, match="approved"):
        tool.run(payload)
    with pytest.raises(PermissionError, match="operator approval endpoint"):
        execute_tool("repair.quarantine-copy", {**payload, "approved": True, "_execution_mode": "automatic"})
    with pytest.raises(PermissionError, match="operator approval endpoint"):
        execute_tool("repair.quarantine-copy", {**payload, "approved": True, "_execution_mode": "manual"})
    approved = execute_tool(
        "repair.quarantine-copy",
        {**payload, "approved": True, "_execution_mode": "manual"},
        approval_granted=True,
    )
    assert approved["result"]["entry"]["status"] == "quarantined"
    assert source.exists()
    assert Path(payload["dest"]).exists()
