"""AgentOS runtime entry point.

Constructs the FastAPI app with:
- AgentOS-mounted agents
- Custom approval API routes
- Knowledge reindexing endpoint
- Health check
"""

import json
import os
import re
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Allow imports from the project root (lib.chunking)
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.chunking import smart_chunk

from fastapi import FastAPI, HTTPException, BackgroundTasks, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

from config.settings import get_settings, Settings
from agents.factory import build_agent_team


# -- API Key Authentication -----------------------------------

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(x_api_key: str = Security(api_key_header)):
    """Verify the X-API-Key header against configured API key.

    If no API key is configured (None or empty), authentication is
    disabled for development convenience.
    """
    settings: Settings = app.state.settings
    expected = getattr(settings, "api_key", None)
    if not expected:  # No key configured = auth disabled for dev
        return
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# -- Pydantic Request/Response Models -------------------------

class CreateApprovalRequest(BaseModel):
    agentRunId: str = Field(..., description="UUID of the agent run requesting approval")
    requestedAction: str = Field(..., description="Plain-English description of the action")
    riskLevel: str = Field(..., pattern="^(low|medium|high|critical)$")


class ApprovalResponse(BaseModel):
    id: str
    approvalStatus: str
    requestedAt: str


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    decidedBy: str = Field(..., description="Name of the person making the decision")
    decisionNotes: Optional[str] = Field(default=None)


class ApprovalDecisionResponse(BaseModel):
    id: str
    approvalStatus: str
    decidedAt: Optional[str] = None


class ReindexRequest(BaseModel):
    basePath: str = Field(default="./knowledge/platform")
    recreate: bool = Field(default=False)


class ReindexResponse(BaseModel):
    indexedDocumentCount: int
    status: str


class HealthResponse(BaseModel):
    status: str
    agents_ready: bool
    db_connected: bool


class MineTranscriptRequest(BaseModel):
    filePath: Optional[str] = Field(
        default=None, description="Filesystem path to transcript file"
    )
    content: Optional[str] = Field(
        default=None, description="Raw transcript text (if no file path)"
    )
    sourceName: str = Field(
        ..., description="Identifier for the transcript source (e.g., 'chat-2024-06-15')"
    )
    chunkSize: int = Field(default=8000, ge=2000, le=16000)
    dryRun: bool = Field(default=False, description="If True, return extracted insights without storing")


class TranscriptInsightItem(BaseModel):
    insightType: str
    title: str
    content: str
    confidence: float = 0.85
    sourcePosition: Optional[str] = None


class MineTranscriptResponse(BaseModel):
    sourceName: str
    chunksProcessed: int
    insightsExtracted: int
    insights: list[TranscriptInsightItem]
    sessionSummary: Optional[str] = None
    stored: bool  # True if persisted to DB


class InsightQueryResponse(BaseModel):
    insights: list[dict]
    total: int


# -- Database helpers -----------------------------------------

async def create_agent_run(
    engine: AsyncEngine,
    agent_name: str,
    prompt_text: str,
    status: str = "pending",
) -> str:
    """Create an agent_run record and return its id."""
    run_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO agent_run (id, agent_name, prompt, status, created_at)
                VALUES (:id, :agent_name, :prompt, :status, NOW())
            """),
            {
                "id": run_id,
                "agent_name": agent_name,
                "prompt": prompt_text[:10000],  # Cap length
                "status": status,
            },
        )
    return run_id


async def create_approval_request(
    engine: AsyncEngine,
    agent_run_id: str,
    action: str,
    risk_level: str,
    requested_by: str = "unknown_agent",
) -> str:
    """Persist a pending approval request and return its id."""
    approval_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO approval_request (id, agent_run_id, requested_action, requested_by_agent, risk_level, approval_status)
                VALUES (:id, :agent_run_id, :action, :requested_by, :risk_level, 'pending')
            """),
            {
                "id": approval_id,
                "agent_run_id": agent_run_id,
                "action": action,
                "requested_by": requested_by,
                "risk_level": risk_level,
            },
        )
    return approval_id


