"""Transcript Miner — parses raw AI chat transcripts and extracts structured insights."""

from agno.agent import Agent

from app.settings import default_model
from db import get_agno_db
from agents.instructions import get_instructions

transcript_miner = Agent(
    id="transcript-miner",
    name="Transcript Miner",
    model=default_model(),
    db=get_agno_db(),
    instructions=get_instructions("transcript_miner"),
    add_history_to_context=True,
    num_history_runs=10,
    markdown=True,
)
