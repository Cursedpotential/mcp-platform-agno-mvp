# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""S3-compatible object store repo layer — R2 today, any S3 (incl. Backblaze B2) via env swap.

Adapted from the donor kit's b2_client.py. All boto3 usage is confined to this
module (enforced by tests/test_structure.py::test_boto3_only_in_repo). B2-specific
naming (user-agent string, "B2" identifiers) has been stripped in favor of the
generic OBJECT_STORE_* settings so switching providers is a pure env swap.
"""

from __future__ import annotations

import io
import logging
import mimetypes
from typing import IO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client():
    """Return a cached boto3 S3 client for the configured object store endpoint.

    Path-style addressing works across R2, B2, MinIO, and AWS S3 alike.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint_url,
        region_name=settings.object_store_region,
        aws_access_key_id=settings.object_store_access_key_id,
        aws_secret_access_key=settings.object_store_secret_access_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def check_connectivity() -> bool:
    """Cheap health check: HEAD the configured bucket."""
    try:
        get_client().head_bucket(Bucket=settings.object_store_bucket)
        return True
    except Exception:
        logger.warning("Object store connectivity check failed", exc_info=True)
        return False


def put_object(key: str, data: bytes | IO[bytes], content_type: str | None = None) -> None:
    """Upload bytes or a file-like object to `key`. Raises RuntimeError on failure."""
    body = data if hasattr(data, "read") else io.BytesIO(data)  # type: ignore[arg-type]
    guessed_type = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
    try:
        get_client().put_object(
            Bucket=settings.object_store_bucket,
            Key=key,
            Body=body,
            ContentType=guessed_type,
        )
    except ClientError as e:
        raise RuntimeError(f"Object store upload failed for '{key}': {e}") from e


def get_object(key: str) -> bytes:
    """Download and return the raw bytes stored at `key`. Raises RuntimeError on failure."""
    try:
        response = get_client().get_object(Bucket=settings.object_store_bucket, Key=key)
        return response["Body"].read()
    except ClientError as e:
        raise RuntimeError(f"Object store download failed for '{key}': {e}") from e


def object_exists(key: str) -> bool:
    """Check whether `key` exists in the bucket. Re-raises on non-404 errors."""
    try:
        get_client().head_object(Bucket=settings.object_store_bucket, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return False
        raise


def presigned_get(key: str, expires: int = 600) -> str:
    """Generate a presigned GET URL for `key`, valid for `expires` seconds."""
    try:
        return get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.object_store_bucket, "Key": key},
            ExpiresIn=expires,
        )
    except ClientError as e:
        raise RuntimeError(f"Object store presign failed for '{key}': {e}") from e
