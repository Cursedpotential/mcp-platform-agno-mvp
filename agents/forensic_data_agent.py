"""Forensic Data Agent — explains schemas, helps construct safe queries, runs approved queries."""

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db
from agents.instructions import get_instructions

forensic_data_agent = Agent(
    id="forensic-data-agent",
    name="Forensic Data Agent",
    model=default_model(),
    db=get_postgres_db(),
    instructions=get_instructions("forensic_data_agent"),
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
