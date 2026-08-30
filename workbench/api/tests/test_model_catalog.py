"""Release gates for live model discovery and the Workbench catalog contract.

Byline: Codex · GPT-5 · 2026-08-16
Byline: Codex · GPT-5.6 · 2026-08-29 (trusted-proxy authentication contract)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from app.runtime import auth
from app.service import model_catalog
from app.service.model_catalog import ModelCatalogService
from app.types.classification import ProviderInfo, ProviderName, ProvidersListResponse
from fastapi.testclient import TestClient
from main import app


def test_catalog_fetches_every_provider_and_honors_refresh(monkeypatch) -> None:
    calls: list[ProviderName] = []

    async def fetch_models(_client: httpx.AsyncClient, provider: ProviderName) -> list[str]:
        calls.append(provider)
        return [f"{provider.value}/model-b", f"{provider.value}/model-a"]

    monkeypatch.setattr(
        model_catalog,
        "list_available_providers",
        lambda: dict.fromkeys(ProviderName, True),
    )
    monkeypatch.setattr(model_catalog, "_fetch_provider_models", fetch_models)
    service = ModelCatalogService(ttl=timedelta(minutes=5))

    first = asyncio.run(service.list())
    cached = asyncio.run(service.list())
    refreshed = asyncio.run(service.list(refresh=True))

    assert len(first.providers) == len(ProviderName)
    assert first.cache_hit is False
    assert cached.cache_hit is True
    assert refreshed.cache_hit is False
    assert len(calls) == len(ProviderName) * 2
    assert first.providers[0].models == ["ollama/model-a", "ollama/model-b"]


def test_catalog_reports_one_provider_failure_without_hiding_others(monkeypatch) -> None:
    async def fetch_models(_client: httpx.AsyncClient, provider: ProviderName) -> list[str]:
        if provider == ProviderName.NVIDIA:
            raise RuntimeError("catalog offline")
        return [f"{provider.value}/model"]

    monkeypatch.setattr(
        model_catalog,
        "list_available_providers",
        lambda: dict.fromkeys(ProviderName, True),
    )
    monkeypatch.setattr(model_catalog, "_fetch_provider_models", fetch_models)

    response = asyncio.run(ModelCatalogService().list(refresh=True))
    by_provider = {item.provider: item for item in response.providers}

    assert by_provider[ProviderName.NVIDIA].models == []
    assert by_provider[ProviderName.NVIDIA].source == "error"
    assert "catalog offline" in (by_provider[ProviderName.NVIDIA].error or "")
    assert by_provider[ProviderName.PORTKEY].models == ["portkey/model"]


def test_portkey_catalog_reads_all_pages(monkeypatch) -> None:
    offsets: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        count = 100 if offset == 0 else 2
        data = [{"id": f"@provider/model-{offset + index}"} for index in range(count)]
        return httpx.Response(
            200,
            request=request,
            json={"object": "list", "total": 102, "data": data},
        )

    monkeypatch.setenv("PORTKEY_API_KEY", "test-key")
    monkeypatch.setenv("PORTKEY_BASE_URL", "https://portkey.test/v1")
    monkeypatch.delenv("PORTKEY_PROVIDER", raising=False)

    async def fetch() -> list[str]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await model_catalog._portkey_models(client)

    models = asyncio.run(fetch())

    assert offsets == [0, 100]
    assert len(models) == 102
    assert "@provider/model-101" in models


def test_self_hosted_portkey_catalog_routes_to_configured_provider(monkeypatch) -> None:
    observed: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers["authorization"]
        observed["provider"] = request.headers["x-portkey-provider"]
        observed["url"] = str(request.url)
        return httpx.Response(200, request=request, json={"data": [{"id": "gpt-owner"}]})

    monkeypatch.setenv("PORTKEY_API_KEY", "provider-key")
    monkeypatch.setenv("PORTKEY_BASE_URL", "http://portkey.internal:8787/v1")
    monkeypatch.setenv("PORTKEY_PROVIDER", "openai")

    async def fetch() -> list[str]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await model_catalog._portkey_models(client)

    assert asyncio.run(fetch()) == ["gpt-owner"]
    assert observed == {
        "authorization": "Bearer provider-key",
        "provider": "openai",
        "url": "http://portkey.internal:8787/v1/models",
    }


def test_both_catalog_routes_share_the_api_contract(monkeypatch) -> None:
    observed_refresh: list[bool] = []
    response = ProvidersListResponse(
        providers=[
            ProviderInfo(
                provider=ProviderName.PORTKEY,
                models=["@owner/gateway-model"],
                default_model="@owner/gateway-model",
                available=True,
                source="live",
            )
        ],
        refreshed_at=datetime.now(UTC),
    )

    async def list_catalog(*, refresh: bool = False) -> ProvidersListResponse:
        observed_refresh.append(refresh)
        return response

    monkeypatch.setattr(auth.settings, "trusted_auth_proxy_cidrs", "10.0.0.0/8")
    monkeypatch.setattr(auth.settings, "tailnet_auth_bypass_enabled", False)
    monkeypatch.setattr(model_catalog.model_catalog_service, "list", list_catalog)
    client = TestClient(app, client=("10.1.2.3", 50000))
    headers = {
        "X-authentik-uid": "user-123",
        "X-authentik-username": "owner@example.test",
    }

    classification = client.get("/api/classification/providers?refresh=true", headers=headers)
    comparison = client.get("/api/comparison/providers", headers=headers)

    assert classification.status_code == 200
    assert comparison.status_code == 200
    assert classification.json()["providers"][0]["provider"] == "portkey"
    assert classification.json()["providers"][0]["models"] == ["@owner/gateway-model"]
    assert comparison.json()["providers"] == classification.json()["providers"]
    assert observed_refresh == [True, False]
