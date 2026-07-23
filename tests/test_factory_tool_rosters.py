"""Tests for agents/factory.py Builder-team tool rosters.

Narrow unit coverage for the agno-2.8.0 FileGenerationTools wire-in
(``docs/DECISION_LOG.md`` / owner "Wire it in", 2026-07-23): asserts
``build_dev_copilot`` includes agno's built-in file-generation tools
alongside the pre-existing ``UserControlFlowTools``, without requiring a
live model/db/knowledge/learning stack (all four are passed as ``None`` —
``build_dev_copilot`` only forwards them into ``Agent(...)`` kwargs, it
never touches them while assembling the tool list).
"""

from __future__ import annotations

from agno.tools.file_generation import FileGenerationTools
from agno.tools.user_control_flow import UserControlFlowTools

from server.agents.factory import build_dev_copilot


def _tool_names(agent) -> set[str]:  # type: ignore[no-untyped-def]
    """Flatten an Agent's tool list to a set of names, whether the entry is a
    bare ``@tool`` ``Function`` (has ``.name``) or a ``Toolkit`` instance
    that expands to several ``Function``s (has ``.functions``)."""
    names: set[str] = set()
    for entry in agent.tools:
        if hasattr(entry, "functions"):  # Toolkit
            names.update(entry.functions.keys())
        else:  # bare @tool Function
            names.add(entry.name)
    return names


def test_dev_copilot_includes_file_generation_tools():
    agent = build_dev_copilot(model=None, db=None, knowledge=None, learning=None, code_tools=[])

    kinds = {type(t) for t in agent.tools}
    assert UserControlFlowTools in kinds
    assert FileGenerationTools in kinds

    names = _tool_names(agent)
    # Default FileGenerationTools() config enables all seven generators.
    assert {
        "generate_json_file",
        "generate_csv_file",
        "generate_text_file",
        "generate_html_file",
        "generate_code_file",
    } <= names


def test_dev_copilot_file_generation_tools_use_default_settings():
    """Default settings per owner instruction: no output_directory means
    ``save_files`` stays False — generated files come back as in-memory
    ``File`` artifacts, never written to disk (no writable sandbox mount
    exists for Builder-team agents today)."""
    agent = build_dev_copilot(model=None, db=None, knowledge=None, learning=None, code_tools=[])
    file_gen = next(t for t in agent.tools if isinstance(t, FileGenerationTools))
    assert file_gen.save_files is False
    assert file_gen.output_directory is None
