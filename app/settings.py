"""
App Settings — provider-agnostic model + embedder factories
===========================================================

ADR-0008: select by available credentials; no hard stale default; pin versioned IDs.
D7 (rev): Ollama Cloud (glm-5.1) is the primary provider. NVIDIA NIM is backup.
Most NVIDIA models ride NVIDIA's OpenAI-compatible endpoint; OpenRouter and Ollama
Cloud are separate. Model IDs below confirmed against live catalogs.

Every id is overridable via env: a global DEFAULT_MODEL_ID, or per-provider
<PROVIDER>_MODEL_ID (e.g. NVIDIA_MODEL_ID, KIMI_MODEL_ID, OLLAMA_MODEL_ID).
Embedder strategy: ADR-0010 (one collection per embedder).
"""

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
_DEFAULT_ORDER = ["ollama", "nvidia", "kimi", "openrouter", "anthropic", "openai", "google", "groq"]

# Embedders (ADR-0010 + ADR-0011) — one collection per embedder. Dims pinned in db/session.py.
# NOTE: db/session.py is the source of truth for embedder IDs/dims; these mirror it for reference.
EMBEDDER_IDS: dict[str, str] = {
    "text": "nvidia/llama-nemotron-embed-vl-1b-v2",  # docs / legal / transcripts — 2048-d
    "code": "nvidia/nv-embedcode-7b-v1",  # code artifacts — 4096-d
}


def _model_id(provider: str) -> str:
    """Resolve a model id: per-provider env > global DEFAULT_MODEL_ID > pinned default."""
    per = getenv(f"{provider.upper()}_MODEL_ID")
    if per:
        return per
    return getenv("DEFAULT_MODEL_ID") or _PINNED[provider]


def _provider_order() -> list[str]:
    forced = getenv("DEFAULT_MODEL_PROVIDER")
    return [forced.strip().lower()] if forced else _DEFAULT_ORDER


def _try_provider(provider: str) -> Optional[Any]:
    """Construct an Agno model for `provider` if its credentials exist, else None."""
    nvidia_key = getenv("NVIDIA_API_KEY")
    nvidia_base = getenv("NVIDIA_BASE_URL", NVIDIA_BASE_URL_DEFAULT)

    if provider == "nvidia":
        if not nvidia_key:
            return None
        from agno.models.openai.like import OpenAILike

        return OpenAILike(id=_model_id("nvidia"), api_key=nvidia_key, base_url=nvidia_base)

    if provider == "kimi":
        # Prefer Moonshot direct if a key is set; else ride NVIDIA NIM.
        moonshot_key = getenv("MOONSHOT_API_KEY")
        from agno.models.openai.like import OpenAILike

        if moonshot_key:
            base = getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
            return OpenAILike(id=getenv("KIMI_MODEL_ID", "kimi-k2.6"), api_key=moonshot_key, base_url=base)
        if nvidia_key:
            return OpenAILike(id=_model_id("kimi"), api_key=nvidia_key, base_url=nvidia_base)
        return None

    if provider == "openrouter":
        key = getenv("OPENROUTER_API_KEY")
        if not key:
            return None
        from agno.models.openai.like import OpenAILike

        return OpenAILike(id=_model_id("openrouter"), api_key=key, base_url="https://openrouter.ai/api/v1")

    if provider == "ollama":
        # Ollama Cloud: OLLAMA_API_KEY makes host default to https://ollama.com.
        # Local: set OLLAMA_HOST (e.g. http://localhost:11434).
        ollama_key = getenv("OLLAMA_API_KEY")
        ollama_host = getenv("OLLAMA_HOST")
        if not (ollama_key or ollama_host):
            return None
        from agno.models.ollama import Ollama

        if ollama_host:
            return Ollama(id=_model_id("ollama"), host=ollama_host)
        return Ollama(id=_model_id("ollama"), api_key=ollama_key)

    if provider == "openai":
        key = getenv("OPENAI_API_KEY")
        if not key:
            return None
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=_model_id("openai"), api_key=key)

    if provider == "anthropic":
        key = getenv("ANTHROPIC_API_KEY")
        if not key:
            return None
        from agno.models.anthropic import Claude

        return Claude(id=_model_id("anthropic"), api_key=key)

    if provider == "google":
        key = getenv("GOOGLE_API_KEY")
        if not key:
            return None
        from agno.models.google import Gemini

        return Gemini(id=_model_id("google"), api_key=key)

    if provider == "groq":
        key = getenv("GROQ_API_KEY")
        if not key:
            return None
        from agno.models.groq import Groq

        return Groq(id=_model_id("groq"), api_key=key)

    return None


def build_model(provider: Optional[str] = None) -> Any:
    """Select and construct a model by available credentials (fresh instance each call)."""
    order = [provider.strip().lower()] if provider else _provider_order()
    for p in order:
        model = _try_provider(p)
        if model is not None:
            return model
    raise ValueError(
        "No model provider configured. Set one of: OLLAMA_API_KEY/OLLAMA_HOST, NVIDIA_API_KEY, "
        "MOONSHOT_API_KEY, OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "GOOGLE_API_KEY, GROQ_API_KEY (or pin DEFAULT_MODEL_PROVIDER)."
    )


def default_model() -> Any:
    """Fresh model instance per agent."""
    return build_model()
