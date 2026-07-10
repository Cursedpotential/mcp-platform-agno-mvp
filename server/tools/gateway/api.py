"""FastAPI surface for the tool gateway (ADR-0023: everything gets an API;
every API gets an MCP wrapper — ContextForge REST-wraps these five routes
into MCP tools, so there is deliberately no MCP SDK dependency here)."""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query

from server.tools.gateway.content_store import ContentStore
from server.tools.gateway.toolfinder import (
    describe_tool,
    execute_tool,
    get_ref,
    get_tool_categories,
    search_tools,
)


def build_app(store: ContentStore | None = None) -> FastAPI:
    store = store or ContentStore()
    app = FastAPI(
        title="Tool Gateway",
        description="Progressive-disclosure meta-API over the atomic-tool registry",
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/categories")
    def categories() -> list[dict[str, Any]]:
        return get_tool_categories()

    @app.get("/tools")
    def tools(
        query: str = Query("", description="search terms (id/description/category)"),
        category: str | None = Query(None),
        limit: int = Query(20, ge=1, le=100),
    ) -> list[dict[str, Any]]:
        return search_tools(query, category, limit)

    @app.get("/tools/{tool_id}")
    def tool(tool_id: str) -> dict[str, Any]:
        try:
            return describe_tool(tool_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown tool {tool_id!r}")

    @app.post("/tools/{tool_id}/execute")
    def execute(tool_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        try:
            return execute_tool(tool_id, payload, store=store)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown tool {tool_id!r}")
        except Exception as exc:  # tool hard-fail (wrong format etc.) -> structured 422
            raise HTTPException(status_code=422, detail=f"{type(exc).__name__}: {exc}")

    @app.get("/refs/{sha}")
    def ref_page(
        sha: str,
        page: int = Query(0, ge=0),
        page_size: int | None = Query(None, ge=1, le=65536),
    ) -> dict[str, Any]:
        try:
            return get_ref(sha, page=page, page_size=page_size, store=store)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"unknown ref {sha!r}")
        except (IndexError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return app
