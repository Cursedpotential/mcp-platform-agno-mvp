"""Bounded SDK adapter for the approved disposable target only.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from surrealdb import AsyncSurreal

from .identity import TargetIdentity, sdk_endpoint, validate_target_identity


@asynccontextmanager
async def connect(
    identity: TargetIdentity,
    *,
    system_credentials: dict[str, str] | None = None,
    token: str | None = None,
) -> AsyncIterator[Any]:
    """Open one validated connection and always close it at slice completion."""

    validate_target_identity(identity)
    database = AsyncSurreal(sdk_endpoint(identity))
    async with database:
        if system_credentials is not None:
            await database.signin(system_credentials)
        await database.use(identity.namespace, identity.database)
        if token is not None:
            await database.authenticate(token)
        yield database


async def raw_query(database: Any, statement: str, variables: dict[str, Any]) -> Any:
    """Submit only parameterized statements and retain every statement result."""

    return await database.query_raw(statement, variables)
