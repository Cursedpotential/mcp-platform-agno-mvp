"""Static and pure-function coverage for complete Weaviate migration.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "migrate_weaviate_instance.py"


def _module():
    spec = importlib.util.spec_from_file_location("weaviate_migration", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_semantic_object_preserves_vectors_tenant_properties_and_weights() -> None:
    module = _module()
    value = module._semantic_object(
        {
            "class": "Example",
            "id": "00000000-0000-4000-8000-000000000001",
            "tenant": "tenant-a",
            "properties": {"ref": [{"beacon": "weaviate://localhost/Other/id"}]},
            "vector": [0.1, 0.2],
            "vectors": {"title": [0.3, 0.4]},
            "vectorWeights": {"title": 1},
            "creationTimeUnix": 1,
        }
    )
    assert set(value) == {"class", "id", "tenant", "properties", "vector", "vectors", "vectorWeights"}
    assert "creationTimeUnix" not in value


def test_reference_detection_distinguishes_weaviate_classes_from_types() -> None:
    module = _module()
    schema = {
        "properties": [
            {"name": "title", "dataType": ["text"]},
            {"name": "related", "dataType": ["OtherClass"]},
        ]
    }
    assert module._reference_property_names(schema) == {"related"}


def test_script_is_create_only_and_covers_complete_instance_contract() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'api.request("GET", "/v1/schema")' in source
    assert 'api.request("GET", "/v1/aliases")' in source
    assert '"include": "vector"' in source
    assert '"vector_count"' in source
    assert '"vectors_sha256"' in source
    assert "/tenants" in source
    assert 'api.request("POST", "/v1/batch/objects"' in source
    assert 'api.request("POST", "/v1/batch/references"' in source
    assert 'api.request("POST", "/v1/aliases"' in source
    assert 'api.request("DELETE"' not in source
    assert "refusing overwrite" in source


def test_export_enumerates_objects_inside_each_tenant_scope(tmp_path) -> None:
    module = _module()

    class FakeApi:
        url = "http://source.invalid"

        def __init__(self):
            self.object_tenants = []

        def request(self, method, path, *, params=None, body=None):
            assert method == "GET"
            if path == "/v1/schema":
                return {
                    "classes": [
                        {
                            "class": "TenantDocs",
                            "multiTenancyConfig": {"enabled": True},
                            "properties": [{"name": "text", "dataType": ["text"]}],
                        }
                    ]
                }
            if path == "/v1/aliases":
                return {"aliases": []}
            if path.endswith("/tenants"):
                return [
                    {"name": "alpha", "activityStatus": "HOT"},
                    {"name": "beta", "activityStatus": "COLD"},
                ]
            assert path == "/v1/objects"
            tenant = params["tenant"]
            self.object_tenants.append(tenant)
            return {
                "objects": [
                    {
                        "class": "TenantDocs",
                        "id": f"00000000-0000-4000-8000-00000000000{1 if tenant == 'alpha' else 2}",
                        "properties": {"text": tenant},
                        "vector": [0.1],
                    }
                ]
            }

    api = FakeApi()
    manifest = module.export_instance(api, tmp_path / "snapshot")
    assert api.object_tenants == ["alpha", "beta"]
    assert manifest["collections"][0]["tenant_count"] == 2
    assert manifest["collections"][0]["object_count"] == 2
    objects = module._load_ndjson(tmp_path / "snapshot" / "collections" / "TenantDocs" / "objects.ndjson")
    assert [(obj["tenant"], obj["properties"]["text"]) for obj in objects] == [
        ("alpha", "alpha"),
        ("beta", "beta"),
    ]
