"""Analysis Orchestrator — runs NLP analysis, detects patterns, builds knowledge graphs."""

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db
from agents.instructions import get_instructions

analysis_orchestrator = Agent(
    id="analysis-orchestrator",
    name="Analysis Orchestrator",
    model=default_model(),
    db=get_postgres_db(),
    instructions=get_instructions("analysis_orchestrator"),
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
