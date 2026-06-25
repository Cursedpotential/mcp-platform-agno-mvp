"""Unit tests for chatminer.core.pipeline + package importability.

The package __init__ exports parse_file/parse_multiple/parse_directory from a
module that previously did not exist, so `import chatminer` raised ImportError.
test_package_imports is the regression guard; the rest cover the thin
orchestration over the parser registry.
"""

from __future__ import annotations

import json

from chatminer.core.pipeline import parse_directory, parse_file, parse_multiple


def test_package_imports_public_api():
    # Regression: chatminer/__init__.py imported the missing core.pipeline.
    import chatminer

    assert callable(chatminer.parse_file)
    assert callable(chatminer.parse_multiple)
    assert callable(chatminer.parse_directory)


def _claude_jsonl(n=4):
    return "\n".join(
        json.dumps({"role": r, "content": f"m{i}"}) for i, r in enumerate(["user", "assistant"] * (n // 2))
    )


def test_parse_file_autodetect(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text(_claude_jsonl(), encoding="utf-8")
    result = parse_file(f)
    assert not result.errors
    assert result.total_conversations == 1
    assert result.total_messages == 4


def test_parse_file_unmatched_records_error(tmp_path):
    f = tmp_path / "nope.txt"
    f.write_text("nothing chat-like here", encoding="utf-8")
    result = parse_file(f)
    assert result.total_conversations == 0
    assert result.errors and result.errors[0]["error"] == "no parser matched"


def test_parse_file_source_hint(tmp_path):
    f = tmp_path / "ambiguous.dat"
    f.write_text(_claude_jsonl(), encoding="utf-8")
    result = parse_file(f, source_hint="claude_code")
    assert not result.errors
    assert result.total_messages == 4


def test_parse_multiple_aggregates(tmp_path):
    good = tmp_path / "a.jsonl"
    good.write_text(_claude_jsonl(), encoding="utf-8")
    bad = tmp_path / "b.txt"
    bad.write_text("prose", encoding="utf-8")
    result = parse_multiple([good, bad])
    assert result.total_conversations == 1
    assert len(result.errors) == 1


def test_parse_directory_non_recursive(tmp_path):
    (tmp_path / "a.jsonl").write_text(_claude_jsonl(), encoding="utf-8")
    (tmp_path / "b.jsonl").write_text(_claude_jsonl(), encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.jsonl").write_text(_claude_jsonl(), encoding="utf-8")

    flat = parse_directory(tmp_path, recursive=False, pattern="*.jsonl")
    assert flat.total_conversations == 2  # excludes sub/

    deep = parse_directory(tmp_path, recursive=True, pattern="*.jsonl")
    assert deep.total_conversations == 3


def test_parse_directory_not_a_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    result = parse_directory(f)
    assert result.errors and result.errors[0]["error"] == "not a directory"
