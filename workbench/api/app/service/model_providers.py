"""Model provider factory for classification and sentiment analysis.

Follows the pattern from server/core/settings.py but tailored for
workbench classification/sentiment use cases.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from agno.models.message import Message
from agno.models.openai.like import OpenAILike
from agno.models.ollama import Ollama
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat
from agno.models.google import Gemini
from agno.models.groq import Groq

from app.types.classification import ProviderName


NVIDIA_BASE_URL_DEFAULT = "https://integrate.api.nvidia.com/v1"

# Pinned default models per provider (can be overridden via env)
_PINNED_MODELS: dict[ProviderName, str] = {
    ProviderName.OLLAMA: "glm-5.1",
    ProviderName.NVIDIA: "nvidia/nemotron-3-super-120b-a12b",
    ProviderName.OPENROUTER: "deepseek/deepseek-chat",
    ProviderName.ANTHROPIC: "claude-sonnet-4-6",
    ProviderName.OPENAI: "gpt-4o",
    ProviderName.GOOGLE: "gemini-2.0-flash",
    ProviderName.GROQ: "llama-3.3-70b-versatile",
    ProviderName.PORTKEY: "gpt-4o",  # Portkey routes to various models
}


class ModelProvider(Protocol):
    """Protocol for model providers used in classification/sentiment."""

    async def arun(self, messages: list[Message], **kwargs: Any) -> Any: ...

    @property
    def id(self) -> str: ...


def _model_id(provider: ProviderName, model_id: str | None = None) -> str:
    """Resolve model ID for provider."""
    if model_id:
        return model_id
    env_key = f"{provider.value.upper()}_MODEL_ID"
    per = os.getenv(env_key)
    if per:
        return per
    return os.getenv("DEFAULT_MODEL_ID") or _PINNED_MODELS[provider]


def _try_provider(provider: ProviderName, model_id: str | None = None) -> ModelProvider | None:
    """Construct a model provider if credentials exist."""
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    nvidia_base = os.getenv("NVIDIA_BASE_URL", NVIDIA_BASE_URL_DEFAULT)

    resolved_model = _model_id(provider, model_id)

    if provider == ProviderName.NVIDIA:
        if not nvidia_key:
            return None
        return OpenAILike(id=resolved_model, api_key=nvidia_key, base_url=nvidia_base)

    if provider == ProviderName.OPENROUTER:
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            return None
        return OpenAILike(id=resolved_model, api_key=key, base_url="https://openrouter.ai/api/v1")

    if provider == ProviderName.OLLAMA:
        ollama_key = os.getenv("OLLAMA_API_KEY")
        ollama_host = os.getenv("OLLAMA_HOST")
        if not (ollama_key or ollama_host):
            return None
        if ollama_host:
            return Ollama(id=resolved_model, host=ollama_host)
        return Ollama(id=resolved_model, api_key=ollama_key)

    if provider == ProviderName.OPENAI:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            return None
        return OpenAIChat(id=resolved_model, api_key=key)

    if provider == ProviderName.ANTHROPIC:
        key = os.getenv("ANTHROPIC_API_KEY")
        auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
        if not (key or auth_token):
            return None
        return Claude(id=resolved_model, api_key=key, auth_token=auth_token)

    if provider == ProviderName.GOOGLE:
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            return None
        return Gemini(id=resolved_model, api_key=key)

    if provider == ProviderName.GROQ:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            return None
        return Groq(id=resolved_model, api_key=key)

    if provider == ProviderName.PORTKEY:
        key = os.getenv("PORTKEY_API_KEY")
        portkey_base = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
        if not key:
            return None
        # Portkey uses OpenAI-compatible API with virtual keys for routing
        # The model_id can include the virtual key routing: e.g., "portkey/virtual-key-name"
        return OpenAILike(id=resolved_model, api_key=key, base_url=portkey_base)

    return None


def build_provider(provider: ProviderName, model_id: str | None = None) -> ModelProvider:
    """Build a model provider instance.

    Creates a fresh instance on every call - do NOT cache.
    """
    model = _try_provider(provider, model_id)
    if model is None:
        available = [p.value for p in ProviderName if _try_provider(p) is not None]
        raise ValueError(
            f"Provider '{provider.value}' not configured. "
            f"Available: {available}. "
            f"Set API key or host for {provider.value}."
        )
    return model


def list_available_providers() -> dict[ProviderName, bool]:
    """Check which providers have valid credentials."""
    return {p: _try_provider(p) is not None for p in ProviderName}


async def run_classification(
    provider: ModelProvider,
    text: str,
    categories: list[str],
    system_prompt: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> tuple[str, float, str, str]:
    """Run classification with a provider.

    Returns: (category, confidence, reasoning, raw_response)
    """
    categories_str = ", ".join(f'"{c}"' for c in categories)

    default_system = f"""You are a precise text classifier. Classify the input text into EXACTLY ONE of these categories: {categories_str}.

