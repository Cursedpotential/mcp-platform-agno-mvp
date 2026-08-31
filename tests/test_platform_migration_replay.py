"""Contract tests for the explicit, non-globbing platform replay packet.

Byline: Codex · GPT-5.6-Sol · 2026-08-30.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = (ROOT / "scripts" / "validate_0054_live.py").read_text(encoding="utf-8")
REHEARSAL = (ROOT / "scripts" / "rehearse_platform_migrations.py").read_text(encoding="utf-8")


def test_replay_allowlist_is_exact_and_ordered() -> None:
    tree = ast.parse(VALIDATOR)
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "REPLAY_FILES"
    )
    assert isinstance(assignment.value, ast.Tuple)
    ids = [ast.literal_eval(element.elts[0]) for element in assignment.value.elts]
    assert ids == [
        "0000_platform_foundation",
        "0036",
        "0037",
        "0038",
        "0039",
        "0042",
        "0048",
        "0050",
        "0051",
        "0053",
        "0054",
    ]


def test_replay_never_discovers_migrations_or_accepts_password_flags() -> None:
    combined = VALIDATOR + REHEARSAL
    assert ".glob(" not in combined
    assert "rglob(" not in combined
    assert "--password" not in combined
    assert "PLATFORM_DATABASE_PASSWORD" not in combined
    assert "migration_hash(path)" in REHEARSAL
    assert "target=platform" in REHEARSAL


def test_replay_refuses_nonempty_or_wrong_target() -> None:
    assert "replay target already has active migration receipts" in REHEARSAL
    assert "replay target already contains context/analysis tables" in REHEARSAL
    assert "database != TARGET_DATABASE" in VALIDATOR
