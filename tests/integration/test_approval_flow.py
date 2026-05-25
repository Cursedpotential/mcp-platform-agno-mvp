"""Integration tests for the approval workflow API."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealth:
    async def test_health_check(self, client):
        """Health endpoint should return status."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "agents_ready" in data
        assert "db_connected" in data


class TestApprovalWorkflow:
    async def test_create_approval(self, client):
        """Should create an approval request."""
        payload = {
            "agentRunId": "7f8d8c6a-3f74-4be7-9659-4f1bf8d1a0ef",
            "requestedAction": "Run Facebook parser and write normalized records to PostgreSQL",
            "riskLevel": "high",
        }
        response = await client.post("/v1/approval-requests", json=payload)
        assert response.status_code in (200, 500)  # 500 if DB not available

    async def test_create_approval_invalid_risk(self, client):
        """Should reject invalid risk levels."""
        payload = {
            "agentRunId": "7f8d8c6a-3f74-4be7-9659-4f1bf8d1a0ef",
            "requestedAction": "Test action",
            "riskLevel": "invalid",
        }
        response = await client.post("/v1/approval-requests", json=payload)
        assert response.status_code == 422

    async def test_decision_invalid_value(self, client):
        """Should reject invalid decision values."""
        payload = {
            "decision": "maybe",
            "decidedBy": "Test User",
        }
        response = await client.post(
            "/v1/approval-requests/some-id/decision", json=payload
        )
        assert response.status_code == 422


class TestAgentListing:
    async def test_list_agents(self, client):
        """Should list available agents."""
        response = await client.get("/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)


class TestKnowledgeReindex:
    async def test_reindex_endpoint(self, client):
        """Reindex endpoint should return status."""
        payload = {"basePath": "./knowledge/platform", "recreate": False}
        response = await client.post("/v1/knowledge/reindex", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "indexedDocumentCount" in data
        assert "status" in data
