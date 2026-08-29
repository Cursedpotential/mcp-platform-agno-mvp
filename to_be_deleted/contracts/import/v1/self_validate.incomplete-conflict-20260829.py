"""Self-validation for contracts/import/v1 — no new dependencies, no network.

Verifies, using only the `jsonschema` + `referencing` packages already pinned
in requirements.txt (both are transitive/direct deps of this repo already):

1. Every schemas/*.schema.json file is itself a structurally valid
   Draft 2020-12 schema.
2. Every $id is unique and every cross-file $ref resolves against an
   in-memory registry (no network fetch — resolution is by preloaded $id).
3. Every examples/*.example.json instance validates against its matching
   schema.
4. A handful of intentionally-broken instances are rejected, proving the
   conditional (if/then) rules actually bite.

Run: uv run python contracts/import/v1/self_validate.py
Exit code is 0 iff every check above passes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).parent
SCHEMAS_DIR = ROOT / "schemas"
EXAMPLES_DIR = ROOT / "examples"

# example filename stem -> schema filename stem
EXAMPLE_TO_SCHEMA = {
    "source-reference": "source-reference",
    "source-metadata": "source-metadata",
    "parser-capability": "parser-capability",
    "parser-request": "parser-request",
    "raw-record": "raw-record",
    "raw-extraction-bundle": "raw-extraction-bundle",
    "activity-receipt": "activity-receipt",
    "normalized-record": "normalized-record",
    "normalization-lineage": "normalization-lineage",
    "hash-receipt": "hash-receipt",
    "reconciliation-receipt": "reconciliation-receipt",
    "generation-manifest": "generation-manifest",
}


def load_schemas() -> dict[str, dict]:
    schemas = {}
    for path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        with path.open(encoding="utf-8") as f:
            schemas[path.name] = json.load(f)
    return schemas


def build_registry(schemas: dict[str, dict]) -> Registry:
    resources = []
    seen_ids: dict[str, str] = {}
    for filename, contents in schemas.items():
        schema_id = contents.get("$id")
        if not schema_id:
            raise AssertionError(f"{filename}: missing required top-level $id")
        if schema_id in seen_ids:
            raise AssertionError(f"$id collision: {filename} and {seen_ids[schema_id]} both declare {schema_id}")
        seen_ids[schema_id] = filename
        resources.append((schema_id, Resource.from_contents(contents, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


def check_meta_schema(schemas: dict[str, dict]) -> list[str]:
    failures = []
    for filename, contents in schemas.items():
        try:
            Draft202012Validator.check_schema(contents)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the sweep
            failures.append(f"{filename}: FAILED meta-schema check: {exc}")
    return failures


def validate_examples(schemas: dict[str, dict], registry: Registry) -> list[str]:
    failures = []
    example_paths = sorted(EXAMPLES_DIR.glob("*.example.json"))
    if len(example_paths) != len(EXAMPLE_TO_SCHEMA):
        failures.append(f"expected {len(EXAMPLE_TO_SCHEMA)} example files, found {len(example_paths)}")
    for path in example_paths:
        stem = path.name.removesuffix(".example.json")
        schema_filename = f"{EXAMPLE_TO_SCHEMA.get(stem, stem)}.schema.json"
        schema = schemas.get(schema_filename)
        if schema is None:
            failures.append(f"{path.name}: no matching schema {schema_filename}")
            continue
        with path.open(encoding="utf-8") as f:
            instance = json.load(f)
        validator = Draft202012Validator(schema, registry=registry)
        errors = sorted(validator.iter_errors(instance), key=str)
        if errors:
            failures.append(f"{path.name}: FAILED against {schema_filename}: {errors[0].message}")
    return failures


def validate_v1_legacy_hash_receipt(schemas: dict[str, dict], registry: Registry) -> list[str]:
    """Prove the vocabulary correction did not break persisted v1 decoding."""
    legacy = {
        "contract_version": "1.0.0",
        "hash_receipt_id": "hashrcpt_legacy_1",
        "activity_receipt_ref": "actr_legacy_1",
        "hash_kind": "h3_raw_generation",
        "algorithm": "sha256",
        "digest": "3b1f6c2a9e7d4c8a1b0f5e2d6c9a8b7e4f3d2c1a0b9e8d7c6f5a4b3c2d1e0f9a",
        "subject_ref": "rawgen_legacy_1",
        "construction": "h3-chain-platform-rawall-genesisempty-v1",
        "ordered_member_digests": [
            "3b1f6c2a9e7d4c8a1b0f5e2d6c9a8b7e4f3d2c1a0b9e8d7c6f5a4b3c2d1e0f9a"
        ],
        "computed_at": "2026-08-20T14:07:00Z",
        "computed_by": "hash_raw_generation_activity",
    }
    validator = Draft202012Validator(schemas["hash-receipt.schema.json"], registry=registry)
    errors = sorted(validator.iter_errors(legacy), key=str)
    if errors:
        return [f"legacy v1 hash receipt no longer decodes: {errors[0].message}"]
    return []


def negative_cases(schemas: dict[str, dict], registry: Registry) -> list[str]:
    """Each of these MUST fail validation; if one passes, the rule it targets is broken."""
    cases = [
        (
            "activity-receipt.schema.json",
            "failed status without an error object",
            {
                "contract_version": "1.0.0",
                "activity_name": "hash_source_activity",
                "workflow_id": "wf_1",
                "status": "failed",
                "attempt": 1,
                "started_at": "2026-08-20T14:03:30Z",
                "completed_at": "2026-08-20T14:03:31Z",
            },
        ),
        (
            "activity-receipt.schema.json",
            "success status without a compact result_ref",
            {
                "contract_version": "1.0.0",
                "activity_name": "hash_source_activity",
                "workflow_id": "wf_1",
                "status": "success",
                "attempt": 1,
                "started_at": "2026-08-20T14:03:30Z",
                "completed_at": "2026-08-20T14:03:31Z",
            },
        ),
        (
            "activity-receipt.schema.json",
            "not_applicable status carrying a usable result",
            {
                "contract_version": "1.0.0",
                "activity_name": "extract_embedded_metadata_activity",
                "workflow_id": "wf_1",
                "status": "not_applicable",
                "attempt": 1,
                "started_at": "2026-08-20T14:03:30Z",
                "completed_at": "2026-08-20T14:03:31Z",
                "result_ref": {"ref_kind": "metadata", "ref_id": "meta_1"},
                "not_applicable_reason": "source has no embedded metadata",
            },
        ),
        (
            "hash-receipt.schema.json",
            "context_raw_generation_fingerprint without construction/ordered_member_digests",
            {
                "contract_version": "1.0.0",
                "hash_receipt_id": "hashrcpt_1",
                "hash_kind": "context_raw_generation_fingerprint",
                "algorithm": "sha256",
                "digest": "3b1f6c2a9e7d4c8a1b0f5e2d6c9a8b7e4f3d2c1a0b9e8d7c6f5a4b3c2d1e0f9a",
                "subject_ref": "gen_1",
                "computed_at": "2026-08-20T14:07:00Z",
                "computed_by": "fingerprint_raw_generation_activity",
            },
        ),
        (
            "raw-record.schema.json",
            "malformed record_status without status_reason",
            {
                "record_ordinal": 0,
                "record_status": "malformed",
                "locator": {
                    "locator_type": "whole_object",
                    "object_ref": {"storage_class": "inline", "uri": "inline://x"},
                },
                "format_id": "sms_xml_backup",
            },
        ),
        (
            "raw-record.schema.json",
            "raw record carrying both a locator and stored bytes",
            {
                "record_ordinal": 0,
                "record_status": "parsed",
                "locator": {
                    "locator_type": "whole_object",
                    "object_ref": {"storage_class": "inline", "uri": "inline://x"},
                },
                "stored_bytes_b64": "eA==",
                "format_id": "sms_xml_backup",
            },
        ),
        (
            "generation-manifest.schema.json",
            "published status missing publication_ref",
            {
                "contract_version": "1.0.0",
                "generation_id": "gen_1",
                "generation_type": "normalized",
                "source_version_ref": "srcv_1",
                "member_ids": ["nrec_1"],
                "member_count": 1,
                "normalized_manifest_hash_receipt_ref": "hashrcpt_1",
                "status": "published",
                "sealed_at": "2026-08-20T14:07:30Z",
                "sealed_by": "seal_generation_activity",
                "published_at": "2026-08-20T14:07:35Z",
            },
        ),
        (
            "generation-manifest.schema.json",
            "sealed raw generation with a null H3 receipt",
            {
                "contract_version": "1.0.0",
                "generation_id": "rawgen_1",
                "generation_type": "raw",
                "source_version_ref": "srcv_1",
                "member_ids": ["raw_1"],
                "member_count": 1,
                "raw_h3_hash_receipt_ref": None,
                "reconciliation_receipt_refs": ["recon_1", "recon_2", "recon_3"],
                "status": "sealed",
                "sealed_at": "2026-08-20T14:07:30Z",
                "sealed_by": "seal_generation_activity",
            },
        ),
        (
            "raw-extraction-bundle.schema.json",
            "parser bundle with no raw rows or envelope span",
            {
                "contract_version": "1.0.0",
                "parser_id": "parser_1",
                "parser_version": "1.0.0",
                "source_version_ref": "srcv_1",
                "format_id": "unknown_binary",
                "records": [],
                "counts": {
                    "emitted": 0,
                    "rejected": 0,
                    "malformed": 0,
                    "unknown": 0,
                    "unparsed": 0,
                    "attachments": 0,
                },
            },
        ),
        (
            "hash-receipt.schema.json",
            "context raw-record fingerprint computed by the wrong Activity",
            {
                "contract_version": "1.0.0",
                "hash_receipt_id": "hashrcpt_1",
                "activity_receipt_ref": "actr_1",
                "hash_kind": "context_raw_record_fingerprint",
                "algorithm": "sha256",
                "digest": "3b1f6c2a9e7d4c8a1b0f5e2d6c9a8b7e4f3d2c1a0b9e8d7c6f5a4b3c2d1e0f9a",
                "subject_ref": "raw_1",
                "construction": "context-rawrecord-fingerprint-v1",
                "computed_at": "2026-08-20T14:07:00Z",
                "computed_by": "hash_source_activity",
            },
        ),
    ]
    failures = []
    for schema_filename, description, bad_instance in cases:
        schema = schemas[schema_filename]
        validator = Draft202012Validator(schema, registry=registry)
        try:
            validator.validate(bad_instance)
        except ValidationError:
            continue
        failures.append(f"{schema_filename}: negative case '{description}' incorrectly PASSED validation")
    return failures


def main() -> int:
    schemas = load_schemas()
    print(f"loaded {len(schemas)} schema files from {SCHEMAS_DIR}")

    meta_failures = check_meta_schema(schemas)
    registry = build_registry(schemas)
    example_failures = validate_examples(schemas, registry)
    compatibility_failures = validate_v1_legacy_hash_receipt(schemas, registry)
    negative_failures = negative_cases(schemas, registry)

    all_failures = meta_failures + example_failures + compatibility_failures + negative_failures
    if all_failures:
        print(f"\n{len(all_failures)} FAILURE(S):")
        for failure in all_failures:
            print(f"  - {failure}")
        return 1

    print(f"meta-schema OK: {len(schemas)}/{len(schemas)}")
    print(f"examples OK: {len(EXAMPLE_TO_SCHEMA)}/{len(EXAMPLE_TO_SCHEMA)}")
    print("legacy v1 hash receipt compatibility OK: 1/1")
    negative_case_count = 10
    print(f"negative cases correctly rejected: {negative_case_count}/{negative_case_count}")
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
