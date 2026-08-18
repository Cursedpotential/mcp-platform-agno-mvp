# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""Unit tests for server.tools.parsers.messaging.facebook_messenger_html.

Covers both DOM layouts Facebook emits (legacy div.message, card _a6-g), fuzzy
timestamp parsing, owner-based direction tagging, and format rejection.
"""

from __future__ import annotations

from typing import Any

import pytest

from server.tools.parsers.messaging.facebook_messenger_html import parse


def _run(tmp_path, html, *, owner=None, name="thread.html"):
    p = tmp_path / name
    p.write_text(html, encoding="utf-8")
    payload: dict[str, Any] = {"path": str(p)}
    if owner:
        payload["source_meta"] = {"owner_name": owner}
    return parse(payload)


def test_legacy_layout_with_direction(tmp_path):
    html = """<html><body>
      <div class="message"><div class="meta">Ex Partner - May 17, 2022, 5:29 PM</div><p>Why are you late again</p></div>
      <div class="message"><div class="meta">Me - May 17, 2022, 5:30 PM</div><p>Traffic on the bridge</p></div>
    </body></html>"""
    result = _run(tmp_path, html, owner="Me")

    assert result["stats"]["messages"] == 2
    assert result["stats"]["layout"] == "legacy"
    assert result["stats"]["participants"] == 2

    ex, me = result["records"]  # chronological
    assert ex["role"] == "Ex Partner"
    assert ex["content"] == "Why are you late again"
    assert ex["attrs"]["direction"] == "inbound"
    assert ex["occurred_at"].startswith("2022-05-17")
    assert me["role"] == "Me" and me["attrs"]["direction"] == "outbound"


def test_card_layout(tmp_path):
    html = """<html><body>
      <div class="_a6-g"><div class="_a6-h">Ex</div><div class="_a6-p">hello there</div></div>
      <div class="_a6-o"><div class="_a72d">May 17, 2022, 5:29 PM</div></div>
    </body></html>"""
    result = _run(tmp_path, html)
    assert result["stats"]["layout"] == "card"
    assert result["records"][0]["content"] == "hello there"
    assert result["records"][0]["role"] == "Ex"


def test_rejects_non_facebook_html(tmp_path):
    with pytest.raises(ValueError, match="not a Facebook HTML export"):
        _run(tmp_path, "<html><body><p>just a webpage</p></body></html>")
