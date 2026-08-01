"""server/core/knowledge_handle.py — C3 spine boot resilience (operator-console-
requirements.md addendum 9's boot-time follow-through: the requirements doc
itself only goes to addendum 6 as of this task's kickoff — this addendum-9
label is the task brief's shorthand for "make agentos-api survive Milvus being
down at boot", which is real and unaddressed; see this module's own docstring
tail + the C3 task report for the full provenance note).

THE PROBLEM (verified from agno source, not assumed; investigated against
Milvus, but the mechanism is store-agnostic and applies unchanged to the
Weaviate store that replaced it — ADR-0040 cutover 2026-07-29):
``server/core/session.py``'s ``create_knowledge()`` builds a vector-db
instance (now ``agno.vectordb.weaviate.Weaviate``) whose
``__init__`` does NOT touch the network (lazy client) — but
``agno.knowledge.knowledge.Knowledge`` (a ``@dataclass``) has:

    def __post_init__(self):
        ...
        if self.vector_db and not self.vector_db.exists():
            self.vector_db.create()

``__post_init__`` runs SYNCHRONOUSLY inside the dataclass constructor, i.e. at
the exact line ``create_knowledge("platform", "platform_knowledge")`` executes
in ``server/api/main.py::_build_app()``. ``Milvus.exists()`` issues a real
``has_collection`` RPC. When Milvus is unreachable, that RPC raises, the
exception propagates out of ``Knowledge(...)``, out of ``create_knowledge()``,
out of ``_build_app()`` — the WHOLE agentos-api process fails to boot. A
transient Milvus outage (a redeploy race, `data-vector` restarting) takes down
runs/records/evidence too, even though none of those actually touch Milvus.

THE FIX: ``KnowledgeHandle`` wraps the ``create_knowledge`` factory. ``main.py``
calls ``try_connect_now()`` ONCE at boot inside a try/except (never lets the
exception escape) instead of calling ``create_knowledge()`` directly. On
failure it logs loudly and leaves ``.instance`` at ``None``; the caller starts
``start_background_retry()`` from the AgentOS lifespan, which retries the same
factory every 60s (bounded jitter-free — this is an operator-visible infra
outage, not a request the operator is waiting on) until it succeeds, then
swaps ``.instance`` in place and stops retrying.

WHAT STILL BREAKS (the documented, accepted limitation — this is the escape
hatch the task brief explicitly allows: "boot continues with knowledge=None +
background reconnect that swaps the handle... document exactly what still
breaks"): AgentOS's own agent/team wiring (``server/api/main.py``'s
``build_context``/``build_agent_team``/``AgentOS(knowledge=[...])``) reads
``knowledge_handle.instance`` ONCE, at boot, to build the agent team and the
native AgentOS knowledge routes. If Milvus was down at that moment, every
agent's knowledge-search tool and AgentOS's own built-in ``/knowledge*``
routes run with NO knowledge base for the lifetime of that process — a later
successful background reconnect does NOT retroactively rewire already-built
agents/AgentOS internals (that would require calling AgentOS's own
``_resync``-family internals, which this task deliberately does NOT attempt —
too invasive for what's asked; a process restart picks up a live Milvus like
normal). What DOES benefit from the live swap: every route THIS module's
caller registers by holding the handle itself (not a snapshotted instance) —
``server/api/run_routes.py`` and ``server/api/evidence_routes.py`` resolve
``knowledge_handle.instance`` fresh on every request via ``resolve_knowledge()``
below, so a run started after Milvus recovers sees the real knowledge engine
even though the process never restarted. ``server/api/main.py``'s
``/v1/knowledge/reindex`` route (knowledge-REQUIRED, addendum 9's own "503
until ready" contract) also resolves fresh and 503s with
``{"detail": "knowledge store unavailable"}`` while ``.ready`` is False.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-22
# Byline: Claude Code · Fable 5 · 2026-07-31 (Milvus→Weaviate doc-drift cleanup (ADR-0040))

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger("evidence.runs")

DEFAULT_RETRY_INTERVAL_S = 60.0


class KnowledgeHandle:
    """Mutable holder for a lazily-(re)connected Knowledge instance.

    ``factory`` is called with no arguments and must return a ready-to-use
    Knowledge instance (or raise). It is called once synchronously at
    ``try_connect_now()`` and, on failure, repeatedly from the background
    retry loop — same factory both times, so a transient failure at boot and
    a later recovery go through identical code.
    """

    def __init__(self, factory: Callable[[], Any], *, retry_interval_s: float = DEFAULT_RETRY_INTERVAL_S) -> None:
        self._factory = factory
        self._retry_interval_s = retry_interval_s
        self._instance: Any = None
        self._retry_task: "asyncio.Task[None] | None" = None
        self.last_error: str | None = None
        self.attempts: int = 0

    @property
    def instance(self) -> Any:
        """The live Knowledge instance, or None if never connected yet."""
        return self._instance

    @property
    def ready(self) -> bool:
        return self._instance is not None

    def try_connect_now(self) -> bool:
        """Synchronous, single attempt. NEVER raises — logs loudly and
        returns False on failure so the caller (``main.py``'s ``_build_app``)
        can boot with ``knowledge=None`` instead of crashing the process.
        Returns True (idempotently) if already connected."""
        if self._instance is not None:
            return True
        self.attempts += 1
        try:
            self._instance = self._factory()
        except Exception as exc:  # noqa: BLE001 - deliberately broad: ANY factory failure must not crash boot
            self.last_error = str(exc)[:500]
            logger.error(
                "KnowledgeHandle: connect attempt %s FAILED (%s) — booting with knowledge unavailable; "
                "background retry will keep trying every %ss",
                self.attempts,
                self.last_error,
                self._retry_interval_s,
            )
            return False
        self.last_error = None
        logger.info("KnowledgeHandle: connected on attempt %s", self.attempts)
        return True

    async def _retry_loop(self) -> None:
        while self._instance is None:
            await asyncio.sleep(self._retry_interval_s)
            logger.info("KnowledgeHandle: retrying connect (attempt %s)...", self.attempts + 1)
            if self.try_connect_now():
                logger.info("KnowledgeHandle: knowledge store now READY (background reconnect succeeded)")
                return

    def start_background_retry(self) -> None:
        """Idempotent: a no-op if already connected or a retry loop is
        already running. Call from an async context (the AgentOS lifespan)
        AFTER an initial ``try_connect_now()`` returned False."""
        if self._instance is not None:
            return
        if self._retry_task is not None and not self._retry_task.done():
            return
        self._retry_task = asyncio.create_task(self._retry_loop())

    def stop_background_retry(self) -> None:
        """Cancel the retry loop (used at shutdown so the lifespan's
        teardown doesn't leak a live asyncio.Task)."""
        if self._retry_task is not None and not self._retry_task.done():
            self._retry_task.cancel()


def resolve_knowledge(knowledge: Any) -> Any:
    """Normalize a route's ``knowledge`` parameter to a concrete Knowledge
    instance (or None): if it's a ``KnowledgeHandle``, read ``.instance``
    FRESH (this is what makes the live-swap visible to a request handled
    after a successful background reconnect); anything else (a raw Knowledge
    instance, or literally None — both are what every pre-C3 test/caller
    already passes) is returned unchanged, so this is a strict backward-
    compatible superset, not a breaking signature change."""
    if isinstance(knowledge, KnowledgeHandle):
        return knowledge.instance
    return knowledge
