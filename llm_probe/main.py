"""llm_probe — standalone FastAPI service that live-tests LLM providers
(NVIDIA NIM, Ollama Cloud, OpenRouter, Google, OpenAI, Mistral, Groq,
Cerebras): liveness, tool-calling, summarization, instruction-following, and
free-form playground prompts with full control over max_tokens/temperature/
reasoning_effort. Persists everything to `casebible.llm_eval`.

Deliberately its own service (own Dockerfile, own tiny dependency set) rather
than folded into the main agent-platform app — one concern per Coolify app.
Runs tailnet-only; holds provider API keys server-side so the frontend never
touches them.

Byline: Claude Code · Sonnet 5 · 2026-08-27
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routers import catalog, probe, results


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_schema()
    yield
    await db.close_pool()


app = FastAPI(title="llm_probe", version="0.1.0", lifespan=lifespan)

# Tailnet-only deployment — CORS origins are the frontend's own tailnet
# address(es), configured via env, not "*".
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(probe.router)
app.include_router(results.router)


@app.get("/health")
async def health():
    from .providers import configured_providers
    return {"status": "ok", "configured_providers": configured_providers()}
