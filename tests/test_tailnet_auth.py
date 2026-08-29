"""Contract tests for the feature-gated Tailnet owner-testing identity."""

from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from server.api.tailnet_auth import tailnet_testing_identity


def _request(*, peer: str = "172.20.0.2", client_ip: str | None = "100.64.1.9") -> Request:
    headers = [] if client_ip is None else [(b"x-real-ip", client_ip.encode())]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/owner/test",
            "raw_path": b"/owner/test",
            "query_string": b"",
            "headers": headers,
            "client": (peer, 43123),
            "server": ("agentos", 8000),
            "scheme": "https",
        }
    )


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTOS_TAILNET_AUTH_BYPASS_ENABLED", "true")
    monkeypatch.setenv("AGENTOS_TAILNET_AUTH_TRUSTED_PROXY_CIDRS", "172.20.0.2/32")
    monkeypatch.setenv("AGENTOS_TAILNET_AUTH_ALLOWED_CIDRS", "100.64.0.0/10")


def test_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTOS_TAILNET_AUTH_BYPASS_ENABLED", raising=False)
    assert tailnet_testing_identity(_request(), app_prefix="AGENTOS") is None


def test_trusted_proxy_and_tailnet_client_create_auditable_identity(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _enable(monkeypatch)
    request = _request()
    with caplog.at_level(logging.INFO, logger="platform.auth.tailnet_testing"):
        identity = tailnet_testing_identity(request, app_prefix="AGENTOS")
    assert identity is not None
    assert identity.principal == "tailnet-owner"
    assert identity.subject_uid == "tailscale:100.64.1.9"
    assert request.state.auth_principal == "tailnet-owner"
    assert '"event":"tailnet_testing_auth_bypass"' in caplog.text
    assert '"subject_uid":"tailscale:100.64.1.9"' in caplog.text


@pytest.mark.parametrize(
    ("peer", "client_ip"),
    [
        ("172.20.0.3", "100.64.1.9"),
        ("172.20.0.2", "192.168.1.5"),
        ("172.20.0.2", "100.64.1.9, 100.64.1.10"),
        ("172.20.0.2", None),
    ],
)
def test_untrusted_or_ineligible_request_does_not_bypass(
    monkeypatch: pytest.MonkeyPatch, peer: str, client_ip: str | None
) -> None:
    _enable(monkeypatch)
    assert tailnet_testing_identity(_request(peer=peer, client_ip=client_ip), app_prefix="AGENTOS") is None


def test_configured_allowed_range_must_stay_inside_tailscale_cgnat(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    monkeypatch.setenv("AGENTOS_TAILNET_AUTH_ALLOWED_CIDRS", "0.0.0.0/0")
    with pytest.raises(HTTPException) as caught:
        tailnet_testing_identity(_request(), app_prefix="AGENTOS")
    assert caught.value.status_code == 503


def test_trusted_proxy_configuration_is_required_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    monkeypatch.delenv("AGENTOS_TAILNET_AUTH_TRUSTED_PROXY_CIDRS")
    with pytest.raises(HTTPException) as caught:
        tailnet_testing_identity(_request(), app_prefix="AGENTOS")
    assert caught.value.status_code == 503


def test_trusted_proxy_configuration_rejects_broad_network(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable(monkeypatch)
    monkeypatch.setenv("AGENTOS_TAILNET_AUTH_TRUSTED_PROXY_CIDRS", "172.20.0.0/16")
    with pytest.raises(HTTPException) as caught:
        tailnet_testing_identity(_request(), app_prefix="AGENTOS")
    assert caught.value.status_code == 503
