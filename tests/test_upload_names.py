"""Upload filename decoding and safety contract.

Byline: Codex · GPT-5 · 2026-08-13
"""

from server.api.uploads import safe_upload_name


def test_rfc2047_unicode_filename_keeps_parser_extension():
    encoded = "=?utf-8?B?4oCOR2VtaW5pIC0gRW1vdGlvbmFsIE1hbmlwdWxhdGlvbiBpbiBSZWxhdGlvbnNoaXBzLm1k?="

    decoded = safe_upload_name(encoded)

    assert decoded == "\u200eGemini - Emotional Manipulation in Relationships.md"
    assert decoded.lower().endswith(".md")


def test_upload_name_removes_both_traversal_styles_and_controls():
    assert safe_upload_name("../../outside.txt") == "outside.txt"
    assert safe_upload_name("..\\..\\outside.txt") == "outside.txt"
    assert safe_upload_name("bad\r\nname.md") == "badname.md"


def test_missing_upload_name_has_safe_fallback():
    assert safe_upload_name(None) == "upload.bin"
