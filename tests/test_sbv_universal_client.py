"""Focused contract tests for the import-scoped SBV Python cutover."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from server.tools._sbv_client import SBVClient, SBVError
from server.tools.parsers.messaging.sbv_sms import _validate_universal_import


class _Response:
    status = 201

    def read(self, *_args):
        return b'{"import_id": 42}'

    def getheaders(self):
        return [("Content-Type", "application/json")]


class _Connection:
    instances: ClassVar[list[_Connection]] = []

    def __init__(self, *_args, **_kwargs):
        self.sent: list[bytes] = []
        self.request_target = ""
        self.__class__.instances.append(self)

    def putrequest(self, _method, target):
        self.request_target = target

    def putheader(self, *_args):
        return None

    def endheaders(self):
        return None

    def send(self, data):
        self.sent.append(bytes(data))

    def getresponse(self):
        return _Response()

    def close(self):
        return None


def test_universal_upload_streams_chunks_without_read_bytes(monkeypatch, tmp_path: Path):
    source = tmp_path / "large.xml"
    source.write_bytes(b"<smses>" + (b"x" * (2 * 1024 * 1024)) + b"</smses>")
    _Connection.instances.clear()
    monkeypatch.setattr("server.tools._sbv_client.http.client.HTTPConnection", _Connection)
    client = SBVClient(base_url="http://sbv", password="secret")
    client._session_id = "sid"

    result = client.import_file(str(source), format="smsbackuprestore-xml")

    assert result["import_id"] == 42
    sent = b"".join(_Connection.instances[0].sent)
    assert b'Content-Disposition: form-data; name="file"' in sent
    assert b"<smses>" in sent and b"</smses>" in sent
    assert len(_Connection.instances[0].sent) >= 4  # prefix, 1+ bounded file chunks, suffix


def test_import_records_and_rejections_paginate_by_id(monkeypatch):
    calls: list[tuple[str, str, dict[str, Any]]] = []
    client = SBVClient(base_url="http://sbv", password="secret")

    def fake_request(method, path, *, params=None, **_kwargs):
        calls.append((method, path, params or {}))
        offset = (params or {}).get("offset", 0)
        if path.endswith("/records"):
            rows = [{"import_id": 7, "seq": offset, "record_hash": str(offset)}] if offset == 0 else []
            return 200, json.dumps({"total": 1, "records": rows}).encode(), {}
        rows = [{"import_id": 7, "seq": 1, "reason": "bad"}] if offset == 0 else []
        return 200, json.dumps({"total": 1, "rejections": rows}).encode(), {}

    monkeypatch.setattr(client, "_request", fake_request)
    assert client.import_records(7, page=2)[0]["import_id"] == 7
    assert client.import_rejections(7, page=2)[0]["reason"] == "bad"
    assert all("/imports/7/" in path for _, path, _ in calls)
    assert not any("latest" in path for _, path, _ in calls)


def test_wait_for_import_polls_explicit_id_until_completed(monkeypatch):
    client = SBVClient(base_url="http://sbv", password="secret")
    details = iter(
        [
            {"import_id": 7, "status": "processing"},
            {"import_id": 7, "status": "completed", "record_count": 1},
        ]
    )
    calls: list[int] = []

    def fake_detail(import_id):
        calls.append(import_id)
        return next(details)

    monkeypatch.setattr(client, "import_detail", fake_detail)
    result = client.wait_for_import(7, poll_s=0, timeout_s=1)

    assert result["status"] == "completed"
    assert calls == [7, 7]


def test_wait_for_import_surfaces_terminal_error(monkeypatch):
    client = SBVClient(base_url="http://sbv", password="secret")
    monkeypatch.setattr(
        client,
        "import_detail",
        lambda import_id: {"import_id": import_id, "status": "error", "error": "decoder failed"},
    )

    with pytest.raises(SBVError, match="decoder failed"):
        client.wait_for_import(7, poll_s=0, timeout_s=1)


def test_universal_validation_rejects_h1_or_h3_mismatch(tmp_path: Path):
    source = tmp_path / "source.xml"
    source.write_bytes(b"<smses count='1'><sms body='x'/></smses>")
    h1 = hashlib.sha256(source.read_bytes()).hexdigest()
    h2 = hashlib.sha256(b"<sms body='x'/>").hexdigest()
    h3 = hashlib.sha256(("\n" + h2).encode()).hexdigest()

    class FakeClient:
        def import_detail(self, import_id):
            return {
                "import_id": import_id,
                "file_hash": h1,
                "file_hash_canon": "h1-rawbytes-v1",
                "record_hash_canon": "h2-rawelement-v1",
                "chain_canon": "h3-chain-sbv-genesisempty-v1",
                "chain_hash": h3,
                "record_count": 1,
                "encountered_count": 1,
                "claimed_count": 1,
                "reconciliation": "reconciled",
            }

        def import_records(self, import_id):
            return [
                {
                    "import_id": import_id,
                    "seq": 0,
                    "status": "accepted",
                    "record_hash": h2,
                    "record_hash_canon": "h2-rawelement-v1",
                }
            ]

        def import_rejections(self, import_id):
            return []

        def import_attachments(self, import_id):
            return []

    good = _validate_universal_import(source, {"import_id": 3}, FakeClient())
    assert good[0] == 3 and len(good[2]) == 1
    bad = FakeClient()
    bad.import_detail = lambda import_id: {**FakeClient.import_detail(bad, import_id), "chain_hash": "wrong"}
    with pytest.raises(SBVError, match="H3 mismatch"):
        _validate_universal_import(source, {"import_id": 3}, bad)


def test_attachment_download_manifest_mismatch_is_quarantined(monkeypatch, tmp_path: Path):
    client = SBVClient(base_url="http://sbv", password="secret")
    monkeypatch.setattr(
        client,
        "import_attachments",
        lambda _import_id: [{"id": 9, "original_name": "voice.amr", "byte_count": 4, "decoded_hash": "deadbeef"}],
    )

    def fake_stream(_import_id, _attachment_id, destination, **_kwargs):
        Path(destination).write_bytes(b"safe")
        return {"path": destination, "byte_count": 4, "sha256": hashlib.sha256(b"safe").hexdigest()}

    monkeypatch.setattr(client, "download_attachment_stream", fake_stream)
    with pytest.raises(SBVError, match="integrity mismatch"):
        client.download_attachment_to_dir(7, 9, str(tmp_path))
    assert not (tmp_path / "voice.amr").exists()
    assert (tmp_path / "to_be_deleted" / "voice.amr.integrity-mismatch").read_bytes() == b"safe"
