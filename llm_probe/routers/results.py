"""GET /results/board — the merged per-model view the frontend board renders:
one row per (provider, model) with its latest liveness result and latest
tool_use/summarization/instruction_following results, whichever run each
came from. Replaces the old hand-run export script with a live query.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from fastapi import APIRouter

from .. import db

router = APIRouter(prefix="/results", tags=["results"])


def _parse_detail(d: Any) -> dict:
    if isinstance(d, str):
        try:
            return json.loads(d)
        except Exception:
            return {}
    return d or {}


def _clean_err(e: Optional[str]) -> Optional[str]:
    if not e:
        return e
    try:
        j = json.loads(e)
        if isinstance(j, list):
            j = j[0]
        msg = j.get("error", {}).get("message") or j.get("message")
        if msg:
            return msg
    except Exception:
        pass
    return e


def _trunc(s: Optional[str], n: int = 160) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", str(s).replace("\n", " ").replace("\r", " ")).strip()
    return (s[:n] + "…") if len(s) > n else s


@router.get("/raw")
async def raw_results(limit: int = 5000):
    return await db.fetch_results(limit)


@router.get("/board")
async def board():
    rows = await db.fetch_results(limit=20000)

    # newest row wins per (provider, model, probe) — created_at DESC already
    # from fetch_results, so first occurrence encountered is the newest.
    liveness: dict[tuple[str, str], dict] = {}
    capability: dict[tuple[str, str], dict[str, dict]] = {}
    for r in rows:
        key = (r["provider"], r["model"])
        if r["probe"] == "liveness":
            liveness.setdefault(key, r)
        elif r["probe"] in ("tool_use", "summarization", "instruction_following"):
            capability.setdefault(key, {}).setdefault(r["probe"], r)

    out = []
    for key, lv in liveness.items():
        provider, model = key
        det = _parse_detail(lv["detail"])
        row = {
            "provider": provider, "model": model,
            "tier0_ok": bool(lv["ok"]), "tier0_status": lv["http_status"],
            "tier0_latency": float(lv["latency_s"]) if lv["latency_s"] is not None else None,
            "tier0_run_id": lv["run_id"], "tier0_tier": lv["tier"],
            "tier0_note": _trunc(det.get("content")) if lv["ok"] else _trunc(_clean_err(det.get("error"))),
            "tier0_full_content": det.get("content"),
            "tier0_full_error": _clean_err(det.get("error")),
            "tier0_followed_format": det.get("followed_format"),
            "tier0_patched": bool(det.get("patched")),
        }
        cap = capability.get(key, {})
        for probe in ("tool_use", "summarization", "instruction_following"):
            p = cap.get(probe)
            if p:
                pdet = _parse_detail(p["detail"])
                row[f"{probe}_ok"] = bool(p["ok"])
                row[f"{probe}_latency"] = float(p["latency_s"]) if p["latency_s"] is not None else None
                row[f"{probe}_note"] = _trunc(pdet.get("content") or pdet.get("reason"))
                row[f"{probe}_detail"] = pdet
        out.append(row)

    out.sort(key=lambda r: (r["provider"], r["model"]))
    return out


@router.get("/summary")
async def summary():
    board_rows = await board()
    total = len(board_rows)
    live = sum(1 for r in board_rows if r["tier0_ok"])
    tested = [r for r in board_rows if "tool_use_ok" in r]
    return {
        "total_models": total,
        "live": live,
        "tier1_tested": len(tested),
        "tool_use_pass": sum(1 for r in tested if r["tool_use_ok"]),
        "summarization_pass": sum(1 for r in tested if r["summarization_ok"]),
        "instruction_following_pass": sum(1 for r in tested if r["instruction_following_ok"]),
        "pass_all_three": sum(1 for r in tested if r["tool_use_ok"] and r["summarization_ok"] and r["instruction_following_ok"]),
    }
