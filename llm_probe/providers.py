"""llm_probe/providers.py — provider registry: base URL, auth, and model-catalog
fetch for every LLM provider this service can probe.

All providers speak the OpenAI-compatible ``/chat/completions`` shape except
Google's native ``/v1beta/models`` catalog listing (its chat calls still go
through its OpenAI-compat layer at ``.../v1beta/openai``).

Keys come from process environment only — this service runs server-side on
the VPS behind Tailscale, so keys never reach a browser. Set them as Coolify
env vars on this app; nothing here reads ``~/.secrets``.

Byline: Claude Code · Sonnet 5 · 2026-08-27
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    api_key_env: Optional[str] = None  # unset for DB-registered custom providers (see _key_override)
    models_url: Optional[str] = None  # override if catalog listing isn't base_url + "/models"
    models_auth: str = "bearer"  # "bearer" | "query_key" (Google's native listing wants ?key=)
    # Live-verified 2026-08-27 (real 200-vs-400 probe, not vendor docs): whether
    # this provider's /chat/completions accepts presence_penalty/frequency_penalty.
    # None = unconfirmed (account was dead/untestable at verification time) —
    # treated as unsupported (hidden) until re-verified, never assumed supported.
    supports_penalty_params: Optional[bool] = None
    is_custom: bool = False
    # Custom providers carry their pgcrypto-decrypted key in-memory for the
    # single request that resolved them — never an env var, never logged,
    # never returned from an API response. None for the 8 hardcoded providers.
    _key_override: Optional[str] = None

    @property
    def api_key(self) -> Optional[str]:
        if self._key_override is not None:
            return self._key_override
        return os.environ.get(self.api_key_env) if self.api_key_env else None

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


PROVIDERS: dict[str, Provider] = {
    "nim": Provider("nim", os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"), "NVIDIA_API_KEY",
                     supports_penalty_params=True),
    "ollama_cloud": Provider("ollama_cloud", "https://ollama.com/v1", "OLLAMA_API_KEY", models_url="https://ollama.com/api/tags",
                              supports_penalty_params=True),
    "openrouter": Provider("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
                            supports_penalty_params=True),
    "google": Provider(
        "google",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "GOOGLE_API_KEY",
        models_url="https://generativelanguage.googleapis.com/v1beta/models",
        models_auth="query_key",
        supports_penalty_params=False,  # verified live: 400 "Unknown name frequency_penalty"
    ),
    "openai": Provider("openai", "https://api.openai.com/v1", "OPENAI_API_KEY", supports_penalty_params=True),
    "mistral": Provider("mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", supports_penalty_params=True),
    "groq": Provider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", supports_penalty_params=True),
    "cerebras": Provider("cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY",
                          supports_penalty_params=None),  # account dead (402) — never confirmed
}


def get_provider(name: str) -> Provider:
    """Hardcoded providers only, synchronous — for call sites that can't
    await (rare). Prefer resolve_provider() everywhere a custom provider
    should also be reachable."""
    if name not in PROVIDERS:
        raise KeyError(f"unknown provider {name!r}; known: {sorted(PROVIDERS)}")
    return PROVIDERS[name]


async def resolve_provider(name: str) -> Provider:
    """Hardcoded providers first, then DB-registered custom providers
    (decrypting the key for this call only). This is the path every actual
    outbound call and catalog fetch should go through."""
    if name in PROVIDERS:
        return PROVIDERS[name]
    from . import db  # local import: avoids a circular import at module load

    row = await db.get_custom_provider(name)
    if row is None:
        raise KeyError(f"unknown provider {name!r}; known: {sorted(PROVIDERS)} + custom providers")
    return Provider(
        name=row["name"], base_url=row["base_url"], models_url=row["models_url"],
        models_auth=row["models_auth"], supports_penalty_params=row["supports_penalty_params"],
        is_custom=True, _key_override=row["api_key"],
    )


def configured_providers() -> list[str]:
    return [p.name for p in PROVIDERS.values() if p.configured]


async def fetch_models(provider_name: str) -> list[dict]:
    """Live-fetch the model catalog for one provider. Raises on HTTP failure —
    callers decide whether to surface it or fall back to a cached list."""
    p = await resolve_provider(provider_name)
    if not p.api_key:
        raise RuntimeError(f"{provider_name}: no API key configured ({p.api_key_env} unset)")

    url = p.models_url or f"{p.base_url}/models"
    headers = {}
    params = {}
    if p.models_auth == "query_key":
        params["key"] = p.api_key
    else:
        headers["Authorization"] = f"Bearer {p.api_key}"

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

    if provider_name == "ollama_cloud":
        return [{"id": m["id"]} for m in data.get("models", data.get("data", []))]
    if provider_name == "google":
        out = []
        for m in data.get("models", []):
            name = m.get("name", "")
            out.append({"id": name.split("/", 1)[-1], "supported_methods": m.get("supportedGenerationMethods", [])})
        return out
    # everything else: OpenAI-style {"data": [{"id": ...}, ...]}
    return [{"id": m["id"], **{k: v for k, v in m.items() if k != "id"}} for m in data.get("data", data if isinstance(data, list) else [])]
