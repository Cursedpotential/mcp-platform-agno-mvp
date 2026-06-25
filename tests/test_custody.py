"""Unit tests for evidence.custody — the chain-of-custody entry gate.

custody is legally load-bearing: every artifact must be hashed write-once and
de-duplicated by digest. These tests stub the SQLAlchemy engine so the custody
*logic* (hashing, idempotency, blob layout, integrity verify) is covered with
no live Postgres.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from evidence import custody


# STUB: minimal fake SQLAlchemy engine used as a test double (no real DB) ---


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeConn:
    def __init__(self, engine):
        self._engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, _stmt, _params=None):
        return _FakeResult(self._engine._next_row())


class _FakeEngine:
    """Returns the queued rows in order, one per execute() call."""

    def __init__(self, rows):
        self._rows = list(rows)
        self._i = 0

    def _next_row(self):
        row = self._rows[self._i]
        self._i += 1
        return row

    def connect(self):
        return _FakeConn(self)

    def begin(self):
        return _FakeConn(self)


@pytest.fixture
def blob_root(tmp_path, monkeypatch):
    root = tmp_path / "r2"
    monkeypatch.setenv("EVIDENCE_BLOB_ROOT", str(root))
    return root


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "evidence.txt"
    f.write_bytes(b"hello evidence")
    return f


def test_sha256_matches_hashlib(sample_file):
    expected = hashlib.sha256(b"hello evidence").hexdigest()
    assert custody._sha256_file(sample_file) == expected


def test_ingest_missing_file_raises(blob_root):
    with pytest.raises(FileNotFoundError):
        custody.ingest_artifact("/no/such/file.txt")


def test_ingest_new_artifact_writes_blob_once(blob_root, sample_file, monkeypatch):
    # connect() lookup -> None (not seen), begin() insert -> new row.
    fake = _FakeEngine([None, {"id": 42, "hashed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}])
    monkeypatch.setattr(custody, "_get_engine", lambda: fake)

    ref = custody.ingest_artifact(sample_file, {"case": "demo"})

    sha = hashlib.sha256(b"hello evidence").hexdigest()
    assert ref.duplicate is False
    assert ref.artifact_id == "42"
    assert ref.sha256 == sha
    # Write-once blob layout: <first-2-of-sha>/<sha>/<original-name>
    assert ref.blob_key == f"{sha[:2]}/{sha}/evidence.txt"
    blob = blob_root / ref.blob_key
    assert blob.is_file()
    assert blob.read_bytes() == b"hello evidence"


def test_ingest_duplicate_returns_existing_without_rewrite(blob_root, sample_file, monkeypatch):
    # connect() lookup returns an existing custody row -> duplicate path.
    existing = {
        "id": 7,
        "source_ref": "/orig/path.txt",
        "blob_key": "aa/aaaa/path.txt",
        "hashed_at": datetime(2025, 6, 1, tzinfo=timezone.utc),
    }
    fake = _FakeEngine([existing])
    monkeypatch.setattr(custody, "_get_engine", lambda: fake)

    ref = custody.ingest_artifact(sample_file)

    assert ref.duplicate is True
    assert ref.artifact_id == "7"
    assert ref.blob_key == "aa/aaaa/path.txt"
    # No new blob should be created for the duplicate's own sha path.
    sha = hashlib.sha256(b"hello evidence").hexdigest()
    assert not (blob_root / f"{sha[:2]}/{sha}/evidence.txt").exists()


def test_verify_artifact_matches_and_detects_tamper(blob_root, sample_file, monkeypatch):
    sha = hashlib.sha256(b"hello evidence").hexdigest()
    digest = bytes.fromhex(sha)

    # verify_artifact issues one SELECT returning the stored digest row (a tuple).
    monkeypatch.setattr(custody, "_get_engine", lambda: _FakeEngine([(digest,)]))
    assert custody.verify_artifact("7", sample_file) is True

    tampered = sample_file.parent / "tampered.txt"
    tampered.write_bytes(b"not the same bytes")
    monkeypatch.setattr(custody, "_get_engine", lambda: _FakeEngine([(digest,)]))
    assert custody.verify_artifact("7", tampered) is False


def test_blob_root_env_override(blob_root):
    assert custody.blob_root() == blob_root
