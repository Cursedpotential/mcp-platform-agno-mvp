"""Platform agents package.

Agents are built via `agents.factory.build_agent_team(ctx)` with the
PlatformContext from `agents.providers.build_context(...)` — see app/main.py.

The flat per-agent modules (ingestion_orchestrator.py, dev_copilot.py, ...)
are the superseded skeleton pattern; they are kept for reference only and are
deliberately NOT imported here (importing them constructs agents at import
time, which requires live credentials).
"""
