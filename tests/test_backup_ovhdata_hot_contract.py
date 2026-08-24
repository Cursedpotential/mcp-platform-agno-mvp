"""Static restore-contract coverage for the operational hot-backup script.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import re
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "backup_ovhdata_hot.sh"


def test_weaviate_backup_exports_typed_schema_and_arbitrary_raw_objects() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert '"$WEAVIATE_URL/v1/schema"' in source
    assert '"$WEAVIATE_URL/v1/objects"' in source
    assert '--data-urlencode "include=vector"' in source
    assert '--data-urlencode "after=$after"' in source
    assert "'.classes[].class'" in source
    assert "'.objects[]'" in source
    assert "${WEAVIATE_URL:?Set WEAVIATE_URL to the explicit current Weaviate target}" in source
    assert "${WEAVIATE_CURRENT_TARGET:?Set WEAVIATE_CURRENT_TARGET" in source
    assert '"$WEAVIATE_URL/v1/aliases"' in source
    assert ".alias == $alias and .class == $target" in source
    assert 'WEAVIATE_API_KEY="${WEAVIATE_API_KEY:-}"' in source
    assert "Authorization: Bearer $WEAVIATE_API_KEY" in source
    assert "weaviate_restore_inventory.tsv" in source
    assert 'has("properties") and has("vector")' in source
    assert "restore-reconciled" in source

    # Regression: the former GraphQL selection exported only Agno-shaped
    # fields and silently omitted every property in a custom typed collection.
    assert "/v1/graphql" not in source
    assert "${CLS}(limit:10000){name content meta_data" not in source


def test_backup_script_contains_no_permanent_delete_command() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*rm(?:\s|$)", source) is None
