"""Release-gate tests for the Traefik+Authentik Workbench boundary.

Byline: Codex · GPT-5 · 2026-08-15
Byline: Codex · GPT-5 · 2026-08-29 (passwordless tailnet access)
Byline: Codex · GPT-5 · 2026-08-29 (strict trusted-proxy + Authentik identity headers)
"""

from __future__ import annotations

import ipaddress
from unittest.mock import patch

from app.config import Settings
from app.runtime import auth
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from main import app as workbench_app
from starlette.middleware.base import BaseHTTPMiddleware


def _client(
    host: str,
    cidrs: str | None = None,
    *,
    tailnet_bypass: bool = False,
    tailnet_cidrs: str = "100.64.0.0/10",
) -> TestClient:
    """Create an isolated auth client without mutating global settings."""
    configured_settings = Settings(_env_file=None)
    if cidrs is not None:
        object.__setattr__(configured_settings, "trusted_auth_proxy_cidrs", cidrs)
    object.__setattr__(configured_settings, "tailnet_auth_bypass_enabled", tailnet_bypass)
    object.__setattr__(configured_settings, "tailnet_auth_bypass_cidrs", tailnet_cidrs)

    app = FastAPI()

    async def isolated_authentication_middleware(request, call_next):
        with patch("app.runtime.auth.settings", configured_settings):
            return await auth.authentication_middleware(request, call_next)

    app.add_middleware(BaseHTTPMiddleware, dispatch=isolated_authentication_middleware)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/principal")
    def principal(request: Request) -> dict[str, str]:
        return {"principal": request.state.principal, "subject_uid": request.state.subject_uid}

    @app.get("/{path:path}")
    def protected_surface(path: str) -> dict[str, str]:
        return {"path": path}

    return TestClient(app, client=(host, 50000))


class TestFeatureGatedTailnetBypass:
    """Tailnet testing bypass works only through the trusted proxy."""

    def test_enabled_tailnet_client_is_authenticated_without_authentik(self) -> None:
        client = _client("172.18.0.4", "172.18.0.4/32", tailnet_bypass=True)
        response = client.get("/principal", headers={"X-Real-IP": "100.88.12.4"})
        assert response.status_code == 200
        assert response.json() == {
            "principal": "tailnet-owner",
            "subject_uid": "tailscale:100.88.12.4",
        }

    def test_disabled_bypass_still_requires_authentik(self) -> None:
        client = _client("172.18.0.4", "172.18.0.4/32")
        response = client.get("/principal", headers={"X-Real-IP": "100.88.12.4"})
        assert response.status_code == 403

    def test_non_tailnet_forwarded_client_is_rejected(self) -> None:
        client = _client("172.18.0.4", "172.18.0.4/32", tailnet_bypass=True)
        response = client.get("/principal", headers={"X-Real-IP": "192.0.2.10"})
        assert response.status_code == 403

    def test_untrusted_peer_cannot_spoof_tailnet_client(self) -> None:
        client = _client("172.19.0.9", "172.18.0.4/32", tailnet_bypass=True)
        response = client.get("/principal", headers={"X-Real-IP": "100.88.12.4"})
        assert response.status_code == 403
        assert response.json() == {"detail": "Untrusted proxy"}

    def test_configured_range_must_remain_inside_tailscale(self) -> None:
        client = _client(
            "172.18.0.4",
            "172.18.0.4/32",
            tailnet_bypass=True,
            tailnet_cidrs="0.0.0.0/0",
        )
        response = client.get("/principal", headers={"X-Real-IP": "100.88.12.4"})
        assert response.status_code == 403


class TestHealthExactness:
    """Test that /health is the ONLY public exception."""

    def test_exact_health_path_is_public(self) -> None:
        client = _client("172.18.0.4", "10.0.0.0/8")
        assert client.get("/health").status_code == 200

    def test_health_with_trailing_slash_is_protected(self) -> None:
        client = _client("172.18.0.4", "10.0.0.0/8")
        assert client.get("/health/").status_code == 403

    def test_health_subpath_is_protected(self) -> None:
        client = _client("172.18.0.4", "10.0.0.0/8")
        assert client.get("/health/check").status_code == 403

    def test_all_other_paths_protected(self) -> None:
        client = _client("172.18.0.4", "10.0.0.0/8")
        assert client.get("/api/matters").status_code == 403
        assert client.get("/").status_code == 403
        assert client.get("/openapi.json").status_code == 403
        assert client.get("/docs").status_code == 403


