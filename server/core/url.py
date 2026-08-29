"""
Database URL
============
"""

from os import getenv
from urllib.parse import quote


def build_db_url() -> str:
    """Build database URL from environment variables."""
    # Prefer explicit connection string if provided
    platform_url = getenv("PLATFORM_DB_URL")
    if platform_url:
        return platform_url

    driver = getenv("DB_DRIVER", "postgresql+psycopg")
    user = getenv("DB_USER", "ai")
    password = quote(getenv("DB_PASS", "ai"), safe="")
    host = getenv("DB_HOST", "localhost")
    port = getenv("DB_PORT", "5432")
    database = getenv("DB_DATABASE", "platform")

    return f"{driver}://{user}:{password}@{host}:{port}/{database}"


db_url = build_db_url()
