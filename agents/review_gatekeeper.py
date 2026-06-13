"""Review Gatekeeper — translates technical actions into plain-English approval requests."""

from agno.agent import Agent

from app.settings import default_model
from db import get_postgres_db
from agents.instructions import get_instructions

review_gatekeeper = Agent(
    id="review-gatekeeper",
    name="Review Gatekeeper",
    model=default_model(),
    db=get_postgres_db(),
    instructions=get_instructions("review_gatekeeper"),
    add_history_to_context=True,
    num_history_runs=3,
    markdown=True,
)
