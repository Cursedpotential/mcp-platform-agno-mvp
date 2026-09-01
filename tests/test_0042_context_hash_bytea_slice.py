"""Filesystem checks pinning migration 0042 and the guard/Go inline-slice repair."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0036 = ROOT / "sql" / "0036_context_import_foundation.sql"
MIGRATION_0042 = ROOT / "sql" / "0042_context_hash_bytea_slice.sql"
HASH_REPOSITORY = ROOT / "modules" / "engine" / "postgres" / "hash_repository.go"
VALIDATE_0042 = ROOT / "scripts" / "validate_0042_live.py"
APPLY_0042 = ROOT / "scripts" / "apply_0042_live.py"

ORIGINAL_BIGINT_ARM = "FROM raw.byte_offset + 1 FOR raw.byte_length"
FORBIDDEN_RAW_FORM = "FROM raw.byte_offset + 1 FOR raw.byte_length"
SAFE_INLINE_MARKERS = (
    "(raw.byte_offset + 1)::int4",
    "raw.byte_length::int4",
    "raw.byte_offset >= 0",
    "raw.byte_offset <= 2147483646",
    "raw.byte_length >= 0",
    "raw.byte_length <= 2147483647",
    "raw.byte_offset + raw.byte_length <= locator_object.byte_length",
    "octet_length(locator_object.inline_bytes)",
)
BEHAVIOR_MARKERS = (
    "hash_source_activity",
    "hash_raw_records_activity",
    "hash_raw_generation_activity",
    "hash_normalized_records_activity",
    "hash_normalized_generation_activity",
    "hash receipt requires successful same-source % receipt",
    "H1 receipt must equal the retained original content_sha256",
    "raw H2 receipt does not match DB-resident stored bytes or inline byte range",
    "normalized record digest must hash its exact canonical_bytes and canonicalization",
    "generation hash receipt requires its matching open manifest",
    "context.assert_hash_manifest_complete",
    "RETURN NEW;",
)


def test_applied_0036_still_contains_original_bigint_inline_arm() -> None:
    source = MIGRATION_0036.read_text(encoding="utf-8")
    assert ORIGINAL_BIGINT_ARM in source, "applied migration 0036 must remain byte-identical"


def test_0042_redefines_guard_forward_only_with_safe_int4_slice() -> None:
    source = MIGRATION_0042.read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION context.guard_hash_receipt_insert" in source
    for marker in SAFE_INLINE_MARKERS:
        assert marker in source, f"0042 is missing the safe inline-slice marker {marker!r}"


def test_0042_omits_raw_bigint_substring_form() -> None:
    source = MIGRATION_0042.read_text(encoding="utf-8")
    assert FORBIDDEN_RAW_FORM not in source, "0042 must not re-introduce the raw bigint substring form"


def test_0042_is_platform_guarded_and_transactional() -> None:
    source = MIGRATION_0042.read_text(encoding="utf-8")
    for marker in (
        "migration 0042 may run only in database platform",
        "BEGIN;",
        "COMMIT;",
        "SET LOCAL ROLE context_owner;",
        "to_regprocedure('context.guard_hash_receipt_insert()')",
        "hash_receipt_insert_gate",
    ):
        assert marker in source, f"0042 is missing the platform-guard marker {marker!r}"


def test_0042_preserves_every_0036_behavior_marker() -> None:
    source = MIGRATION_0042.read_text(encoding="utf-8")
    for marker in BEHAVIOR_MARKERS:
        assert marker in source, f"0042 dropped preserved 0036 behavior marker {marker!r}"


def test_go_repository_queries_safe_int4_inline_slice() -> None:
    source = HASH_REPOSITORY.read_text(encoding="utf-8")
    for marker in ("(raw.byte_offset + 1)::int4", "raw.byte_length::int4"):
        assert marker in source, f"hash_repository.go is missing the safe integer form {marker!r}"
    assert FORBIDDEN_RAW_FORM not in source, "hash_repository.go still uses the bigint substring form"


def test_validate_0042_is_rollback_only_and_shares_helpers() -> None:
    source = VALIDATE_0042.read_text(encoding="utf-8")
    assert "from validate_0037_live import" in source
    assert re.search(r"conn\.commit\s*\(", source) is None, "rollback validator must not commit"


def test_apply_0042_requires_explicit_apply_gate() -> None:
    source = APPLY_0042.read_text(encoding="utf-8")
    assert "refusing to run without explicit --apply" in source
    assert "from validate_0037_live import" in source
    assert "from validate_0042_live import" in source


def test_live_scripts_pin_0042_advisory_lock_names() -> None:
    validate_source = VALIDATE_0042.read_text(encoding="utf-8")
    apply_source = APPLY_0042.read_text(encoding="utf-8")
    assert "validate-0042-context-hash-bytea-slice" in validate_source
    assert "apply-0042-context-hash-bytea-slice" in apply_source
