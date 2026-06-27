"""Unit tests for evidence.tools.imessage_html — imessage-exporter HTML export.

The DOM discriminator (div.message > div.sent|received > timestamp+sender) is
what lets the mesh tell an iMessage HTML export from a Facebook one. Covers
sent/received attribution, bubble text, announcements, and format rejection.
"""

from __future__ import annotations

import pytest

from evidence.tools.imessage_html import parse

_HTML = """<html><body>
  <div class="message">
    <div class="received">
      <p><span class="timestamp"><a href="#">May 17, 2022  5:29:42 PM</a></span><span class="sender">Ex Partner</span></p>
      <div class="message_part"><span class="bubble">Why are you late</span></div>
    </div>
  </div>
  <div class="message">
    <div class="sent iMessage">
      <p><span class="timestamp"><a href="#">May 17, 2022  5:30:00 PM</a></span><span class="sender">Me</span></p>
      <div class="message_part"><span class="bubble">Traffic on the bridge</span></div>
    </div>
  </div>
  <div class="announcement"><p><span class="timestamp">May 17, 2022  6:00:00 PM</span> You renamed the conversation.</p></div>
</body></html>"""


def _run(tmp_path, html=_HTML, name="thread.html"):
    p = tmp_path / name
    p.write_text(html, encoding="utf-8")
    return parse({"path": str(p)})


def test_sent_received_and_announcement(tmp_path):
    result = _run(tmp_path)
    assert result["stats"]["messages"] == 2
    assert result["stats"]["announcements"] == 1

    received, sent, announcement = result["records"]  # chronological

    assert received["role"] == "Ex Partner"
    assert received["content"] == "Why are you late"
    assert received["record_type"] == "message"
    assert received["occurred_at"].startswith("2022-05-17")

    assert sent["role"] == "owner"
    assert sent["content"] == "Traffic on the bridge"
    assert sent["attrs"]["sender_label"] == "Me"

    assert announcement["record_type"] == "event"
    assert "renamed" in announcement["content"]


def test_rejects_non_imessage_html(tmp_path):
    # A Facebook-style / plain page must be rejected so the mesh falls back.
    html = '<html><body><div class="message"><div class="meta">X - May 1, 2022</div><p>hi</p></div></body></html>'
    with pytest.raises(ValueError, match="not an imessage-exporter HTML export"):
        _run(tmp_path, html)
