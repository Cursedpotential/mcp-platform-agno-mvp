"""Observed neutral-ingest proof against an explicitly disposable PostgreSQL target.

Run only with ``HORIZON_SCRATCH_LIVE=1`` and scratch DB/SBV environment
variables. The test refuses the canonical ``primary`` matter scope.

Byline: Codex · GPT-5 · 2026-08-16
Byline amendment: Codex · GPT-5 · 2026-08-18 (source/chunk read-model split)
"""

from __future__ import annotations

from os import getenv
from pathlib import Path

import pytest

from server.contracts.ingest import IngestLane, IngestRequest
from server.proffer.query import get_item, list_items
from server.proffer.service import ingest_file

pytestmark = pytest.mark.integration

_MATTER_ID = "swift-mvp-synthetic-20260816"
_SCRATCH_DATABASE = "horizon_scratch"
_SCRATCH_TARGET_UUID = "yrhzg9ksyr8sjko1yg44qvgc"
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "swift_mvp"


@pytest.mark.skipif(getenv("HORIZON_SCRATCH_LIVE") != "1", reason="scratch integration is opt-in")
def test_markdown_and_sbv_export_land_in_scratch_postgres() -> None:
    assert getenv("DB_DATABASE") == _SCRATCH_DATABASE
    assert getenv("HORIZON_SCRATCH_TARGET_UUID") == _SCRATCH_TARGET_UUID
    assert _MATTER_ID != "primary"

    markdown = ingest_file(
        IngestRequest(
            staged_path=str(_FIXTURES / "knowledge.md"),
            lane=IngestLane.platform,
            matter_id=_MATTER_ID,
            custody_tier="light",
            source_identity={"fixture": True, "purpose": "swift-mvp-integration"},
        )
    )
    sms = ingest_file(
        IngestRequest(
            staged_path=str(_FIXTURES / "sms.xml"),
            lane=IngestLane.evidence,
            message_corpus="first_party",
            source_principal="scratch-owner",
            caller_owns_conversation=True,
            matter_id=_MATTER_ID,
            coverage_hint="smsbackuprestore-xml",
            engine="auto",
            allow_fallback=False,
            custody_tier="full",
            source_identity={"fixture": True, "purpose": "swift-mvp-integration"},
        )
    )

    assert markdown.status == "completed"
    assert markdown.source_sha256 and markdown.parser_id and markdown.chunker_id
    assert sms.status == "completed"
    assert sms.parser_engine == "go"
    assert sms.parser_id == "sbv-go:smsbackuprestore-xml"
    assert sms.source_sha256 and sms.chunker_id

    items = list_items(matter_id=_MATTER_ID)
    artifact_ids = {item["artifact_id"] for item in items}
    assert markdown.artifact_id in artifact_ids
    assert sms.artifact_id in artifact_ids
    sms_item = get_item(str(sms.artifact_id), matter_id=_MATTER_ID)
    assert sms_item is not None
    assert sms_item["source_sha256"] == sms.source_sha256
    assert sms_item["records"][0]["attrs"]["parser_id"] == sms.parser_id
    markdown_item = get_item(str(markdown.artifact_id), matter_id=_MATTER_ID)
    assert markdown_item is not None
    assert markdown_item["source_sha256"] == markdown.source_sha256
    assert markdown.chunker_id == "chonkie.recursive@1.7.0:1500-chars"
    assert markdown_item["record_count"] == len(markdown_item["records"]) == markdown.record_count == 1
    assert markdown.chunk_count == markdown_item["chunk_count"] == len(markdown_item["chunks"]) > 1
    assert all(chunk["chunker_id"] == markdown.chunker_id for chunk in markdown_item["chunks"])
    assert [chunk["chunk_index"] for chunk in markdown_item["chunks"]] == list(range(markdown.chunk_count))
