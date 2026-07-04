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


def test_owner_custom_variant_parses_bubbles_and_meta(tmp_path):
    # The owner-CUSTOM exporter shape (div.bubble.from-me/from-them + .meta):
    # the real vault format. Direction from the bubble class, sender + minute-
    # precision timestamp from the .meta line, document order preserved for
    # same-minute messages, attachment links captured.
    html = """
    <html><body>
      <div class="bubble from-them">Where is she</div>
      <div class="meta">+18105551234 - 2023-03-04 02:15 PM</div>
      <div class="bubble from-me">At practice like the schedule says</div>
      <div class="meta">Me - 2023-03-04 02:15 PM</div>
      <div class="bubble from-me">See attached</div>
      <div class="meta">Me - 2023-03-04 02:16 PM</div>
      <a class="attachment-link" href="IMG_1.jpeg">IMG_1.jpeg</a>
    </body></html>
    """
    result = _run(tmp_path, html)
    assert result["stats"]["variant"] == "owner-custom"
    r1, r2, r3 = result["records"]  # document order within the same minute

    assert r1["role"] == "+18105551234"
    assert r1["attrs"]["direction"] == "inbound"
    assert r1["content"] == "Where is she"
    assert r1["occurred_at"].startswith("2023-03-04T14:15")

    assert r2["role"] == "owner"
    assert r2["attrs"]["direction"] == "outbound"
    assert r2["attrs"]["sequence_number"] == 1  # same minute as r1, order kept

    assert r3["attrs"]["attachments"] == [{"kind": "link", "uri": "IMG_1.jpeg", "text": "IMG_1.jpeg"}]
    assert set(r1["participants"]) == {"owner", "+18105551234"}
