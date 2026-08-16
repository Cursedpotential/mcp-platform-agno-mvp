"""Workspace-level guardrails for the disposable Surreal surface.

Byline: Codex · GPT-5 · 2026-08-16
"""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_new_compose_is_isolated_and_legacy_compose_is_not_reused() -> None:
    compose = (ROOT / "compose.surreal-phase1.yaml").read_text(encoding="utf-8")
    assert "data-surreal-phase1-t0-r1" in compose
    assert "/data/agno/experiments/phase1-surreal-t0-r1" in compose
    assert "phase1-surreal-t0-r1" in compose
    assert "compose.data-surreal.yaml" not in compose
    assert "/data/agno/volumes/surrealdb" not in compose
    assert "100.119.96.29" not in compose
    assert "external: true" not in compose
    assert "--allow-rpc=attach,signin,use,query,authenticate,info,invalidate" in compose
    assert "--allow-rpc" in compose
    assert "--allow-rpc=" in compose


def test_workbench_incorporates_surrealdb_studio_without_credentials() -> None:
    page = (ROOT / "workbench/web/src/app/surreal/page.tsx").read_text(encoding="utf-8")
    sidebar = (ROOT / "workbench/web/src/components/layout/app-sidebar.tsx").read_text(encoding="utf-8")
    assert "SurrealDB Studio" in page
    assert "https://studio.surrealdb.com" in page
    assert "projection, not authority" in page.lower()
    assert "SURREALDB_PASS" not in page
    assert "100.119.96.29" not in page
    assert 'href: "/surreal"' in sidebar
