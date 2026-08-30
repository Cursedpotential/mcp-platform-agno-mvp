"""Fail-closed capability gate for the platform-native case registry.

Byline: Codex · GPT-5.6-Sol · 2026-08-30
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api.case_management_routes import register_case_management_routes
from server.case_management import repository, service
from server.contracts.case_management import KnowledgeSourceResolveRequest


MATTER_ID = UUID("11111111-1111-4111-8111-111111111111")


def test_capability_endpoint_reports_registry_without_claiming_advanced_evidence(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_capabilities",
        lambda: {
            "registry_available": True,
            "advanced_evidence_available": False,
            "advanced_evidence_reason": repository.ADVANCED_EVIDENCE_UNAVAILABLE_DETAIL,
        },
    )
    app = FastAPI()
    register_case_management_routes(app)

    response = TestClient(app).get("/v1/case-management/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "registry_available": True,
        "advanced_evidence_available": False,
        "advanced_evidence_reason": repository.ADVANCED_EVIDENCE_UNAVAILABLE_DETAIL,
    }


def test_advanced_service_fails_503_without_calling_legacy_repository(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_capabilities",
        lambda: {
            "registry_available": True,
            "advanced_evidence_available": False,
            "advanced_evidence_reason": repository.ADVANCED_EVIDENCE_UNAVAILABLE_DETAIL,
        },
    )
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("advanced repository must not be called")

    monkeypatch.setattr(repository, "resolve_source", forbidden)
    request = KnowledgeSourceResolveRequest(
        lane="evidence",
        partition_key="primary",
        artifact_id=UUID("22222222-2222-4222-8222-222222222222"),
        sha256="a" * 64,
        retrieval_ref="hit-1",
    )

    with pytest.raises(service.CaseManagementError) as caught:
        service.resolve_source(MATTER_ID, request)

    assert caught.value.status_code == 503
    assert caught.value.detail == repository.ADVANCED_EVIDENCE_UNAVAILABLE_DETAIL
    assert called is False