async def record_approval_decision(
    engine: AsyncEngine,
    approval_id: str,
    decision: str,
    actor: str,
    notes: Optional[str] = None,
) -> None:
    """Update approval_request and release or terminate the blocked workflow."""
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                UPDATE approval_request
                SET approval_status = :decision,
                    decided_at = NOW(),
                    decided_by = :actor,
                    decision_notes = :notes
                WHERE id = :approval_id
            """),
            {
                "decision": decision,
                "actor": actor,
                "notes": notes,
                "approval_id": approval_id,
            },
        )
        # Also update the linked agent_run
        if decision == "approved":
            await conn.execute(
                text("""
                    UPDATE agent_run
                    SET status = 'running'
                    WHERE id = (SELECT agent_run_id FROM approval_request WHERE id = :approval_id)
                    AND status = 'awaiting_approval'
                """),
                {"approval_id": approval_id},
            )
        elif decision == "rejected":
            await conn.execute(
                text("""
                    UPDATE agent_run
                    SET status = 'cancelled',
                        completed_at = NOW()
                    WHERE id = (SELECT agent_run_id FROM approval_request WHERE id = :approval_id)
                    AND status = 'awaiting_approval'
                """),
                {"approval_id": approval_id},
            )


async def store_learned_knowledge(
    engine: AsyncEngine,
    namespace: str,
    title: str,
    content: str,
    source_agent: str,
    confidence: float = 0.8,
) -> str:
    """Persist a durable lesson."""
    knowledge_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO learned_knowledge (id, namespace, title, content, source_agent, confidence)
                VALUES (:id, :namespace, :title, :content, :source_agent, :confidence)
            """),
            {
                "id": knowledge_id,
                "namespace": namespace,
                "title": title,
                "content": content,
                "source_agent": source_agent,
                "confidence": confidence,
            },
        )
    return knowledge_id


async def store_transcript_insights(
    engine: AsyncEngine,
    source_name: str,
    insights: list[dict],
    related_insight_ids: list[str] | None = None,
) -> int:
    """Persist extracted transcript insights to the database.

    Args:
        engine: Shared async SQLAlchemy engine
        source_name: Identifier for the transcript source
        insights: List of insight dicts with keys: insight_type, title, content,
                  confidence, source_position
        related_insight_ids: Optional list of related insight IDs to link.

    Returns:
        Number of insights stored
    """
    count = 0
    related_ids_json = json.dumps(related_insight_ids) if related_insight_ids else None
    async with engine.begin() as conn:
        for insight in insights:
            insight_id = str(uuid.uuid4())
            await conn.execute(
                text("""
                    INSERT INTO transcript_insight
                    (id, transcript_source, source_position, insight_type, title, content, confidence, related_insight_ids)
                    VALUES (:id, :source, :position, :itype, :title, :content, :confidence, :related)
                """),
                {
                    "id": insight_id,
                    "source": source_name,
                    "position": insight.get("sourcePosition"),
                    "itype": insight["insightType"],
                    "title": insight["title"],
                    "content": insight["content"],
                    "confidence": insight.get("confidence", 0.85),
                    "related": related_ids_json,
                },
            )
            count += 1
    return count


