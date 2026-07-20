# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Knowledge Workbench API entrypoint — the C1 Operator Console backend.

Stages uploaded files locally (LanceDB whole-file store + object-store copy),
starts/lists/inspects spine runs (custody -> parse -> store -> knowledge, via
AGENTOS_API_URL's /v1/runs), and proxies MCP tool servers for the Tool
Explorer. Never chunks, embeds, or writes Milvus/Postgres itself — see
workbench/api/README.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.runtime import documents, files, health, metrics, promote, runs, tools, upload

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
app.include_router(tools.router)
app.include_router(metrics.router)

# Static frontend (built separately) mounted LAST so /api + /health always win.
_static_dir = Path(settings.static_dir)
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
    logger.info("Serving static frontend from %s", _static_dir)
else:
    logger.info("STATIC_DIR %s not found — no frontend mounted", _static_dir)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=settings.app_port)
