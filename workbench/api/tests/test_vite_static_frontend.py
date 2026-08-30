"""Focused Vite SPA/static-asset serving contract.

Byline: Codex · GPT-5.6-Sol · 2026-08-30.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from main import _WorkbenchStaticFiles


def _client(tmp_path) -> TestClient:
    (tmp_path / "index.html").write_text("<title>Workbench Vite entry</title>", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("window.__workbench = true", encoding="utf-8")
    application = FastAPI()
    application.mount("/", _WorkbenchStaticFiles(directory=str(tmp_path), html=True), name="static")
    return TestClient(application)


def test_extensionless_deep_link_falls_back_to_vite_entry(tmp_path) -> None:
    response = _client(tmp_path).get("/evidence/preview")

    assert response.status_code == 200
    assert "Workbench Vite entry" in response.text


def test_existing_asset_is_served_without_spa_fallback(tmp_path) -> None:
    response = _client(tmp_path).get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "window.__workbench = true"


def test_missing_asset_like_path_remains_not_found(tmp_path) -> None:
    response = _client(tmp_path).get("/assets/missing.js")

    assert response.status_code == 404
    assert "Workbench Vite entry" not in response.text


def test_missing_api_path_never_receives_spa_html(tmp_path) -> None:
    response = _client(tmp_path).get("/api/missing")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "Workbench Vite entry" not in response.text
