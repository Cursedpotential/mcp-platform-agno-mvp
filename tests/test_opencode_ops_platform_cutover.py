"""Focused contracts for the OpenCode-ops Platform API cutover.

Byline: Codex · GPT-5.6-Sol · 2026-08-29.
"""

from __future__ import annotations

import importlib.util
import json
from argparse import Namespace
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tool-skills" / "opencode-ops" / "scripts" / "oc.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("opencode_ops_oc", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retired_agentos_surfaces_are_absent_from_live_cli() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "AGENTOS" not in source
    assert "OS_SECURITY_KEY" not in source
    assert "/info" not in source
    assert "/knowledge/search" not in source
    assert "agentos" not in source.lower()


def test_platform_bearer_is_reread_from_runtime_file(tmp_path: Path) -> None:
    oc = _load_module()
    bearer_file = tmp_path / "platform-api-bearer"
    oc.PLATFORM_API_BEARER_SECRET_FILE = str(bearer_file)

    bearer_file.write_text("first\n", encoding="utf-8")
    assert oc.get_platform_api_bearer() == "first"

    bearer_file.write_text("rotated\n", encoding="utf-8")
    assert oc.get_platform_api_bearer() == "rotated"


def test_runs_list_uses_platform_api_and_runtime_file_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    oc = _load_module()
    calls: list[tuple[str, str, dict]] = []
    monkeypatch.setattr(oc, "PLATFORM_API_URL", "http://platform-api:8000")
    monkeypatch.setattr(oc, "get_platform_api_bearer", lambda: "runtime-file-secret")

    def fake_http_json(method: str, url: str, **kwargs):
        calls.append((method, url, kwargs))
        return 200, []

    monkeypatch.setattr(oc, "http_json", fake_http_json)
    args = Namespace(action="list", id=None, file=None, timeout=2.0, json=False)

    assert oc.cmd_runs(args) == 0
    assert calls == [
        (
            "GET",
            "http://platform-api:8000/v1/runs",
            {"bearer": "runtime-file-secret", "timeout": 2.0},
        )
    ]


def test_runs_start_uses_native_multipart_contract(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    oc = _load_module()
    upload = tmp_path / "sample.json"
    upload.write_bytes(b'{"message":"verbatim"}\x00')
    captured: dict = {}
    monkeypatch.setattr(oc, "PLATFORM_API_URL", "http://platform-api:8000")
    monkeypatch.setattr(oc, "get_platform_api_bearer", lambda: "runtime-file-secret")

    def fake_http_request(method: str, url: str, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return 202, {}, json.dumps({"run_id": "run-1"})

    monkeypatch.setattr(oc, "http_request", fake_http_request)
    args = Namespace(
        action="start",
        id=None,
        file=str(upload),
        workflow="chat-transcript",
        domain="context",
        timeout=2.0,
        json=False,
    )

    assert oc.cmd_runs(args) == 0
    assert captured["method"] == "POST"
    assert captured["url"] == "http://platform-api:8000/v1/runs"
    assert captured["bearer"] == "runtime-file-secret"
    assert captured["extra_headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="sample.json"' in captured["raw_body"]
    assert b'name="workflow"' in captured["raw_body"]
    assert upload.read_bytes() in captured["raw_body"]
    assert "json_body" not in captured


def test_generic_ksearch_fails_closed_without_network(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    oc = _load_module()

    def forbidden_network(*_args, **_kwargs):
        raise AssertionError("generic search must not make a network call")

    monkeypatch.setattr(oc, "http_json", forbidden_network)
    args = Namespace(query="anything", limit=10, timeout=2.0, json=False)

    assert oc.cmd_ksearch(args) == 1
    assert "generic knowledge search is retired" in capsys.readouterr().err


def test_mcp_catalog_is_contextforge_only() -> None:
    oc = _load_module()
    parser = oc.build_parser()

    parsed = parser.parse_args(["tools", "list", "--server", "contextforge"])
    assert parsed.server == "contextforge"
    with pytest.raises(SystemExit):
        parser.parse_args(["tools", "list", "--server", "agentos"])
