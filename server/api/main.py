"""Framework-neutral production HTTP host for the Platform API.

AgentOS is deliberately absent. This module owns only the plain FastAPI
process, platform-owned route registration, the owner API security boundary,
and restart-safe background lifecycle work. Durable orchestration belongs to
Temporal; MCP publication belongs to ContextForge; model routing belongs to
Portkey. Bounded Agno agents, when introduced, run only inside explicitly
allowlisted Temporal activities and are never mounted here.

Byline: Codex · GPT-5.6-Sol · 2026-08-29
"""

from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from os import getenv
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from server.api.platform_auth import read_platform_api_bearer
from server.api.tailnet_auth import tailnet_testing_identity

_LOGGER = logging.getLogger(__name__)
_PUBLIC_PATHS = frozenset({"/health"})
_SELF_AUTHENTICATING_ROUTES = frozenset(
    {
        ("POST", "/v1/evidence/search"),
        ("POST", "/v1/operator/evidence/search"),
    }
)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _native_evidence_enabled() -> bool:
    """Return the explicit native-projection activation gate."""

    return getenv("NATIVE_EVIDENCE_ENABLED", "").strip().lower() in _TRUE_VALUES


def _replace_authorization_header(request: Request, credential: str) -> None:
    """Inject the bearer after a trusted Tailnet testing bypass succeeds.

    Some platform routes enforce the bearer locally as defense in depth. The
    replacement keeps those checks intact while allowing the audited,
    feature-gated Tailnet identity through the outer boundary.
    """

    headers = [(key, value) for key, value in request.scope.get("headers", []) if key.lower() != b"authorization"]
    headers.append((b"authorization", f"Bearer {credential}".encode()))
    request.scope["headers"] = headers


def _tailnet_testing_bypass(request: Request) -> bool:
    """Accept the explicitly configured Platform API testing identity."""

    return tailnet_testing_identity(request, app_prefix="PLATFORM_API") is not None


def _install_owner_auth(app: FastAPI) -> None:
    """Install the rotatable bearer boundary formerly supplied by AgentOS."""

    @app.middleware("http")
    async def require_owner_auth(request: Request, call_next: Any) -> Any:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # These two routes enforce stronger, purpose-specific credentials in
        # their handlers. Requiring the platform-owner bearer first would make
        # their signed walk capability and distinct operator credential
        # impossible to present in the single Authorization header. Keep the
        # exemption method-and-path exact; every other route remains behind
        # the outer owner boundary.
        if (request.method, request.url.path) in _SELF_AUTHENTICATING_ROUTES:
            return await call_next(request)

        expected = read_platform_api_bearer()
        if not expected:
            return JSONResponse(
                status_code=503,
                content={"detail": "platform API authorization is not configured"},
            )

        if _tailnet_testing_bypass(request):
            _replace_authorization_header(request, expected)
            return await call_next(request)

        scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not hmac.compare_digest(credential.encode(), expected.encode())
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.auth_principal = "platform-owner"
        request.state.auth_method = "bearer"
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run required startup recovery and native projection background work."""

    from server.api.runtime_support import ensure_duckdb_r2_secret

    _LOGGER.info("Platform API lifespan: startup")
    _LOGGER.info("pg_duckdb R2 secret ensured: %s", ensure_duckdb_r2_secret())

    native_runtime = app.state.native_evidence_runtime
    native_stop: asyncio.Event | None = None
    native_task: asyncio.Task[None] | None = None
    if native_runtime is not None:
        from server.core.native_evidence_runtime import run_native_projection_worker

        native_stop = asyncio.Event()
        native_task = asyncio.create_task(
            run_native_projection_worker(
                native_runtime,
                native_stop,
                batch_limit=int(getenv("NATIVE_EVIDENCE_DRAIN_BATCH_LIMIT", "100")),
                idle_interval_s=float(getenv("NATIVE_EVIDENCE_DRAIN_INTERVAL_SECONDS", "5")),
                error_backoff_s=float(getenv("NATIVE_EVIDENCE_DRAIN_ERROR_BACKOFF_SECONDS", "15")),
                max_error_backoff_s=float(getenv("NATIVE_EVIDENCE_DRAIN_MAX_BACKOFF_SECONDS", "60")),
            ),
            name="native-evidence-projection-drain",
        )

    async def run_ingest_recovery() -> None:
        from server.ingest.service import recover_incomplete_ingests

        try:
            recovered = await recover_incomplete_ingests(
                projector=native_runtime.projector if native_runtime is not None else None
            )
        except Exception:
            _LOGGER.exception("durable ingest recovery failed")
            return
        _LOGGER.info("Durable ingest recovery finished: recovered=%s", recovered)

    recovery_task = asyncio.create_task(run_ingest_recovery(), name="durable-ingest-recovery")
    _LOGGER.info("Durable ingest recovery scheduled from the workflow ledger")
    try:
        yield
    finally:
        if not recovery_task.done():
            recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass

        if native_runtime is not None:
            assert native_stop is not None
            native_stop.set()
            try:
                if native_task is not None:
                    await native_task
            finally:
                native_runtime.close()
        _LOGGER.info("Platform API lifespan: shutdown")


def register_knowledge_routes(app: FastAPI, _knowledge: Any = None) -> None:
    """Register framework-neutral canonical knowledge ingestion routes."""

    @app.post("/v1/knowledge/reindex")
    async def reindex_knowledge() -> dict[str, Any]:
        from scripts.ingest_knowledge import ingest_all

        count = await ingest_all()
        return {"indexedDocumentCount": count, "status": "completed", "store": "postgresql"}


def _build_native_evidence_runtime() -> Any | None:
    """Build the optional native projector without importing AgentOS."""

    if not _native_evidence_enabled():
        return None
    from server.api.runtime_support import create_weaviate_client
    from server.core.native_evidence_runtime import create_native_evidence_runtime

    return create_native_evidence_runtime(
        weaviate_client=create_weaviate_client(),
        validate_activation=True,
    )


def create_app() -> FastAPI:
    """Build the production FastAPI app from platform-owned routers only."""

    native_runtime = _build_native_evidence_runtime()
    native_projector = native_runtime.projector if native_runtime is not None else None
    app = FastAPI(title="Platform API", lifespan=lifespan)
    app.state.native_evidence_runtime = native_runtime
    _install_owner_auth(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    register_knowledge_routes(app)

    from server.api.case_management_routes import register_case_management_routes
    from server.api.entity_routes import register_entity_routes
    from server.api.evidence_routes import register_evidence_routes
    from server.api.ingest_routes import register_ingest_routes
    from server.api.inspect_routes import register_inspect_routes
    from server.api.native_evidence_search_routes import register_native_evidence_search_routes
    from server.api.repair_routes import router as repair_router
    from server.api.run_routes import register_run_routes

    # Compatibility routes accept None without constructing Agno Knowledge.
    # SMS/evidence projection uses the native PostgreSQL-outbox projector.
    register_evidence_routes(app, None)
    register_run_routes(app, None, native_projector=native_projector)
    register_inspect_routes(app, None, native_projector)
    register_ingest_routes(app, native_projector)
    if native_runtime is not None:
        register_native_evidence_search_routes(app, native_runtime=native_runtime)
    register_entity_routes(app)
    register_case_management_routes(app)
    app.include_router(repair_router)
    return app


# Compatibility name for focused construction tests and prior internal users.
_build_app = create_app
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.api.main:app", host="0.0.0.0", port=8000, reload=False)
