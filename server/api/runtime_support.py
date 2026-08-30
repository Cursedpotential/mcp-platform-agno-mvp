"""Framework-neutral runtime dependencies for the Platform API host.

This prevents API startup from importing Agno's session, Knowledge, or vector
adapters merely to configure PostgreSQL/R2 or a native Weaviate client.

Byline: Codex · GPT-5.6-Sol · 2026-08-29
"""

from __future__ import annotations

from os import getenv
from typing import Any

from server.core.url import db_url


def ensure_duckdb_r2_secret() -> bool:
    """Idempotently provision pg_duckdb's R2 secret when credentials exist."""

    key = getenv("R2_ACCESS_KEY_ID")
    secret = getenv("R2_SECRET_ACCESS_KEY")
    account = getenv("R2_ACCOUNT_ID")
    if not (key and secret and account):
        return False

    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "SELECT duckdb.create_simple_secret(type := 'S3', key_id := :key, "
                    "secret := :secret, region := 'auto', endpoint := :endpoint)"
                ),
                {
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
