"""
Eval Cases
==========

Each case sends one input to one agent and (optionally) checks two things:

- **judge** — `AgentAsJudgeEval` scores the response against `criteria`
  (binary pass/fail) using an LLM.
- **reliability** — `ReliabilityEval` checks which tools fired against
  `expected_tool_calls`.

The skeleton's web_search/code_search cases were removed with those agents
(v8.1 topology). Cases for the v8.1 agents (routing, governance, boundaries)
land with the evals phase — see docs/planning/BUILD_TODO.md Phase 12.

Add a case below, then run `python -m evals`.
"""

from dataclasses import dataclass

from agno.agent import Agent

from db import get_postgres_db

# Single eval DB instance — every case logs through it.
eval_db = get_postgres_db()


@dataclass(frozen=True)
class Case:
    """One eval case: an input to one agent + optional judge/reliability checks."""

    name: str
    agent: Agent
    input: str

    # Judge check (LLM judge against a rubric, binary pass/fail). Set ``criteria`` to enable.
    criteria: str | None = None

    # Reliability check (tool-call assertion). Set ``expected_tool_calls`` to enable.
    expected_tool_calls: tuple[str, ...] | None = None
    allow_additional_tool_calls: bool = True


CASES: tuple[Case, ...] = ()  # v8.1 cases land with Phase 12 (routing/governance/boundaries)
