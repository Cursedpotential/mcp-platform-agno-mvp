"""Agent factory: constructs all platform and builder agents.

Each agent is wired with:
- Model (from settings.get_model())
- Knowledge (project context from ingested docs)
- MCP Tools (from existing MCP_PLATFORM servers)
- Instructions (from instructions.py)
- Memory and learning (for builder agents)
"""

from typing import Any

from agno.agent import Agent
from agno.tools.mcp import MCPTools

from config.settings import Settings
from agents.instructions import get_instructions


async def build_knowledge_base(
    base_path: str, db_url: str, table_name: str = "platform_docs"
) -> Any:
    """Create or return the Agno Knowledge object bound to pgvector.

    Args:
        base_path: Filesystem path to project docs/chats/notes
        db_url: PostgreSQL connection string
        table_name: Table name for the knowledge store

    Returns:
        Agno AgentKnowledge instance or None if dependencies unavailable
    """
    try:
        from agno.knowledge import AgentKnowledge
        from agno.vectordb.pgvector import PgVector
        from agno.embedder.openai import OpenAIEmbedder

        vector_db = PgVector(
            table_name=table_name,
            db_url=db_url,
            embedder=OpenAIEmbedder(id="text-embedding-3-small"),
        )

        knowledge = AgentKnowledge(vector_db=vector_db)
        return knowledge
    except ImportError as e:
        print(f"Warning: Could not build knowledge base: {e}")
        return None


async def build_mcp_tools(command: str, timeout_seconds: int = 30) -> MCPTools:
    """Create a connected MCPTools instance using command-based startup.

    Args:
        command: Shell command to start the MCP server
        timeout_seconds: Startup timeout

    Returns:
        Connected MCPTools instance
    """
    return MCPTools(command=command, timeout=timeout_seconds)


async def build_agent_team(settings: Settings) -> dict[str, Agent]:
    """Return all agents keyed by stable public name.

    Creates 4 platform agents + 3 builder agents, each with:
    - Model from settings
    - Knowledge base (project context)
    - MCP tools (from existing servers)
    - Role-specific instructions

    Args:
        settings: Application settings

    Returns:
        Dictionary of agent_name -> Agent
    """
    # -- Shared resources -----------------------------------------
    model = settings.get_model()
    knowledge = await build_knowledge_base(
        settings.knowledge_base_path, settings.platform_db_url
    )

    # -- MCP Tool Connections -------------------------------------
    ts_tools = None
    py_tools = None
    js_tools = None

    try:
        ts_tools = await build_mcp_tools(settings.ts_mcp_command)
    except Exception as e:
        print(f"Warning: Could not connect to TS MCP server: {e}")

    try:
        py_tools = await build_mcp_tools(settings.py_mcp_command)
    except Exception as e:
        print(f"Warning: Could not connect to Py MCP server: {e}")

    if settings.js_mcp_command:
        try:
            js_tools = await build_mcp_tools(settings.js_mcp_command)
        except Exception as e:
            print(f"Warning: Could not connect to JS MCP server: {e}")

    # Collect available tools per agent
    platform_tools = []
    if ts_tools:
        platform_tools.append(ts_tools)
    if py_tools:
        platform_tools.append(py_tools)

    builder_tools = []
    if ts_tools:
        builder_tools.append(ts_tools)
    if py_tools:
        builder_tools.append(py_tools)

    # -- Platform Agents ------------------------------------------

    ingestion_orchestrator = Agent(
        name="ingestion_orchestrator",
        agent_id="ingestion_orchestrator",
        model=model,
        tools=platform_tools,
        instructions=get_instructions("ingestion_orchestrator"),
        knowledge=knowledge,
        search_knowledge=True,
        add_history_to_messages=True,
        num_history_responses=5,
        markdown=True,
    )

    analysis_orchestrator = Agent(
        name="analysis_orchestrator",
        agent_id="analysis_orchestrator",
        model=model,
        tools=platform_tools,
        instructions=get_instructions("analysis_orchestrator"),
        knowledge=knowledge,
        search_knowledge=True,
        add_history_to_messages=True,
        num_history_responses=5,
        markdown=True,
    )

    review_gatekeeper = Agent(
        name="review_gatekeeper",
        agent_id="review_gatekeeper",
        model=model,
        instructions=get_instructions("review_gatekeeper"),
        add_history_to_messages=True,
        num_history_responses=3,
        markdown=True,
    )

    transcript_miner = Agent(
        name="transcript_miner",
        agent_id="transcript_miner",
        model=model,
        tools=platform_tools,
        instructions=get_instructions("transcript_miner"),
        knowledge=knowledge,
        search_knowledge=True,
        add_history_to_messages=True,
        num_history_responses=10,
        markdown=True,
        # Transcript miner gets deep context to correlate across sessions
    )

    # -- Builder Agents -------------------------------------------

    dev_copilot = Agent(
        name="dev_copilot",
        agent_id="dev_copilot",
        model=model,
        tools=builder_tools,
        instructions=get_instructions("dev_copilot"),
        knowledge=knowledge,
        search_knowledge=True,
        add_history_to_messages=True,
        num_history_responses=10,
        markdown=True,
    )

    project_pal = Agent(
        name="project_pal",
        agent_id="project_pal",
        model=model,
        tools=builder_tools,
        instructions=get_instructions("project_pal"),
        knowledge=knowledge,
        search_knowledge=True,
        add_history_to_messages=True,
        num_history_responses=10,
        markdown=True,
    )

    forensic_data_agent = Agent(
        name="forensic_data_agent",
        agent_id="forensic_data_agent",
        model=model,
        tools=builder_tools,
        instructions=get_instructions("forensic_data_agent"),
        knowledge=knowledge,
        search_knowledge=True,
        add_history_to_messages=True,
        num_history_responses=5,
        markdown=True,
    )

    return {
        "ingestion_orchestrator": ingestion_orchestrator,
        "analysis_orchestrator": analysis_orchestrator,
        "review_gatekeeper": review_gatekeeper,
        "transcript_miner": transcript_miner,
        "dev_copilot": dev_copilot,
        "project_pal": project_pal,
        "forensic_data_agent": forensic_data_agent,
    }
