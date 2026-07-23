# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: corroboration flags)
"""Corroboration flags — requirements addendum 6. Proxies to the spine's /v1/flags.

A flag is an analysis-lane annotation ("this claim needs corroborating
evidence") — the story-to-evidence map for AI-chat material that's the
owner's account, not yet evidence. Flags are metadata; they never mutate
evidence. Thin passthrough, same posture as app/service/inspect.py.
"""

from __future__ import annotations

from app.repo.spine_client import SpineError, spine_json

__all__ = ["SpineError", "create_flag", "list_flags", "update_flag"]


def create_flag(payload: dict) -> dict:
    """POST /v1/flags passthrough.

    `payload` shape: `{target_kind, target_id, claim, claim_date_start?,
    claim_date_end?, evidence_wanted?, notes?}` — see
    app/types/inspect.py::FlagCreateRequest.
    """
    return spine_json("POST", "/v1/flags", json=payload)


def list_flags(*, status: str | None = None, target_kind: str | None = None) -> list[dict]:
    """GET /v1/flags?status=&target_kind= passthrough -> the flag list.

    Backs both the inline "flags on this record/run" views and the
    Evidence Queue page (grouped by evidence_wanted type).
    """
    params: dict[str, str] = {}
    if status:
        params["status"] = status
    if target_kind:
        params["target_kind"] = target_kind
    result = spine_json("GET", "/v1/flags", params=params)
    return result if isinstance(result, list) else result.get("flags", [])


def update_flag(flag_id: str, patch: dict) -> dict:
    """PATCH /v1/flags/{id} passthrough — status transitions
    (open -> partial -> corroborated/unobtainable) + notes + linking a
    corroborating artifact once found. `patch` carries only explicitly-set
    keys — see app/types/inspect.py::FlagUpdateRequest.
    """
    return spine_json("PATCH", f"/v1/flags/{flag_id}", json=patch)