class TestEmptyConfigFailClosed:
    """Test that empty/invalid config denies all protected traffic."""

    def test_empty_cidrs_denies_all(self) -> None:
        client = _client("10.1.2.3", "")
        assert client.get("/api/matters").status_code == 403
        assert client.get("/api/matters").json() == {"detail": "Authentication gateway not configured"}

    def test_missing_cidrs_denies_all(self) -> None:
        # Settings with default empty string
        client = _client("10.1.2.3", None)
        assert client.get("/api/matters").status_code == 403
        assert client.get("/api/matters").json() == {"detail": "Authentication gateway not configured"}

    def test_whitespace_only_cidrs_denies_all(self) -> None:
        client = _client("10.1.2.3", "   ")
        assert client.get("/api/matters").status_code == 403


class TestValidTrustedProxyWithIdentity:
    """Test valid trusted proxy + valid Authentik identity headers."""

    def test_valid_trusted_proxy_and_identity(self) -> None:
        cidrs = "10.0.0.0/8,172.16.0.0/12"
        client = _client("10.1.2.3", cidrs)

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-123",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"principal": "john.doe", "subject_uid": "user-123"}

    def test_case_insensitive_headers(self) -> None:
        cidrs = "10.0.0.0/8"
        client = _client("10.1.2.3", cidrs)

        # Starlette Headers are case-insensitive
        response = client.get(
            "/principal",
            headers={
                "x-authentik-uid": "user-456",
                "x-authentik-username": "jane.doe",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"principal": "jane.doe", "subject_uid": "user-456"}

    def test_mixed_case_headers(self) -> None:
        cidrs = "10.0.0.0/8"
        client = _client("10.1.2.3", cidrs)

        response = client.get(
            "/principal",
            headers={
                "X-Authentik-Uid": "user-789",
                "X-Authentik-Username": "mixed.case",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"principal": "mixed.case", "subject_uid": "user-789"}

    def test_ipv6_cidr(self) -> None:
        cidrs = "2001:db8::/32"
        client = _client("2001:db8::1", cidrs)

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-ipv6",
                "X-authentik-username": "ipv6.user",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"principal": "ipv6.user", "subject_uid": "user-ipv6"}

    def test_multiple_cidrs_first_matches(self) -> None:
        cidrs = "10.0.0.0/8,192.168.0.0/16"
        client = _client("10.5.6.7", cidrs)

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-multi",
                "X-authentik-username": "multi.cidr",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"principal": "multi.cidr", "subject_uid": "user-multi"}


