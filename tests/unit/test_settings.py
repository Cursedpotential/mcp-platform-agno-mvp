"""Unit tests for config/settings.py."""

import os
from unittest.mock import patch

import pytest

from config.settings import Settings, get_settings


class TestSettings:
    def test_default_values(self):
        """Settings should have sensible defaults."""
        settings = Settings()
        assert settings.default_model_provider == "openai"
        assert settings.default_model_id == "gpt-4o"
        assert settings.hitl_require_approval is True
        assert settings.hitl_approval_timeout_seconds == 3600
        assert settings.api_port == 8000

    def test_env_override(self):
        """Environment variables should override defaults."""
        with patch.dict(
            os.environ,
            {
                "DEFAULT_MODEL_PROVIDER": "anthropic",
                "DEFAULT_MODEL_ID": "claude-sonnet-4-20250514",
                "HITL_REQUIRE_APPROVAL": "false",
                "API_PORT": "9000",
            },
        ):
            settings = Settings()
            assert settings.default_model_provider == "anthropic"
            assert settings.default_model_id == "claude-sonnet-4-20250514"
            assert settings.hitl_require_approval is False
            assert settings.api_port == 9000

    def test_get_model_no_keys(self):
        """get_model should raise ValueError when no API keys are set."""
        settings = Settings(
            openai_api_key=None,
            anthropic_api_key=None,
            google_api_key=None,
            groq_api_key=None,
            ollama_base_url=None,
        )
        with pytest.raises(ValueError, match="No model provider API key found"):
            settings.get_model()

    def test_cached_settings(self):
        """get_settings should return cached instance."""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
