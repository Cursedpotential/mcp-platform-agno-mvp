"""Safety contract for the retired numbered-chain restore experiment.

Byline: Codex · GPT-5 · 2026-08-15
"""

from scripts._wave0_fresh_restore import main


def test_retired_numbered_chain_restore_refuses_without_connecting(capsys) -> None:
    assert main() == 4
    output = capsys.readouterr().out
    assert "REFUSED" in output
    assert "schema_baseline.sql" in output
    assert "No database connection or mutation was attempted" in output
