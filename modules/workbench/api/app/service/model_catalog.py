"""Live model discovery for the Workbench provider test surface.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.service.model_providers import NVIDIA_BASE_URL_DEFAULT, _model_id, list_available_providers
from app.types.classification import ProviderInfo, ProviderName, ProvidersListResponse


def _model_ids(payload: dict[str, Any]) -> list[str]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return sorted(
        {
            item["id"]
            for item in data
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
        }
    )


async def _openai_models(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
) -> list[str]:
    response = await client.get(url, headers=headers)
    response.raise_for_status()
    return _model_ids(response.json())


async def _portkey_models(client: httpx.AsyncClient) -> list[str]:
    """Fetch models from self-hosted provider mode or the cloud workspace catalog."""
    base_url = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")
    key = os.environ["PORTKEY_API_KEY"]
    if provider := os.getenv("PORTKEY_PROVIDER"):
        return await _openai_models(
            client,
            f"{base_url}/models",
            {"Authorization": f"Bearer {key}", "x-portkey-provider": provider},
        )

    headers = {"x-portkey-api-key": key}
    limit, offset = 100, 0
    identifiers: set[str] = set()
    while True:
        response = await client.get(
            f"{base_url}/models",
            headers=headers,
            params={"limit": limit, "offset": offset, "sort": "name", "order": "asc"},
        )
        response.raise_for_status()
        payload = response.json()
        identifiers.update(_model_ids(payload))
        raw_page = payload.get("data")
        page_size = len(raw_page) if isinstance(raw_page, list) else 0
        total = payload.get("total")
        offset += page_size
        if not page_size or (isinstance(total, int) and offset >= total) or page_size < limit:
            return sorted(identifiers)
        if offset >= 10000:
            raise RuntimeError("Portkey model catalog exceeded the 10,000-model safety limit")


async def _anthropic_models(client: httpx.AsyncClient) -> list[str]:
    headers = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"}
    after_id: str | None = None
    identifiers: set[str] = set()
    while True:
        params: dict[str, str | int] = {"limit": 100}
        if after_id:
            params["after_id"] = after_id
        response = await client.get("https://api.anthropic.com/v1/models", headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        identifiers.update(_model_ids(payload))
        data = payload.get("data")
        if not payload.get("has_more") or not isinstance(data, list) or not data:
            return sorted(identifiers)
        last = data[-1]
        after_id = last.get("id") if isinstance(last, dict) else None
        if not after_id:
            return sorted(identifiers)


async def _google_models(client: httpx.AsyncClient) -> list[str]:
    page_token: str | None = None
    identifiers: set[str] = set()
    while True:
        params: dict[str, str | int] = {"key": os.environ["GOOGLE_API_KEY"], "pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        response = await client.get("https://generativelanguage.googleapis.com/v1beta/models", params=params)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models")
        if isinstance(models, list):
            for model in models:
                if not isinstance(model, dict):
                    continue
                methods, name = model.get("supportedGenerationMethods", []), model.get("name")
                if isinstance(name, str) and isinstance(methods, list) and "generateContent" in methods:
                    identifiers.add(name.removeprefix("models/"))
        page_token = payload.get("nextPageToken")
        if not isinstance(page_token, str) or not page_token:
            return sorted(identifiers)


async def _ollama_models(client: httpx.AsyncClient) -> list[str]:
    host = os.getenv("OLLAMA_HOST")
    if not host:
        raise RuntimeError("OLLAMA_HOST is required for live model discovery")
    headers = {"Authorization": f"Bearer {key}"} if (key := os.getenv("OLLAMA_API_KEY")) else {}
    response = await client.get(f"{host.rstrip('/')}/api/tags", headers=headers)
    response.raise_for_status()
    models = response.json().get("models")
    if not isinstance(models, list):
        return []
    return sorted(
        {
            model["name"]
            for model in models
            if isinstance(model, dict) and isinstance(model.get("name"), str) and model["name"].strip()
        }
    )


async def _fetch_provider_models(client: httpx.AsyncClient, provider: ProviderName) -> list[str]:
    if provider == ProviderName.PORTKEY:
        return await _portkey_models(client)
    if provider == ProviderName.OLLAMA:
        return await _ollama_models(client)
    if provider == ProviderName.ANTHROPIC:
        return await _anthropic_models(client)
    if provider == ProviderName.GOOGLE:
        return await _google_models(client)
    endpoints: dict[ProviderName, tuple[str, str]] = {
        ProviderName.NVIDIA: (
            f"{os.getenv('NVIDIA_BASE_URL', NVIDIA_BASE_URL_DEFAULT).rstrip('/')}/models",
            "NVIDIA_API_KEY",
        ),
        ProviderName.OPENROUTER: ("https://openrouter.ai/api/v1/models", "OPENROUTER_API_KEY"),
        ProviderName.OPENAI: ("https://api.openai.com/v1/models", "OPENAI_API_KEY"),
        ProviderName.GROQ: ("https://api.groq.com/openai/v1/models", "GROQ_API_KEY"),
    }
    url, key_name = endpoints[provider]
    return await _openai_models(client, url, {"Authorization": f"Bearer {os.environ[key_name]}"})


class ModelCatalogService:
    """Server-side live model catalog with a short, explicit cache."""

    def __init__(self, ttl: timedelta = timedelta(minutes=5)) -> None:
        self._ttl = ttl
        self._cached: ProvidersListResponse | None = None

    def clear_cache(self) -> None:
        self._cached = None

    async def list(self, *, refresh: bool = False) -> ProvidersListResponse:
        now = datetime.now(UTC)
        if not refresh and self._cached and now - self._cached.refreshed_at < self._ttl:
            return self._cached.model_copy(update={"cache_hit": True})
        available = list_available_providers()
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            providers = await asyncio.gather(
                *(self._provider_info(client, provider, available[provider]) for provider in ProviderName)
            )
        self._cached = ProvidersListResponse(providers=list(providers), refreshed_at=now)
        return self._cached

    async def _provider_info(
        self,
        client: httpx.AsyncClient,
        provider: ProviderName,
        available: bool,
    ) -> ProviderInfo:
        default = _model_id(provider)
        if not available:
            return ProviderInfo(
                provider=provider,
                models=[],
                default_model=default,
                available=False,
                source="unconfigured",
                error=f"{provider.value} credentials or host are not configured",
            )
        try:
            models = sorted(set(await _fetch_provider_models(client, provider)))
            return ProviderInfo(
                provider=provider,
                models=models,
                default_model=default,
                available=True,
                source="live",
                error=None if models else "Provider returned an empty model catalog",
            )
        except (httpx.HTTPError, KeyError, RuntimeError, ValueError) as exc:
            return ProviderInfo(
                provider=provider,
                models=[],
                default_model=default,
                available=True,
                source="error",
                error=f"Live model discovery failed: {exc}",
            )


model_catalog_service = ModelCatalogService()
