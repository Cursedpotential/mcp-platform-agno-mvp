"""Pass-bound native evidence HTTP authorization contract tests.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api.native_evidence_search_routes import (
    WalkSearchContext,
    register_native_evidence_search_routes,
)
from server.evidence.search_capability import issue_walk_search_capability

_OPERATOR_HEADERS = {"Authorization": "Bearer test-operator-key"}
_RUN_ID = "00000000-0000-4000-8000-000000000001"
_STEP_ID = "00000000-0000-4000-8000-000000000002"
_CHECKPOINT_ID = "00000000-0000-4000-8000-000000000003"
_AGENT_BODY = {
    "query": "what happened",
    "walk_run_id": _RUN_ID,
    "walk_step_id": _STEP_ID,
    "checkpoint_id": _CHECKPOINT_ID,
}


def _agent_headers() -> dict[str, str]:
    token = issue_walk_search_capability(UUID(_RUN_ID), UUID(_STEP_ID), UUID(_CHECKPOINT_ID))
    return {"Authorization": f"Bearer {token}"}


@dataclass
class _Result:
    documents: list[object]
    kept: int = 1
    denied: int = 0
    audit_id: int = 91


async def _ignorant_context(*_ids: UUID) -> WalkSearchContext:
    return WalkSearchContext(
        case_id="matter-1",
        actor="agent:ignorant",
        horizon=datetime(2025, 6, 1, tzinfo=timezone.utc),
        disclosure_tiers=("contemporaneous", "discovered"),
        horizon_policy="ignorant",
    )


def _client(executor, resolver=_ignorant_context) -> TestClient:
    app = FastAPI()
    register_native_evidence_search_routes(app, execute_search=executor, resolve_walk_context=resolver)
    return TestClient(app)


def _configure_operator_bearer(monkeypatch, tmp_path, credential: str) -> None:
    from server.api import platform_auth

    secret = tmp_path / "evidence-operator-security-key"
    secret.write_text(credential, encoding="utf-8")
    monkeypatch.setattr(platform_auth, "_EVIDENCE_OPERATOR_BEARER_FILE", secret)


def test_agent_endpoint_uses_only_ledger_resolved_authority(monkeypatch) -> None:
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "test-walk-signing-key")
    captured = {}

    async def executor(query, **kwargs):
        captured.update(query=query, **kwargs)
        document = SimpleNamespace(
            uuid="weaviate-uuid",
            properties={
                "chunk_id": "chunk-1",
                "content": "visible fact",
                "normalized_record_id": "record-1",
                "source_sha256": "a" * 64,
            },
            metadata=SimpleNamespace(score=0.82, distance=None),
        )
        return _Result([document])

    response = _client(executor).post("/v1/evidence/search", headers=_agent_headers(), json=_AGENT_BODY)

    assert response.status_code == 200
    assert captured["case_id"] == "matter-1"
    assert captured["actor"] == "agent:ignorant"
    assert captured["horizon"] == datetime(2025, 6, 1, tzinfo=timezone.utc)
    assert captured["disclosure_tiers"] == ("contemporaneous", "discovered")
    assert response.json()["data"][0]["content"] == "visible fact"


def test_agent_endpoint_rejects_omitted_walk_context(monkeypatch) -> None:
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "test-walk-signing-key")

    async def executor(*args, **kwargs):  # pragma: no cover - validation stops first
        raise AssertionError("executor must not run")

    response = _client(executor).post("/v1/evidence/search", headers=_agent_headers(), json={"query": "no pass"})
    assert response.status_code == 422


def test_agent_endpoint_rejects_caller_horizon_and_hindsight_tier(monkeypatch) -> None:
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "test-walk-signing-key")

    async def executor(*args, **kwargs):  # pragma: no cover - validation stops first
        raise AssertionError("executor must not run")

    client = _client(executor)
    arbitrary_future = client.post(
        "/v1/evidence/search",
        headers=_agent_headers(),
        json={**_AGENT_BODY, "horizon": "2999-01-01T00:00:00Z"},
    )
    hindsight = client.post(
        "/v1/evidence/search",
        headers=_agent_headers(),
        json={**_AGENT_BODY, "disclosure_tiers": ["hindsight"]},
    )
    assert arbitrary_future.status_code == 422
    assert hindsight.status_code == 422


def test_agent_endpoint_denies_non_reconciling_ledger_context(monkeypatch) -> None:
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "test-walk-signing-key")

    async def denied(*_ids):
        raise PermissionError("walk checkpoint base version does not reconcile")

    async def executor(*args, **kwargs):  # pragma: no cover - resolver stops first
        raise AssertionError("executor must not run")

    response = _client(executor, denied).post("/v1/evidence/search", headers=_agent_headers(), json=_AGENT_BODY)
    assert response.status_code == 403


def test_agent_endpoint_fails_closed_without_valid_service_bearer(monkeypatch) -> None:
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "test-walk-signing-key")

    async def executor(*args, **kwargs):  # pragma: no cover - auth stops first
        raise AssertionError("executor must not run")

    client = _client(executor)
    assert client.post("/v1/evidence/search", json=_AGENT_BODY).status_code == 401
    assert (
        client.post(
            "/v1/evidence/search",
            headers={"Authorization": "Bearer wrong"},
            json=_AGENT_BODY,
        ).status_code
        == 401
    )


def test_shared_os_bearer_cannot_select_a_hindsight_pass(monkeypatch) -> None:
    monkeypatch.setenv("OS_SECURITY_KEY", "shared-os-key")
    monkeypatch.setenv("WALK_PASS_SIGNING_KEY", "server-only-signing-key")

    async def executor(*args, **kwargs):  # pragma: no cover - capability stops first
        raise AssertionError("executor must not run")

    response = _client(executor).post(
        "/v1/evidence/search",
        headers={"Authorization": "Bearer shared-os-key"},
        json=_AGENT_BODY,
    )
    assert response.status_code == 401


def test_operator_endpoint_is_distinct_bounded_and_never_hindsight(monkeypatch, tmp_path) -> None:
    _configure_operator_bearer(monkeypatch, tmp_path, "test-operator-key")
    captured = {}

    async def executor(query, **kwargs):
        captured.update(query=query, **kwargs)
        return _Result([], kept=0)

    response = _client(executor).post(
        "/v1/operator/evidence/search",
        headers=_OPERATOR_HEADERS,
        json={"query": "explore", "case_id": "matter-7", "horizon": "2999-01-01T00:00:00Z"},
    )
    assert response.status_code == 200
    assert captured["actor"] == "workbench:owner:evidence-search"
    assert captured["disclosure_tiers"] == ("contemporaneous", "discovered")
    assert captured["horizon"] <= datetime.now(timezone.utc)


def test_operator_endpoint_requires_distinct_owner_credential(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OS_SECURITY_KEY", "shared-os-key")
    _configure_operator_bearer(monkeypatch, tmp_path, "owner-only-key")

    async def executor(*args, **kwargs):  # pragma: no cover - auth stops first
        raise AssertionError("executor must not run")

    response = _client(executor).post(
        "/v1/operator/evidence/search",
        headers={"Authorization": "Bearer shared-os-key"},
        json={"query": "q"},
    )
    assert response.status_code == 401


def test_default_executor_constructs_pinned_embedder_and_native_store_without_live_io(monkeypatch, tmp_path) -> None:
    """Regression: the non-injected production path imports and constructs."""

    import openai

    import server.core.evidence_vector_store as vector_store
    import server.core.session as session
    import server.evidence.retrieval as retrieval
    from server.core.evidence_vector_store import EVIDENCE_EMBED_DIM, EVIDENCE_EMBED_MODEL

    _configure_operator_bearer(monkeypatch, tmp_path, "test-operator-key")
    monkeypatch.setenv("NVIDIA_API_KEY", "not-a-live-key")
    seen = {}

    class FakeEmbeddings:
        def create(self, *, model, input):
            seen.update(model=model, input=input)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * EVIDENCE_EMBED_DIM)])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            seen["openai"] = kwargs
            self.embeddings = FakeEmbeddings()

    class FakeClient:
        collections = SimpleNamespace(use=lambda _name: object())

        def close(self):
            seen["closed"] = True

    def fake_native_search(store, embed_query, query, **kwargs):
        vector = embed_query(query)
        seen["vector_length"] = len(vector)
        return _Result([], kept=0)

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(vector_store, "validate_evidence_vector_activation", lambda _client: None)
    monkeypatch.setattr(session, "get_weaviate_client", lambda: FakeClient())
    monkeypatch.setattr(retrieval, "native_evidence_search", fake_native_search)

    app = FastAPI()
    register_native_evidence_search_routes(app)
    response = TestClient(app).post(
        "/v1/operator/evidence/search",
        headers=_OPERATOR_HEADERS,
        json={"query": "construct me"},
    )

    assert response.status_code == 200
    assert seen["model"] == EVIDENCE_EMBED_MODEL
    assert seen["vector_length"] == EVIDENCE_EMBED_DIM
    assert seen["closed"] is True
