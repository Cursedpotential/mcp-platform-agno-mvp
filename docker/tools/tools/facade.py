"""platform-tools facade — one HTTP/OpenAPI surface over the platform tools.

Two surfaces, ONE FastAPI app (so ContextForge REST-wraps a single OpenAPI):

  1. REGISTRY-BACKED parsers (/tools/...) — the `server` package is BAKED into
     the image at build (docker/tools/Dockerfile `COPY server/ /opt/tools/server/`),
     NOT bind-mounted: Coolify does not honor relative bind mounts, and prod
     rebuilds this image on every deploy, so a self-contained image is strictly
     better. Every parser module self-registers via load_builtin_tools(), so the
     inventory + execution surface stay in sync with the registry. Porting a
     parser = adding one module to server/evidence/tools/, nothing to edit here.

  2. SBV PROXY (/sbv/...) — proxies the session-authenticated SBV REST API
     (localhost:8085/api/...) so every SBV function is callable over this
     facade (and thus over MCP via ContextForge). The facade owns the SBV
     service-account session so callers never deal with the cookie.

ROBUSTNESS (the 2-day FATAL fix): the OLD facade did `from evidence.registry
import ...` at module top, so an empty/missing evidence package crashed uvicorn
-> supervisord FATAL-looped -> the WHOLE container's tool surface was down. Now
the registry load is wrapped: a bad/absent package DEGRADES the /tools endpoints
(503) but the app still starts and the /sbv proxy still works. We also pin
/opt/tools onto sys.path so `import server.*` resolves regardless of how
uvicorn is launched (the baked package lives at /opt/tools/server).

Payload paths must be visible to THIS container — use the shared /r2 mount
(custody blobs live at /r2/evidence/<aa>/<sha>/<name>).
"""

from __future__ import annotations

import os
import sys
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

# Belt-and-suspenders: ensure the WORKDIR (where the evidence package is
# mounted) is importable no matter how the process was launched.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

app = FastAPI(
    title="platform-tools facade",
    description="Registry-backed evidence parsers + SBV (SMS Backup Viewer) REST proxy. "
    "One OpenAPI surface for ContextForge to REST-wrap into MCP tools.",
    version="1.1.0",
)

# ---------------------------------------------------------------------------
# Surface 1: registry-backed parser tools (degrades, never crashes)
# ---------------------------------------------------------------------------
REGISTRY_OK = False
REGISTRY_ERROR = ""
TOOL_COUNT = 0
registry = None  # set on successful load

try:
    from server.evidence.registry import load_builtin_tools, registry as _registry

    TOOL_COUNT = load_builtin_tools()
    registry = _registry
    REGISTRY_OK = True
except Exception as exc:  # empty/missing evidence mount, import error, etc.
    REGISTRY_ERROR = f"{type(exc).__name__}: {exc}"
    # Do NOT raise — the app must still start so the SBV proxy works and
    # supervisord doesn't FATAL-loop. /tools/* will report the degradation.


def _require_registry():
    if not REGISTRY_OK or registry is None:
        raise HTTPException(
            status_code=503,
            detail=f"registry unavailable — server.evidence package not importable ({REGISTRY_ERROR}). "
            "The baked /opt/tools/server tree is missing/broken; rebuild the platform-tools image.",
        )


@app.get("/health")
async def health() -> dict[str, Any]:
    """Facade health: surfaces BOTH the registry state and SBV reachability."""
    return {
        "status": "ok" if REGISTRY_OK else "degraded",
        "registry_ok": REGISTRY_OK,
        "registry_error": REGISTRY_ERROR or None,
        "tool_count": TOOL_COUNT,
        "tools": sorted(t.id for t in registry.all()) if REGISTRY_OK else [],  # type: ignore[union-attr]
        "sbv": _sbv_status(),
    }


@app.get("/tools")
async def tools() -> list[dict[str, str]]:
    """Full registry manifest: id, capability, description, provenance."""
    _require_registry()
    return registry.manifest()  # type: ignore[union-attr]


@app.get("/tools/resolve/{capability}")
async def resolve(capability: str, hint: str = "", size: int = 0) -> list[str]:
    """Which tools would run for a capability+input (substitution candidates, in order)."""
    _require_registry()
    return [t.id for t in registry.resolve(capability, media_hint=hint, size_bytes=size)]  # type: ignore[union-attr]


