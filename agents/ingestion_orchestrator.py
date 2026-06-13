"""Ingestion Orchestrator — receives evidence files, coordinates parsing, hashing, normalization."""

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db
from agents.instructions import get_instructions

ingestion_orchestrator = Agent(
    id="ingestion-orchestrator",
    name="Ingestion Orchestrator",
    model=default_model(),
    db=get_postgres_db(),
    instructions=get_instructions("ingestion_orchestrator"),
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
