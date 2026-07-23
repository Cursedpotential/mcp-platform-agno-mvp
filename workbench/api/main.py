# Byline: Claude Code · Sonnet (agent) · 2026-07-22 (C3: inspect router — records/schemas/verify/flags)
"""Knowledge Workbench API entrypoint — the C1-C3 Operator Console backend.

Stages uploaded files locally (LanceDB whole-file store + object-store copy),
starts/lists/inspects spine runs (custody -> parse -> store -> knowledge, via
AGENTOS_API_URL's /v1/runs), proxies MCP tool servers for the Tool Explorer,
and (C3) proxies the spine's record browser, PG/Milvus schema views, active
hash verification, and corroboration flags. Never chunks, embeds, or writes
Milvus/Postgres itself — see workbench/api/README.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.runtime import copilot, documents, files, health, inspect, metrics, promote, runs, tools, upload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workbench")

app = FastAPI(
    title="Knowledge Workbench API",
    description="Staging + promote surface over the existing platform ingestion API",
    version="0.1.0",
)

# Request timing + in-process metrics counters (app.runtime.metrics)
app.add_middleware(BaseHTTPMiddleware, dispatch=metrics.timing_middleware)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(files.router)
app.include_router(promote.router)
app.include_router(documents.router)
app.include_router(runs.router)
app.include_router(inspect.router)
app.include_router(tools.router)
app.include_router(copilot.router)
app.include_router(metrics.router)

# Static frontend (built separately) mounted LAST so /api + /health always win.
_static_dir = Path(settings.static_dir)


class _NextStaticFiles(StaticFiles):
    """StaticFiles that also maps extensionless paths to Next's flat exports.

    `output: 'export'` (no trailingSlash) writes `/runs` as `runs.html`, which
    plain StaticFiles(html=True) won't serve for a deep link to `/runs`."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        if response.status_code == 404 and path and "." not in path.rsplit("/", 1)[-1]:
            candidate = Path(self.directory) / f"{path}.html"  # type: ignore[arg-type]
            if candidate.is_file():
                return await super().get_response(f"{path}.html", scope)
        return response


if _static_dir.is_dir():
    app.mount("/", _NextStaticFiles(directory=str(_static_dir), html=True), name="static")
    logger.info("Serving static frontend from %s", _static_dir)
else:
    logger.info("STATIC_DIR %s not found — no frontend mounted", _static_dir)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=settings.app_port)
