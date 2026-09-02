"""Framework-neutral runtime dependencies for the Platform API host.

This prevents API startup from importing Agno's session, Knowledge, or vector
adapters merely to configure PostgreSQL/R2 or a native Weaviate client.

Byline: Codex · GPT-5.6-Sol · 2026-08-29
Byline: Claude Code · Sonnet 5 · 2026-09-02 (secret-idempotence fix, BUILD LANE E1)
"""

from __future__ import annotations

from os import getenv
from typing import Any

from server.core.url import db_url

# pg_duckdb auto-names each duckdb.create_simple_secret() call with no
# explicit `name` argument as pgduckdb_secret_simple_s3_secret[_N] — calling
# it unconditionally on every API boot (the prior behavior here) never
# collides, so it silently accumulated one new secret per restart (94 found
# live on the platform DB, 2026-09-02). Naming the secret explicitly makes
# duckdb_secrets() itself the idempotency key: CREATE ... IF NOT EXISTS-style
# behavior via an existence check first, one fixed name, never a bare retry.
_DUCKDB_R2_SECRET_NAME = "platform_r2"


def _duckdb_r2_secret_exists(connection: Any) -> bool:
    """True if a secret named ``_DUCKDB_R2_SECRET_NAME`` already exists.

    Split out from ``ensure_duckdb_r2_secret`` so it is unit-testable against
    a fake ``connection.execute(...).fetchone()`` without a real database.
    """

    from sqlalchemy import text

    row = connection.execute(
        text(
            "SELECT 1 FROM duckdb.query("
            "$pgduckdb_secret_probe$SELECT name FROM duckdb_secrets()$pgduckdb_secret_probe$"
            ") AS t(name text) WHERE t.name = :name"
        ),
        {"name": _DUCKDB_R2_SECRET_NAME},
    ).fetchone()
    return row is not None


def ensure_duckdb_r2_secret() -> bool:
    """Idempotently provision pg_duckdb's R2 secret when credentials exist.

    Checks ``duckdb_secrets()`` for the named secret first and only calls
    ``duckdb.create_simple_secret`` when it is absent — the prior
    implementation called ``create_simple_secret`` unconditionally on every
    call, and because pg_duckdb auto-names unnamed secrets uniquely, every
    API restart left one more orphaned secret behind (94 duplicates found
    live, 2026-09-02).
    """

    key = getenv("R2_ACCESS_KEY_ID")
    secret = getenv("R2_SECRET_ACCESS_KEY")
    account = getenv("R2_ACCOUNT_ID")
    if not (key and secret and account):
        return False

    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            if _duckdb_r2_secret_exists(connection):
                return True
            connection.execute(
                text(
                    "SELECT duckdb.create_simple_secret(type := 'S3', name := :name, "
                    "key_id := :key, secret := :secret, region := 'auto', endpoint := :endpoint)"
                ),
                {
                    "name": _DUCKDB_R2_SECRET_NAME,
                    "key": key,
                    "secret": secret,
                    "endpoint": f"{account}.r2.cloudflarestorage.com",
                },
            )
        return True
    except Exception:
        # Existing secret and unavailable optional pg_duckdb are non-fatal.
        return False
    finally:
        engine.dispose()


def create_weaviate_client() -> Any:
    """Create the native lazy Weaviate v4 client from deployment settings."""

    import weaviate
    from weaviate.classes.init import Auth

    host = getenv("WEAVIATE_HTTP_HOST", "100.91.190.107")
    api_key = getenv("WEAVIATE_API_KEY", "")
    return weaviate.connect_to_custom(
        http_host=host,
        http_port=int(getenv("WEAVIATE_HTTP_PORT", "8081")),
        http_secure=False,
        grpc_host=host,
        grpc_port=int(getenv("WEAVIATE_GRPC_PORT", "50051")),
        grpc_secure=False,
        auth_credentials=Auth.api_key(api_key) if api_key else None,
        skip_init_checks=True,
    )
