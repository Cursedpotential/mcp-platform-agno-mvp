# Byline: Claude Code · Sonnet (agent) · 2026-07-21
"""POST /api/copilot/ask, POST /api/copilot/continue, GET /api/copilot/health,
GET /api/copilot/models, GET /api/copilot/presets — the C2.5 Ops Copilot.

Backs the console's /copilot page: a chat pane over the platform's EXISTING
headless OpenCode server. See app/repo/opencode_client.py for the raw HTTP
shapes and app/service/copilot[_presets].py for the context-injection +
preset-merge logic this router proxies.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.service.copilot import CopilotError, ask, continue_ask, health, list_models
from app.service.copilot_presets import list_presets
from app.types.copilot import CopilotAskRequest, CopilotContinueRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.post("/ask")
async def ask_endpoint(body: CopilotAskRequest):
    try:
        context = body.context.model_dump() if body.context else None
        return ask(body.prompt, context=context, model=body.model)
    except CopilotError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.post("/continue")
async def continue_endpoint(body: CopilotContinueRequest):
    try:
        return continue_ask(body.session_id, body.prompt, model=body.model)
    except CopilotError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/health")
async def health_endpoint():
    return health()


@router.get("/models")
async def models_endpoint():
    try:
        return list_models()
    except CopilotError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/presets")
async def presets_endpoint():
    return list_presets()
