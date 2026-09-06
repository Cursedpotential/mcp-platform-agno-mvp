"""Restart-safe framework-neutral ingest recovery contracts.

Byline: Codex · GPT-5.6 · 2026-08-29
"""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import pytest

from server.contracts.ingest import IngestRequest
from server.proffer.service import (
    IngestRunAlreadyActive,
    PostgresReceiptJournal,
    _eligible_for_recovery,
    ingest_file,
    recover_incomplete_ingests,
)


NOW = datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)


def _run(path: Path, run_id: str = "run-1", **overrides: Any) -> dict[str, Any]:
    run = {
        "run_id": run_id,
        "workflow": "framework-neutral-ingest",
        "status": "running",
        "gate_state": None,
        "source_path": str(path),
        "source_context": {
            "source_identity": {"origin": "test"},
            "lane": "context",
            "classification_target": "context",
            "matter_id": "matter-1",
            "engine": "python",
            "allow_fallback": False,
        },
        "custody_tier": "light",
        "created_at": NOW - timedelta(hours=1),
        "updated_at": NOW - timedelta(hours=1),
        "stages": [
            {"seq": 1, "name": "custody", "status": "success", "finished_at": NOW - timedelta(hours=1)},
            {"seq": 2, "name": "parse", "status": "running", "started_at": NOW - timedelta(hours=1)},
            {"seq": 3, "name": "store", "status": "pending"},
            {"seq": 4, "name": "projection", "status": "pending"},
        ],
    }
    run.update(overrides)
    return run


