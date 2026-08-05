"""Tests for server/core/model_registry.py — the AgentOS Studio model catalog.

Covers the parsing contract (Ollama tags contain colons, NVIDIA ids contain
slashes), the credential-driven skip, and the config.yaml round-trip that keeps
`AgentOSConfig.available_models` and `Registry.models` from drifting apart.

Byline: Claude Code · Fable 5 · 2026-08-02
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.core.model_registry import (
    build_catalog_models,
    load_available_models,
    parse_model_string,
)

CONFIG_YAML = Path(__file__).resolve().parents[1] / "server" / "api" / "config.yaml"


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("ollama:glm-5.1", ("ollama", "glm-5.1")),
        # Ollama tags legitimately contain a colon — split on the FIRST one only.
        ("ollama:deepseek-v4-flash:0731", ("ollama", "deepseek-v4-flash:0731")),
        # NVIDIA ids are slash-namespaced, not colon-namespaced.
        ("nvidia:meta/llama-3.3-70b-instruct", ("nvidia", "meta/llama-3.3-70b-instruct")),
        ("OLLAMA:glm-5.1", ("ollama", "glm-5.1")),
    ],
)
def test_parse_model_string_valid(entry: str, expected: tuple[str, str]) -> None:
    assert parse_model_string(entry) == expected


@pytest.mark.parametrize("entry", ["", "glm-5.1", "ollama:", "notaprovider:foo", ":foo"])
def test_parse_model_string_rejects(entry: str) -> None:
    assert parse_model_string(entry) is None


def test_build_catalog_models_skips_uncredentialed_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only providers with live credentials become picker entries."""
    for var in (
        "OLLAMA_API_KEY",
        "OLLAMA_HOST",
        "NVIDIA_API_KEY",
        "MOONSHOT_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "DEFAULT_MODEL_ID",
        "OLLAMA_MODEL_ID",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")

    models = build_catalog_models(["ollama:glm-5.1", "ollama:kimi-k3", "nvidia:meta/llama-3.3-70b-instruct", "garbage"])

    assert [m.id for m in models] == ["glm-5.1", "kimi-k3"]


def test_build_catalog_models_dedups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.delenv("OLLAMA_MODEL_ID", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL_ID", raising=False)
    models = build_catalog_models(["ollama:glm-5.1", "ollama:glm-5.1"])
    assert len(models) == 1


def test_explicit_model_id_beats_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """A catalog entry names an exact model — env defaults must not hijack it."""
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_MODEL_ID", "some-other-model")
    monkeypatch.setenv("DEFAULT_MODEL_ID", "yet-another-model")
    models = build_catalog_models(["ollama:glm-5.2"])
    assert [m.id for m in models] == ["glm-5.2"]


def test_config_yaml_available_models_all_parse() -> None:
    """Every published catalog entry must be constructible-shaped.

    This is the guard that keeps `available_models` (the /config surface) and
    `Registry.models` (the Studio picker surface) describing the same set.
    """
    entries = load_available_models(CONFIG_YAML)
    assert entries, "config.yaml lost its available_models list"
    unparsed = [e for e in entries if parse_model_string(e) is None]
    assert unparsed == []


def test_load_available_models_missing_file_is_not_fatal(tmp_path: Path) -> None:
    assert load_available_models(tmp_path / "nope.yaml") == []
