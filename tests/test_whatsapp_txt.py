"""Unit tests for server.tools.parsers.messaging.whatsapp_txt.

The court-critical bits: the locale-dependent date order is declared or inferred
and REFUSED when ambiguous (a wrong date silently corrupts a timeline);
multi-line continuations stay attached to their message instead of being
truncated; a sender name containing a colon does not swallow the body; system
events such as missed calls are kept as contact-attempt evidence rather than
discarded; and `<Media omitted>` is flagged so absent media is never read as an
absent message.

Byline: Claude Code · Opus 5 · 2026-09-03.
"""

from __future__ import annotations

import pytest

from server.tools.parsers.messaging.whatsapp_txt import parse


def _run(tmp_path, text, name="_chat.txt", **extra):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return parse({"path": str(p), **extra})


def test_bracketed_ios_style_lines(tmp_path):
    result = _run(
        tmp_path,
        "[13/03/2024, 14:07:33] Katrina: that never happened\n[13/03/2024, 14:08:01] Matt: I have the screenshots\n",
    )
    assert result["stats"]["record_count"] == 2
    first, second = result["records"]
    assert first["role"] == "Katrina"
    assert first["content"] == "that never happened"
    assert second["role"] == "Matt"
    # 13 > 12 settles dd/mm unambiguously.
    assert "first component > 12" in result["stats"]["day_first_basis"]
    assert first["occurred_at"].startswith("2024-03-13T14:07:33")


def test_unbracketed_android_style_lines(tmp_path):
    result = _run(tmp_path, "13/03/2024, 14:07 - Katrina: hello\n")
    assert result["stats"]["record_count"] == 1
    assert result["records"][0]["content"] == "hello"


# THE central safety property: refuse rather than guess.
def test_ambiguous_date_order_refuses(tmp_path):
    with pytest.raises(ValueError, match="ambiguous"):
        _run(tmp_path, "[03/09/2026, 10:00:00] Katrina: hi\n[04/09/2026, 11:00:00] Matt: hey\n")


def test_declared_day_first_resolves_ambiguity(tmp_path):
    day_first = _run(tmp_path, "[03/09/2026, 10:00:00] K: hi\n", day_first=True)
    assert day_first["records"][0]["occurred_at"].startswith("2026-09-03")
    assert day_first["stats"]["day_first_basis"] == "declared by operator"

    month_first = _run(tmp_path, "[03/09/2026, 10:00:00] K: hi\n", name="b.txt", day_first=False)
    assert month_first["records"][0]["occurred_at"].startswith("2026-03-09")


def test_inference_uses_evidence_from_elsewhere_in_the_file(tmp_path):
    """One unambiguous line settles the order for the whole export."""
    result = _run(
        tmp_path,
        "[03/09/2026, 10:00:00] K: ambiguous line\n[25/09/2026, 11:00:00] K: settles it\n",
    )
    assert "first component > 12" in result["stats"]["day_first_basis"]
    assert result["records"][0]["occurred_at"].startswith("2026-09-03")

    reverse = _run(
        tmp_path,
        "[09/03/2026, 10:00:00] K: ambiguous\n[09/25/2026, 11:00:00] K: settles it\n",
        name="c.txt",
    )
    assert "second component > 12" in reverse["stats"]["day_first_basis"]


def test_day_first_must_be_boolean_when_supplied(tmp_path):
    with pytest.raises(ValueError, match="must be a boolean"):
        _run(tmp_path, "[13/03/2024, 10:00:00] K: hi\n", day_first="yes")


def test_multiline_continuations_stay_attached(tmp_path):
    """Continuation lines carry no timestamp; dropping them truncates messages."""
    result = _run(
        tmp_path,
        "[13/03/2024, 14:07:33] Katrina: first line\nsecond line\nthird line\n[13/03/2024, 14:09:00] Matt: separate\n",
    )
    assert result["stats"]["record_count"] == 2
    assert result["stats"]["continuation_lines"] == 2
    assert result["records"][0]["content"] == "first line\nsecond line\nthird line"


def test_sender_name_with_a_colon_does_not_swallow_the_body(tmp_path):
    result = _run(tmp_path, "[13/03/2024, 14:07:33] Katrina: look: I told you\n")
    record = result["records"][0]
    assert record["role"] == "Katrina"
    assert record["content"] == "look: I told you"


def test_system_events_are_retained_as_contact_attempts(tmp_path):
    """A missed call is evidence of a contact attempt, not noise (D-136)."""
    result = _run(
        tmp_path,
        "[13/03/2024, 14:00:00] Messages and calls are end-to-end encrypted\n"
        "[13/03/2024, 14:05:00] Missed voice call\n"
        "[13/03/2024, 14:07:33] Katrina: hi\n",
    )
    assert result["stats"]["record_count"] == 3, "system lines must not be discarded"
    assert result["stats"]["system_events"] == 2
    system = [r for r in result["records"] if r["attrs"]["is_system_event"]]
    assert any("Missed voice call" in r["content"] for r in system)
    assert all(r["role"] == "system" for r in system)
    assert all(r["participants"] == [] for r in system)


def test_media_omitted_is_flagged_not_dropped(tmp_path):
    result = _run(tmp_path, "[13/03/2024, 14:07:33] Katrina: <Media omitted>\n")
    record = result["records"][0]
    assert result["stats"]["media_omitted"] == 1
    assert record["attrs"]["media_omitted"] is True
    assert record["content"] == "<Media omitted>"


def test_verbatim_source_timestamp_is_preserved_for_the_fidelity_digest(tmp_path):
    result = _run(tmp_path, "[13/03/2024, 14:07:33] Katrina: hi\n")
    assert result["records"][0]["attrs"]["source_timestamp_raw"] == "13/03/2024, 14:07:33"


def test_twelve_hour_clock_is_handled(tmp_path):
    result = _run(tmp_path, "[13/03/2024, 2:07:33 PM] Katrina: hi\n")
    assert result["records"][0]["occurred_at"].startswith("2024-03-13T14:07:33")


def test_two_digit_year(tmp_path):
    result = _run(tmp_path, "[13/03/24, 14:07] Katrina: hi\n")
    assert result["records"][0]["occurred_at"].startswith("2024-03-13")


def test_non_whatsapp_text_raises(tmp_path):
    with pytest.raises(ValueError, match="no WhatsApp message lines"):
        _run(tmp_path, "just some notes\nwith no timestamps at all\n")


def test_tool_is_registered_under_the_messaging_lane(tmp_path):
    from server.tools.registry import registry

    tool = registry.get("messages.whatsapp-txt")
    assert tool.capability == "parse.whatsapp"
    assert tool.accept("_chat.txt", 2048) is True
