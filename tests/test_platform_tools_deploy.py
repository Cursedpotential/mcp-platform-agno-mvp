"""Deployment-contract tests for the consolidated platform-tools image.

Byline: Codex · GPT-5 · 2026-08-16
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sbv_image_is_immutable_and_state_uses_the_mounted_path() -> None:
    """SBV releases and SQLite state must survive a container replacement."""
    dockerfile = (ROOT / "docker" / "tools" / "Dockerfile").read_text(encoding="utf-8")
    supervisor = (ROOT / "docker" / "tools" / "supervisord.conf").read_text(encoding="utf-8")
    deployment = (ROOT / "deploy" / "platform-tools.yaml").read_text(encoding="utf-8")

    assert "FROM ghcr.io/cursedpotential/sbv-forensic@sha256:" in dockerfile
    assert 'DB_PATH_PREFIX="/opt/sbv/data"' in supervisor
    assert "/data/agno/volumes/sbv_data:/opt/sbv/data" in deployment
