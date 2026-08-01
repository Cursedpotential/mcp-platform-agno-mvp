"""server/agents/claude_code_agent.py — Claude Code as an AgentOS agent.

STATUS: staged, NOT mounted into the live topology. ``build_claude_code_agent``
is importable and functional but is deliberately not called from
``factory.build_agent_team()`` / ``server/api/main.py`` — wiring it into the
Root Router is an architecture-level topology change (ADR-0006) that needs
explicit owner sign-off, not something a config/audit task should do
silently. This module is the concrete "file, call site, config" wiring plan
made runnable, ready for a one-line addition to ``build_agent_team`` once
approved.

## What this actually is

``agno.agents.claude.ClaudeAgent`` wraps the Claude Agent SDK
(https://github.com/anthropics/claude-agent-sdk-python) — it runs Claude
Code itself (the coding agent, with its own tool loop: Read/Edit/Bash/etc.)
as a subprocess and streams its output back through AgentOS. This is
DIFFERENT from ``agno.models.anthropic.Claude`` (the plain chat-completion
model wrapper server/core/settings.py's "anthropic" provider branch uses) —
that gives you Claude as an LLM backend for agno's own tool-calling loop;
this gives you Claude Code's own agent loop as a whole separate AgentOS
agent. Confirmed present in the installed agno 2.8.6
(``.venv/Lib/site-packages/agno/agents/claude/agent.py``) and documented at
https://docs.agno.com/agent-os/multi-framework/claude-agent-sdk — this is a
real, current, non-deprecated agno feature, not a stale vendor doc (the
Semantica integration that turned out dead on 2.8.0 was a different case).

## What it needs that isn't in place yet

1. ``pip install claude-agent-sdk`` (repo extra: ``uv pip install -e
   ".[claude-code]"`` — see pyproject.toml). NOT installed in this repo's
   venv as of 2026-08-01; ``import claude_agent_sdk`` currently fails.
   The package bundles its own native Claude Code binary (confirmed via
   Anthropic's own SDK quickstart docs) — no separate Node.js/CLI install
   needed, but it IS a heavier install than the plain `anthropic` package.

2. Auth: Anthropic's own docs (`https://code.claude.com/docs/en/agent-sdk`)
   set `ANTHROPIC_API_KEY` as THE documented method for the Agent SDK, and
   explicitly warn: "Unless previously approved, Anthropic does not allow
   third party developers to offer claude.ai login or rate limits for their
   products, including agents built on the Claude Agent SDK. Use the API key
   authentication methods... instead." No ANTHROPIC_API_KEY exists in this
   platform's secrets — only a Claude Code subscription OAuth token
   (CLAUDE_CODE_OAUTH_TOKEN). That token DOES work for the plain
   ``agno.models.anthropic.Claude`` path (see settings.py's
   ANTHROPIC_AUTH_TOKEN fallback, verified live 2026-08-01) because that's a
   direct Messages-API bearer-token call. Whether the *bundled Claude Code
   binary* the SDK subprocess launches will itself accept
   ANTHROPIC_AUTH_TOKEN / CLAUDE_CODE_OAUTH_TOKEN in its subprocess
   environment the same way is UNVERIFIED — it wasn't installed to test.
   Given the ToS note above, running this as a single-owner personal tool
   (not a product offered to other users) is the plausible-fine reading, but
   it's a real compliance question, not just a technical one — flag it to
   the owner rather than assume.

3. Topology: where would this even live? The obvious slot is a new leaf
   under Builder (alongside dev_copilot/project_pal/forensic_data_agent) —
   Claude Code's own Read/Edit/Bash loop overlaps hard with dev_copilot's
   job. Needs an explicit decision on whether it REPLACES dev_copilot,
   sits ALONGSIDE it, or is a standalone top-level agent outside the
   Router/coordinate topology entirely (BaseExternalAgent doesn't require
   living inside a Team). Not decided here.

## Byline

Claude Code · Sonnet (agent) · 2026-08-01
"""

from __future__ import annotations

from typing import Any, Optional

# Doesn't import agno.agents.claude at module scope — that import would fail
# hard if claude-agent-sdk isn't installed (see build_claude_code_agent's own
# lazy import + the ImportError agno's ClaudeAgent itself raises).


def claude_code_available() -> bool:
    """Whether the claude-agent-sdk optional dependency is importable.

    Cheap capability check for a caller (e.g. a future factory.py hookup)
    to decide whether to offer this agent at all — mirrors the
    "return None if credentials/deps missing" pattern in
    server/core/settings.py's _try_provider.
    """
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return False
    return True


def build_claude_code_agent(
    *,
    name: str = "Claude Code Agent",
    model: str = "claude-sonnet-4-6",
    allowed_tools: Optional[list[str]] = None,
    permission_mode: str = "plan",
    max_turns: Optional[int] = 10,
    max_budget_usd: Optional[float] = None,
    cwd: Optional[str] = None,
    db: Optional[Any] = None,
) -> Any:
    """Build a ``ClaudeAgent`` (Claude Code, wrapped for AgentOS).

    Raises
    ------
    ImportError
        NOT here, despite what you'd expect — verified empirically
        2026-08-01. ``ClaudeAgent(...)`` construction succeeds even without
        ``claude-agent-sdk`` installed; ``agno.agents.claude.agent``'s
        ``_sdk()`` import is lazy and only fires inside ``_arun_adapter`` /
        ``_arun_adapter_stream``, i.e. the FIRST ``.run()``/``.arun()``/
        ``.print_response()`` call raises it, not this factory. Call
        ``claude_code_available()`` before *running* the agent (not before
        building it) if you want a soft skip instead of a failure mid-run —
        matches settings.py's provider-chain convention of checking
        credentials/deps before use rather than after a hard crash.

    Notes
    -----
    ``permission_mode`` defaults to ``"plan"`` here (NOT agno's own example
    default of ``"acceptEdits"``) — this repo's dev_copilot/forensic_data_agent
    already run inside a HITL-gated review flow (``review_gatekeeper``,
    OQ-8 error convention); defaulting a subprocess coding agent to
    auto-accept file edits would bypass that without an explicit owner
    decision to do so. Override deliberately, not by accident.

    Parameters mirror ``agno.agents.claude.ClaudeAgent`` directly — see
    https://docs.agno.com/agent-os/multi-framework/claude-agent-sdk for the
    full parameter reference (system_prompt, disallowed_tools, mcp_servers,
    options_kwargs are also available on the underlying class but not
    threaded through this factory yet; add them here, not by calling
    ``ClaudeAgent`` directly elsewhere, to keep one call site).
    """
    from agno.agents.claude import ClaudeAgent  # raises ImportError with a clear message if missing

    return ClaudeAgent(
        name=name,
        model=model,
        allowed_tools=allowed_tools or ["Read", "Grep", "Glob"],
        permission_mode=permission_mode,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        cwd=cwd,
        db=db,
    )
