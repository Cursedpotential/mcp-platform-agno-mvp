"""Pass-bound agent and owner-only operator native evidence search.

The agent surface accepts only ledger identities.  Case, actor, horizon, and
disclosure tiers are resolved from the attested walk/run/checkpoint rows.  The
operator surface is deliberately separate and requires a distinct credential.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from hmac import compare_digest
from os import getenv
from typing import Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from server.evidence.search_capability import issue_walk_search_capability

NativeSearchExecutor = Callable[..., Awaitable[Any]]
WalkContextResolver = Callable[[UUID, UUID, UUID], Awaitable["WalkSearchContext"]]

_SAFE_TIERS = ("contemporaneous", "discovered")
_HINDSIGHT_TIERS = (*_SAFE_TIERS, "hindsight")
_OPERATOR_ACTOR = "workbench:owner:evidence-search"


@dataclass(frozen=True)
class WalkSearchContext:
    """Server-resolved authority for one exact next walk step."""

    case_id: str
    actor: str
    horizon: datetime | None
    disclosure_tiers: tuple[str, ...]
    horizon_policy: str


class AgentEvidenceSearchRequest(BaseModel):
    """Agent input contains references, never permission-bearing values."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    walk_run_id: UUID
    walk_step_id: UUID
    checkpoint_id: UUID
    limit: int = Field(default=20, ge=1, le=100)
    mode: Literal["near_vector", "hybrid"] = "hybrid"