def test_recovery_eligibility_is_stale_running_only(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("evidence", encoding="utf-8")
    base = _run(source)

    assert _eligible_for_recovery(base, now=NOW, min_age=timedelta(minutes=15))
    assert not _eligible_for_recovery({**base, "status": "paused"}, now=NOW, min_age=timedelta())
    assert not _eligible_for_recovery({**base, "status": "completed"}, now=NOW, min_age=timedelta())
    assert not _eligible_for_recovery({**base, "gate_state": "waiting"}, now=NOW, min_age=timedelta())
    assert not _eligible_for_recovery(
        {
            **base,
            "updated_at": NOW - timedelta(minutes=2),
            "stages": base["stages"][:1]
            + [
                {"seq": 2, "name": "parse", "status": "running", "started_at": NOW - timedelta(minutes=2)},
                *base["stages"][2:],
            ],
        },
        now=NOW,
        min_age=timedelta(minutes=15),
    )
    assert not _eligible_for_recovery(
        {**base, "stages": [*base["stages"][:1], {"seq": 2, "name": "parse", "status": "failed"}, *base["stages"][2:]]},
        now=NOW,
        min_age=timedelta(),
    )


def test_recovery_replays_exact_request_fields(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    run = _run(source)
    run["source_context"].update({"coverage_hint": "messages_transcript", "caller_owns_conversation": False})
    captured: list[tuple[IngestRequest, str]] = []

    def execute(payload: IngestRequest, **kwargs: Any) -> object:
        captured.append((payload, kwargs["receipt_id"]))
        return object()

    recovered = asyncio.run(
        recover_incomplete_ingests(
            min_age=timedelta(minutes=15),
            list_runs_fn=lambda **_kwargs: [run],
            get_run_fn=lambda _run_id: run,
            ingest_fn=execute,  # type: ignore[arg-type]
            journal_factory=lambda: object(),  # type: ignore[arg-type]
            now=NOW,
        )
    )

    assert recovered == 1
    payload, receipt_id = captured[0]
    assert receipt_id == "run-1"
    assert payload.matter_id == "matter-1"
    assert payload.lane.value == "context"
    assert payload.engine == "python"
    assert payload.coverage_hint == "messages_transcript"
    assert payload.source_identity == {"origin": "test"}


def test_recovery_bounds_concurrency_and_isolates_failures(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    runs = [_run(source, f"run-{index}") for index in range(4)]
    active = 0
    maximum = 0
    lock = threading.Lock()

    def execute(_payload: IngestRequest, **kwargs: Any) -> object:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            time.sleep(0.03)
            if kwargs["receipt_id"] == "run-2":
                raise RuntimeError("isolated failure")
            return object()
        finally:
            with lock:
                active -= 1

    by_id = {run["run_id"]: run for run in runs}
    recovered = asyncio.run(
        recover_incomplete_ingests(
            concurrency=2,
            min_age=timedelta(),
            list_runs_fn=lambda **_kwargs: runs,
            get_run_fn=by_id.get,
            ingest_fn=execute,  # type: ignore[arg-type]
            journal_factory=lambda: object(),  # type: ignore[arg-type]
            now=NOW,
        )
    )

    assert recovered == 3
    assert maximum == 2


def test_recovery_treats_existing_owner_as_not_recovered(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    run = _run(source)

    def execute(_payload: IngestRequest, **_kwargs: Any) -> object:
        raise IngestRunAlreadyActive("owned")

    recovered = asyncio.run(
        recover_incomplete_ingests(
            min_age=timedelta(),
            list_runs_fn=lambda **_kwargs: [run],
            get_run_fn=lambda _run_id: run,
            ingest_fn=execute,  # type: ignore[arg-type]
            journal_factory=lambda: object(),  # type: ignore[arg-type]
            now=NOW,
        )
    )
    assert recovered == 0


def test_missing_durable_source_is_terminalized(tmp_path: Path) -> None:
    run = _run(tmp_path / "missing.txt")
    marked: list[tuple[dict[str, Any], str]] = []

    recovered = asyncio.run(
        recover_incomplete_ingests(
            min_age=timedelta(),
            list_runs_fn=lambda **_kwargs: [run],
            get_run_fn=lambda _run_id: run,
            ingest_fn=lambda *_args, **_kwargs: object(),  # type: ignore[arg-type]
            journal_factory=lambda: object(),  # type: ignore[arg-type]
            mark_unrecoverable_fn=lambda row, detail: marked.append((row, detail)),
            now=NOW,
        )
    )

    assert recovered == 0
    assert marked and marked[0][0] is run
    assert "cannot replay source" in marked[0][1]


def test_ingest_guard_prevents_pipeline_execution(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    custody_called = False

    class LockedJournal:
        def start(self, _request: IngestRequest, _path: Path) -> str:
            return "run-locked"

        @contextmanager
        def run_guard(self, _receipt_id: str) -> Iterator[bool]:
            yield False

        def finish(self, _receipt: object, error: str | None = None) -> None:
            del error

    def custody(*_args: Any, **_kwargs: Any) -> object:
        nonlocal custody_called
        custody_called = True
        return object()

    with pytest.raises(IngestRunAlreadyActive, match="run-locked"):
        ingest_file(IngestRequest(staged_path=str(source)), journal=LockedJournal(), custody=custody)
    assert not custody_called


def test_journal_persists_every_replay_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    captured: dict[str, Any] = {}

    def create_run(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "run-1"

    monkeypatch.setattr("server.evidence.run_ledger.create_run", create_run)
    monkeypatch.setattr("server.evidence.run_ledger.seed_stages", lambda *_args: None)
    request = IngestRequest(
        staged_path=str(source),
        source_identity={"origin": "upload"},
        coverage_hint="messages_transcript",
        matter_id="matter-9",
        engine="python",
        allow_fallback=False,
    )

    assert PostgresReceiptJournal().start(request, source) == "run-1"
    context = captured["source_context"]
    assert context["matter_id"] == "matter-9"
    assert context["lane"] == "context"
    assert context["coverage_hint"] == "messages_transcript"
    assert context["engine"] == "python"
    assert context["classification_target"] == "context"


@pytest.mark.parametrize("concurrency", [0, 9])
def test_recovery_rejects_unbounded_concurrency(concurrency: int) -> None:
    with pytest.raises(ValueError, match="concurrency"):
        asyncio.run(recover_incomplete_ingests(concurrency=concurrency))