async def query_transcript_insights(
    engine: AsyncEngine,
    insight_type: Optional[str] = None,
    source_name: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Query stored transcript insights with optional filters."""
    conditions = []
    params = {"limit": limit}

    if insight_type:
        conditions.append("insight_type = :itype")
        params["itype"] = insight_type
    if source_name:
        conditions.append("transcript_source = :source")
        params["source"] = source_name

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"""
                SELECT id, transcript_source, source_position, insight_type,
                       title, content, confidence, extracted_at
                FROM transcript_insight
                {where_clause}
                ORDER BY extracted_at DESC
                LIMIT :limit
            """),
            params,
        )
        rows = result.mappings().all()
    return [dict(r) for r in rows]


# -- FastAPI App ------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    settings = get_settings()

    # Create shared async engine with connection pooling (C2 fix)
    app.state.engine = create_async_engine(
        settings.platform_db_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
    )

    # Build agent team (connects to MCP servers)
    mcp_tools = []
    try:
        agents = await build_agent_team(settings)
        app.state.agents = agents
        app.state.agents_ready = True
        print(f"Loaded {len(agents)} agents: {list(agents.keys())}")

        # Collect MCP tool references for cleanup on shutdown (C5 fix)
        for agent_name, agent in agents.items():
            if hasattr(agent, "tools") and agent.tools:
                for tool in agent.tools:
                    if tool and tool not in mcp_tools:
                        mcp_tools.append(tool)
        app.state.mcp_tools = mcp_tools

    except Exception as e:
        print(f"Warning: Could not load agents: {e}")
        app.state.agents = {}
        app.state.agents_ready = False
        app.state.mcp_tools = []

    app.state.settings = settings
    yield

    # Shutdown
    print("Shutting down AgentOS...")

    # Clean up MCP subprocesses (C5 fix)
    for tool in getattr(app.state, "mcp_tools", []):
        if tool and hasattr(tool, "close"):
            try:
                await tool.close()
            except Exception:
                pass

    # Dispose shared engine (C2 fix)
    engine: AsyncEngine = getattr(app.state, "engine", None)
    if engine:
        await engine.dispose()


app = FastAPI(
    title="Agno MCP Platform",
    description="Agno-based control layer for the MCP forensic evidence platform",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    settings: Settings = app.state.settings
    engine: AsyncEngine = app.state.engine
    db_connected = False

    # H1 fix: use try/finally to ensure no connection leak
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_connected = True
    except Exception:
        db_connected = False

    return HealthResponse(
        status="healthy" if app.state.agents_ready else "degraded",
        agents_ready=app.state.agents_ready,
        db_connected=db_connected,
    )


@app.post("/v1/approval-requests", response_model=ApprovalResponse, dependencies=[Security(verify_api_key)])
async def create_approval(req: CreateApprovalRequest):
    """Create a new approval request."""
    settings: Settings = app.state.settings
    engine: AsyncEngine = app.state.engine

    # M10 fix: Pydantic already validated riskLevel via regex; no redundant check needed
    try:
        # M9 fix: create agent_run record first
        run_id = await create_agent_run(
            engine=engine,
            agent_name="review_gatekeeper",
            prompt_text=req.requestedAction,
            status="awaiting_approval",
        )

        approval_id = await create_approval_request(
            engine=engine,
            agent_run_id=run_id,
            action=req.requestedAction,
            risk_level=req.riskLevel,
        )
        return ApprovalResponse(
            id=approval_id,
            approvalStatus="pending",
            requestedAt=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create approval: {str(e)}")


@app.post("/v1/approval-requests/{approval_id}/decision", response_model=ApprovalDecisionResponse, dependencies=[Security(verify_api_key)])
async def submit_decision(approval_id: str, req: ApprovalDecisionRequest):
    """Submit an approval decision."""
    engine: AsyncEngine = app.state.engine

    # M10 fix: Pydantic already validated decision via regex; no redundant check needed
    try:
        await record_approval_decision(
            engine=engine,
            approval_id=approval_id,
            decision=req.decision,
            actor=req.decidedBy,
            notes=req.decisionNotes,
        )
        return ApprovalDecisionResponse(
            id=approval_id,
            approvalStatus=req.decision,
            decidedAt=datetime.now(timezone.utc).isoformat() if req.decision else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record decision: {str(e)}")


@app.post("/v1/knowledge/reindex", response_model=ReindexResponse, dependencies=[Security(verify_api_key)])
async def reindex_knowledge(req: ReindexRequest):
    """Trigger knowledge reindexing from filesystem."""
    # This would call the ingest_knowledge script
    # For MVP, return a stub that shows the API contract
    return ReindexResponse(
        indexedDocumentCount=0,
        status="not_implemented_run_script_directly",
    )


# -- Agent Routes -----------------------------------------------

@app.post("/v1/agents/{agent_name}/run", dependencies=[Security(verify_api_key)])
async def run_agent(agent_name: str, prompt: dict):
    """Run an agent with a given prompt.

    Args:
        agent_name: One of the 7 agent keys
        prompt: { "message": "..." }

    Returns:
        Agent response
    """
    agents = app.state.agents
    if agent_name not in agents:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Available: {list(agents.keys())}"
        )

    agent = agents[agent_name]
    message = prompt.get("message", "")

    try:
        response = await agent.arun(message)
        return {
            "agent": agent_name,
            "response": response.content if hasattr(response, "content") else str(response),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/v1/agents")
async def list_agents():
    """List all available agents."""
    agents = app.state.agents
    PLATFORM_AGENT_NAMES = {
        "ingestion_orchestrator",
        "analysis_orchestrator",
        "review_gatekeeper",
        "transcript_miner",
    }
    return {
        "agents": [
            {
                "name": name,
                "type": "platform" if name in PLATFORM_AGENT_NAMES else "builder",
                "ready": True,
            }
            for name in agents.keys()
        ]
    }


# -- Transcript Mining Routes ---------------------------------

@app.post("/v1/transcripts/mine", response_model=MineTranscriptResponse, dependencies=[Security(verify_api_key)])
async def mine_transcript(req: MineTranscriptRequest):
    """Mine a transcript for structured insights.

    Accepts either a file path or raw content. Chunks the transcript
    server-side using smart_chunk(), loops over ALL chunks, aggregates
    insights, and (optionally) stores them.

    C3 fix: previously only processed content[:req.chunkSize] — now
    processes every chunk returned by smart_chunk().
    """
    settings: Settings = app.state.settings
    engine: AsyncEngine = app.state.engine
    agents = app.state.agents

    # Validate input
    if not req.filePath and not req.content:
        raise HTTPException(
            status_code=422, detail="Provide either filePath or content"
        )

    # Read file if path given
    # C1 fix: validate filePath against knowledge_base_path allowlist
    content = req.content or ""
    if req.filePath:
        base_path = Path(settings.knowledge_base_path).resolve()
        fp = Path(req.filePath).resolve()
        try:
            fp.relative_to(base_path)
        except ValueError:
            raise HTTPException(
                status_code=403, detail="Access denied: path outside knowledge base"
            )
        if not fp.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {req.filePath}")
        content = fp.read_text(encoding="utf-8", errors="replace")

    if not content.strip():
        raise HTTPException(status_code=422, detail="Transcript content is empty")

    # Chunk the transcript server-side (C3 fix)
    chunks = smart_chunk(content, req.chunkSize)

    agent = agents.get("transcript_miner")
    if agent is None:
        raise HTTPException(status_code=503, detail="transcript_miner agent not available")

    # Process each chunk and aggregate insights
    all_insights: list[dict] = []

    for i, chunk in enumerate(chunks):
        mining_prompt = f"""Mine chunk {i + 1}/{len(chunks)} of transcript for structured insights.

SOURCE: {req.sourceName}
CHUNK_POSITION: {chunk['position']} ({chunk['estimated_tokens']:,} estimated tokens)
DRY_RUN: {req.dryRun}

CHUNK:
{chunk['content']}

Extract insights as a JSON array with this shape per item:
{{
  "insightType": "decision|code_artifact|goal|blocker|architecture|next_action|issue_found|learning",
  "title": "Short descriptive title",
  "content": "Detailed description with all relevant context",
  "confidence": 0.0-1.0,
  "sourcePosition": "Where in the transcript this was found"
}}

After extraction, provide a session summary with key decisions, blockers, and next actions.
"""
        try:
            response = await agent.arun(mining_prompt)
            response_text = response.content if hasattr(response, "content") else str(response)

            # Parse JSON array from the agent response
            try:
                json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
                if json_match:
                    chunk_insights = json.loads(json_match.group())
                else:
                    chunk_insights = []
            except (json.JSONDecodeError, AttributeError):
                chunk_insights = []

            # Wrap raw insights into the expected shape
            for ins in chunk_insights:
                if isinstance(ins, dict):
                    all_insights.append({
                        "insightType": ins.get("insightType", "learning"),
                        "title": ins.get("title", "Untitled"),
                        "content": ins.get("content", ""),
                        "confidence": ins.get("confidence", 0.85),
                        "sourcePosition": ins.get("sourcePosition", chunk["position"]),
                    })
        except Exception as e:
            # Log chunk-level errors but continue processing remaining chunks
            print(f"Warning: Chunk {i + 1}/{len(chunks)} failed: {e}")
            continue

    # Store if not dry run
    stored = False
    if not req.dryRun and all_insights:
        try:
            # Collect insight IDs from the same source for cross-linking
            count = await store_transcript_insights(
                engine=engine,
                source_name=req.sourceName,
                insights=all_insights,
                related_insight_ids=None,
            )
            stored = count > 0
        except Exception as e:
            # Don't fail the request if DB storage fails in MVP
            print(f"Warning: Could not store insights: {e}")

    return MineTranscriptResponse(
        sourceName=req.sourceName,
        chunksProcessed=len(chunks),
        insightsExtracted=len(all_insights),
        insights=[TranscriptInsightItem(**i) for i in all_insights],
        sessionSummary=None,  # Would be parsed from agent response
        stored=stored,
    )


@app.get("/v1/transcripts/insights", response_model=InsightQueryResponse)
async def list_insights(
    insight_type: Optional[str] = None,
    source_name: Optional[str] = None,
    limit: int = 50,
):
    """Query stored transcript insights with optional filters."""
    engine: AsyncEngine = app.state.engine

    try:
        insights = await query_transcript_insights(
            engine=engine,
            insight_type=insight_type,
            source_name=source_name,
            limit=limit,
        )
        return InsightQueryResponse(insights=insights, total=len(insights))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query insights: {str(e)}")


# H2 fix: gate reload behind env var (never use in production)
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    reload_flag = os.environ.get("UVICORN_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=reload_flag,
    )
