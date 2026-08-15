"""Release-gate tests for the mandatory Workbench authentication boundary.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

import base64

from app.runtime import auth
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from main import app as workbench_app
from starlette.middleware.base import BaseHTTPMiddleware


def _client(monkeypatch, key: str) -> TestClient:
    monkeypatch.setattr(auth.settings, "workbench_api_key", key)
    app = FastAPI()
    app.add_middleware(BaseHTTPMiddleware, dispatch=auth.authentication_middleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/principal")
    def principal(request: Request) -> dict[str, str]:
        return {"principal": request.state.principal}

    @app.get("/{path:path}")
    def protected_surface(path: str) -> dict[str, str]:
        return {"path": path}

    return TestClient(app)


def _basic(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def test_exact_health_path_is_the_only_public_exception(monkeypatch) -> None:
    client = _client(monkeypatch, "")

    assert client.get("/health").status_code == 200
    assert client.get("/health/").status_code == 503
    assert client.get("/api/matters").status_code == 503


def test_missing_configuration_fails_closed(monkeypatch) -> None:
    response = _client(monkeypatch, "").get("/docs")

    assert response.status_code == 503
    assert response.json() == {"detail": "Workbench authentication is not configured"}


def test_missing_or_invalid_credentials_get_basic_browser_challenge(monkeypatch) -> None:
    client = _client(monkeypatch, "correct-secret")

    for authorization in (None, "Bearer wrong", "Basic !!!", "Digest value"):
        headers = {"Authorization": authorization} if authorization else {}
        response = client.get("/api/matters", headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == 'Basic realm="Knowledge Workbench", charset="UTF-8"'


def test_valid_bearer_sets_owner_principal(monkeypatch) -> None:
    response = _client(monkeypatch, "correct-secret").get(
        "/principal",
        headers={"Authorization": "Bearer correct-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"principal": "owner"}


def test_valid_basic_supports_browser_login(monkeypatch) -> None:
    response = _client(monkeypatch, "correct-secret").get(
        "/principal",
        headers={"Authorization": _basic("owner", "correct-secret")},
    )

    assert response.status_code == 200
    assert response.json() == {"principal": "owner"}


def test_basic_rejects_wrong_owner_or_password(monkeypatch) -> None:
    client = _client(monkeypatch, "correct-secret")

    assert client.get("/principal", headers={"Authorization": _basic("admin", "correct-secret")}).status_code == 401
    assert client.get("/principal", headers={"Authorization": _basic("owner", "wrong")}).status_code == 401


def test_real_app_wiring_protects_docs_api_and_static_surface(monkeypatch) -> None:
    monkeypatch.setattr(auth.settings, "workbench_api_key", "correct-secret")
    client = TestClient(workbench_app)

    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/api/matters").status_code == 401
    assert client.get("/").status_code == 401
    assert (
        client.get(
            "/openapi.json",
            headers={"Authorization": "Bearer correct-secret"},
        ).status_code
        == 200
    )
