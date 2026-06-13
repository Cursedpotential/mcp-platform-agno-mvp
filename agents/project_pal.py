"""Project PAL — maintains rolling memory of project goals, blockers, decisions, preferences."""

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db
from agents.instructions import get_instructions

project_pal = Agent(
    id="project-pal",
    name="Project PAL",
    model=default_model(),
    db=get_postgres_db(),
    instructions=get_instructions("project_pal"),
    add_history_to_context=True,
    num_history_runs=10,
    markdown=True,
)
