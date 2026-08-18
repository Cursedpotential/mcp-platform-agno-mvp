"""Opaque capabilities for one exact walk/checkpoint evidence read.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

from hashlib import sha256
from hmac import new as new_hmac
from os import getenv
from uuid import UUID

WALK_CAPABILITY_VERSION = "v1"


def issue_walk_search_capability(walk_run_id: UUID, walk_step_id: UUID, checkpoint_id: UUID) -> str:
    """Issue a server-signed token bound to one exact ledger transition."""

    secret = getenv("WALK_PASS_SIGNING_KEY", "")
    if not secret:
        raise RuntimeError("walk search capability signing is not configured")
    binding = f"{WALK_CAPABILITY_VERSION}:{walk_run_id}:{walk_step_id}:{checkpoint_id}"
    digest = new_hmac(secret.encode(), binding.encode(), sha256).hexdigest()
    return f"{WALK_CAPABILITY_VERSION}.{digest}"


__all__ = ["issue_walk_search_capability"]
