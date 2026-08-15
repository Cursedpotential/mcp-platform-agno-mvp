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
from agno.models.openai.like import OpenAILike

from server.core import get_agno_db

# Single eval DB instance — every case logs through it.
eval_db = get_agno_db()


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


# Classification & Sentiment Test Agents
# These agents test the classification/sentiment comparison endpoints

classification_test_agent = Agent(
    name="classification-tester",
    model=OpenAILike(id="glm-5.1", api_key="test"),  # Will be overridden by test
    instructions="""
You are a test agent for classification and sentiment analysis.
Your role is to verify that the classification and sentiment endpoints work correctly.
""",
    tools=[],
)

sentiment_test_agent = Agent(
    name="sentiment-tester",
    model=OpenAILike(id="glm-5.1", api_key="test"),
    instructions="""
You are a test agent for sentiment analysis.
""",
    tools=[],
)

comparison_test_agent = Agent(
    name="comparison-tester",
    model=OpenAILike(id="glm-5.1", api_key="test"),
    instructions="""
You are a test agent for multi-provider comparison.
""",
    tools=[],
)


# Test Cases for Classification & Sentiment Analysis System

CASES: tuple[Case, ...] = (
    # Basic classification test
    Case(
        name="classification-legal-text",
        agent=classification_test_agent,
        input="I need to file a motion for custody modification in Genesee County family court. The current parenting time schedule is not working.",
        criteria="Classifies as 'legal' category with confidence > 0.8",
        expected_tool_calls=(),
    ),
    # Platform/technical classification
    Case(
        name="classification-platform-text",
        agent=classification_test_agent,
        input="We need to deploy the FastAPI application to Docker with PostgreSQL and pgvector. The migration scripts need to run before startup.",
        criteria="Classifies as 'platform' category with confidence > 0.8",
        expected_tool_calls=(),
    ),
    # Personal history classification
    Case(
        name="classification-personal-history-text",
        agent=classification_test_agent,
        input="I was afraid of him for years. The gaslighting and coercive control made me question my own reality. The trauma still affects me daily.",
        criteria="Classifies as 'personal_history' category with confidence > 0.8",
        expected_tool_calls=(),
    ),
    # Sentiment analysis test - negative
    Case(
        name="sentiment-negative-text",
        agent=sentiment_test_agent,
        input="This is absolutely terrible. I hate everything about this situation. It's making me furious and anxious.",
        criteria="Sentiment is 'negative' with score < -0.5",
        expected_tool_calls=(),
    ),
    # Sentiment analysis test - positive
    Case(
        name="sentiment-positive-text",
        agent=sentiment_test_agent,
        input="I'm so grateful and happy! This is wonderful news. Thank you so much for helping me through this difficult time.",
        criteria="Sentiment is 'positive' with score > 0.5",
        expected_tool_calls=(),
    ),
    # Sentiment analysis test - neutral
    Case(
        name="sentiment-neutral-text",
        agent=sentiment_test_agent,
        input="The meeting is scheduled for 3 PM tomorrow. Please bring the documents we discussed.",
        criteria="Sentiment is 'neutral' with score between -0.3 and 0.3",
        expected_tool_calls=(),
    ),
    # Multi-provider comparison test
    Case(
        name="comparison-ollama-vs-nvidia",
        agent=comparison_test_agent,
        input="I need to file a motion for temporary custody relief. The children are in danger.",
        criteria="Both providers classify as 'legal' with confidence > 0.7",
        expected_tool_calls=(),
    ),
    # Batch classification test
    Case(
        name="batch-classification-mixed",
        agent=classification_test_agent,
        input="Legal text: motion for custody. Platform text: deploy docker. Personal: afraid of abuse.",
        criteria="Handles multiple categories correctly in batch mode",
        expected_tool_calls=(),
    ),
)
