"""
Database URL
============

Credential resolution order (D-122, 2026-09-01 — Coolify env carries no secret
values; rotation must never require a rebuild or redeploy):

1. ``PLATFORM_DB_URL`` — explicit connection string (tests / local only).
2. **Infisical dynamic credentials** — when ``INFISICAL_HOST``,
   ``INFISICAL_CLIENT_ID``, ``INFISICAL_CLIENT_SECRET`` and
   ``INFISICAL_PROJECT_SLUG`` are set, a short-lived PostgreSQL role is leased
   from the broker at process start. No static database password exists
   anywhere in the deployment; the only bootstrap secret is the machine
   identity's client secret.
3. ``DB_USER`` / ``DB_PASS`` env — legacy fallback, retained only so a broker
   outage can be bridged deliberately; not a supported steady state.
"""

from __future__ import annotations

import json
import logging
from os import getenv
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)


def _post_json(url: str, body: dict[str, object], token: str | None = None, timeout: int = 20) -> dict[str, object]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - tailnet broker URL from deployment config
        return json.loads(response.read().decode())


def lease_dynamic_db_credentials() -> tuple[str, str] | None:
    """Lease a PostgreSQL username/password pair from Infisical.

    Returns ``None`` when the broker is not configured. Raises when it is
    configured but the lease cannot be obtained — a misconfigured broker must
    fail loudly, never silently downgrade to a static password.
    """
    host = getenv("INFISICAL_HOST", "").rstrip("/")
    client_id = getenv("INFISICAL_CLIENT_ID", "")
    client_secret = getenv("INFISICAL_CLIENT_SECRET", "")
    project = getenv("INFISICAL_PROJECT_SLUG", "")
    if not (host and client_id and client_secret and project):
        return None

    login = _post_json(
        f"{host}/api/v1/auth/universal-auth/login",
        {"clientId": client_id, "clientSecret": client_secret},
    )
    token = str(login["accessToken"])
    lease = _post_json(
        f"{host}/api/v1/dynamic-secrets/leases",
        {
            "dynamicSecretName": getenv("INFISICAL_DB_DYNAMIC_SECRET", "platform-postgres"),
            "projectSlug": project,
            "environmentSlug": getenv("INFISICAL_ENV_SLUG", "prod"),
            "path": getenv("INFISICAL_SECRET_PATH", "/"),
            "ttl": getenv("INFISICAL_DB_LEASE_TTL", "720h"),
        },
        token=token,
    )
    data = lease.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Infisical dynamic secret lease returned no data block")
    username, password = data.get("DB_USERNAME"), data.get("DB_PASSWORD")
    if not (isinstance(username, str) and isinstance(password, str) and username and password):
        raise RuntimeError("Infisical dynamic secret lease returned no DB_USERNAME/DB_PASSWORD")
    lease_meta = lease.get("lease")
    lease_id = lease_meta.get("id") if isinstance(lease_meta, dict) else None
    _log.info("database credentials leased from Infisical (role=%s, lease=%s)", username, lease_id)
    return username, password


def build_db_url() -> str:
    """Build database URL from the broker or, failing that, environment variables."""
    # Prefer explicit connection string if provided
    platform_url = getenv("PLATFORM_DB_URL")
    if platform_url:
        return platform_url

    driver = getenv("DB_DRIVER", "postgresql+psycopg")
    host = getenv("DB_HOST", "localhost")
    port = getenv("DB_PORT", "5432")
    database = getenv("DB_DATABASE", "platform")

    user, password = getenv("DB_USER", "ai"), getenv("DB_PASS", "ai")
    try:
        leased = lease_dynamic_db_credentials()
    except (URLError, OSError, KeyError, ValueError, RuntimeError) as exc:
        if getenv("DB_PASS"):
            _log.error(
                "Infisical lease failed (%s); bridging on legacy DB_PASS env — not a supported steady state", exc
            )
            leased = None
        else:
            raise
    if leased:
        user, password = leased

    return f"{driver}://{user}:{quote(password, safe='')}@{host}:{port}/{database}"


db_url = build_db_url()
