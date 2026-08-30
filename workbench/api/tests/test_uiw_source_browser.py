"""Case Bible Sorted source-browser contract tests.

Byline: Codex · GPT-5 · 2026-08-29.
"""

from __future__ import annotations

from datetime import UTC, datetime
import io
import json

from app.repo import object_store_client
from app.service import uiw


def test_browser_lists_fixed_bucket_with_delimiter_pagination_and_filter(monkeypatch) -> None:
    captured = {}

    def fake_list(**kwargs):
        captured.update(kwargs)
        return {
            "IsTruncated": True,
            "NextContinuationToken": "opaque-next",
            "CommonPrefixes": [{"Prefix": "exports/messages/"}, {"Prefix": "exports/photos/"}],
            "Contents": [
                {
                    "Key": "exports/messages/thread.json",
                    "Size": 41,
                    "ETag": '"not-a-sha256"',
                    "LastModified": datetime(2026, 8, 29, tzinfo=UTC),
                },
                {"Key": "exports/photos/photo.jpg", "Size": 99},
            ],
        }

    monkeypatch.setattr(uiw, "list_casebible_sorted_objects", fake_list)
    result = uiw.browse_sources(
        prefix="exports/", continuation_token="opaque-current", filter_text="message", page_size=25
    )

    assert captured == {"prefix": "exports/", "continuation_token": "opaque-current", "max_keys": 25}
    assert result.source == "casebible-sorted"
    assert result.delimiter == "/"
    assert result.filter == "message" and result.filter_applied is True
    assert result.is_truncated is True and result.continuation_token == "opaque-next"
    assert [item.prefix for item in result.prefixes] == ["exports/messages/"]
    assert [item.key for item in result.objects] == ["exports/messages/thread.json"]
    assert not hasattr(result.objects[0], "sha256"), "remote listings must not claim an acquisition digest"


def test_object_store_client_never_accepts_a_bucket_from_the_browser(monkeypatch) -> None:
    class Client:
        def list_objects_v2(self, **kwargs):
            assert kwargs["Bucket"] == "casebible-sorted"
            assert kwargs["Delimiter"] == "/"
            return {"Contents": [], "CommonPrefixes": []}

    monkeypatch.setattr(object_store_client, "get_casebible_sorted_client", lambda: Client())
    object_store_client.list_casebible_sorted_objects(prefix="", max_keys=10)


def test_runtime_json_accessor_supplies_credentials_without_configurable_bucket(monkeypatch, tmp_path) -> None:
    secret_path = tmp_path / "casebible-r2.json"
    secret_path.write_text(
        json.dumps(
            {
                "endpoint_url": "https://example.r2.cloudflarestorage.com",
                "region": "auto",
                "access_key_id": "test-ak",
                "secret_access_key": "test-sk",
            }
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_client(service, **kwargs):
        captured.update(service=service, **kwargs)
        return object()

    monkeypatch.setattr(object_store_client, "get_casebible_r2_config_path", lambda: str(secret_path))
    monkeypatch.setattr(object_store_client.boto3, "client", fake_client)
    object_store_client.get_r2_client.cache_clear()
    object_store_client.get_r2_client()

    assert captured["service"] == "s3"
    assert captured["endpoint_url"] == "https://example.r2.cloudflarestorage.com"
    assert "bucket" not in captured
    object_store_client.get_r2_client.cache_clear()


def test_runtime_client_uses_fixed_source_and_staging_buckets(monkeypatch) -> None:
    calls = []

    class Client:
        def head_bucket(self, **kwargs):
            calls.append(("head", kwargs))

        def put_object(self, **kwargs):
            calls.append(("put", kwargs))

        def get_object(self, **kwargs):
            calls.append(("get", kwargs))
            return {"Body": io.BytesIO(b"source")}

        def head_object(self, **kwargs):
            calls.append(("exists", kwargs))

        def generate_presigned_url(self, operation, **kwargs):
            calls.append((operation, kwargs))
            return "https://example.invalid/object"

    client = Client()
    monkeypatch.setattr(object_store_client, "get_r2_client", lambda: client)
    monkeypatch.setattr(object_store_client, "get_client", lambda: client)

    assert object_store_client.check_connectivity() is True
    object_store_client.put_object("workbench/staging/sha/source.md", b"text")
    assert object_store_client.get_object("workbench/staging/sha/source.md") == b"source"
    assert object_store_client.object_exists("workbench/staging/sha/source.md") is True
    assert object_store_client.presigned_get("workbench/staging/sha/source.md")

    assert [call[1]["Bucket"] for call in calls[:2]] == ["casebible-sorted", "nexus"]
    assert calls[2][0] == "put"
    assert calls[2][1]["Bucket"] == "nexus"
    assert calls[3][1]["Bucket"] == "nexus"
    assert calls[4][1]["Bucket"] == "nexus"
    assert calls[5][1]["Params"]["Bucket"] == "nexus"


def test_browser_rejects_escape_prefix_before_object_store_call(monkeypatch) -> None:
    monkeypatch.setattr(
        uiw,
        "list_casebible_sorted_objects",
        lambda **_: (_ for _ in ()).throw(AssertionError("object store must not be called")),
    )
    try:
        uiw.browse_sources(prefix="../wrong-case/")
    except uiw.UIWError as error:
        assert error.status_code == 422
    else:
        raise AssertionError("escaping prefix accepted")
