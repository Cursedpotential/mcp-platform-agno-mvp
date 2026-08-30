"""Plain FastAPI host contract after the AgentOS retirement.

Byline: Codex · GPT-5.6-Sol · 2026-08-29
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api.main import create_app
from server.api.native_evidence_search_routes import WalkSearchContext
from server.evidence.search_capability import issue_walk_search_capability

_ROOT = Path(__file__).resolve().parents[1]
_MAIN = _ROOT / "server" / "api" / "main.py"
_RUN_ID = UUID("00000000-0000-4000-8000-000000000001")
_STEP_ID = UUID("00000000-0000-4000-8000-000000000002")
_CHECKPOINT_ID = UUID("00000000-0000-4000-8000-000000000003")
_AGENT_SEARCH_BODY = {
    "query": "what happened",
    "walk_run_id": str(_RUN_ID),
    "walk_step_id": str(_STEP_ID),
    "checkpoint_id": str(_CHECKPOINT_ID),
}


@dataclass
class _SearchResult:
    documents: list[object]
    kept: int = 0
    denied: int = 0
    audit_id: int = 91


def _composed_search_client(monkeypatch) -> TestClient:
    """Build the production composition with inert native dependencies."""

    from server.api import main as main_module
    from server.api import native_evidence_search_routes as search_routes
    from server.evidence import retrieval

    runtime = SimpleNamespace(
        store=object(),
        embedder=object(),
        projector=None,
        close=lambda: None,
    )

    async def resolve_walk_context(*_ids: UUID) -> WalkSearchContext:
        return WalkSearchContext(
            case_id="matter-1",
            actor="agent:ignorant",
            horizon=datetime(2025, 6, 1, tzinfo=timezone.utc),
            disclosure_tiers=("contemporaneous", "discovered"),
            horizon_policy="ignorant",
        )

    monkeypatch.setattr(main_module, "_build_native_evidence_runtime", lambda: runtime)
    monkeypatch.setattr(search_routes, "_resolve_walk_context", resolve_walk_context)
    monkeypatch.setattr(retrieval, "native_evidence_search", lambda *_args, **_kwargs: _SearchResult([]))
    return TestClient(create_app())


def _configure_owner_bearer(monkeypatch, tmp_path: Path, credential: str = "owner-test-key") -> Path:
    """Point the production reader at a temporary rotatable secret file."""

    from server.api import platform_auth

    bearer_file = tmp_path / "platform-api-bearer"
    bearer_file.write_text(credential, encoding="utf-8")
    monkeypatch.setattr(platform_auth, "_PLATFORM_API_BEARER_FILE", bearer_file)
    return bearer_file


def test_composition_root_has_no_agentos_or_agno_import() -> None:
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names} | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not any(name == "agno" or name.startswith("agno.") for name in imported)
    assert "AgentOS" not in {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "agno.os" not in sys.modules


def test_fresh_platform_api_import_loads_no_agno_modules() -> None:
    environment = os.environ.copy()
    environment.pop("NATIVE_EVIDENCE_ENABLED", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import server.api.main; "
                "loaded = sorted(name for name in sys.modules "
                "if name == 'agno' or name.startswith('agno.')); "
                "assert not loaded, loaded"
            ),
        ],
        cwd=_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_create_app_returns_plain_fastapi_with_native_routes(monkeypatch) -> None:
    monkeypatch.delenv("NATIVE_EVIDENCE_ENABLED", raising=False)
    app = create_app()
    assert type(app) is FastAPI

    paths = {route.path for route in app.routes}
    assert {
        "/health",
        "/v1/knowledge/reindex",
        "/v1/evidence/import",
        "/v1/runs",
        "/v1/records",
        "/v1/ingest",
        "/v1/entities",
        "/v1/matters",
        "/v1/repairs/execute",
    } <= paths
    assert not ({"/agents", "/teams", "/workflows", "/registry", "/mcp"} & paths)


def test_health_is_public_but_native_routes_keep_owner_bearer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NATIVE_EVIDENCE_ENABLED", raising=False)
    _configure_owner_bearer(monkeypatch, tmp_path)
    monkeypatch.delenv("PLATFORM_API_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    monkeypatch.delenv("AGENTOS_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    denied = client.get("/v1/records")
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == "Bearer"
    assert client.get("/v1/records", headers={"Authorization": "Bearer owner-test-key"}).status_code != 401


def test_composed_agent_search_preserves_signed_walk_authorization(monkeypatch, tmp_path: Path) -> None:
    _configure_owner_bearer(monkeypatch, tmp_path)
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "test-walk-signing-key")
    monkeypatch.delenv("PLATFORM_API_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    client = _composed_search_client(monkeypatch)
    capability = issue_walk_search_capability(_RUN_ID, _STEP_ID, _CHECKPOINT_ID)

    accepted = client.post(
        "/v1/evidence/search",
        headers={"Authorization": f"Bearer {capability}"},
        json=_AGENT_SEARCH_BODY,
    )
    denied = client.post(
        "/v1/evidence/search",
        headers={"Authorization": "Bearer owner-test-key"},
        json=_AGENT_SEARCH_BODY,
    )

    assert accepted.status_code == 200
    assert denied.status_code == 401
    assert denied.json() == {"detail": "walk search capability is invalid"}


def test_composed_operator_search_preserves_distinct_operator_authorization(monkeypatch, tmp_path: Path) -> None:
    _configure_owner_bearer(monkeypatch, tmp_path)
    monkeypatch.setenv("EVIDENCE_OPERATOR_SECURITY_KEY", "operator-test-key")
    monkeypatch.delenv("PLATFORM_API_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    client = _composed_search_client(monkeypatch)

    accepted = client.post(
        "/v1/operator/evidence/search",
        headers={"Authorization": "Bearer operator-test-key"},
        json={"query": "what happened", "case_id": "matter-1"},
    )
    denied = client.post(
        "/v1/operator/evidence/search",
        headers={"Authorization": "Bearer owner-test-key"},
        json={"query": "what happened", "case_id": "matter-1"},
    )

    assert accepted.status_code == 200
    assert denied.status_code == 401
    assert denied.json() == {"detail": "evidence search authorization failed"}


def test_self_auth_exemption_is_exact_and_does_not_open_neighboring_routes(monkeypatch, tmp_path: Path) -> None:
    _configure_owner_bearer(monkeypatch, tmp_path)
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "test-walk-signing-key")
    monkeypatch.delenv("PLATFORM_API_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    client = _composed_search_client(monkeypatch)
    capability = issue_walk_search_capability(_RUN_ID, _STEP_ID, _CHECKPOINT_ID)

    assert client.get("/v1/evidence/search", headers={"Authorization": f"Bearer {capability}"}).status_code == 401
    assert client.get("/v1/records", headers={"Authorization": f"Bearer {capability}"}).status_code == 401


def test_owner_bearer_rotates_from_file_between_requests(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NATIVE_EVIDENCE_ENABLED", raising=False)
    monkeypatch.delenv("PLATFORM_API_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    bearer_file = _configure_owner_bearer(monkeypatch, tmp_path, "first-owner-key")
    client = TestClient(create_app())

    assert client.get("/v1/records", headers={"Authorization": "Bearer first-owner-key"}).status_code != 401
    bearer_file.write_text("second-owner-key\n", encoding="utf-8")
    assert client.get("/v1/records", headers={"Authorization": "Bearer first-owner-key"}).status_code == 401
    assert client.get("/v1/records", headers={"Authorization": "Bearer second-owner-key"}).status_code != 401


def test_owner_auth_fails_closed_when_runtime_secret_is_missing_or_empty(monkeypatch, tmp_path: Path) -> None:
    from server.api import platform_auth

    monkeypatch.delenv("NATIVE_EVIDENCE_ENABLED", raising=False)
    monkeypatch.delenv("PLATFORM_API_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    missing = tmp_path / "missing-platform-api-bearer"
    monkeypatch.setattr(platform_auth, "_PLATFORM_API_BEARER_FILE", missing)
    client = TestClient(create_app())

    assert client.get("/v1/records", headers={"Authorization": "Bearer anything"}).status_code == 503
    missing.write_text("  \n", encoding="utf-8")
    assert client.get("/v1/records", headers={"Authorization": "Bearer anything"}).status_code == 503


def test_lifespan_runs_r2_initialization_and_ingest_recovery(monkeypatch) -> None:
    from server.api import runtime_support
    from server.ingest import service as ingest_service

    calls: list[tuple[str, object]] = []

    def ensure_r2() -> bool:
        calls.append(("r2", True))
        return True

    async def recover(*, projector=None) -> int:
        calls.append(("recovery", projector))
        return 2

    monkeypatch.delenv("NATIVE_EVIDENCE_ENABLED", raising=False)
    monkeypatch.setattr(runtime_support, "ensure_duckdb_r2_secret", ensure_r2)
    monkeypatch.setattr(ingest_service, "recover_incomplete_ingests", recover)

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200

    assert calls == [("r2", True), ("recovery", None)]