class TestMissingIdentityHeaders:
    """Test rejection when Authentik headers are missing."""

    def test_missing_uid_header(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={"X-authentik-username": "john.doe"},
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_missing_username_header(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={"X-authentik-uid": "user-123"},
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_both_headers_missing(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get("/principal")
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}


class TestBlankIdentityHeaders:
    """Test rejection when Authentik headers are blank."""

    def test_blank_uid_header(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_blank_username_header(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-123",
                "X-authentik-username": "",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_whitespace_only_headers(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "   ",
                "X-authentik-username": "  ",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}


class TestSpoofedHeadersFromUntrustedPeer:
    """Test rejection of Authentik headers from untrusted socket peers."""

    def test_untrusted_peer_with_valid_headers_denied(self) -> None:
        client = _client("172.18.0.4", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-123",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Untrusted proxy"}

    def test_tailnet_peer_directly_denied(self) -> None:
        # Direct tailnet IP (100.64.0.0/10) not in trusted CIDRs
        client = _client("100.101.22.33", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-123",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Untrusted proxy"}

    def test_docker_default_bridge_denied(self) -> None:
        client = _client("172.17.0.2", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-123",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Untrusted proxy"}


class TestXForwardedForNonAuthority:
    """Test that X-Forwarded-For is ignored for trust decisions."""

    def test_x_forwarded_for_ignored_for_trust(self) -> None:
        # Client is untrusted (172.18.0.4), but X-Forwarded-For claims trusted IP
        client = _client("172.18.0.4", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-Forwarded-For": "10.1.2.3",
                "X-authentik-uid": "user-123",
                "X-authentik-username": "john.doe",
            },
        )
        # Must be denied because socket peer is untrusted
        assert response.status_code == 403
        assert response.json() == {"detail": "Untrusted proxy"}

    def test_x_forwarded_for_chain_ignored(self) -> None:
        client = _client("172.18.0.4", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-Forwarded-For": "10.1.2.3, 10.2.3.4, 10.3.4.5",
                "X-authentik-uid": "user-123",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Untrusted proxy"}


class TestMalformedCIDR:
    """Test that malformed CIDR configuration fails closed."""

    def test_invalid_cidr_syntax(self) -> None:
        client = _client("10.1.2.3", "not-a-cidr")
        assert client.get("/api/matters").status_code == 403
        assert client.get("/api/matters").json() == {"detail": "Authentication gateway not configured"}

    def test_invalid_cidr_host_bits_set(self) -> None:
        # 10.1.2.3/8 has host bits set - strict=True should reject
        client = _client("10.1.2.3", "10.1.2.3/8")
        assert client.get("/api/matters").status_code == 403
        assert client.get("/api/matters").json() == {"detail": "Authentication gateway not configured"}

    def test_malformed_in_list(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8,invalid,192.168.0.0/16")
        assert client.get("/api/matters").status_code == 403
        assert client.get("/api/matters").json() == {"detail": "Authentication gateway not configured"}

    def test_empty_part_in_list(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8,,192.168.0.0/16")
        assert client.get("/api/matters").status_code == 403
        assert client.get("/api/matters").json() == {"detail": "Authentication gateway not configured"}


class TestControlCharsAndLengthLimits:
    """Test rejection of control characters and oversized header values."""

    def test_control_char_in_uid(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user\x00123",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_control_char_in_username(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-123",
                "X-authentik-username": "john\x1fdoe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_del_char_in_header(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user\x7f123",
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_oversized_uid(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        oversized = "u" * 257  # > 256 limit
        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": oversized,
                "X-authentik-username": "john.doe",
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_oversized_username(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        oversized = "u" * 257  # > 256 limit
        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": "user-123",
                "X-authentik-username": oversized,
            },
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Missing or invalid Authentik identity"}

    def test_exact_max_length_accepted(self) -> None:
        client = _client("10.1.2.3", "10.0.0.0/8")

        exact = "u" * 256  # exactly at limit
        response = client.get(
            "/principal",
            headers={
                "X-authentik-uid": exact,
                "X-authentik-username": exact,
            },
        )
        assert response.status_code == 200


class TestRealAppWiring:
    """Test real app wiring with settings patched safely."""

    def test_real_app_health_public(self) -> None:
        # Health must be public even on real app
        with patch("app.runtime.auth.settings", Settings(_env_file=None)):
            client = TestClient(workbench_app, client=("172.18.0.4", 50000))
            assert client.get("/health").status_code == 200

    def test_real_app_protected_denied_without_config(self) -> None:
        with patch("app.runtime.auth.settings", Settings(_env_file=None)):
            client = TestClient(workbench_app, client=("172.18.0.4", 50000))
            assert client.get("/openapi.json").status_code == 403

    def test_real_app_valid_proxy_and_identity(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "10.0.0.0/8")
        with patch("app.runtime.auth.settings", s):
            client = TestClient(workbench_app, client=("10.1.2.3", 50000))
            response = client.get(
                "/openapi.json",
                headers={
                    "X-authentik-uid": "user-123",
                    "X-authentik-username": "john.doe",
                },
            )
            assert response.status_code == 200

    def test_real_app_untrusted_peer_denied(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "10.0.0.0/8")
        with patch("app.runtime.auth.settings", s):
            client = TestClient(workbench_app, client=("172.18.0.4", 50000))
            response = client.get(
                "/openapi.json",
                headers={
                    "X-authentik-uid": "user-123",
                    "X-authentik-username": "john.doe",
                },
            )
            assert response.status_code == 403
            assert response.json() == {"detail": "Untrusted proxy"}


class TestSettingsParsing:
    """Test the settings trusted_auth_proxy_cidrs_parsed property directly."""

    def test_valid_cidrs_parsed(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "10.0.0.0/8,192.168.0.0/16")
        parsed = s.trusted_auth_proxy_cidrs_parsed
        assert len(parsed) == 2
        assert ipaddress.ip_network("10.0.0.0/8") in parsed
        assert ipaddress.ip_network("192.168.0.0/16") in parsed

    def test_valid_ipv6_cidrs_parsed(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "2001:db8::/32,2001:db9::/32")
        parsed = s.trusted_auth_proxy_cidrs_parsed
        assert len(parsed) == 2
        assert ipaddress.ip_network("2001:db8::/32") in parsed

    def test_empty_string_returns_empty_list(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "")
        assert s.trusted_auth_proxy_cidrs_parsed == []

    def test_whitespace_returns_empty_list(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "   ")
        assert s.trusted_auth_proxy_cidrs_parsed == []

    def test_invalid_cidr_returns_empty_list(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "not-a-cidr")
        assert s.trusted_auth_proxy_cidrs_parsed == []

    def test_host_bits_set_returns_empty_list(self) -> None:
        s = Settings(_env_file=None)
        object.__setattr__(s, "trusted_auth_proxy_cidrs", "10.1.2.3/8")
        assert s.trusted_auth_proxy_cidrs_parsed == []
