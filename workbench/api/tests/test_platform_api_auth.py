"""Runtime Platform API bearer-file contract tests.

Byline: Codex · GPT-5 · 2026-08-29
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.repo import platform_api_auth


def _use_secret(monkeypatch, path) -> None:
    monkeypatch.setattr(platform_api_auth.settings, "platform_api_bearer_secret_file", str(path))


def test_bearer_is_read_fresh_for_every_request(monkeypatch, tmp_path) -> None:
    secret = tmp_path / "os-security-key"
    _use_secret(monkeypatch, secret)
    secret.write_bytes(b"first-key")

    assert platform_api_auth.platform_api_bearer_headers() == {"Authorization": "Bearer first-key"}

    secret.write_bytes(b"rotated-key")
    assert platform_api_auth.platform_api_bearer_headers() == {"Authorization": "Bearer rotated-key"}


@pytest.mark.parametrize(
    "raw",
    [b"", b"key\n", b"key\r\n", b"key with spaces", b"Bearer key", b"bad:key", b"\xff"],
)
def test_invalid_secret_fails_closed_without_echoing_content(monkeypatch, tmp_path, raw: bytes) -> None:
    secret = tmp_path / "os-security-key"
    secret.write_bytes(raw)
    _use_secret(monkeypatch, secret)

    with pytest.raises(platform_api_auth.PlatformAPIAuthError) as caught:
        platform_api_auth.platform_api_bearer_headers()

    assert str(caught.value) == "Platform API bearer secret is unavailable or invalid"
    assert repr(raw) not in str(caught.value)


def test_missing_secret_fails_closed_without_exposing_path(monkeypatch, tmp_path) -> None:
    secret = tmp_path / "missing-os-security-key"
    _use_secret(monkeypatch, secret)

    with pytest.raises(platform_api_auth.PlatformAPIAuthError) as caught:
        platform_api_auth.platform_api_bearer_headers()

    assert str(secret) not in str(caught.value)


def test_legacy_agentos_api_token_environment_is_not_consumed(monkeypatch) -> None:
    monkeypatch.setenv("AGENTOS_API_TOKEN", "must-not-be-consumed")

    configured = Settings(_env_file=None)

    assert not hasattr(configured, "agentos_api_token")
