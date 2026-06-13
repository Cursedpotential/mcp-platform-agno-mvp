"""Dev Copilot — helps port tools, propose implementation changes, generate migration plans."""

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db
from agents.instructions import get_instructions

dev_copilot = Agent(
    id="dev-copilot",
    name="Dev Copilot",
    model=default_model(),
    db=get_postgres_db(),
    instructions=get_instructions("dev_copilot"),
    add_history_to_context=True,
    num_history_runs=10,
    markdown=True,
)
