from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOWS = ROOT / "deploy/docker/n8n/workflows/proffer"


def _workflow(name: str) -> dict:
    return json.loads((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_repair_activity_exports_are_inactive_reference_only_wrappers() -> None:
    expected = {
        "wf-assess-source-repair-activity.json": (
            "proffer/assess-source-repair-activity",
            "/activities/assess_source_repair_activity",
            {"original", "filesystem_metadata", "container_manifest", "metadata_manifest"},
        ),
        "wf-resolve-source-repair-activity.json": (
            "proffer/resolve-source-repair-activity",
            "/activities/resolve_source_repair_activity",
            {"original", "repair_assessment", "repair_decision"},
        ),
    }
    for filename, (webhook_path, runtime_path, refs) in expected.items():
        workflow = _workflow(filename)
        assert workflow["active"] is False
        assert len(workflow["nodes"]) == 5
        webhook = next(node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.webhook")
        assert webhook["parameters"]["path"] == webhook_path
        assert webhook["parameters"]["authentication"] == "headerAuth"
        request = next(node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.httpRequest")
        assert request["parameters"]["url"].endswith(runtime_path)
        assert request["parameters"]["authentication"] == "genericCredentialType"
        validator = next(node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.code")
        script = validator["parameters"]["jsCode"]
        assert all(ref in script for ref in refs)
        assert "binary" in script
        assert "repair_decision" in script if "resolve" in filename else "original" in script


def test_temporal_routes_match_checked_in_repair_webhooks() -> None:
    # Since the flow-binding registry (d0b18f5) the repair webhooks are bound from the
    # checked-in workflow JSON, not hard-coded in n8n_client.go; assert the JSON side.
    assess = _workflow("wf-assess-source-repair-activity.json")
    resolve = _workflow("wf-resolve-source-repair-activity.json")
    paths = {
        node["parameters"].get("path")
        for wf in (assess, resolve)
        for node in wf["nodes"]
        if "path" in node.get("parameters", {})
    }
    assert {"proffer/assess-source-repair-activity", "proffer/resolve-source-repair-activity"} <= paths
