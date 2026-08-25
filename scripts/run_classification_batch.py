"""Start ONE small ClassificationBatchPipeline run against Temporal (the go-live smoke).

Byline: Claude Code · Fable 5 · 2026-08-24

Usage (from the repo root, small batches ONLY — owner rule):
    uv run --no-sync python scripts/run_classification_batch.py            # 10 example messages
    uv run --no-sync python scripts/run_classification_batch.py --limit 5
    uv run --no-sync python scripts/run_classification_batch.py --supervised   # HITL gate ON

Pulls N rows from analysis.human_label (the NON-CANONICAL example set — safe test corpus),
starts the workflow on Temporal (100.91.190.107:7233, queue evidence-pipeline), waits, and
prints the result. Watch it live in the Temporal UI: http://100.91.190.107:8233
Results land as DRAFTS in analysis.chunk_classification (purge after review:
DELETE FROM analysis.chunk_classification WHERE run_key = '<printed run_key>').
"""
from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path


def _env() -> dict[str, str]:
    vals: dict[str, str] = {}
    for line in (Path(__file__).resolve().parent.parent / ".env").read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if m and not line.lstrip().startswith("#"):
            vals[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return vals


def fetch_examples(limit: int) -> list[dict]:
    import psycopg

    e = _env()
    dsn = (
        f"host=100.91.190.107 port={e['DB_PORT']} dbname={e['DB_DATABASE']} "
        f"user={e['DB_USER']} password={e['DB_PASS']} connect_timeout=20"
    )
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT conversation_key, seq, occurred_at, who, message_text
               FROM analysis.human_label
               WHERE length(message_text) > 20
               ORDER BY seq LIMIT %s""",
            (limit,),
        )
        return [
            {
                "conversation_key": r[0],
                "seq": r[1],
                "occurred_at": r[2].isoformat(),
                "who": r[3],
                "text": r[4],
                "record_ref": f"{r[0]}#{r[1]}",
            }
            for r in cur.fetchall()
        ]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--supervised", action="store_true",
                    help="pause on needs_review until a gate_decision Signal (default: off for smoke runs)")
    ap.add_argument("--version", default="clf-v0-smoke")
    args = ap.parse_args()
    if args.limit > 25:
        raise SystemExit("small batches only (owner rule) — limit must be <= 25")

    items = fetch_examples(args.limit)
    print(f"fetched {len(items)} example messages (analysis.human_label, non-canonical set)")

    from temporalio.client import Client

    from server.temporal.classification_workflow import ClassificationBatchInput

    run_key = f"smoke-{args.version}-{items[0]['seq']}-{items[-1]['seq']}-n{len(items)}"
    client = await Client.connect("100.91.190.107:7233", namespace="default")
    handle = await client.start_workflow(
        "ClassificationBatchPipeline",
        ClassificationBatchInput(
            batches=[items],
            classifier_version=args.version,
            run_key=run_key,
            supervised=args.supervised,
        ),
        id=f"classify-{run_key}",
        task_queue="evidence-pipeline",
    )
    print(f"workflow started: {handle.id}")
    print(f"watch: http://100.91.190.107:8233  ·  run_key = {run_key}")
    result = await handle.result()
    print("RESULT:", result)
    print(f"\nverify:  SELECT labels, sentiment, severity, judge_confidence, review_state, "
          f"left(message_text,60) FROM analysis.chunk_classification WHERE run_key = '{run_key}';")
    print(f"purge:   DELETE FROM analysis.chunk_classification WHERE run_key = '{run_key}';")


if __name__ == "__main__":
    asyncio.run(main())
