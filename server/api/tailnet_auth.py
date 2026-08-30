"""Fail-closed owner testing authentication over a trusted Tailnet proxy.

This is a temporary bootstrap feature flag, not an authorization-policy engine.
Normal application authentication must be evaluated first.  Callers may use
this fallback only when the app-specific flag is enabled and the immediate
peer is an explicitly trusted Traefik address.

Byline: Codex · GPT-5 · 2026-08-29
"""

from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass
from os import getenv

from fastapi import HTTPException, Request

_TAILSCALE_CGNAT: ipaddress.IPv4Network = ipaddress.IPv4Network("100.64.0.0/10")
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_LOGGER = logging.getLogger("platform.auth.tailnet_testing")


@dataclass(frozen=True)
class TailnetTestingIdentity:
    """Auditable identity established by the Tailnet testing bypass."""

    principal: str
    subject_uid: str
    client_ip: str
    auth_method: str = "tailnet-testing-bypass"


def _env_name(app_prefix: str, suffix: str) -> str:
    normalized = app_prefix.strip().upper().replace("-", "_")
    if not normalized or not normalized.replace("_", "").isalnum():
        raise ValueError("app_prefix must contain only letters, numbers, hyphens, or underscores")
    return f"{normalized}_TAILNET_AUTH_{suffix}"


def _networks(raw: str, *, setting: str) -> tuple[ipaddress.IPv4Network, ...]:
    values = [value.strip() for value in raw.split(",") if value.strip()]
    if not values:
        raise HTTPException(status_code=503, detail=f"{setting} must contain at least one IPv4 CIDR")
    try:
        networks = tuple(ipaddress.ip_network(value, strict=True) for value in values)
    except ValueError:
        raise HTTPException(status_code=503, detail=f"{setting} contains an invalid CIDR") from None
    if any(not isinstance(network, ipaddress.IPv4Network) for network in networks):
        raise HTTPException(status_code=503, detail=f"{setting} accepts IPv4 CIDRs only")
    return networks  # type: ignore[return-value]


def tailnet_testing_identity(request: Request, *, app_prefix: str) -> TailnetTestingIdentity | None:
    """Return the testing identity when the request satisfies the bypass contract.

    Disabled or ineligible requests return ``None`` so the caller's normal auth
    behavior is unchanged.  An enabled but unsafe configuration fails closed.
    """

    enabled_name = _env_name(app_prefix, "BYPASS_ENABLED")
    if getenv(enabled_name, "false").strip().lower() not in _TRUE_VALUES:
        return None

    trusted_name = _env_name(app_prefix, "TRUSTED_PROXY_CIDRS")
    trusted_proxies = _networks(getenv(trusted_name, ""), setting=trusted_name)
    if any(network.prefixlen != 32 for network in trusted_proxies):
        raise HTTPException(status_code=503, detail=f"{trusted_name} accepts exact IPv4 peers (/32) only")
    peer_text = request.client.host if request.client else ""
    try:
        peer = ipaddress.ip_address(peer_text)
    except ValueError:
        return None
    if not isinstance(peer, ipaddress.IPv4Address) or not any(peer in network for network in trusted_proxies):
        return None

    # X-Real-IP is accepted only from the exact trusted peer set.  Multiple
    # values are rejected because this contract requires one proxy-controlled
    # client identity, not a client-supplied forwarding chain.
    client_text = request.headers.get("x-real-ip", "").strip()
    if not client_text or "," in client_text:
        return None
    try:
        client = ipaddress.ip_address(client_text)
    except ValueError:
        return None
    if not isinstance(client, ipaddress.IPv4Address):
        return None

    allowed_name = _env_name(app_prefix, "ALLOWED_CIDRS")
    allowed = _networks(getenv(allowed_name, str(_TAILSCALE_CGNAT)), setting=allowed_name)
    if any(not network.subnet_of(_TAILSCALE_CGNAT) for network in allowed):
        raise HTTPException(status_code=503, detail=f"{allowed_name} must be a subset of 100.64.0.0/10")
    if not any(client in network for network in allowed):
        return None

    identity = TailnetTestingIdentity(
        principal="tailnet-owner",
        subject_uid=f"tailscale:{client}",
        client_ip=str(client),
    )
    request.state.auth_principal = identity.principal
    request.state.auth_subject_uid = identity.subject_uid
    request.state.auth_method = identity.auth_method
    _LOGGER.info(
        json.dumps(
            {
                "event": "tailnet_testing_auth_bypass",
                "app": app_prefix.lower(),
                "principal": identity.principal,
                "subject_uid": identity.subject_uid,
                "client_ip": identity.client_ip,
                "method": request.method,
                "path": request.url.path,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return identity
