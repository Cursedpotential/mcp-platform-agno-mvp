"""Tests for the MCL 722.23 Best Interest Factor taxonomy in the behavioral corpus.

Load-bearing contract: a factor's ``name`` is what gets rendered as a human-facing
label — report headings, UI badges, exhibit tables. Its ``description`` is the
statutory text. If those two disagree, the system prints internally-correct codes
under inverted labels, which is worse than failing outright.

``patterns.py`` validates only that factor letters are members of
``MCL_LETTERS = set("abcdefghijkl")``. It never reads ``mcl_factors`` at all, so it
cannot catch a name/description swap between two otherwise-valid letters. These
tests close that gap.

Statutory anchors below are taken from MCL 722.23 (a)-(l). The two most
consequential are:

    (j) the willingness and ability of each party to FACILITATE and encourage a
        close and continuing parent-child relationship with the other parent
    (k) DOMESTIC VIOLENCE, regardless of whether directed against or witnessed
        by the child

Those two are adjacent, easily transposed, and carry opposite meaning in a
custody record. A swap misattributes domestic violence findings to a
gatekeeping factor and vice versa.
"""

from __future__ import annotations

import pytest

from server.analysis.patterns import MCL_LETTERS, load_corpus

# (letter, token required in `name`, token required in `description`)
# Tokens are lowercase substrings; matching is case-insensitive.
STATUTORY_ANCHORS: list[tuple[str, str, str]] = [
    ("a", "affection", "love, affection"),
    ("b", "education", "education"),
    ("c", "provide", "food, clothing"),
    ("d", "length of time", "length of time"),
    ("e", "permanence", "permanence"),
    ("f", "moral fitness", "moral fitness"),
    ("g", "health", "mental and physical health"),
    ("h", "record", "home, school, and community record"),
    ("i", "preference", "reasonable preference"),
    ("j", "facilitate", "facilitate and encourage"),
    ("k", "domestic violence", "domestic violence"),
    ("l", "other", "other factor"),
]


def _factors_by_letter() -> dict[str, dict]:
    return {f["letter"]: f for f in load_corpus()["mcl_factors"]}


def test_all_twelve_statutory_letters_present_exactly_once():
    factors = load_corpus()["mcl_factors"]
    letters = [f["letter"] for f in factors]

    assert sorted(letters) == sorted(MCL_LETTERS), (
        f"corpus letters {sorted(letters)} != MCL_LETTERS {sorted(MCL_LETTERS)}"
    )
    assert len(letters) == len(set(letters)), f"duplicate letters: {letters}"


@pytest.mark.parametrize(("letter", "name_token", "desc_token"), STATUTORY_ANCHORS)
def test_factor_description_matches_statute(letter: str, name_token: str, desc_token: str):
    """The description must carry its own statutory anchor."""
    factor = _factors_by_letter()[letter]

    assert desc_token in factor["description"].lower(), (
        f"factor ({letter}) description does not contain {desc_token!r}; got: {factor['description'][:120]!r}"
    )


@pytest.mark.parametrize(("letter", "name_token", "desc_token"), STATUTORY_ANCHORS)
def test_factor_name_agrees_with_its_description(letter: str, name_token: str, desc_token: str):
    """The rendered label must describe the same factor as the statutory text.

    This is the assertion that catches a name/description transposition — the
    defect class ``patterns.py`` is structurally unable to detect.
    """
    factor = _factors_by_letter()[letter]

    assert name_token in factor["name"].lower(), (
        f"factor ({letter}) name {factor['name']!r} does not contain {name_token!r} — "
        f"its description is the ({letter}) statutory text, so the name is wrong "
        f"or transposed with another letter"
    )


def test_domestic_violence_and_facilitation_are_not_transposed():
    """Explicit guard on the (j)/(k) pair — adjacent, opposite in meaning.

    Regression test for the inversion found 2026-08-23: (j) was named
    "Domestic Violence" while carrying the facilitate-relationship description,
    and (k) was named "Willingness to Facilitate Relationship" while carrying
    the domestic-violence description.
    """
    factors = _factors_by_letter()

    j_name = factors["j"]["name"].lower()
    k_name = factors["k"]["name"].lower()

    assert "domestic violence" not in j_name, (
        f"factor (j) is the facilitate-relationship factor, not domestic violence — got name {factors['j']['name']!r}"
    )
    assert "domestic violence" in k_name, (
        f"factor (k) IS domestic violence under MCL 722.23(k) — got name {factors['k']['name']!r}"
    )
