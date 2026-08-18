"""Static lifecycle wiring contract for the native evidence drain worker.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

from pathlib import Path


MAIN = Path(__file__).parents[1] / "server" / "api" / "main.py"


def test_main_starts_worker_and_awaits_stop_before_runtime_close() -> None:
    source = MAIN.read_text(encoding="utf-8")

    start = source.index("asyncio.create_task(")
    stop = source.index("_native_evidence_stop.set()")
    awaited = source.index("await _native_evidence_task")
    closed = source.index("_native_evidence_runtime.close()")

    assert start < stop < awaited < closed
    assert 'name="native-evidence-projection-drain"' in source
    assert "run_native_projection_worker(" in source
    assert 'getenv("NATIVE_EVIDENCE_DRAIN_BATCH_LIMIT", "100")' in source
