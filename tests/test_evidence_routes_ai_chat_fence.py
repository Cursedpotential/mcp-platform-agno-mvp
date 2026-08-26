"""D-082 permanent AI-chat evidence fence (GAP-032/WP-C01) at the REST
boundary: POST /v1/evidence/import must deny workflow="chat-transcript"
(the AI-chat vertical, and the only workflow this route ever accepted) with
403, before touching the multipart body's file, domain, or source_meta, and
without ever calling run_chat_transcript / reaching custody.
"""

from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api.evidence_routes import register_evidence_routes


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    register_evidence_routes(app, knowledge=None)

    # If the route ever reaches run_chat_transcript for a denied workflow,
    # this fails loudly instead of silently doing real work.
    import server.evidence.workflows as workflows_mod

    async def _must_not_be_called(*args, **kwargs):
        raise AssertionError("run_chat_transcript was called for a workflow that must be denied at the route")

    monkeypatch.setattr(workflows_mod, "run_chat_transcript", _must_not_be_called)

    return TestClient(app)


def test_chat_transcript_workflow_is_denied_with_403(client):
    response = client.post(
        "/v1/evidence/import",
        files={"file": ("conversations.json", io.BytesIO(b'[{"mapping": {}}]'), "application/json")},
        data={"workflow": "chat-transcript", "domain": "context"},
    )

    assert response.status_code == 403
    body = response.json()["detail"]
    assert body["denied"] is True
    assert body["workflow"] == "chat-transcript"
    assert "D-082" in body["reason"]


def test_chat_transcript_denial_ignores_domain_value(client):
    """Denial happens before domain validation — an otherwise-invalid domain
    must not change the outcome or leak a different error path."""
    response = client.post(
        "/v1/evidence/import",
        files={"file": ("conversations.json", io.BytesIO(b"{}"), "application/json")},
        data={"workflow": "chat-transcript", "domain": "not-a-real-domain"},
    )
    assert response.status_code == 403


def test_unknown_workflow_still_422s_not_403(client):
    """Denial is specific to recognized AI-chat workflow names; a bogus
    workflow string keeps its original 422 behavior, unchanged."""
    response = client.post(
        "/v1/evidence/import",
        files={"file": ("f.txt", io.BytesIO(b"hi"), "text/plain")},
        data={"workflow": "totally-bogus-workflow"},
    )
    assert response.status_code == 422
