# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Workbench settings — S3-agnostic object store (R2 now, B2/any-S3 = env swap later).

Env var names are the pydantic-settings default (uppercase of the field name)
and must match compose.workbench.yaml exactly — see that file for the deployed
defaults and the Coolify env-literal-rendering gotcha.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- S3-compatible object store: R2 today, B2/AWS/any-S3 = pure env swap ---
    object_store_endpoint_url: str = ""
    object_store_bucket: str = ""
    object_store_access_key_id: str = ""
    object_store_secret_access_key: str = ""
    object_store_region: str = "auto"
    object_store_prefix: str = "workbench/staging"

    # --- LanceDB local whole-file staging store (no S3, no AWS env vars) ---
    lancedb_path: str = "/data/lancedb"

    # --- Existing platform ingestion API (the promote target) ---
    agentos_api_url: str = "http://100.72.169.40:8000"
    agentos_api_token: str | None = None

    # --- App ---
    app_port: int = 8020
    static_dir: str = "/app/static"
    max_upload_mb: int = 200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
