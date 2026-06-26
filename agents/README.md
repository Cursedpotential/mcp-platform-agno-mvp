# agents/ — Progressive Disclosure Map

> Entry point for all agent code. Read this first, then drill into the specific
> file or subdirectory you need. Never load the whole directory into context at once.

## Directory Map

```
agents/
  README.md              <- YOU ARE THIS FILE. Navigation + topology overview.
  factory.py             <- Agent/team constructors (the "how to build" file).
  providers.py           <- Context providers, learning, MCP wiring (the "runtime plumbing" file).
  instructions.py        <- Agent role text, guardrails, behavioural prompts (the "what they say" file).
  document_digest.py     <- Gemini long-context specialist (conditional, GOOGLE_API_KEY).
  analysis_orchestrator.py  <- Platform Ops: analysis agent.
  dev_copilot.py         <- Builder: dev assistant agent.
  forensic_data_agent.py <- Builder: read-only data interface agent.
  ingestion_orchestrator.py  <- Platform Ops: ingestion agent.
  project_pal.py         <- Builder: project memory agent.
  review_gatekeeper.py   <- Platform Ops: human-approval interface agent.
  transcript_miner.py    <- Platform Ops: transcript parsing agent.
```

## Topology

```
Root Router (mode=route)
├── Platform Ops (mode=coordinate)
│   ├── ingestion_orchestrator   — ingests files through custody → parse → normalize → store
│   ├── analysis_orchestrator    — runs analysis on stored data; produces artifacts
│   └── review_gatekeeper       — translates technical actions into plain-English approval requests
├── Builder (mode=coordinate)
│   ├── dev_copilot              — proposes code, migrations, interface contracts
│   ├── project_pal              — maintains rolling memory of goals, blockers, decisions
│   └── forensic_data_agent     — read-only schema explanations and data queries
└── document_digest             — Gemini long-context specialist (optional, GOOGLE_API_KEY)
```

## How to Read This Directory

| You need to understand... | Read this |
|---|---|
| What agents exist and how they connect | This file (README.md) |
| How to construct an agent or team | `factory.py` |
| How runtime context is wired (DB, knowledge, learning, MCP) | `providers.py` |
| What an agent says (role, instructions, guardrails) | `instructions.py` |
| The Gemini document digest specialist | `document_digest.py` |

## Conventions

- **One file, one agent** (except `factory.py` and `providers.py` which are infrastructure).
- **Docstrings are authority** — agent roles, guardrails, and behaviours are documented in
  docstrings, not in external markdown. When docstring and behaviour conflict, fix the code.
- **Type hints everywhere** — `from __future__ import annotations` + full annotations.
- **Stable IDs** — `id=` on every Agent/Team is a public contract (UI/tests depend on it).
- **Instructions live in `instructions.py`** — factory functions reference them by key; do not
  inline multi-line instructions inside factory constructors.

## Adding a New Agent

1. Add the agent's role/guardrail text to `instructions.py` under a new constant.
2. Add a `build_<name>()` function in `factory.py`.
3. Register the agent in `build_agent_team()` inside `factory.py`.
4. If the agent needs custom tools or conditional wiring, add those in `providers.py`.
