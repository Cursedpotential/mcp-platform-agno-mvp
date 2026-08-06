# Byline: Codex · GPT-5 · 2026-08-03
"""AgentOS repair-workbench participant and guardrail tests."""

from __future__ import annotations

from app.service import repair_agents


def test_participants_are_discovered_from_live_agentos_contract(monkeypatch) -> None:
    def fake_spine(method: str, path: str, **kwargs):
        if path == "/agents":
            return [{"id": "ingestion-orchestrator", "name": "Ingestion Orchestrator", "role": "Ingest"}]
        return [{"id": "platform-ops", "name": "Platform Ops", "role": "Operate"}]

    monkeypatch.setattr(repair_agents, "spine_json", fake_spine)
    participants = repair_agents.list_participants()
    assert [(item["type"], item["id"]) for item in participants] == [
        ("agent", "ingestion-orchestrator"),
        ("team", "platform-ops"),
    ]
    assert all(item["recommended"] for item in participants)


def test_agent_review_is_real_nonstreaming_agentos_run_and_forbids_writes(monkeypatch) -> None:
    captured: dict = {}

    def fake_spine(method: str, path: str, **kwargs):
        captured.update({"method": method, "path": path, **kwargs})
        return {"run_id": "run-1", "session_id": "session-1", "content": "proposal"}

    monkeypatch.setattr(repair_agents, "spine_json", fake_spine)
    result = repair_agents.run_review(
        participant_type="agent",
        participant_id="ingestion-orchestrator",
        path="/evidence/export.json",
        task="Review it",
        assessment={"status": "damaged"},
        session_id=None,
    )
    assert result["run_id"] == "run-1"
    assert captured["path"] == "/agents/ingestion-orchestrator/runs"
    assert captured["data"]["stream"] == "false"
    assert "Do NOT call repair.write-derived" in captured["data"]["message"]
    assert "return a PROPOSAL" in captured["data"]["message"]
