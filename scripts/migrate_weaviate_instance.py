"""Clone and attest a complete Weaviate instance without mutating the source.

Exports every class schema, tenant, object UUID, property (including beacons),
vector/named vectors, vector weights, and source system timestamps. Replay is
create-only and two-pass: scalar objects first, then cross-references. Verify
exports the target into a new directory and compares deterministic manifests.

Weaviate creation/update timestamps are source-attested but cannot be assigned
through the object API; semantic reconciliation covers every replayable field.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

_PAGE_SIZE = 100
_BATCH_SIZE = 50
_PRIMITIVE_TYPES = {
    "blob",
    "boolean",
    "boolean[]",
    "date",
    "date[]",
    "geoCoordinates",
    "int",
    "int[]",
    "number",
    "number[]",
    "object",
    "object[]",
    "phoneNumber",
    "text",
    "text[]",
    "uuid",
    "uuid[]",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_canonical(value) + b"\n")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _chunks(values: list[dict[str, Any]], size: int = _BATCH_SIZE) -> Iterator[list[dict[str, Any]]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


class WeaviateApi:
    """Small REST client whose errors never include credentials."""

    def __init__(self, url: str, api_key: str = "") -> None:
        self.url = url.rstrip("/")
        self.headers = {"Accept": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        url = f"{self.url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        data = None if body is None else _canonical(body)
        headers = dict(self.headers)
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=180) as response:  # noqa: S310 - explicit operator URL
                payload = response.read()
        except HTTPError as exc:
            detail = exc.read(2_000).decode("utf-8", errors="replace")
            raise RuntimeError(f"Weaviate {method} {path} failed ({exc.code}): {detail}") from None
        except URLError as exc:
            raise RuntimeError(f"Weaviate {method} {path} unavailable: {exc.reason}") from None
        return json.loads(payload) if payload else None


def _reference_property_names(class_schema: dict[str, Any]) -> set[str]:
    names = set()
    for prop in class_schema.get("properties", []):
        types = prop.get("dataType") or []
        if any(data_type not in _PRIMITIVE_TYPES for data_type in types):
            names.add(str(prop["name"]))
    return names


def _semantic_object(obj: dict[str, Any]) -> dict[str, Any]:
    value = {
        key: obj[key]
        for key in ("class", "id", "properties", "tenant", "vector", "vectors", "vectorWeights")
        if key in obj
    }
    value.setdefault("properties", {})
    return value


def _system_metadata(obj: dict[str, Any]) -> dict[str, Any]:
    return {key: obj[key] for key in ("class", "id", "tenant", "creationTimeUnix", "lastUpdateTimeUnix") if key in obj}


def _object_pages(api: WeaviateApi, class_name: str, *, tenant: str | None = None) -> Iterator[list[dict[str, Any]]]:
    after = ""
    while True:
        params: dict[str, Any] = {
            "class": class_name,
            "limit": _PAGE_SIZE,
            "include": "vector",
        }
        if after:
            params["after"] = after
        if tenant is not None:
            params["tenant"] = tenant
        response = api.request("GET", "/v1/objects", params=params)
        objects = response.get("objects") if isinstance(response, dict) else None
        if not isinstance(objects, list):
            raise RuntimeError(f"invalid object page for {class_name}")
        if not objects:
            return
        yield objects
        next_after = str(objects[-1].get("id") or "")
        if not next_after or next_after == after:
            raise RuntimeError(f"object cursor did not advance for {class_name}")
        after = next_after
        if len(objects) < _PAGE_SIZE:
            return


def _tenants(api: WeaviateApi, class_schema: dict[str, Any]) -> list[dict[str, Any]]:
    if not (class_schema.get("multiTenancyConfig") or {}).get("enabled"):
        return []
    class_name = quote(str(class_schema["class"]), safe="")
    response = api.request("GET", f"/v1/schema/{class_name}/tenants", params={"limit": 10_000})
    tenants = response if isinstance(response, list) else response.get("tenants", [])
    if not isinstance(tenants, list):
        raise RuntimeError(f"invalid tenant response for {class_schema['class']}")
    return sorted(tenants, key=lambda tenant: str(tenant.get("name", "")))


def export_instance(api: WeaviateApi, output: Path) -> dict[str, Any]:
    """Create a source-preserving snapshot and deterministic manifest."""

    output.mkdir(parents=True, exist_ok=False)
    collections_dir = output / "collections"
    collections_dir.mkdir()
    schema = api.request("GET", "/v1/schema")
    classes = sorted(schema.get("classes", []), key=lambda item: str(item.get("class", "")))
    if len(classes) != len({item.get("class") for item in classes}):
        raise RuntimeError("source schema contains duplicate class names")
    aliases_response = api.request("GET", "/v1/aliases")
    aliases = sorted(aliases_response.get("aliases", []), key=lambda item: str(item.get("alias", "")))
    _write_json(output / "schema.json", {"classes": classes})
    _write_json(output / "aliases.json", {"aliases": aliases})

    collection_manifests = []
    for class_schema in classes:
        class_name = str(class_schema["class"])
        class_dir = collections_dir / class_name
        class_dir.mkdir()
        tenants = _tenants(api, class_schema)
        _write_json(class_dir / "schema.json", class_schema)
        _write_json(class_dir / "tenants.json", tenants)
        reference_names = _reference_property_names(class_schema)
        object_index: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []
        tenant_scopes: list[str | None] = [str(tenant["name"]) for tenant in tenants] if tenants else [None]
        objects_path = class_dir / "objects.ndjson"
        with objects_path.open("wb") as objects_file:
            for tenant_scope in tenant_scopes:
                for page in _object_pages(api, class_name, tenant=tenant_scope):
                    for obj in page:
                        if tenant_scope is not None:
                            obj.setdefault("tenant", tenant_scope)
                        semantic = _semantic_object(obj)
                        objects_file.write(_canonical(semantic) + b"\n")
                        properties = semantic.get("properties") or {}
                        for prop_name in reference_names:
                            for reference in properties.get(prop_name) or []:
                                if isinstance(reference, dict) and reference.get("beacon"):
                                    references.append(
                                        {
                                            "from": f"weaviate://localhost/{class_name}/{semantic['id']}/{prop_name}",
                                            "to": reference["beacon"],
                                            **({"tenant": semantic["tenant"]} if semantic.get("tenant") else {}),
                                        }
                                    )
                        object_index.append(
                            {
                                "id": str(semantic["id"]),
                                "tenant": semantic.get("tenant"),
                                "semantic_sha256": _digest(semantic),
                                "properties_sha256": _digest(semantic.get("properties", {})),
                                "has_vector": any(
                                    key in semantic and bool(semantic[key]) for key in ("vector", "vectors")
                                ),
                                "vector_sha256": _digest(
                                    {
                                        key: semantic[key]
                                        for key in ("vector", "vectors", "vectorWeights")
                                        if key in semantic
                                    }
                                ),
                                "source_system_metadata": _system_metadata(obj),
                            }
                        )

        object_index.sort(
            key=lambda item: (
                str(item.get("tenant") or ""),
                item["id"],
                _digest(item.get("source_system_metadata", {})),
            )
        )
        references.sort(key=_canonical)
        with (class_dir / "object_manifest.ndjson").open("wb") as index_file:
            for entry in object_index:
                index_file.write(_canonical(entry) + b"\n")
        with (class_dir / "references.ndjson").open("wb") as reference_file:
            for reference in references:
                reference_file.write(_canonical(reference) + b"\n")
        collection_manifest = {
            "class": class_name,
            "schema_sha256": _digest(class_schema),
            "tenant_count": len(tenants),
            "tenants_sha256": _digest(tenants),
            "object_count": len(object_index),
            "vector_count": sum(1 for row in object_index if row["has_vector"]),
            "semantic_objects_sha256": _digest(
                [{"tenant": row["tenant"], "id": row["id"], "sha256": row["semantic_sha256"]} for row in object_index]
            ),
            "vectors_sha256": _digest(
                [
                    {
                        "tenant": row["tenant"],
                        "id": row["id"],
                        "has_vector": row["has_vector"],
                        "sha256": row["vector_sha256"],
                    }
                    for row in object_index
                ]
            ),
            "source_system_metadata_sha256": _digest(
                [
                    {
                        "tenant": row["tenant"],
                        "id": row["id"],
                        "metadata": row["source_system_metadata"],
                    }
                    for row in object_index
                ]
            ),
            "reference_count": len(references),
            "references_sha256": _digest(references),
        }
        _write_json(class_dir / "manifest.json", collection_manifest)
        collection_manifests.append(collection_manifest)
        print(f"exported {class_name}: {len(object_index)} objects, {len(references)} references")

    manifest = {
        "format": "weaviate-complete-instance-v1",
        "aliases": aliases,
        "aliases_sha256": _digest(aliases),
        "collection_count": len(collection_manifests),
        "collections": collection_manifests,
    }
    _write_json(output / "manifest.json", manifest)
    _write_json(
        output / "attestation.json",
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source_url": api.url,
            "manifest_sha256": _digest(manifest),
        },
    )
    return manifest


def _load_ndjson(path: Path) -> list[dict[str, Any]]:
    values = []
    with path.open("r", encoding="utf-8") as source:
        for line_no, line in enumerate(source, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RuntimeError(f"{path}:{line_no} is not an object")
                values.append(value)
    return values


def _assert_batch_ok(response: Any, *, operation: str) -> None:
    if not isinstance(response, list):
        return
    failures = []
    for item in response:
        errors = ((item.get("result") or {}).get("errors") or {}).get("error") if isinstance(item, dict) else None
        if errors:
            failures.append({"id": item.get("id"), "errors": errors})
    if failures:
        raise RuntimeError(f"{operation} returned per-item failures: {failures[:5]}")


def replay_instance(api: WeaviateApi, snapshot: Path) -> None:
    """Replay a snapshot into an empty side-by-side target; never overwrite."""

    manifest = _read_json(snapshot / "manifest.json")
    if manifest.get("format") != "weaviate-complete-instance-v1":
        raise RuntimeError("unsupported snapshot format")
    source_schema = _read_json(snapshot / "schema.json")
    target_schema = api.request("GET", "/v1/schema")
    target_classes = {item.get("class") for item in target_schema.get("classes", [])}
    source_classes = {item.get("class") for item in source_schema.get("classes", [])}
    overlap = sorted(target_classes & source_classes)
    if overlap:
        raise RuntimeError(f"target already contains source classes; refusing overwrite: {overlap}")

    deferred_properties: dict[str, list[dict[str, Any]]] = {}
    for class_schema in source_schema.get("classes", []):
        class_name = str(class_schema["class"])
        reference_names = _reference_property_names(class_schema)
        base_schema = copy.deepcopy(class_schema)
        deferred_properties[class_name] = [
            prop for prop in base_schema.get("properties", []) if prop.get("name") in reference_names
        ]
        base_schema["properties"] = [
            prop for prop in base_schema.get("properties", []) if prop.get("name") not in reference_names
        ]
        api.request("POST", "/v1/schema", body=base_schema)
    for class_name, properties in deferred_properties.items():
        for prop in properties:
            api.request("POST", f"/v1/schema/{quote(class_name, safe='')}/properties", body=prop)

    for collection in manifest["collections"]:
        class_name = collection["class"]
        class_dir = snapshot / "collections" / class_name
        tenants = _read_json(class_dir / "tenants.json")
        if tenants:
            api.request("POST", f"/v1/schema/{quote(class_name, safe='')}/tenants", body=tenants)

    reference_names_by_class = {
        item["class"]: _reference_property_names(item) for item in source_schema.get("classes", [])
    }
    for collection in manifest["collections"]:
        class_name = collection["class"]
        objects = _load_ndjson(snapshot / "collections" / class_name / "objects.ndjson")
        reference_names = reference_names_by_class[class_name]
        for obj in objects:
            object_properties = dict(obj.get("properties") or {})
            for prop_name in reference_names:
                object_properties.pop(prop_name, None)
            obj["properties"] = object_properties
        for batch in _chunks(objects):
            response = api.request("POST", "/v1/batch/objects", body={"objects": batch})
            _assert_batch_ok(response, operation=f"object replay for {class_name}")
        print(f"replayed {class_name}: {len(objects)} objects")

    all_references: list[dict[str, Any]] = []
    for collection in manifest["collections"]:
        all_references.extend(_load_ndjson(snapshot / "collections" / collection["class"] / "references.ndjson"))
    for batch in _chunks(all_references):
        response = api.request("POST", "/v1/batch/references", body={"references": batch})
        _assert_batch_ok(response, operation="reference replay")

    for alias in manifest.get("aliases", []):
        api.request("POST", "/v1/aliases", body=alias)
    print(f"replay complete: {len(manifest['collections'])} collections, {len(all_references)} references")


def _reconciliation_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Drop source-only server timestamps, retaining every replayable field."""

    value = copy.deepcopy(manifest)
    for collection in value.get("collections", []):
        collection.pop("source_system_metadata_sha256", None)
    return value


