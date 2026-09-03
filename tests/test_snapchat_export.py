"""Unit tests for server.tools.parsers.messaging.snapchat_export.

The court-critical bits: BOTH export generations parse (the corpus has both);
non-text snaps are retained because a snap with no text still proves contact
occurred; direction is never guessed (unknown stays unknown, since direction is
sealed into the fidelity digest); the verbatim source timestamp survives for that
digest; the saved-only export caveat travels on every record; and an
unrecognized shape RAISES rather than returning an empty set, because a silent
zero is indistinguishable from an empty conversation.

Byline: Claude Code · Opus 5 · 2026-09-03.
"""

from __future__ import annotations

import json

import pytest

from server.tools.parsers.messaging.snapchat_export import parse


def _run(tmp_path, payload_obj, name="chat_history.json"):
    p = tmp_path / name
    p.write_text(json.dumps(payload_obj), encoding="utf-8")
    return parse({"path": str(p)})


def test_conversation_keyed_generation(tmp_path):
    """Newer chat_history.json: dict keyed by username, IsSender + microseconds."""
    result = _run(
        tmp_path,
        {
            "katrina": [
                {
                    "From": "katrina",
                    "Media Type": "TEXT",
                    "Created(microseconds)": 1699564800000000,
                    "IsSender": False,
                    "Text": "that never happened",
                },
                {
                    "To": "katrina",
                    "Media Type": "TEXT",
                    "Created(microseconds)": 1699564900000000,
                    "IsSender": True,
                    "Text": "I have the screenshots",
                },
            ]
        },
    )
    assert result["stats"]["export_generation"] == "conversation-keyed"
    assert result["stats"]["record_count"] == 2
    assert result["stats"]["text_messages"] == 2

    inbound, outbound = result["records"]
    assert inbound["attrs"]["direction"] == "inbound"
    assert inbound["content"] == "that never happened"
    assert outbound["attrs"]["direction"] == "outbound"
    # Chronological order preserved.
    assert inbound["occurred_at"] < outbound["occurred_at"]


def test_history_keyed_generation_and_utc_string_timestamp(tmp_path):
    """Older form: history-type keys, and `Created` as "... UTC".

    datetime.fromisoformat cannot parse the trailing " UTC", which is why this
    parser does not rely on the shared parse_timestamp helper.
    """
    result = _run(
        tmp_path,
        {
            "Received Snap History": [{"From": "katrina", "Media Type": "IMAGE", "Created": "2018-08-09 14:40:38 UTC"}],
            "Sent Snap History": [{"To": "katrina", "Media Type": "VIDEO", "Created": "2018-08-09 14:41:00 UTC"}],
        },
    )
    assert result["stats"]["export_generation"] == "history-keyed"
    assert result["stats"]["record_count"] == 2
    received, sent = result["records"]
    assert received["attrs"]["direction"] == "inbound"
    assert sent["attrs"]["direction"] == "outbound"
    assert received["occurred_at"] is not None, "the ' UTC' suffix must parse"
    assert received["occurred_at"].startswith("2018-08-09T14:40:38")


def test_non_text_snaps_are_retained_as_proof_of_contact(tmp_path):
    """A snap with no text still proves contact at that moment (D-136)."""
    result = _run(
        tmp_path,
        {
            "katrina": [
                {"From": "katrina", "Media Type": "IMAGE", "Created(microseconds)": 1699564800000000, "IsSender": False}
            ]
        },
    )
    assert result["stats"]["record_count"] == 1, "a media-only snap must not be dropped"
    assert result["stats"]["media_snaps"] == 1
    record = result["records"][0]
    assert record["content"] == "[image snap]"
    assert record["attrs"]["media_type"] == "IMAGE"
    assert record["attrs"]["is_text"] is False


