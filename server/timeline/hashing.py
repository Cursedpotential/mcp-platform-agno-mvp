# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""Canonical serialization + membership/content hashing (R09 "Canonical serialization is
versioned once: UTF-8, key ordering, timestamp precision, null representation... and hash
domain tags").

Every hash produced here embeds `SERIALIZATION_VERSION` and a domain tag, so a future change to
either the encoding rules or a specific hash's field set is a new, visibly different version
string — never a silent redefinition of an existing hash.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

SERIALIZATION_VERSION = "timeline-canonical-v1"


def iso_utc(value: datetime) -> str:
    """Fixed-precision UTC ISO-8601, `Z` suffix. Naive datetimes are rejected — a display/hash
    input with no declared timezone is exactly the kind of silent-precision bug this contract
    exists to prevent."""
    if value.tzinfo is None:
        raise ValueError("iso_utc: naive datetime cannot be canonically serialized")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _default(value: Any) -> Any:
    if isinstance(value, datetime):
        return iso_utc(value)
    raise TypeError(f"not canonically serializable: {type(value)!r}")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_default)


def domain_hash(domain_tag: str, payload: dict[str, Any]) -> str:
    """sha256 hex of `<SERIALIZATION_VERSION>:<domain_tag>:<canonical_json(payload)>`."""
    body = f"{SERIALIZATION_VERSION}:{domain_tag}:{_canonical_json(payload)}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def stable_member_id(source_member_id: str) -> str:
    """The stable Timesketch-facing identity for one `timeline.timeline_member` row.

    Deliberately just the source row's own uuid (as text) — `timeline_member` rows are
    themselves immutable once created (sql/0035's `timeline_member_source_immutable` trigger),
    so their id is already a correct, permanent logical identity. No hashing needed here; the
    hash lives in `opensearch_doc_id` below, which is versioned separately from PG's own ids.
    """
    return str(source_member_id)


def opensearch_doc_id(stable_id: str) -> str:
    """Deterministic OpenSearch `_id` for a `stable_member_id`. Never a function of the
    generation — replay/rebuild must always target the identical document (R09 invariant 4:
    "at-least-once delivery plus deterministic IDs yields exactly one logical object")."""
    return hashlib.sha256(f"{SERIALIZATION_VERSION}:opensearch-doc-v1:{stable_id}".encode("utf-8")).hexdigest()


def idempotency_key_for_generation(content_hash: str) -> str:
    """Deterministic from `content_hash` alone: rebuilding from an unchanged member set produces
    the same key, so `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING` makes a repeated build
    a no-op instead of a duplicate generation."""
    return f"gen:{content_hash}"
