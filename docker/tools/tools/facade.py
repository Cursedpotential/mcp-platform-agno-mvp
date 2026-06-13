"""platform-tools facade — one HTTP surface over the registered atomic tools.

REGISTRY-BACKED (P2): the evidence package is mounted at /opt/tools/evidence
(compose volume, read-only); every parser module self-registers on startup via
load_builtin_tools(). The inventory and execution surface below are therefore
ALWAYS in sync with the registry — porting a parser = adding one module to
evidence/tools/, nothing to edit here.

Payload paths must be visible to THIS container — use the shared /r2 mount
(custody blobs live at /r2/evidence/<aa>/<sha>/<name>).
"""

from typing import Any

from fastapi import FastAPI, HTTPException

from evidence.registry import load_builtin_tools, registry

app = FastAPI(title="platform-tools facade")

TOOL_COUNT = load_builtin_tools()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "tool_count": TOOL_COUNT, "tools": sorted(t.id for t in registry.all())}


@app.get("/tools")
async def tools() -> list[dict[str, str]]:
    """Full registry manifest: id, capability, description, provenance."""
    return registry.manifest()


@app.get("/tools/resolve/{capability}")
async def resolve(capability: str, hint: str = "", size: int = 0) -> list[str]:
    """Which tools would run for a capability+input (substitution candidates, in order)."""
    return [t.id for t in registry.resolve(capability, media_hint=hint, size_bytes=size)]


@app.post("/tools/{tool_id}/run")
async def run_tool(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute one atomic tool with its contract payload (e.g. {"path": "/r2/..."})."""
    try:
        tool = registry.get(tool_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown tool {tool_id!r}")
    try:
        return tool.run(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        # contract rejection (wrong format) — caller should try resolve() alternatives
        raise HTTPException(status_code=422, detail=str(exc))