@app.post("/tools/{tool_id}/run")
async def run_tool(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one atomic tool with its contract payload (e.g. {"path": "/r2/..."})."""
    _require_registry()
    try:
        tool = registry.get(tool_id)  # type: ignore[union-attr]
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown tool {tool_id!r}")
    try:
        return tool.run(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        # contract rejection (wrong format) — caller should try resolve() alternatives
        raise HTTPException(status_code=422, detail=str(exc))


# ---------------------------------------------------------------------------
# Surface 2: SBV proxy (/sbv/...) — every SBV function over the facade
# ---------------------------------------------------------------------------
# Import the shared SBV client. It normally lives in the mounted evidence
# package; if the mount is empty we degrade the SBV surface the same way.
SBV_OK = False
SBV_IMPORT_ERROR = ""
try:
    from server.evidence.tools._sbv_client import SBVClient, SBVError

    SBV_OK = True
except Exception as exc:
    SBV_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

    class SBVError(RuntimeError):  # type: ignore[no-redef]
        def __init__(self, message: str, status: int | None = None) -> None:
            super().__init__(message)
            self.status = status


_sbv_client_singleton = None


def _get_sbv() -> "SBVClient":
    """One service-account session for the whole facade process."""
    global _sbv_client_singleton
    if not SBV_OK:
        raise HTTPException(
            status_code=503,
            detail=f"SBV client unavailable ({SBV_IMPORT_ERROR}). The baked server.evidence package is missing/broken.",
        )
    if _sbv_client_singleton is None:
        _sbv_client_singleton = SBVClient()
    return _sbv_client_singleton


def _sbv_status() -> dict[str, Any]:
    if not SBV_OK:
        return {"reachable": False, "error": SBV_IMPORT_ERROR}
    try:
        client = SBVClient()
        return {"reachable": client.health(), "base_url": client.base, "version": _safe(client.version)}
    except Exception as exc:
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


def _sbv_call(fn, *args, **kwargs):
    """Run an SBVClient method, mapping SBVError -> HTTP status."""
    try:
        return fn(*args, **kwargs)
    except SBVError as exc:
        status = getattr(exc, "status", None) or 502
        raise HTTPException(status_code=status, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/sbv/health", tags=["sbv"])
async def sbv_health() -> dict[str, Any]:
    """SBV service health (public SBV endpoint, no auth)."""
    return _sbv_status()


@app.get("/sbv/version", tags=["sbv"])
async def sbv_version() -> Any:
    return _sbv_call(_get_sbv().version)


@app.post("/sbv/upload", tags=["sbv"])
async def sbv_upload(payload: dict[str, Any]) -> Any:
    """Upload an SMS backup XML to SBV for parsing. payload: {"path": "/r2/...xml"}.
    The path must be visible to THIS container (use the shared /r2 mount)."""
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=422, detail="payload must include 'path'")
    client = _get_sbv()
    result = _sbv_call(client.upload, str(path))
    if isinstance(result, dict) and result.get("processing") and payload.get("wait", True):
        _sbv_call(client.wait_for_processing)
        result = {**result, "processing": False, "waited": True}
    return result


@app.get("/sbv/progress", tags=["sbv"])
async def sbv_progress() -> Any:
    return _sbv_call(_get_sbv().progress)


# NOTE: SBV endpoints return either JSON objects or bare arrays (e.g.
# /conversations -> []), so these return `Any` — pinning them to dict makes
# FastAPI 500 on array responses.
@app.get("/sbv/messages", tags=["sbv"])
async def sbv_messages(
    address: str | None = Query(None),
    limit: int | None = Query(None),
    offset: int | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> Any:
    return _sbv_call(
        _get_sbv().messages,
        address=address,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
    )


@app.get("/sbv/conversations", tags=["sbv"])
async def sbv_conversations() -> Any:
    return _sbv_call(_get_sbv().conversations)


@app.get("/sbv/calls", tags=["sbv"])
async def sbv_calls(limit: int | None = Query(None), offset: int | None = Query(None)) -> Any:
    return _sbv_call(_get_sbv().calls, limit=limit, offset=offset)


@app.get("/sbv/analytics", tags=["sbv"])
async def sbv_analytics() -> Any:
    return _sbv_call(_get_sbv().analytics)


@app.get("/sbv/search", tags=["sbv"])
async def sbv_search(q: str = Query(...), limit: int | None = Query(None)) -> Any:
    return _sbv_call(_get_sbv().search, q, limit=limit)


@app.post("/sbv/export", tags=["sbv"])
async def sbv_export(payload: dict[str, Any]) -> JSONResponse:
    """Export-as-a-function. SBV's deployed build (git-0.1.11) has NO server-side
    /api/export route — export is client-side in the GUI. We synthesize the
    export here from /sbv/messages (+/calls) so 'export' is still MCP-callable.
    payload: {"format": "json"|"csv", "address": <opt>, "include_calls": <bool>}."""
    fmt = (payload.get("format") or "json").lower()
    if fmt not in ("json", "csv"):
        raise HTTPException(status_code=422, detail="format must be 'json' or 'csv'")
    client = _get_sbv()
    messages = _sbv_call(client.all_messages, address=payload.get("address"))
    calls = _sbv_call(client.all_calls) if payload.get("include_calls", True) else []
    if fmt == "json":
        return JSONResponse({"format": "json", "messages": messages, "calls": calls})
    # csv
    import csv
    import io

    buf = io.StringIO()
    if messages:
        cols = sorted({k for m in messages for k in m.keys()})
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(messages)
    return JSONResponse(
        {"format": "csv", "csv": buf.getvalue(), "message_count": len(messages), "call_count": len(calls)}
    )