class OperatorEvidenceSearchRequest(BaseModel):
    """Owner exploration input; it never grants hindsight tiers."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    case_id: str = Field(default="primary", min_length=1, max_length=200)
    horizon: datetime | None = None
    limit: int = Field(default=20, ge=1, le=100)
    mode: Literal["near_vector", "hybrid"] = "hybrid"


def _bounded_horizon(requested: datetime | None, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if requested is None:
        return current
    if requested.tzinfo is None or requested.utcoffset() is None:
        raise ValueError("horizon must include a timezone")
    return min(requested.astimezone(timezone.utc), current)


def _authenticate_operator_bearer(request: Request) -> None:
    from server.api.platform_auth import read_evidence_operator_bearer

    expected = read_evidence_operator_bearer()
    if not expected:
        raise HTTPException(status_code=503, detail="evidence search authorization is not configured")
    scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
    if not (
        separator
        and scheme.lower() == "bearer"
        and credential
        and compare_digest(credential.encode(), expected.encode())
    ):
        raise HTTPException(status_code=401, detail="evidence search authorization failed")


def _authenticate_walk_capability(
    request: Request,
    walk_run_id: UUID,
    walk_step_id: UUID,
    checkpoint_id: UUID,
) -> None:
    scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
    try:
        expected = issue_walk_search_capability(walk_run_id, walk_step_id, checkpoint_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    if not (
        separator
        and scheme.lower() == "bearer"
        and credential
        and compare_digest(credential.encode(), expected.encode())
    ):
        raise HTTPException(status_code=401, detail="walk search capability is invalid")


async def _resolve_walk_context(
    walk_run_id: UUID,
    walk_step_id: UUID,
    checkpoint_id: UUID,
) -> WalkSearchContext:
    """Resolve an exact resumable checkpoint -> next-step grant from Postgres."""

    from anyio import to_thread

    def resolve() -> WalkSearchContext:
        from sqlalchemy import text

        from server.core.session import get_postgres_db

        statement = text(
            """
            SELECT r.case_id, r.agent_id, r.bound_lane, r.horizon_policy,
                   r.horizon_ceiling, r.status, r.base_version AS run_base_version,
                   c.checkpoint_kind, c.is_resumable,
                   c.base_version AS checkpoint_base_version,
                   c.last_completed_step_no, s.step_no, s.horizon_at
              FROM working.walk_run r
              JOIN working.walk_checkpoint c
                ON c.walk_run_id = r.id AND c.id = :checkpoint_id
              JOIN working.walk_step s
                ON s.walk_run_id = r.id AND s.id = :walk_step_id
               AND s.step_no = c.last_completed_step_no + 1
             WHERE r.id = :walk_run_id
            """
        )
        engine = get_postgres_db().db_engine
        with engine.connect() as connection:
            row = (
                connection.execute(
                    statement,
                    {
                        "walk_run_id": str(walk_run_id),
                        "walk_step_id": str(walk_step_id),
                        "checkpoint_id": str(checkpoint_id),
                    },
                )
                .mappings()
                .first()
            )

        if row is None:
            raise PermissionError("walk search context is not an exact checkpoint-bound next step")
        if row["bound_lane"] != "evidence":
            raise PermissionError("walk is not bound to the evidence lane")
        if row["status"] not in {"running", "paused"}:
            raise PermissionError("walk is not active or resumable")
        if row["checkpoint_kind"] != "healthy" or not row["is_resumable"]:
            raise PermissionError("walk checkpoint is not resumable")
        if row["run_base_version"] != row["checkpoint_base_version"]:
            raise PermissionError("walk checkpoint base version does not reconcile")

        policy = str(row["horizon_policy"])
        horizon = row["horizon_at"]
        tiers: tuple[str, ...]
        if policy == "hindsight":
            if horizon is not None:
                raise PermissionError("hindsight walk step has an invalid bounded horizon")
            tiers = _HINDSIGHT_TIERS
        elif policy in {"ignorant", "custom"}:
            if horizon is None:
                raise PermissionError("bounded walk step has no horizon")
            if horizon.tzinfo is None or horizon.utcoffset() is None:
                raise PermissionError("walk step horizon is not timezone-aware")
            horizon = horizon.astimezone(timezone.utc)
            ceiling = row["horizon_ceiling"]
            if policy == "custom" and (ceiling is None or horizon > ceiling):
                raise PermissionError("custom walk step exceeds its horizon ceiling")
            tiers = _SAFE_TIERS
        else:
            raise PermissionError("walk horizon policy is not recognized")

        return WalkSearchContext(
            case_id=str(row["case_id"]),
            actor=str(row["agent_id"]),
            horizon=horizon,
            disclosure_tiers=tiers,
            horizon_policy=policy,
        )

    return await to_thread.run_sync(resolve)


async def _execute_native_search(query: str, **kwargs: Any) -> Any:
    """Construct the pinned 4096-d query embedder and native store lazily."""

    from anyio import to_thread

    def execute() -> Any:
        from server.core.evidence_vector_store import (
            EVIDENCE_EMBED_DIM,
            EVIDENCE_EMBED_MODEL,
            NativeEvidenceVectorStore,
            validate_evidence_vector_activation,
        )
        from server.core.native_evidence_runtime import NativeEvidenceEmbedder
        from server.core.session import get_weaviate_client
        from server.evidence.retrieval import native_evidence_search

        embed_api_key = getenv("EMBED_API_KEY") or getenv("NVIDIA_API_KEY", "")
        embed_base_url = getenv("EMBED_BASE_URL") or getenv("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
        if not embed_api_key:
            raise RuntimeError("native evidence query embedder is not configured")
        embedder = NativeEvidenceEmbedder(
            api_key=embed_api_key,
            base_url=embed_base_url,
            model=EVIDENCE_EMBED_MODEL,
            dimensions=EVIDENCE_EMBED_DIM,
        )
        client = get_weaviate_client()
        try:
            validate_evidence_vector_activation(client)
            store = NativeEvidenceVectorStore(client)
            return native_evidence_search(store, embedder, query, **kwargs)
        finally:
            embedder.close()
            client.close()

    try:
        return await to_thread.run_sync(execute)
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise RuntimeError("native evidence search unavailable") from exc


def _search_hit(document: Any) -> dict[str, Any]:
    properties = dict(getattr(document, "properties", None) or {})
    metadata = getattr(document, "metadata", None)
    score = getattr(metadata, "score", None)
    if not isinstance(score, (int, float)):
        distance = getattr(metadata, "distance", None)
        score = 1.0 - distance if isinstance(distance, (int, float)) else None
    chunk_id = str(properties.get("chunk_id") or getattr(document, "uuid", ""))
    content = str(properties.pop("content", ""))
    properties.setdefault("knowledge_lane", "evidence")
    return {
        "id": chunk_id,
        "name": chunk_id,
        "content": content,
        "meta_data": properties,
        "reranking_score": score,
        "content_id": properties.get("normalized_record_id"),
    }


def _response(result: Any, *, limit: int, context: WalkSearchContext) -> dict[str, Any]:
    hits = [_search_hit(document) for document in result.documents]
    return {
        "data": hits,
        "meta": {
            "page": 1,
            "limit": limit,
            "total_pages": 1 if hits else 0,
            "total_count": len(hits),
            "knowledge_lane": "evidence",
            "case_id": context.case_id,
            "horizon": context.horizon.isoformat() if context.horizon is not None else None,
            "horizon_policy": context.horizon_policy,
            "audit_id": result.audit_id,
            "kept": result.kept,
            "denied": result.denied,
        },
    }


def register_native_evidence_search_routes(
    app: FastAPI,
    *,
    native_runtime: Any | None = None,
    execute_search: NativeSearchExecutor | None = None,
    resolve_walk_context: WalkContextResolver | None = None,
) -> None:
    """Register pass-bound agent and owner-only operator search routes."""

    if execute_search is not None:
        executor = execute_search
    elif native_runtime is not None:

        async def execute_runtime_search(query: str, **kwargs: Any) -> Any:
            from anyio import to_thread

            from server.evidence.retrieval import native_evidence_search

            return await to_thread.run_sync(
                lambda: native_evidence_search(
                    native_runtime.store,
                    native_runtime.embedder,
                    query,
                    **kwargs,
                )
            )

        executor = execute_runtime_search
    else:
        executor = _execute_native_search
    context_resolver = resolve_walk_context or _resolve_walk_context

    @app.post("/v1/evidence/search")
    async def search_agent_evidence(request: Request, body: AgentEvidenceSearchRequest) -> dict[str, Any]:
        _authenticate_walk_capability(
            request,
            body.walk_run_id,
            body.walk_step_id,
            body.checkpoint_id,
        )
        try:
            query = body.query.strip()
            if not query:
                raise ValueError("query must be a non-empty string")
            context = await context_resolver(body.walk_run_id, body.walk_step_id, body.checkpoint_id)
            result = await executor(
                query,
                horizon=context.horizon,
                actor=context.actor,
                disclosure_tiers=context.disclosure_tiers,
                case_id=context.case_id,
                limit=body.limit,
                mode=body.mode,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        return _response(result, limit=body.limit, context=context)

    @app.post("/v1/operator/evidence/search")
    async def search_operator_evidence(request: Request, body: OperatorEvidenceSearchRequest) -> dict[str, Any]:
        _authenticate_operator_bearer(request)
        try:
            query = body.query.strip()
            case_id = body.case_id.strip()
            if not query:
                raise ValueError("query must be a non-empty string")
            if not case_id:
                raise ValueError("case_id must be a non-empty string")
            context = WalkSearchContext(
                case_id=case_id,
                actor=_OPERATOR_ACTOR,
                horizon=_bounded_horizon(body.horizon),
                disclosure_tiers=_SAFE_TIERS,
                horizon_policy="operator-bounded",
            )
            result = await executor(
                query,
                horizon=context.horizon,
                actor=context.actor,
                disclosure_tiers=context.disclosure_tiers,
                case_id=context.case_id,
                limit=body.limit,
                mode=body.mode,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        return _response(result, limit=body.limit, context=context)