def test_verbatim_source_timestamp_is_preserved_for_the_fidelity_digest(tmp_path):
    """engine/fidelity seals the source's own timestamp text, not our rendering."""
    result = _run(
        tmp_path,
        {
            "katrina": [
                {
                    "From": "katrina",
                    "Media Type": "TEXT",
                    "Created": "2018-08-09 14:40:38 UTC",
                    "IsSender": False,
                    "Text": "hi",
                }
            ]
        },
    )
    attrs = result["records"][0]["attrs"]
    assert attrs["source_timestamp_raw"] == "2018-08-09 14:40:38 UTC"

    micro = _run(
        tmp_path,
        {
            "k": [
                {
                    "From": "k",
                    "Media Type": "TEXT",
                    "Created(microseconds)": 1699564800000000,
                    "IsSender": False,
                    "Text": "hi",
                }
            ]
        },
        name="chat_history_2.json",
    )
    assert micro["records"][0]["attrs"]["source_timestamp_raw"] == "1699564800000000"


def test_direction_is_never_guessed(tmp_path):
    """No IsSender, no From/To asymmetry, no history key -> unknown, not a guess.

    Direction is sealed into the fidelity digest, so a guess would be a
    fabricated fact carrying a certificate of faithfulness.
    """
    result = _run(
        tmp_path,
        {
            "katrina": [
                {
                    "From": "katrina",
                    "To": "katrina",
                    "Media Type": "TEXT",
                    "Created(microseconds)": 1699564800000000,
                    "Text": "ambiguous",
                }
            ]
        },
    )
    assert result["records"][0]["attrs"]["direction"] == "unknown"
    assert result["stats"]["unknown_direction"] == 1


def test_saved_only_caveat_travels_on_every_record(tmp_path):
    """Absence from a Snapchat export proves nothing; the caveat must not live
    only in a doc nobody reads at exhibit time."""
    result = _run(
        tmp_path,
        {
            "k": [
                {
                    "From": "k",
                    "Media Type": "TEXT",
                    "Created(microseconds)": 1699564800000000,
                    "IsSender": False,
                    "Text": "hi",
                }
            ]
        },
    )
    caveat = result["records"][0]["attrs"]["export_limitation"]
    assert "only messages a participant explicitly saved" in caveat.lower()
    assert "does not imply" in caveat.lower()


def test_unrecognized_shape_raises_rather_than_returning_nothing(tmp_path):
    """A silent empty result is indistinguishable from an empty conversation —
    that is how 516 attachment-only MMS records were once lost."""
    with pytest.raises(ValueError, match="not a Snapchat"):
        _run(tmp_path, {"messages": [{"sender_name": "x", "content": "y"}]})

    with pytest.raises(ValueError, match="must be a JSON object"):
        _run(tmp_path, [{"From": "x"}])


def test_empty_conversation_is_kept_without_inventing_records(tmp_path):
    result = _run(
        tmp_path,
        {
            "katrina": [],
            "dennis": [
                {
                    "From": "dennis",
                    "Media Type": "TEXT",
                    "Created(microseconds)": 1699564800000000,
                    "IsSender": False,
                    "Text": "hi",
                }
            ],
        },
    )
    assert result["stats"]["conversations"] == 2
    assert result["stats"]["record_count"] == 1


def test_undated_messages_are_counted_not_discarded(tmp_path):
    result = _run(
        tmp_path,
        {"k": [{"From": "k", "Media Type": "TEXT", "Created": "not-a-date", "IsSender": False, "Text": "hi"}]},
    )
    assert result["stats"]["record_count"] == 1, "an unparseable date must not drop the message"
    assert result["stats"]["undated"] == 1
    assert result["records"][0]["attrs"]["source_timestamp_raw"] == "not-a-date"


def test_handle_is_the_sources_own_identifier(tmp_path):
    """The digest seals this value, so it must be the source's username string."""
    result = _run(
        tmp_path,
        {
            "katrina.k": [
                {
                    "From": "katrina.k",
                    "Media Type": "TEXT",
                    "Created(microseconds)": 1699564800000000,
                    "IsSender": False,
                    "Text": "hi",
                }
            ]
        },
    )
    assert result["records"][0]["attrs"]["handle"] == "katrina.k"


def test_tool_is_registered_under_the_messaging_lane(tmp_path):
    from server.tools.registry import registry

    tool = registry.get("messages.snapchat-json")
    assert tool.capability == "parse.snapchat"
    assert tool.accept("chat_history.json", 1024) is True
