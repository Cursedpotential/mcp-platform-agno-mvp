"""
server/temporal — Temporal durable-execution skeleton for the evidence pipelines.

STATUS: **INERT**. Nothing in the platform imports this package, and nothing
dispatches to it. It is the P1 skeleton described in
``docs/plans/TEMPORAL-INTEGRATION-PLAN-2026-08-23.md`` §P1: the chat-transcript
ingest expressed as one workflow over four Activities, so the shape can be
reviewed, replay-tested and benchmarked before any live traffic moves.

The live path stays exactly where it is — agno's ``Workflow.arun`` driven by
``server/evidence/workflows.py::run_chat_transcript`` (:940). The seam that
flips between the two ("a swap, not a shadow", plan §P1) is a single dispatch
switch inside ``run_chat_transcript`` and is deliberately NOT part of this
commit. Zero blast radius is the point: adding this package changes no
existing behavior, and ``requirements.txt`` (the production image lockfile) is
untouched — ``temporalio`` ships only as the optional ``temporal`` extra.

Ruled context (DECISION_LOG **D-067**, 2026-08-23):

- Persistence for the Temporal server itself lives in the existing PG18 on
  ``ovh-files`` as two databases — no second database server (ask 1 = A).
- The cutover is one live move, fix forward — no parallel stack (ask 2 = A).
- The workbench console is the approval surface; the reference project's own
  approval web-ui is discarded (ask 3 = yes, with the caveat that deploying the
  workbench is a P2 prerequisite).

Non-negotiables this package is written to respect (plan §1, §3):

- **Postgres stays authority.** Every Activity calls the EXISTING platform
  function — ``custody.py::ingest_artifact``, the ``parse.transcript`` registry
  chain, ``workflows.py::_store_step_impl``, ``workflows.py::_knowledge_step_impl``.
  Nothing here reimplements custody hashing, walk derivation, or projection
  authority. Temporal history is diagnostic telemetry, the same status
  ``run_report.py:154`` already assigns to traces.
- **Replay determinism.** ``workflows.py`` in this package imports only
  ``temporalio`` + stdlib + the dataclass types from ``activities``; every
  ``server.*`` import happens INSIDE an Activity body. The in-repo precedent is
  ``server/evidence/run_ledger.py:31`` (``db_url`` imported inside
  ``_get_engine()`` "to avoid import-time env coupling"); the counter-examples
  to keep out of workflow modules are ``server/core/url.py:27`` (module-level
  ``build_db_url()``) and ``server/core/session.py`` (module-level ``getenv``
  for SurrealDB/Weaviate/OpenRouter/NVIDIA).

Layout:

- ``activities.py`` — the four Activities (custody / parse / store / knowledge)
  plus their JSON-serializable dataclass params and results.
- ``workflows.py`` — ``ChatTranscriptIngest``: the four Activities in sequence,
  with declared RetryPolicies, per-stage timeouts, and the push-HITL gate
  (Signal + ``workflow.wait_condition``) that replaces the 2s poll loop at
  ``server/evidence/workflows.py:297-312``.
- ``knowledge_harness/`` — the framework bake: the knowledge step implemented
  twice behind one interface (Agno-as-library vs PydanticAI), both calling the
  same governed door. See ``knowledge_harness/BAKE.md`` for the scoring sheet
  and the rule that the loser is deleted, not kept.

Byline: Claude Code · Opus 5 · 2026-08-23
"""

from __future__ import annotations

__all__: list[str] = []
