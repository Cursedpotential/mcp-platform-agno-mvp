"""server/temporal/n8n_activities.py — the generic n8n-webhook activity (Stage 5, D-068).

Byline: Claude Code · Fable 5 · 2026-08-24

THE WRAP IS THE ACTIVITY BOUNDARY (owner ruling 2026-08-24): each composed n8n workflow
(classify-batch, judge-gate, persist-results, …) is the BODY of exactly one Temporal
activity. This module provides that body-invoker: a single activity that POSTs a JSON
payload to an n8n webhook and returns the JSON response. Temporal owns sequence, retries,
and history; n8n owns integration logic; neither keeps the other's state.

Import rule (plan §4 risk 2): temporalio + stdlib at module level only; network deps
imported inside the activity body.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from temporalio import activity


@dataclass
class N8nCallParams:
    """One n8n activity-body invocation.

    webhook_path: path under the n8n base URL (e.g. "webhook/classify-batch").
    payload:      JSON body — MUST carry timestamps on records (temporal mandate)
                  and the run's idempotency key so re-delivery collapses.
    timeout_s:    per-call HTTP timeout; keep small — bodies are small batches by rule.
    """

    webhook_path: str
    payload: dict[str, Any] = field(default_factory=dict)
    timeout_s: float = 300.0


@dataclass
class N8nCallResult:
    status_code: int
    body: dict[str, Any] = field(default_factory=dict)


@activity.defn(name="n8n_webhook_activity")
def n8n_webhook_activity(params: N8nCallParams) -> N8nCallResult:
    """POST params.payload to {N8N_BASE_URL}/{webhook_path}; return parsed JSON.

    Raises on non-2xx / network error so Temporal's RetryPolicy governs retries —
    n8n has no durable retry of its own (it removed stalled-job recovery in 2.0),
    which is precisely why this call lives inside a Temporal activity.
    """
    import httpx  # runtime dep of the worker image; keep import out of module scope

    base = os.environ.get("N8N_BASE_URL", "https://n8n.mitechconsult.com").rstrip("/")
    url = f"{base}/{params.webhook_path.lstrip('/')}"
    headers = {}
    token = os.environ.get("N8N_WEBHOOK_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    activity.logger.info("n8n activity body -> %s", url)
    resp = httpx.post(url, json=params.payload, headers=headers, timeout=params.timeout_s)
    resp.raise_for_status()
    try:
        body = resp.json()
        if isinstance(body, list):  # n8n "last node" responses are often item arrays
            body = {"items": body}
    except ValueError:
        body = {"raw": resp.text}
    return N8nCallResult(status_code=resp.status_code, body=body)