Return ONLY a JSON object with this exact structure:
{{
  "category": "<one of the categories>",
  "confidence": <float 0-1>,
  "reasoning": "<brief explanation>"
}}"""

    messages = [
        Message(role="system", content=system_prompt or default_system),
        Message(role="user", content=text),
    ]

    response = await provider.arun(messages, temperature=temperature, max_tokens=max_tokens)

    raw = str(response.content) if response.content else ""

    # Parse JSON response
    import json

    try:
        # Try to extract JSON from response
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            parsed = json.loads(raw[json_start:json_end])
            category = parsed.get("category", categories[0])
            confidence = float(parsed.get("confidence", 0.5))
            reasoning = parsed.get("reasoning", "No reasoning provided")
        else:
            # Fallback: try to find category in text
            category = categories[0]
            confidence = 0.5
            reasoning = "Failed to parse structured response"
    except (json.JSONDecodeError, ValueError, KeyError):
        category = categories[0]
        confidence = 0.5
        reasoning = "Failed to parse response as JSON"

    return category, confidence, reasoning, raw


async def run_sentiment(
    provider: ModelProvider,
    text: str,
    system_prompt: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    include_emotions: bool = True,
) -> tuple[str, float, dict[str, float], str, str]:
    """Run sentiment analysis with a provider.

    Returns: (sentiment, score, emotions, reasoning, raw_response)
    """
    emotions_list = "anger, joy, fear, sadness, surprise, disgust, trust, anticipation"

    default_system = f"""You are a precise sentiment analyzer. Analyze the input text and return ONLY a JSON object with this exact structure:
{{
  "sentiment": "<positive|negative|neutral|mixed>",
  "score": <float -1.0 to 1.0>,
  "emotions": {{"{emotions_list.replace(", ", '": 0.0, "')}": 0.0}},
  "reasoning": "<brief explanation>"
}}

The emotions object should contain scores 0.0-1.0 for each emotion present."""

    messages = [
        Message(role="system", content=system_prompt or default_system),
        Message(role="user", content=text),
    ]

    response = await provider.arun(messages, temperature=temperature, max_tokens=max_tokens)

    raw = str(response.content) if response.content else ""

    import json

    try:
        json_start = raw.find("{")
        json_end = raw.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            parsed = json.loads(raw[json_start:json_end])
            sentiment = parsed.get("sentiment", "neutral")
            score = float(parsed.get("score", 0.0))
            emotions = parsed.get("emotions", {})
            reasoning = parsed.get("reasoning", "No reasoning provided")
        else:
            sentiment = "neutral"
            score = 0.0
            emotions = {}
            reasoning = "Failed to parse structured response"
    except (json.JSONDecodeError, ValueError, KeyError):
        sentiment = "neutral"
        score = 0.0
        emotions = {}
        reasoning = "Failed to parse response as JSON"

    return sentiment, score, emotions, reasoning, raw
