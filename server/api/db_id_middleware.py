"""Default the ``db_id`` query parameter on agno routes that accept one.

WHY THIS EXISTS (2026-08-01, HANDOFF-2026-07-30 audit #1 follow-through)
=======================================================================
agno's ``AgentOS`` registers databases in a ``dict[str, list[db]]`` keyed by
``db.id`` (``agno/os/app.py::_register_db_with_validation``) and its route
resolver decides "is this a multi-db setup?" by counting **keys**
(``agno/os/utils.py``)::

    if len(dbs) > 1:
        raise HTTPException(400, "The db_id query parameter is required when using multiple databases")

That single line gives us two failure modes and no good default:

* **One shared id** (what we had until ``9a7e4ac``): the guard never fires and
  the resolver returns ``all_dbs[0]`` — the *first-registered* backend,
  regardless of which one actually owns the requested table. Memory, session
  and knowledge routes resolved by registration-order lottery. This was the
  root cause of the "memory/knowledge broken on first open" breakage.
* **Distinct ids** (correct, applied in ``9a7e4ac``): the guard now fires, and
  because ``db_id`` is ``Optional[str] = Query(default=None)`` on *every* one
  of these routes, any client that omits it gets a hard **400** where it
  previously got a silently-wrong **200**.

Neither is acceptable on its own. This middleware supplies the missing third
option: when a request hits a route that accepts ``db_id`` and does not carry
one, inject the operational store's id. Routing becomes **deliberate** rather
than a lottery or an error, and clients that *do* send ``db_id`` are untouched.

Verified against ``agno==2.8.0`` (the pinned prod version) by
``scratchpad/db_id_gate_probe.py``: one shared id -> 200, three ids -> 400.

DESIGN NOTES
------------
* Target routes are discovered by **inspecting endpoint signatures** for a
  ``db_id`` parameter, not by hard-coding paths. agno adds and renames routes
  between minor versions; a path allowlist would rot silently and reintroduce
  the 400.
* Only routes agno itself declares with ``db_id`` are touched. Knowledge routes
  prefer ``knowledge_id`` (which uniquely identifies an instance even when
  several share a database), so a request already carrying ``knowledge_id`` is
  left alone.
* The default is applied to the *query string in the ASGI scope* before the
  route's dependency resolution runs, so agno sees an ordinary explicit
  ``db_id`` and no agno code needs patching.
"""
# Byline: Claude Code · Opus 5 · 2026-08-01 (db_id default — HANDOFF-2026-07-30 audit #1 deploy gate)

from __future__ import annotations

import inspect
from typing import Any
from urllib.parse import parse_qsl, urlencode

from fastapi import FastAPI
from fastapi.routing import APIRoute

__all__ = ["install_db_id_default"]


def _walk(routes: Any, depth: int = 0, prefix: str = "") -> Any:
    """Yield every leaf APIRoute reachable from a Starlette/FastAPI route list.

    Route trees are NOT flat, and the shape is FastAPI-version dependent. With
    the ``base_app=`` pattern agno uses, ``app.routes`` holds mostly
    ``fastapi.routing._IncludedRouter`` objects — a private class that exposes
    NEITHER ``.routes`` NOR ``.endpoint``, only ``.original_router``. A naive
    ``isinstance(r, APIRoute)`` scan over ``app.routes`` therefore matches
    ZERO routes and this guard silently protects nothing.

    That is not hypothetical: it shipped. On 2026-08-01 the first deploy of this
    middleware logged "installed on NO routes" in prod while the same code
    matched 48 routes in a bare ``AgentOS(agents=...)`` test — because the test
    did not use ``base_app=``. Live topology was 17 APIRoute + 21
    _IncludedRouter + 1 Mount + 4 Route at top level, with all 48 db_id routes
    hidden one level down. Hence: descend generically, never assume a shape.

    Yields ``(prefix, route)``. ``prefix`` is the mount path a nested route sits
    behind — a mounted sub-app's ``route.path`` is RELATIVE to its mount, so
    matching it against the absolute request path silently fails without it.
    """
    if depth > 6 or routes is None:  # cycle/pathology guard
        return
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix, route
            continue
        # A Mount contributes its own path as an additional prefix;
        # include_router already baked its prefix into the child paths.
        mount_path = getattr(route, "path", "") or ""
        for attr in ("original_router", "app"):
            nested = getattr(route, attr, None)
            if nested is not None and hasattr(nested, "routes"):
                sub_prefix = prefix + mount_path if attr == "app" else prefix
                yield from _walk(nested.routes, depth + 1, sub_prefix)
        nested_routes = getattr(route, "routes", None)
        if nested_routes:
            yield from _walk(nested_routes, depth + 1, prefix)


def _routes_accepting_db_id(app: FastAPI) -> list[Any]:
    """Every reachable APIRoute whose endpoint declares a ``db_id`` parameter."""
    matched = []
    seen = set()
    for prefix, route in _walk(app.routes):
        if (prefix, id(route)) in seen:  # the same route is reachable by >1 path
            continue
        seen.add((prefix, id(route)))
        try:
            signature = inspect.signature(route.endpoint)
        except (TypeError, ValueError):  # builtins / C-implemented callables
            continue
        if "db_id" in signature.parameters:
            matched.append((prefix, route))
    return matched


def install_db_id_default(app: FastAPI, default_db_id: str) -> int:
    """Inject ``db_id=default_db_id`` on db_id-accepting routes that omit it.

    Returns the number of routes that will be defaulted, so the caller can log
    it — a count of 0 means agno changed its route signatures and this guard has
    silently stopped protecting anything.
    """
    targets = _routes_accepting_db_id(app)
    if not targets:
        return 0

    # Compiled path regexes are cheaper per-request than re-walking the router,
    # and they respect path params (e.g. /memories/{memory_id}).
    # (mount prefix, compiled path regex, allowed methods) per target route.
    matchers = [(prefix, route.path_regex, route.methods or set()) for prefix, route in targets]

    @app.middleware("http")
    async def _default_db_id(request, call_next):  # type: ignore[no-untyped-def]
        query = request.scope.get("query_string", b"")
        # Fast path: already explicit, or addressed by knowledge_id instead.
        if b"db_id=" in query or b"knowledge_id=" in query:
            return await call_next(request)

        path = request.scope.get("path", "")
        method = request.scope.get("method", "")
        if any(
            path.startswith(prefix) and pattern.match(path[len(prefix) :]) and (not allowed or method in allowed)
            for prefix, pattern, allowed in matchers
        ):
            pairs = parse_qsl(query.decode("latin-1"), keep_blank_values=True)
            pairs.append(("db_id", default_db_id))
            request.scope["query_string"] = urlencode(pairs).encode("latin-1")

        return await call_next(request)

    return len(targets)
