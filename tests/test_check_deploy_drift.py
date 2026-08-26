"""Tests for scripts/check_deploy_drift.py (GAP-019).

Fixture/mock only: no live Coolify call, no real git subprocess. The fake
resolver stands in for GitRefResolver so results don't depend on this
checkout's actual branch history.
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-26

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from scripts.check_deploy_drift import (
    THIS_REPO_DEFAULT,
    _covers,
    _normalize_watch_paths,
    build_receipt,
    check_app,
    main,
    render_summary,
)

FIXTURE = Path(__file__).parent / "fixtures" / "deploy_drift" / "sample.json"
SHA_A = "a" * 40
SHA_B = "b" * 40


class FakeResolver:
    """Stand-in for GitRefResolver — no subprocess, no real git state."""

    def __init__(self, branch_commits: dict[str, str], existing: dict[tuple[str, str], bool]) -> None:
        self.branch_commits = branch_commits
        self.existing = existing

    def resolve_branch_commit(self, branch: str) -> Optional[str]:
        return self.branch_commits.get(branch)

    def path_exists_at_branch(self, branch: str, path: str) -> Optional[bool]:
        return self.existing.get((branch, path.lstrip("/")))


def make_app(**overrides) -> dict:
    app = {
        "name": "app",
        "uuid": "u1",
        "git_repository": THIS_REPO_DEFAULT,
        "git_branch": "main",
        "docker_compose_location": "/deploy/app.yaml",
        "git_commit_sha": SHA_A,
        "watch_paths": "deploy/app.yaml",
        "config_hash": "h1",
        "status": "running:healthy",
    }
    app.update(overrides)
    return app


def finished(commit: str) -> list[dict]:
    return [{"commit": commit, "status": "finished"}]


# --- individual checks -------------------------------------------------


def test_clean_app_has_no_drift() -> None:
    app = make_app()
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): True})
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["drift"] is False
    assert all(c["severity"] != "actionable" for c in result["checks"].values())


def test_retired_root_compose_watch_path_flagged() -> None:
    app = make_app(watch_paths="compose.app.yaml\ndocker/app/**")
    resolver = FakeResolver(
        {"main": SHA_A},
        {("main", "deploy/app.yaml"): True, ("main", "compose.app.yaml"): False},
    )
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["drift"] is True
    check = result["checks"]["retired_watch_paths"]
    assert check["severity"] == "actionable"
    assert "compose.app.yaml" in check["missing"]


def test_missing_watch_coverage_of_own_manifest() -> None:
    app = make_app(watch_paths="docker/app/**")  # never mentions deploy/app.yaml
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): True})
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["drift"] is True
    assert result["checks"]["watch_coverage"]["severity"] == "actionable"


def test_no_watch_paths_at_all_is_actionable() -> None:
    app = make_app(watch_paths=None)
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): True})
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["checks"]["watch_coverage"]["severity"] == "actionable"


def test_head_ref_is_non_immutable() -> None:
    app = make_app(git_commit_sha="HEAD")
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): True})
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["drift"] is True
    assert result["checks"]["commit_sha_immutability"]["severity"] == "actionable"


def test_compose_location_missing_on_its_own_branch() -> None:
    app = make_app()
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): False})
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["drift"] is True
    assert result["checks"]["compose_location_exists"]["severity"] == "actionable"


def test_deployment_commit_behind_branch_tip() -> None:
    app = make_app()
    resolver = FakeResolver({"main": SHA_B}, {("main", "deploy/app.yaml"): True})
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    check = result["checks"]["deployment_commit_drift"]
    assert result["drift"] is True
    assert check["severity"] == "actionable"
    assert check["deployed_commit"] == SHA_A
    assert check["remote_commit"] == SHA_B


def test_no_finished_deployment_is_actionable() -> None:
    app = make_app()
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): True})
    deployments = [{"commit": SHA_B, "status": "failed"}, {"commit": SHA_B, "status": "in_progress"}]
    result = check_app(app, deployments, resolver, THIS_REPO_DEFAULT)
    assert result["drift"] is True
    assert result["checks"]["deployment_commit_drift"]["severity"] == "actionable"


def test_cross_repo_app_skips_ref_checks_but_still_catches_non_ref_drift() -> None:
    app = make_app(git_repository="Other/repo", git_commit_sha="HEAD", watch_paths="compose.app.yaml")
    resolver = FakeResolver({"main": SHA_A}, {})  # would find drift if consulted
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["checks"]["retired_watch_paths"]["severity"] == "skipped"
    assert result["checks"]["compose_location_exists"]["severity"] == "skipped"
    assert result["checks"]["deployment_commit_drift"]["severity"] == "skipped"
    # non-ref check still fires: cross-repo doesn't hide a genuinely moving ref
    assert result["checks"]["commit_sha_immutability"]["severity"] == "actionable"
    assert result["drift"] is True


def test_unresolved_branch_is_skipped_not_actionable() -> None:
    """Branch not fetched locally yet -> 'skipped', never a false actionable."""
    app = make_app(watch_paths="compose.app.yaml")
    resolver = FakeResolver({}, {})  # no local knowledge of "main" at all
    result = check_app(app, finished(SHA_A), resolver, THIS_REPO_DEFAULT)
    assert result["checks"]["retired_watch_paths"]["severity"] == "skipped"
    assert result["checks"]["compose_location_exists"]["severity"] == "skipped"
    assert result["checks"]["deployment_commit_drift"]["severity"] == "skipped"


def test_no_git_flag_reports_disabled_reason() -> None:
    app = make_app(watch_paths="compose.app.yaml")
    result = check_app(app, finished(SHA_A), None, THIS_REPO_DEFAULT)
    assert "no-git" in result["checks"]["retired_watch_paths"]["detail"]


# --- helpers -------------------------------------------------------------


def test_normalize_watch_paths_handles_string_list_and_none() -> None:
    assert _normalize_watch_paths(None) == []
    assert _normalize_watch_paths("a\nb\n\n c ") == ["a", "b", "c"]
    assert _normalize_watch_paths(["a", " b "]) == ["a", "b"]


def test_covers_exact_and_glob_prefix() -> None:
    assert _covers(["deploy/app.yaml"], "deploy/app.yaml")
    assert _covers(["deploy/**"], "deploy/app.yaml")
    assert not _covers(["docker/**"], "deploy/app.yaml")
    assert not _covers([], "deploy/app.yaml")


# --- receipt / CLI ---------------------------------------------------------


def test_build_receipt_filters_by_app_name() -> None:
    apps = [make_app(name="a", uuid="u1"), make_app(name="b", uuid="u2")]
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): True})
    receipt = build_receipt(
        apps, {"u1": finished(SHA_A), "u2": finished(SHA_A)}, resolver, THIS_REPO_DEFAULT, apps_filter=["a"]
    )
    assert receipt["apps_checked"] == 1
    assert receipt["results"][0]["app"] == "a"


def test_render_summary_lists_only_drifted_apps() -> None:
    apps = [make_app(name="clean", uuid="u1"), make_app(name="drifted", uuid="u2", git_commit_sha="HEAD")]
    resolver = FakeResolver({"main": SHA_A}, {("main", "deploy/app.yaml"): True})
    receipt = build_receipt(apps, {"u1": finished(SHA_A), "u2": finished(SHA_A)}, resolver, THIS_REPO_DEFAULT)
    summary = render_summary(receipt)
    detail_lines = summary.splitlines()[1:]
    assert any("drifted" in line for line in detail_lines)
    assert not any("clean" in line for line in detail_lines)


def test_main_end_to_end_with_fixture_no_git_exits_nonzero_on_drift(tmp_path: Path, capsys) -> None:
    exit_code = main(["--fixture", str(FIXTURE), "--no-git"])
    captured = capsys.readouterr()
    receipt = json.loads(captured.out)
    assert receipt["apps_checked"] == 2
    drifted = {r["app"] for r in receipt["results"] if r["drift"]}
    assert "drifted-app" in drifted
    assert exit_code == 1


def test_main_writes_receipt_to_out_file(tmp_path: Path) -> None:
    out = tmp_path / "receipt.json"
    main(["--fixture", str(FIXTURE), "--no-git", "--out", str(out)])
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["gap"] == "GAP-019"
    assert receipt["apps_checked"] == 2


def test_main_apps_filter_narrows_fixture_run() -> None:
    exit_code = main(["--fixture", str(FIXTURE), "--no-git", "--apps", "clean-app"])
    assert exit_code == 0