def verify_instance(api: WeaviateApi, snapshot: Path, output: Path) -> None:
    """Export target independently and require exact semantic reconciliation."""

    expected = _read_json(snapshot / "manifest.json")
    actual = export_instance(api, output)
    expected_reconciliation = _reconciliation_manifest(expected)
    actual_reconciliation = _reconciliation_manifest(actual)
    if actual_reconciliation != expected_reconciliation:
        expected_by_class = {item["class"]: item for item in expected_reconciliation.get("collections", [])}
        actual_by_class = {item["class"]: item for item in actual_reconciliation.get("collections", [])}
        differing = sorted(
            name
            for name in set(expected_by_class) | set(actual_by_class)
            if expected_by_class.get(name) != actual_by_class.get(name)
        )
        raise RuntimeError(f"target reconciliation failed; differing collections: {differing}")
    print(f"RECONCILED semantic_manifest_sha256={_digest(actual_reconciliation)}")


def _api(args: argparse.Namespace) -> WeaviateApi:
    api_key = os.getenv(args.api_key_env, "") if args.api_key_env else ""
    return WeaviateApi(args.url, api_key)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "replay", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--url", required=True, help="Explicit source or target Weaviate HTTP URL")
        command.add_argument("--api-key-env", default="WEAVIATE_API_KEY")
        command.add_argument("--snapshot", type=Path)
        command.add_argument("--out", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "export":
            if args.out is None:
                raise ValueError("export requires --out")
            export_instance(_api(args), args.out)
        elif args.command == "replay":
            if args.snapshot is None:
                raise ValueError("replay requires --snapshot")
            replay_instance(_api(args), args.snapshot)
        else:
            if args.snapshot is None or args.out is None:
                raise ValueError("verify requires --snapshot and --out")
            verify_instance(_api(args), args.snapshot, args.out)
    except (RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
