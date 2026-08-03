"""app/settings.py — provider-agnostic model and embedder factory.

Selection strategy (ADR-0008):
- No hard default. Models are selected by available credentials.
- Per-provider env override: ``<PROVIDER>_MODEL_ID``.
- Global override: ``DEFAULT_MODEL_ID`` / ``DEFAULT_MODEL_PROVIDER``.

Provider priority chain (when no override):
    Ollama → NVIDIA → Kimi → OpenRouter → Anthropic → OpenAI → Google → Groq

Ollama Cloud (``glm-5.1``) is the primary provider (D7 revision).
NVIDIA NIM is the backup — its OpenAI-compatible endpoint serves most models.

Embedder strategy (ADR-0010; store = Weaviate per ADR-0040):
- One vector collection per embedder, embedder pinned at creation.
- Text: ``nvidia/nv-embed-v1`` (4096-d) — LIVE contract since 2026-07-19
  (bge-m3 retired: 500ing on NIM since 2026-07-04, store re-embedded).
- Code: ``codestral-embed-2505`` (1536-d) via OpenRouter.

Environment variables:
- ``DEFAULT_MODEL_PROVIDER`` — force a specific provider.
- ``DEFAULT_MODEL_ID`` — force a specific model ID (overrides pinned defaults).
- ``<PROVIDER>_MODEL_ID`` — per-provider model ID override.
- ``<PROVIDER>_API_KEY`` — API key for the provider.
- ``ANTHROPIC_AUTH_TOKEN`` — bearer-token fallback for "anthropic" (e.g. a
  Claude Code subscription OAuth token from ``claude setup-token``) when no
  standard ``ANTHROPIC_API_KEY`` is set. See ``_try_provider``.
- Provider-specific: ``OLLAMA_HOST``, ``NVIDIA_BASE_URL``, ``MOONSHOT_BASE_URL``,
  ``NVIDIA_RERANK_URL``.

Full enumerated model catalogs for Ollama Cloud and NVIDIA NIM (what the
account can actually reach, not a guess) live in ``server/core/model_catalog.py``
— data only, doesn't change the selection logic here.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01 (direct-provider wiring: ANTHROPIC_AUTH_TOKEN fallback + model_catalog.py cross-ref)

from __future__ import annotations

from os import getenv
from typing import Any, Optional

NVIDIA_BASE_URL_DEFAULT = "https://integrate.api.nvidia.com/v1"

# Confirmed-available default model id per provider (override via env).
_PINNED: dict[str, str] = {
    # Ollama Cloud — primary per D7 (rev).
    "ollama": "glm-5.1",
    # NVIDIA NIM (OpenAI-compatible). Backup provider.
    "nvidia": "nvidia/nemotron-3-super-120b-a12b",
    # Kimi K2.6 — served on NVIDIA NIM (or Moonshot direct if MOONSHOT_API_KEY set).
    "kimi": "moonshotai/kimi-k2.6",
    "openrouter": "deepseek/deepseek-chat",  # set OPENROUTER_MODEL_ID to taste
    "anthropic": "claude-sonnet-4-6",  # opus: claude-opus-4-8
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
}

# Selection order when DEFAULT_MODEL_PROVIDER is not set. Ollama first per D7 (rev).
_DEFAULT_ORDER: list[str] = [
    "ollama",
    "nvidia",
    "kimi",
    "openrouter",
    "anthropic",
    "openai",
    "google",
    "groq",
]

# LEGACY/NIM-fallback embedder IDs — these do NOT mirror the live contract and never did
# ("db/session.py" here means server/core/session.py, the actual source of truth).
# Current platform truth: nv-embed-v1 4096-d text (LIVE since 2026-07-19, symmetric —
# see session.py EMBED_TEXT_ID). nemotron-embed-vl is an ASYMMETRIC NIM embedqa model
# (owner rule: avoid — silently degrades retrieval without per-call input_type).
_EMBEDDER_IDS: dict[str, str] = {
    "text": "nvidia/llama-nemotron-embed-vl-1b-v2",  # legacy NIM fallback — 2048-d, asymmetric
    "code": "nvidia/nv-embedcode-7b-v1",  # code artifacts — 4096-d
}


def _model_id(provider: str, model_id: Optional[str] = None) -> str:
    """Resolve a model ID for *provider*.

    Resolution order: explicit *model_id* argument → ``<PROVIDER>_MODEL_ID``
    env → ``DEFAULT_MODEL_ID`` env → pinned default from ``_PINNED``.

    Parameters
    ----------
    provider:
        Provider key (e.g. ``"ollama"``, ``"nvidia"``).
    model_id:
        Caller-supplied model ID. When given it wins over every env override
        — a caller naming an exact id (e.g. the model-catalog registry
        builder) is asking for THAT model, not the deployment default.

    Returns
    -------
    str
        The resolved model ID.
    """
    if model_id:
        return model_id
    per = getenv(f"{provider.upper()}_MODEL_ID")
    if per:
        return per
    return getenv("DEFAULT_MODEL_ID") or _PINNED[provider]


def _provider_order() -> list[str]:
    """Return the provider selection order.

    If ``DEFAULT_MODEL_PROVIDER`` is set, returns a single-element list
    with that provider. Otherwise returns the default priority chain.

    Returns
    -------
    list[str]
        Ordered list of provider keys to try.
    """
    forced = getenv("DEFAULT_MODEL_PROVIDER")
    return [forced.strip().lower()] if forced else list(_DEFAULT_ORDER)


def _try_provider(provider: str, model_id: Optional[str] = None) -> Optional[Any]:
    """Construct an Agno model for *provider* if its credentials exist.

    Returns ``None`` when the provider has no credentials configured — the
    caller skips to the next provider in the chain.

    Parameters
    ----------
    provider:
        Provider key (e.g. ``"ollama"``, ``"nvidia"``, ``"kimi"``).
    model_id:
        Exact model ID to construct. When ``None`` the provider's usual
        env-override/pinned-default resolution applies (unchanged behaviour).

    Returns
    -------
    Any | None
        A configured Agno model instance, or ``None``.
    """
    nvidia_key = getenv("NVIDIA_API_KEY")
    nvidia_base = getenv("NVIDIA_BASE_URL", NVIDIA_BASE_URL_DEFAULT)

    if provider == "nvidia":
        if not nvidia_key:
            return None
        from agno.models.openai.like import OpenAILike

        return OpenAILike(id=_model_id("nvidia", model_id), api_key=nvidia_key, base_url=nvidia_base)

    if provider == "kimi":
        # Prefer Moonshot direct if a key is set; else ride NVIDIA NIM.
        moonshot_key = getenv("MOONSHOT_API_KEY")
        from agno.models.openai.like import OpenAILike

        if moonshot_key:
            base = getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
            return OpenAILike(
                id=model_id or getenv("KIMI_MODEL_ID", "kimi-k2.6"),
                api_key=moonshot_key,
                base_url=base,
            )
        if nvidia_key:
            return OpenAILike(id=_model_id("kimi", model_id), api_key=nvidia_key, base_url=nvidia_base)
        return None

    if provider == "openrouter":
        key = getenv("OPENROUTER_API_KEY")
        if not key:
            return None
        from agno.models.openai.like import OpenAILike

        return OpenAILike(id=_model_id("openrouter", model_id), api_key=key, base_url="https://openrouter.ai/api/v1")

    if provider == "ollama":
        # Ollama Cloud: OLLAMA_API_KEY makes host default to https://ollama.com.
        # Local: set OLLAMA_HOST (e.g. http://localhost:11434).
        ollama_key = getenv("OLLAMA_API_KEY")
        ollama_host = getenv("OLLAMA_HOST")
        if not (ollama_key or ollama_host):
            return None
        from agno.models.ollama import Ollama

        if ollama_host:
            return Ollama(id=_model_id("ollama", model_id), host=ollama_host)
        return Ollama(id=_model_id("ollama", model_id), api_key=ollama_key)

    if provider == "openai":
        key = getenv("OPENAI_API_KEY")
        if not key:
            return None
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=_model_id("openai", model_id), api_key=key)

    if provider == "anthropic":
        key = getenv("ANTHROPIC_API_KEY")
        # ANTHROPIC_AUTH_TOKEN fallback: agno.models.anthropic.Claude natively
        # reads this env var (see agno/models/anthropic/claude.py
        # _get_client_params) and passes it as the Anthropic SDK client's
        # `auth_token` param -> `Authorization: Bearer <token>`, vs. `api_key`
        # -> `x-api-key`. This lets a Claude Code subscription OAuth token
        # (`claude setup-token`, stored as CLAUDE_CODE_OAUTH_TOKEN in
        # ~/.secrets/anthropic.env) work here too — copy its value into
        # ANTHROPIC_AUTH_TOKEN to use it. Verified live 2026-08-01: the
        # bearer-token call succeeds against both /v1/models and
        # /v1/messages with NO anthropic-beta header required. No separate
        # ANTHROPIC_API_KEY exists in this platform's secrets as of that date
        # — only the OAuth token, so this fallback is currently the only way
        # the "anthropic" provider in this chain has live credentials.
        auth_token = getenv("ANTHROPIC_AUTH_TOKEN")
        if not (key or auth_token):
            return None
        from agno.models.anthropic import Claude

        return Claude(id=_model_id("anthropic", model_id), api_key=key, auth_token=auth_token)

    if provider == "google":
        key = getenv("GOOGLE_API_KEY")
        if not key:
            return None
        from agno.models.google import Gemini

        return Gemini(id=_model_id("google", model_id), api_key=key)

    if provider == "groq":
        key = getenv("GROQ_API_KEY")
        if not key:
            return None
        from agno.models.groq import Groq

        return Groq(id=_model_id("groq", model_id), api_key=key)

    return None


def build_model(provider: Optional[str] = None, model_id: Optional[str] = None) -> Any:
    """Select and construct a model by available credentials.

    Creates a fresh model instance on every call — do NOT cache. Each agent
    gets its own model so provider failures are isolated.

    Parameters
    ----------
    provider:
        Force a specific provider. When ``None``, tries each provider in
        priority order until one succeeds.
    model_id:
        Force a specific model ID for the chosen provider. Only meaningful
        together with *provider* (the chain would otherwise apply one id to
        whichever provider happens to answer first).

    Returns
    -------
    Any
        A configured Agno model instance.

    Raises
    ------
    ValueError
        If no provider in the chain has valid credentials.
    """
    order = [provider.strip().lower()] if provider else _provider_order()
    for p in order:
        model = _try_provider(p, model_id)
        if model is not None:
            return model
    raise ValueError(
        "No model provider configured. Set one of: OLLAMA_API_KEY/OLLAMA_HOST, NVIDIA_API_KEY, "
        "MOONSHOT_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "GOOGLE_API_KEY, GROQ_API_KEY (or pin DEFAULT_MODEL_PROVIDER)."
    )


def default_model() -> Any:
    """Return a fresh model instance using the default provider chain.

    This is the convenience wrapper used by agent constructors when no
    specific provider is requested.

    Returns
    -------
    Any
        A configured Agno model instance.
    """
    return build_model()
