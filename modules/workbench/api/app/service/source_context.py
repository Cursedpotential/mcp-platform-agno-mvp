"""Authenticated adapter for durable UIW source-context receipts.

Byline: Codex · GPT-5.6-Sol · 2026-08-30.
"""

from __future__ import annotations

import hashlib
import json

from app.service.uiw import _json_payload, _request, _validated
from app.types.source_context import SourceContextCreateRequest, SourceContextReceipt
from app.types.uiw import UIWDecisionActor


async def create_source_context(
    request: SourceContextCreateRequest,
    actor: UIWDecisionActor,
) -> SourceContextReceipt:
    canonical = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    key = hashlib.sha256(f"{actor.subject_uid}\x00{canonical}".encode()).hexdigest()
    response = await _request(
        "POST",
        "/reference-import/source-contexts",
        json=request.model_dump(mode="json"),
        headers={
            "X-authentik-uid": actor.subject_uid,
            "X-authentik-username": actor.username,
            "Idempotency-Key": f"uiw-source-context:{key}",
        },
    )
    return _validated(
        SourceContextReceipt,
        _json_payload(response, "source context response"),
        "source context response",
    )
