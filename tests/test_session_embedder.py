"""Unit tests for server/core/session.py's embedder provider routing.

Regression coverage for the live 2026-08-01 knowledge-ingest outage: the text
embedder (``nvidia/nv-embed-v1``) is an NVIDIA NIM model, but before this fix
its base_url/api_key defaulted to OpenRouter whenever ``EMBED_BASE_URL``/
``EMBED_API_KEY`` were unset. OpenRouter does not host that model (verified
live: 400 "Model nvidia/nv-embed-v1 does not exist") and the platform's
OpenRouter key had no credits regardless (verified live: 402 on an
OpenRouter-native embedding model) — so every text-embed call silently
returned no vector via agno's swallow-and-return-None embedder contract,
while ``server/core/knowledge_vectordb.py`` (tested separately) covers the
"still reports COMPLETED" half of the bug.

session.py resolves its provider defaults at MODULE level (``getenv()`` calls
executed at import time), so each test reloads the module fresh from its file
after setting env vars — same technique as ``tests/test_db_url.py``.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

_SESSION_PATH = Path(__file__).resolve().parents[1] / "server" / "core" / "session.py"

_ENV_VARS = (
    "EMBED_BASE_URL",
    "EMBED_API_KEY",
    "EMBED_TEXT_ID",
    "EMBED_TEXT_DIM",
    "EMBED_CODE_ID",
    "EMBED_CODE_DIM",
    "NVIDIA_BASE_URL",
    "NVIDIA_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_API_KEY",
)


def _load_module(monkeypatch, **env):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    spec = importlib.util.spec_from_file_location("_session_under_test", _SESSION_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_module_no_live_weaviate(monkeypatch, **env):
    """Same as :func:`_load_module`, but with the Weaviate client factories
    stubbed out.

    ``create_knowledge()`` calls ``get_weaviate_client()`` (a *connecting*
    ``weaviate.connect_to_custom()`` call — see server/core/session.py) as a
    side effect of building the ``Knowledge`` object, even though these
    tests' actual intent is routing/wiring coverage (which embedder got
    picked, which VectorDb subclass got wired), never live Weaviate behavior.
    Without this stub the test suite opens a real socket to whatever
    WEAVIATE_HTTP_HOST resolves to and hangs/fails offline (2026-08-09 S2
    build-and-test-green task 2). ``VerifiedWeaviate.__init__`` (and agno's
    ``Weaviate.__init__`` beneath it) only *stores* the client it's given, but
    agno's ``Knowledge.__init__``/``get_client()`` path probes
    ``client.is_connected()`` during construction, so a plain sentinel object
    is not enough — a ``MagicMock`` (truthy, any-attribute) is.
    """
    mod = _load_module(monkeypatch, **env)
    monkeypatch.setattr(mod, "get_weaviate_client", lambda: MagicMock(name="fake_weaviate_client"))
    monkeypatch.setattr(mod, "get_weaviate_async_client", lambda: MagicMock(name="fake_weaviate_async_client"))
    return mod


# --- default routing (no explicit EMBED_* override) --------------------------


def test_text_embedder_defaults_to_nvidia_nim_not_openrouter(monkeypatch):
    # This is the exact bug: before the fix, an unset EMBED_BASE_URL/EMBED_API_KEY
    # made the text embedder fall through to OpenRouter, which does not host
    # nvidia/nv-embed-v1.
    mod = _load_module(
        monkeypatch,
        NVIDIA_BASE_URL="https://integrate.api.nvidia.com/v1",
        NVIDIA_API_KEY="nim-key",
        OPENROUTER_API_KEY="or-key",
    )
    assert mod._EMBED_TEXT_BASE_URL == "https://integrate.api.nvidia.com/v1"
    assert mod._EMBED_TEXT_API_KEY == "nim-key"


def test_text_embedder_uses_nvidia_default_base_url_when_unset(monkeypatch):
    # Even with no NVIDIA_BASE_URL override, the text embedder must land on the
    # real NVIDIA NIM host, not OpenRouter's.
    mod = _load_module(monkeypatch, NVIDIA_API_KEY="nim-key")
    assert mod._EMBED_TEXT_BASE_URL == "https://integrate.api.nvidia.com/v1"
    assert "openrouter" not in mod._EMBED_TEXT_BASE_URL


def test_code_embedder_still_defaults_to_openrouter(monkeypatch):
    # codestral-embed-2505 IS OpenRouter-hosted — only the text embedder's
    # default provider changes.
    mod = _load_module(monkeypatch, OPENROUTER_API_KEY="or-key")
    assert mod._EMBED_CODE_BASE_URL == "https://openrouter.ai/api/v1"
    assert mod._EMBED_CODE_API_KEY == "or-key"


# --- explicit EMBED_BASE_URL / EMBED_API_KEY override wins for BOTH ----------


def test_explicit_embed_override_wins_over_nvidia_default(monkeypatch):
    mod = _load_module(
        monkeypatch,
        EMBED_BASE_URL="https://custom-gateway.example/v1",
        EMBED_API_KEY="custom-key",
        NVIDIA_API_KEY="nim-key",
    )
    assert mod._EMBED_TEXT_BASE_URL == "https://custom-gateway.example/v1"
    assert mod._EMBED_TEXT_API_KEY == "custom-key"


def test_explicit_embed_override_wins_over_openrouter_default(monkeypatch):
    mod = _load_module(
        monkeypatch,
        EMBED_BASE_URL="https://custom-gateway.example/v1",
        EMBED_API_KEY="custom-key",
        OPENROUTER_API_KEY="or-key",
    )
    assert mod._EMBED_CODE_BASE_URL == "https://custom-gateway.example/v1"
    assert mod._EMBED_CODE_API_KEY == "custom-key"


# --- _embedder() wiring --------------------------------------------------------


def test_embedder_builds_openai_embedder_with_given_base_url_and_key(monkeypatch):
    mod = _load_module(monkeypatch)
    embedder = mod._embedder("nvidia/nv-embed-v1", 4096, "https://integrate.api.nvidia.com/v1", "nim-key")

    assert embedder.id == "nvidia/nv-embed-v1"
    assert embedder.dimensions == 4096
    assert embedder.api_key == "nim-key"
    assert embedder.client_params == {"base_url": "https://integrate.api.nvidia.com/v1"}


def test_create_knowledge_text_embedder_uses_nvidia_routing(monkeypatch):
    # Routing/wiring coverage only — the Weaviate client factories are stubbed
    # (see _load_module_no_live_weaviate) so this stays a fast unit test and
    # never opens a real socket to Weaviate.
    mod = _load_module_no_live_weaviate(monkeypatch, NVIDIA_API_KEY="nim-key")
    knowledge = mod.create_knowledge("platform", "platform_knowledge")

    embedder = knowledge.vector_db.embedder
    assert embedder.id == "nvidia/nv-embed-v1"
    assert embedder.client_params == {"base_url": "https://integrate.api.nvidia.com/v1"}
    assert embedder.api_key == "nim-key"


def test_create_knowledge_code_embedder_uses_openrouter_routing(monkeypatch):
    # Routing/wiring coverage only — see test_create_knowledge_text_embedder_
    # uses_nvidia_routing above for why the Weaviate client is stubbed.
    mod = _load_module_no_live_weaviate(monkeypatch, OPENROUTER_API_KEY="or-key")
    knowledge = mod.create_knowledge("platform_code", "platform_code_knowledge", use_code_embedder=True)

    embedder = knowledge.vector_db.embedder
    assert embedder.id == "mistralai/codestral-embed-2505"
    assert embedder.client_params == {"base_url": "https://openrouter.ai/api/v1"}
    assert embedder.api_key == "or-key"


def test_create_knowledge_uses_verified_weaviate(monkeypatch):
    # Regression guard for the "COMPLETED with zero vectors" bug: create_knowledge()
    # must wire VerifiedWeaviate (server/core/knowledge_vectordb.py), not the raw
    # agno Weaviate class, or a dead embedder silently reports success again.
    # This only checks the WIRED TYPE, not live behavior, so the Weaviate
    # client factories are stubbed (see _load_module_no_live_weaviate).
    mod = _load_module_no_live_weaviate(monkeypatch)
    knowledge = mod.create_knowledge("platform", "platform_knowledge")

    assert type(knowledge.vector_db).__name__ == "VerifiedWeaviate"
