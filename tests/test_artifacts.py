"""Unit tests for chatminer.core.artifacts.extract_artifacts.

Pulls actionable artifacts (code, files, URLs, evidence references, strategy)
out of parsed messages. The evidence-reference path is also a regression guard:
it constructs ArtifactType.EVIDENCE_REFERENCE, which previously did not exist
and raised AttributeError at runtime.
"""

from __future__ import annotations

from server.vendored.chatminer.core.artifacts import extract_artifacts
from server.vendored.chatminer.core.types import ArtifactType, ContentType, ParsedMessage


def _msg(content, *, content_type=ContentType.TEXT, mid="m1"):
    return ParsedMessage(
        message_id=mid,
        source_file="conv.md",
        source_format="generic_md",
        source_index=0,
        content=content,
        content_type=content_type,
        sender="You",
    )


def _types(arts):
    return {a.artifact_type for a in arts}


def test_extract_code_block():
    msg = _msg("```python\nprint('hello world')\n```", content_type=ContentType.CODE)
    arts = extract_artifacts([msg])
    code = [a for a in arts if a.artifact_type is ArtifactType.CODE_SNIPPET]
    assert len(code) == 1
    assert code[0].language == "python"
    assert code[0].content == "print('hello world')"


def test_tiny_code_block_skipped():
    msg = _msg("```\nx=1\n```", content_type=ContentType.CODE)  # <10 chars of code
    arts = extract_artifacts([msg])
    assert ArtifactType.CODE_SNIPPET not in _types(arts)


def test_extract_url():
    arts = extract_artifacts([_msg("reference: https://example.com/evidence/42 here")])
    urls = [a for a in arts if a.artifact_type is ArtifactType.URL]
    assert urls and "example.com" in (urls[0].title or urls[0].content or "")


def test_extract_file_reference():
    arts = extract_artifacts([_msg("see the attached custody_report.pdf for details")])
    files = [a for a in arts if a.artifact_type is ArtifactType.DATA_FILE]
    assert any(a.title == "custody_report.pdf" for a in files)


def test_evidence_reference_does_not_crash_and_is_tagged():
    # Regression: ArtifactType.EVIDENCE_REFERENCE used to be undefined -> this
    # path raised AttributeError on any evidence-like term.
    arts = extract_artifacts([_msg("I still have the screenshots and emails as evidence.")])
    assert ArtifactType.EVIDENCE_REFERENCE in _types(arts)


def test_dedup_identical_artifacts():
    same = "```python\nprint('duplicated snippet here')\n```"
    arts = extract_artifacts(
        [_msg(same, content_type=ContentType.CODE, mid="a"), _msg(same, content_type=ContentType.CODE, mid="b")]
    )
    code = [a for a in arts if a.artifact_type is ArtifactType.CODE_SNIPPET]
    assert len(code) == 1  # deduped by (type, title, content prefix)


def test_empty_messages():
    assert extract_artifacts([]) == []
