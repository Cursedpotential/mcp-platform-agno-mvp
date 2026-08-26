"""GAP-004 — agent authority boundary.

Agno is a replaceable orchestration/runtime adapter and owns no evidence,
horizon, memory, provider, HITL, admin, or canonical truth
(``docs/PROJECT_CANON.md``). Ordinary agents (ingestion/analysis
orchestrators, transcript miner) must never receive an independent,
ungoverned, authority-bearing database writer from Agno's own context-
provider defaults. The only platform-owned governed write contract is
``apply_db_modification`` (``agents/factory.py``): schema-allowlisted,
``evidence``-hard-denied, ``@approval``-gated (blocking HITL, persisted
pending-approval row), and transaction-bound.

See ``docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md`` (GAP-004)
and ``docs/reviews/2026-08-25-schema-audit/GAP-004-IMPLEMENTATION-STATUS.md``.

No live DB connection is required: ``create_engine()`` is lazy (no socket
opens until first use) and ``DatabaseContextProvider.get_tools()`` only
inspects ``self.read`` / ``self.write`` flags to decide which tool
functions to build — it never touches the engine at construction time.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine

from agno.context.database import DatabaseContextProvider

from server.agents.factory import apply_db_modification
from server.agents.providers import build_context

_DUMMY_DB_URL = "postgresql+psycopg://u:p@localhost:5432/db"


def _tool_names(tools: list[Any]) -> set[str]:
    names: set[str] = set()
    for entry in tools:
        if hasattr(entry, "functions"):  # Toolkit
            names.update(entry.functions.keys())
        else:  # bare @tool Function
            names.add(entry.name)
    return names


# ---------------------------------------------------------------------------
# Denial: no independent Agno-native writer reaches ordinary agents
# ---------------------------------------------------------------------------


def test_database_context_provider_write_false_exposes_no_update_tool():
    """Direct unit test of the Agno primitive: ``write=False`` must drop the
    ``update_<id>`` tool entirely, not merely hide it behind a flag agents
    could still reach."""
    engine = create_engine(_DUMMY_DB_URL)
    provider = DatabaseContextProvider(
        id="database",
        sql_engine=engine,
        readonly_engine=engine,
        model=None,
        write=False,
    )
    names = _tool_names(provider.get_tools())
    assert names == {"query_database"}
    assert "update_database" not in names


def test_build_context_source_tools_deny_update_database():
    """The actual wiring point (GAP-004 evidence line): ``source_tools`` is
    handed to every ordinary agent (ingestion/analysis orchestrators,
    transcript miner) in ``factory.build_agent_team``. It must never carry
    an Agno-native ``update_database`` tool."""
    ctx = build_context(model=None, db=None, knowledge=None, learning=None, db_url=_DUMMY_DB_URL)
    names = _tool_names(ctx.source_tools)
    assert "update_database" not in names
    assert "update_evidence" not in names


def test_readonly_db_tools_never_carried_a_write_tool():
    """Forensic Data Agent's read-only provider (``evidence_provider``,
    pre-existing ``write=False``) — regression guard so a future edit can't
    silently flip this one back on either."""
    ctx = build_context(model=None, db=None, knowledge=None, learning=None, db_url=_DUMMY_DB_URL)
    names = _tool_names(ctx.readonly_db_tools)
    assert names == {"query_evidence"}


# ---------------------------------------------------------------------------
# Allowed: read access is preserved
# ---------------------------------------------------------------------------


def test_build_context_source_tools_allow_query_database():
    ctx = build_context(model=None, db=None, knowledge=None, learning=None, db_url=_DUMMY_DB_URL)
    names = _tool_names(ctx.source_tools)
    assert "query_database" in names


def test_database_context_provider_write_false_still_allows_read():
    engine = create_engine(_DUMMY_DB_URL)
    provider = DatabaseContextProvider(
        id="database",
        sql_engine=engine,
        readonly_engine=engine,
        model=None,
        write=False,
    )
    names = _tool_names(provider.get_tools())
    assert "query_database" in names


# ---------------------------------------------------------------------------
# Approval path: the ONE platform-owned governed write contract
# (apply_db_modification, agents/factory.py — already exists in this
# ownership boundary, so its HITL wiring and guard logic get direct coverage)
# ---------------------------------------------------------------------------


def test_apply_db_modification_requires_blocking_approval():
    """The governed writer must be HITL-gated at the agno tool-metadata
    level, not merely by convention — ``@approval`` composed under
    ``@tool(requires_confirmation=True)`` sets both flags on the resulting
    ``Function``."""
    assert apply_db_modification.requires_confirmation is True
    assert apply_db_modification.approval_type == "required"


def test_apply_db_modification_denies_evidence_schema_reference():
    result = apply_db_modification.entrypoint(
        statement="UPDATE evidence.raw_message SET body = 'x'",
        target_schema="analysis",
    )
    assert result.startswith("REJECTED:")
    assert "evidence" in result


def test_apply_db_modification_denies_evidence_schema_reference_case_insensitive():
    result = apply_db_modification.entrypoint(
        statement="update EVIDENCE.raw_message set body = 'x'",
        target_schema="analysis",
    )
    assert result.startswith("REJECTED:")


def test_apply_db_modification_denies_non_allowlisted_schema():
    result = apply_db_modification.entrypoint(
        statement="INSERT INTO foo (id) VALUES (1)",
        target_schema="not_in_allowlist",
    )
    assert result.startswith("REJECTED:")
    assert "target_schema must be one of" in result


def test_apply_db_modification_denies_search_path_injection_schema_name():
    """A schema value carrying SQL syntax (attempted ``search_path``
    injection, since ``target_schema`` is interpolated into
    ``SET LOCAL search_path TO {target_schema}``) is denied — it is neither
    in the allowlist nor a bare identifier."""
    result = apply_db_modification.entrypoint(
        statement="SELECT 1",
        target_schema="analysis; DROP SCHEMA public",
    )
    assert result.startswith("REJECTED:")
