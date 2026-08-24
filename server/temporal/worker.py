"""server/temporal/worker.py — the Temporal worker entrypoint (P1 task 1).

Byline: Claude Code · Fable 5 · 2026-08-24

Runs as its OWN Coolify app (docker/temporal-worker/Dockerfile, CMD
``python -m server.temporal.worker``). Joins task queue ``evidence-pipeline``
and registers:

  workflows:  ChatTranscriptIngest (P1), P0DurabilityProbe (the P0 exit test)
  activities: custody_activity, parse_activity, store_activity (sync — run in
              a thread pool), knowledge_activity (async)

Env:
  TEMPORAL_ADDRESS    frontend address (default temporal-server:7233 on the
                      shared `agno` network; the deployed app overrides with
                      the tailnet address 100.91.190.107:7233)
  TEMPORAL_NAMESPACE  default: "default"
  TEMPORAL_TASK_QUEUE default: "evidence-pipeline"
  TEMPORAL_ACTIVITY_THREADS  sync-activity pool size, default 8
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from server.temporal.activities import (
    custody_activity,
    knowledge_activity,
    parse_activity,
    store_activity,
)
from server.temporal.workflows import ChatTranscriptIngest, P0DurabilityProbe

log = logging.getLogger("temporal.worker")

TASK_QUEUE_DEFAULT = "evidence-pipeline"


async def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    address = os.environ.get("TEMPORAL_ADDRESS", "temporal-server:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", TASK_QUEUE_DEFAULT)
    threads = int(os.environ.get("TEMPORAL_ACTIVITY_THREADS", "8"))

    log.info("connecting to Temporal at %s (namespace=%s)", address, namespace)
    client = await Client.connect(address, namespace=namespace)
    log.info("connected; joining task queue %r (%d activity threads)", task_queue, threads)

    with ThreadPoolExecutor(max_workers=threads) as executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[ChatTranscriptIngest, P0DurabilityProbe],
            activities=[custody_activity, parse_activity, store_activity, knowledge_activity],
            activity_executor=executor,
        )
        log.info("worker running — workflows: ChatTranscriptIngest, P0DurabilityProbe")
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
