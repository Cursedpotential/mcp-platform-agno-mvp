# Byline: Claude Code · Sonnet (agent) · 2026-07-21
"""Unit tests for app/service/copilot.py's context-building — the OpenCode
client itself is mocked out (monkeypatch on app.repo.opencode_client), so
these never touch the network. Covers: model-string parsing, run/file
digest building (found + not-found/unreachable), preamble composition, and
ask()/continue_ask() wiring the built preamble into the outgoing prompt.
"""

from __future__ import annotations

import pytest

from app.service import chat_context, copilot
from app.service.copilot_presets import DEFAULT_PRESETS, list_presets
from app.service.runs import RunsError


def test_split_model_default(monkeypatch):
    monkeypatch.setattr(copilot.settings, "opencode_model", "groq/llama-3.3-70b-versatile")
    assert copilot._split_model(None) == ("groq", "llama-3.3-70b-versatile")


def test_split_model_explicit():
    assert copilot._split_model("nvidia/z-ai/glm-5.2") == ("nvidia", "z-ai/glm-5.2")


def test_split_model_invalid_raises():
    with pytest.raises(copilot.CopilotError) as exc:
        copilot._split_model("not-a-provider-slash-model")
    assert exc.value.status_code == 400


def test_build_preamble_empty_context():
    assert copilot.build_preamble(None) == ""
    assert copilot.build_preamble({}) == ""


def test_build_preamble_page_only():
    preamble = copilot.build_preamble({"page": "runs"})
    assert "runs" in preamble
    assert "run_id" not in preamble  # no run attached -> no digest section


def test_run_digest_success(monkeypatch):
    def fake_get_run(run_id):
        assert run_id == "run-123"
        return {
            "run_id": "run-123",
            "workflow": "chat-transcript",
            "mode": "auto",
            "status": "failed",
            "domain": "timeline_relationship",
            "gate_state": None,
            "error": "boom",
            "stages": [{"seq": 1, "name": "custody", "status": "success", "output": {"sha256": "abc"}}],
        }

    monkeypatch.setattr(chat_context, "get_run", fake_get_run)
    digest = copilot._run_digest("run-123")
    assert "run-123" in digest
    assert "chat-transcript" in digest
    assert "custody" in digest


def test_run_digest_unavailable_degrades(monkeypatch):
    def fake_get_run(run_id):
        raise RunsError("run 'run-404' not found", 404)

    monkeypatch.setattr(chat_context, "get_run", fake_get_run)
    digest = copilot._run_digest("run-404")
    assert "run-404" in digest
    assert "unavailable" in digest


def test_file_digest_found(monkeypatch):
    def fake_get(file_id):
        assert file_id == "sha-abc"
        return {
            "id": "sha-abc",
            "name": "chat.md",
            "mime": "text/markdown",
            "detected_type": "chat_export",
            "meta": {"domain": "legal_strategy"},
            "text": "x" * 5000,
        }

    monkeypatch.setattr(chat_context.staging, "get", fake_get)
    digest = copilot._file_digest("sha-abc")
    assert "chat.md" in digest
    # text preview must be capped, not the full 5000 chars
    assert digest.count("x") <= copilot._FILE_TEXT_PREVIEW_CHARS + 100


def test_file_digest_not_found(monkeypatch):
    monkeypatch.setattr(chat_context.staging, "get", lambda file_id: None)
    digest = copilot._file_digest("missing")
    assert "not found" in digest


def test_build_preamble_with_run_and_file(monkeypatch):
    monkeypatch.setattr(chat_context, "get_run", lambda run_id: {"run_id": run_id, "stages": []})
    monkeypatch.setattr(
        chat_context.staging,
        "get",
        lambda file_id: {"id": file_id, "name": "f.md", "text": "hi"},
    )
    preamble = copilot.build_preamble({"page": "intake", "run_id": "r1", "file_id": "f1"})
    assert "intake" in preamble
    assert "r1" in preamble
    assert "f.md" in preamble
    assert preamble.endswith("---\n\n")


class _FakeOpenCodeClient:
    """Stand-in for app.repo.opencode_client — records calls, returns canned replies."""

    def __init__(self):
        self.created_directories = []
        self.sent = []

    def create_session(self, directory=None, timeout=30.0):
        self.created_directories.append(directory)
        return "session-1"

    def send_message(self, session_id, provider_id, model_id, prompt, directory=None, timeout=180.0):
        self.sent.append((session_id, provider_id, model_id, prompt, directory))
        return ("ack", None)


def test_ask_injects_preamble_and_creates_session(monkeypatch):
    fake = _FakeOpenCodeClient()
    monkeypatch.setattr(copilot, "opencode_client", fake)
    monkeypatch.setattr(copilot.settings, "opencode_workspace_dir", "/workspace/copilot")

    result = copilot.ask("what happened?", context={"page": "runs"}, model="groq/llama-3.3-70b-versatile")

    assert result == {"reply": "ack", "session_id": "session-1", "model": "groq/llama-3.3-70b-versatile"}
    assert fake.created_directories == ["/workspace/copilot"]
    (session_id, provider_id, model_id, prompt, directory) = fake.sent[0]
    assert session_id == "session-1"
    assert provider_id == "groq"
    assert model_id == "llama-3.3-70b-versatile"
    assert "runs" in prompt  # preamble made it into the outgoing prompt
    assert prompt.endswith("what happened?")
    assert directory == "/workspace/copilot"


def test_continue_ask_skips_session_create(monkeypatch):
    fake = _FakeOpenCodeClient()
    monkeypatch.setattr(copilot, "opencode_client", fake)

    result = copilot.continue_ask("existing-session", "follow up", model="groq/llama-3.3-70b-versatile")

    assert result["session_id"] == "existing-session"
    assert fake.created_directories == []  # no new session for a continue
    assert fake.sent[0][3] == "follow up"  # no preamble re-injected


def test_default_presets_shape():
    ids = {p["id"] for p in DEFAULT_PRESETS}
    assert "summarize-file" in ids
    assert "diagnose-run" in ids
    for preset in DEFAULT_PRESETS:
        assert preset["wants_context"] in ("file", "run", None)


def test_list_presets_no_override_file(monkeypatch, tmp_path):
    monkeypatch.setattr(copilot.settings, "copilot_presets_path", str(tmp_path / "nope.json"))
    presets = list_presets()
    assert len(presets) == len(DEFAULT_PRESETS)


def test_list_presets_override_merges(monkeypatch, tmp_path):
    import json as _json

    override_path = tmp_path / "presets.json"
    override_path.write_text(
        _json.dumps(
            [
                {
                    "id": "summarize-file",
                    "label": "Summarize (custom)",
                    "prompt": "custom prompt",
                    "wants_context": "file",
                },
                {"id": "new-one", "label": "New preset", "prompt": "do the thing", "wants_context": None},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(copilot.settings, "copilot_presets_path", str(override_path))
    presets = {p["id"]: p for p in list_presets()}
    assert presets["summarize-file"]["label"] == "Summarize (custom)"
    assert presets["new-one"]["prompt"] == "do the thing"
    assert len(presets) == len(DEFAULT_PRESETS) + 1
