"""Release-gate tests for the direct-tailnet Workbench boundary.

Byline: Codex · GPT-5 · 2026-08-15
Byline: Codex · GPT-5 · 2026-08-29 (passwordless tailnet access)
"""

from __future__ import annotations

from app.runtime import auth
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from main import app as workbench_app
from starlette.middleware.base import BaseHTTPMiddleware


def _client(host: str) -> TestClient:
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

    return TestClient(app, client=(host, 50000))


def test_exact_health_path_is_the_only_public_exception() -> None:
    client = _client("172.18.0.4")

    assert client.get("/health").status_code == 200
    assert client.get("/health/").status_code == 403
    assert client.get("/api/matters").status_code == 403


def test_direct_tailnet_peer_sets_owner_principal() -> None:
    response = _client("100.101.22.33").get("/principal")

    assert response.status_code == 200
    assert response.json() == {"principal": "owner"}


def test_non_tailnet_peer_is_denied_even_with_auth_headers() -> None:
    client = _client("172.18.0.4")

    response = client.get(
        "/api/matters",
        headers={"Authorization": "Basic ignored", "X-Forwarded-For": "100.101.22.33"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Direct tailnet access required"}


def test_real_app_wiring_accepts_direct_tailnet_surface() -> None:
    client = TestClient(workbench_app, client=("100.101.22.33", 50000))

    assert client.get("/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/").status_code == 200
