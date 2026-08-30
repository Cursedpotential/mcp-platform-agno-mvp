# Byline: Claude Code · Sonnet 5 · 2026-08-26
# Byline: Codex · GPT-5.6-Sol · 2026-08-29 (framework-neutral ingest route contract)
"""D-082 permanent AI-chat evidence fence (GAP-032/WP-C01) at the Workbench
promote service. A chat_export-detected staged file must be denied locally —
no HTTP call to the platform spine at all — while a doc-detected file keeps
its existing spine-promotion behavior unchanged."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Request
from app.service import promote


@pytest.mark.asyncio
async def test_chat_export_is_denied_without_any_network_call(monkeypatch):
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("no HTTP call should be made for a chat_export promote attempt")

    monkeypatch.setattr(httpx.AsyncClient, "post", _must_not_be_called)
    monkeypatch.setattr(httpx.AsyncClient, "get", _must_not_be_called)

    result = await promote._promote_chat_export({"id": "sha", "name": "x.json"}, client=object())

    assert result["status"] == "failed"
    assert result["denied"] is True
    assert "D-082" in result["error"]
    assert "permanent" in result["error"].lower()


@pytest.mark.asyncio
async def test_promote_dispatches_chat_export_to_the_denial_path(monkeypatch):
    monkeypatch.setattr(
        promote.staging,
        "get",
        lambda file_id: {
            "id": file_id,
            "name": "conversations.json",
            "detected_type": "chat_export",
            "meta": {},
            "r2_key": "irrelevant",
            "text": "",
        },
    )
    updates = []
    monkeypatch.setattr(
        promote.staging,
        "update_status",
        lambda file_id, status, promote_result=None: (
            updates.append((status, promote_result))
            or {"id": file_id, "status": status, "promote_result": promote_result}
        ),
    )

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("no HTTP call should be made for a chat_export promote attempt")

    monkeypatch.setattr(httpx.AsyncClient, "post", _must_not_be_called)
    monkeypatch.setattr(httpx.AsyncClient, "get", _must_not_be_called)

    result = await promote.promote("sha")

    assert result["status"] == "failed"
    assert result["error"] is not None
    assert "D-082" in result["error"]
    # First update_status call is the "promoting" transition; second is the
    # terminal denial — confirms the denial is recorded, not silently dropped.
    assert updates[-1][0] == "failed"
    assert updates[-1][1]["denied"] is True


@pytest.mark.asyncio
async def test_doc_promote_uses_framework_neutral_ingest_and_durable_run_contract(monkeypatch, tmp_path):
    """Exercise the real replacement URL and multipart contracts through ASGI."""
    app = FastAPI()
    captured = {}

    @app.post("/v1/ingest", status_code=202)
    async def ingest(request: Request):
        form = await request.form()
        upload = form["file"]
        captured["form"] = {key: str(value) for key, value in form.items() if key != "file"}
        captured["filename"] = upload.filename
        captured["bytes"] = await upload.read()
        captured["authorization"] = request.headers.get("authorization")
        return {"run_id": "receipt-1", "workflow": "framework-neutral-ingest", "status": "running"}

    @app.get("/v1/runs/{run_id}")
    async def run_status(run_id: str, request: Request):
        captured["polled_run_id"] = run_id
        captured["poll_authorization"] = request.headers.get("authorization")
        return {"run_id": run_id, "status": "completed", "artifact_id": "artifact-1"}

    async def _fake_load_file_bytes(record):
        return b"hello", record["name"]

    monkeypatch.setattr(promote, "_load_file_bytes", _fake_load_file_bytes)
    secret = tmp_path / "os-security-key"
    secret.write_bytes(b"server-only-token")
    monkeypatch.setattr(promote.settings, "platform_api_bearer_secret_file", str(secret))
    monkeypatch.setattr(promote.settings, "platform_api_url", "http://platform-api:8000")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://platform-api:8000") as client:
        result = await promote._promote_doc(
            {
                "id": "sha",
                "name": "doc.txt",
                "mime": "text/plain",
                "meta": {
                    "matter_id": "matter-7",
                    "domain": "legal",
                    "sha256": "untrusted-metadata",
                    "original_name": "wrong-name.txt",
                },
            },
            client,
        )

    assert result == {
        "status": "promoted",
        "run_id": "receipt-1",
        "content_id": "artifact-1",
        "artifact_id": "artifact-1",
    }
    assert captured["filename"] == "doc.txt"
    assert captured["bytes"] == b"hello"
    assert captured["form"]["lane"] == "context"
    assert captured["form"]["matter_id"] == "matter-7"
    assert captured["form"]["engine"] == "auto"
    assert captured["form"]["allow_fallback"] == "true"
    assert captured["form"]["custody_tier"] == "light"
    assert '"sha256": "sha"' in captured["form"]["source_identity"]
    assert '"original_name": "doc.txt"' in captured["form"]["source_identity"]
    assert "untrusted-metadata" not in captured["form"]["source_identity"]
    assert captured["authorization"] == "Bearer server-only-token"
    assert captured["polled_run_id"] == "receipt-1"
    assert captured["poll_authorization"] == "Bearer server-only-token"


@pytest.mark.asyncio
async def test_completed_ingest_without_artifact_id_fails_closed(monkeypatch, tmp_path):
    app = FastAPI()

    @app.post("/v1/ingest", status_code=202)
    async def ingest():
        return {"run_id": "receipt-no-artifact", "status": "running"}

    @app.get("/v1/runs/{run_id}")
    async def run_status(run_id: str):
        return {"run_id": run_id, "status": "completed", "artifact_id": None}

    async def _fake_load_file_bytes(record):
        return b"hello", record["name"]

    monkeypatch.setattr(promote, "_load_file_bytes", _fake_load_file_bytes)
    secret = tmp_path / "os-security-key"
    secret.write_bytes(b"server-only-token")
    monkeypatch.setattr(promote.settings, "platform_api_bearer_secret_file", str(secret))
    monkeypatch.setattr(promote.settings, "platform_api_url", "http://platform-api:8000")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://platform-api:8000") as client:
        result = await promote._promote_doc({"id": "sha", "name": "doc.txt", "meta": {}}, client)

    assert result["status"] == "failed"
    assert result["run_id"] == "receipt-no-artifact"
    assert result["error"] == "completed ingest receipt has no artifact_id"


@pytest.mark.asyncio
async def test_original_object_failure_never_substitutes_staged_text(monkeypatch):
    def fail_object_fetch(key):
        raise RuntimeError(f"missing object {key}")

    monkeypatch.setattr(promote, "get_object", fail_object_fetch)

    with pytest.raises(promote.PromoteError, match="original source bytes are unavailable") as error:
        await promote._load_file_bytes(
            {
                "name": "source.md",
                "r2_key": "original/source.md",
                "text": "derivative text that must never be substituted",
            }
        )

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_elapsed_poll_window_keeps_durable_run_promoting(monkeypatch, tmp_path):
    app = FastAPI()
    polls = []

    @app.post("/v1/ingest", status_code=202)
    async def ingest():
        return {"run_id": "receipt-still-running", "status": "running"}

    @app.get("/v1/runs/{run_id}")
    async def run_status(run_id: str):
        polls.append(run_id)
        return {"run_id": run_id, "status": "running"}

    async def _fake_load_file_bytes(record):
        return b"hello", record["name"]

    monkeypatch.setattr(promote, "_POLL_TIMEOUT_S", -1)
    monkeypatch.setattr(promote, "_load_file_bytes", _fake_load_file_bytes)
    secret = tmp_path / "os-security-key"
    secret.write_bytes(b"server-only-token")
    monkeypatch.setattr(promote.settings, "platform_api_bearer_secret_file", str(secret))
    monkeypatch.setattr(promote.settings, "platform_api_url", "http://platform-api:8000")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://platform-api:8000") as client:
        result = await promote._promote_doc({"id": "sha", "name": "doc.txt", "meta": {}}, client)

    assert polls == []
    assert result == {
        "status": "promoting",
        "run_id": "receipt-still-running",
        "pending": True,
        "detail": "durable ingest continues; polling window elapsed before a terminal receipt",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("poll_status", [404, 503])
async def test_poll_failure_preserves_accepted_run_identity(monkeypatch, tmp_path, poll_status):
    app = FastAPI()

    @app.post("/v1/ingest", status_code=202)
    async def ingest():
        return {"run_id": "receipt-accepted", "status": "running"}

    @app.get("/v1/runs/{run_id}", status_code=poll_status)
    async def run_status(run_id: str):
        return {"run_id": run_id, "detail": "temporarily unavailable"}

    async def _fake_load_file_bytes(record):
        return b"hello", record["name"]

    monkeypatch.setattr(promote, "_load_file_bytes", _fake_load_file_bytes)
    secret = tmp_path / "platform-api-bearer"
    secret.write_bytes(b"server-only-token\n")
    monkeypatch.setattr(promote.settings, "platform_api_bearer_secret_file", str(secret))
    monkeypatch.setattr(promote.settings, "platform_api_url", "http://platform-api:8000")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://platform-api:8000") as client:
        result = await promote._promote_doc({"id": "sha", "name": "doc.txt", "meta": {}}, client)

    assert result == {
        "status": "promoting",
        "run_id": "receipt-accepted",
        "pending": True,
        "detail": "durable ingest was accepted; receipt polling is temporarily unavailable",
    }
