"""scripts/check_deploy_drift.py — collision-safe deployment-drift checker (GAP-019).

Compares each Coolify application's configured branch, compose/Dockerfile
location, watch paths, and reported deployed commit against the tracked
files and current remote commit of the branch it says it deploys from.
Platform-neutral: nothing here is specific to any one app's stack.

Detects, per app:
  - retired_watch_paths     — a watch path names a bare root `compose.*.yaml`
                               (or `docker-compose.yaml`) file that no longer
                               exists at the tip of the app's own branch, so
                               edits to the real manifest never trigger a
                               redeploy (NC-1 / SG-7 "false green").
  - missing_watch_coverage  — the app's OWN configured manifest path is not
                               itself covered by any watch-path entry.
  - non_immutable_ref       — `git_commit_sha` is "HEAD" (or otherwise not a
                               40-hex SHA): the deploy trigger is a moving
                               ref, not a pinned commit.
  - compose_location_missing— the configured manifest path does not exist at
                               the tip of the app's own branch (broken, not
                               just stale-watch).
  - deployment_commit_drift — the latest *finished* deployment's commit does
                               not match the current tip of the branch the
                               app is configured to track (or no finished
                               deployment exists at all).

Two independent data sources, both read-only:
  1. Coolify REST API (GET /applications, GET /deployments/applications/{uuid})
     — see ~/.claude/local-plugins/plugins/coolify-write/skills/coolify-write/
     references/API.md for the endpoint contract this was written against.
  2. Local git refs (`origin/<branch>`) for the SAME checkout this script
     ships in — used to resolve "does this path exist at the tip of that
     branch" and "what is the current remote commit". Run `git fetch` before
     a live run for freshness; this script never fetches or writes.

Never mutates Coolify (GET only) and never writes to the git repo.

Usage:
    .venv/Scripts/python.exe scripts/check_deploy_drift.py
    .venv/Scripts/python.exe scripts/check_deploy_drift.py --out receipt.json
    .venv/Scripts/python.exe scripts/check_deploy_drift.py --fixture tests/fixtures/deploy_drift/sample.json --no-git

Exit code: 0 if no actionable drift, 1 if any app has an actionable finding,
2 on a hard error (auth/network/fixture-load failure).
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-26

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

HOME = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "~").expanduser()
DEFAULT_COOLIFY_ENV = HOME / ".secrets" / "coolify-ionos-api.env"
DEFAULT_BASE_URL = "http://100.98.98.38:8000/api/v1"
THIS_REPO_DEFAULT = "Cursedpotential/probata"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# A bare root-level compose file reference: no directory component, no glob.
_ROOT_COMPOSE_RE = re.compile(r"^(compose\.[A-Za-z0-9_.-]+\.yaml|docker-compose\.yaml)$")


def load_dotenv(path: Path) -> dict[str, str]:
    """Tolerant KEY=VALUE parse — never `source`d (CLAUDE.md ~/.secrets rule)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$", line)
        if m:
            value = m.group(2)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            env[m.group(1)] = value
    return env


@dataclass
class CheckResult:
    ok: bool
    severity: str  # "actionable" | "info" | "skipped"
    detail: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {"ok": self.ok, "severity": self.severity, "detail": self.detail, **self.data}


class CoolifyClient:
    """Minimal read-only client. GET only — never mutates Coolify."""

    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        self._timeout = timeout

    def list_applications(self) -> list[dict[str, Any]]:
        import requests  # local import: not needed in fixture-only test runs

        resp = requests.get(f"{self.base_url}/applications", headers=self._headers, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])

    def list_deployments(self, app_uuid: str, take: int = 5) -> list[dict[str, Any]]:
        import requests

        resp = requests.get(
            f"{self.base_url}/deployments/applications/{app_uuid}",
            headers=self._headers,
            params={"take": take},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get("deployments", [])
        return data


class GitRefResolver:
    """Resolves paths/commits against local `origin/<branch>` refs only.

    Read-only: runs `git rev-parse` / `git cat-file` against the existing
    local checkout. Never fetches, never writes. Returns None (not False)
    when the ref isn't available locally, so callers can distinguish
    "checked, and it's missing" from "couldn't check".
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def _git(self, *args: str) -> Optional[str]:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()

    def resolve_branch_commit(self, branch: str) -> Optional[str]:
        return self._git("rev-parse", f"origin/{branch}")

    def path_exists_at_branch(self, branch: str, path: str) -> Optional[bool]:
        if self.resolve_branch_commit(branch) is None:
            return None
        try:
            proc = subprocess.run(
                ["git", "cat-file", "-e", f"origin/{branch}:{path.lstrip('/')}"],
                cwd=self.repo_root,
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return proc.returncode == 0


def _normalize_watch_paths(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    return [line.strip() for line in str(raw).splitlines() if line.strip()]


def _covers(watch_paths: list[str], target: str) -> bool:
    """Does any watch-path entry cover `target` (exact match or `dir/**` prefix)?"""
    target = target.lstrip("/")
    for entry in watch_paths:
        entry_norm = entry.lstrip("/")
        if entry_norm == target:
            return True
        if entry_norm.endswith("/**") and target.startswith(entry_norm[:-2]):
            return True
    return False


def _unresolvable_reason(resolver: Optional[GitRefResolver], repo: str, this_repo: str) -> Optional[str]:
    """None if refs for `repo` are resolvable via `resolver`; else why not."""
    if resolver is None:
        return "git ref resolution disabled (--no-git)"
    if repo != this_repo:
        return f"repo {repo!r} not resolvable from this checkout (expected {this_repo!r})"
    return None


def check_app(
    app: dict[str, Any], deployments: list[dict[str, Any]], resolver: Optional[GitRefResolver], this_repo: str
) -> dict[str, Any]:
    name = app.get("name", "<unknown>")
    branch = app.get("git_branch") or ""
    repo = app.get("git_repository") or ""
    compose_path = app.get("docker_compose_location") or ""
    commit_sha_field = app.get("git_commit_sha") or ""
    watch_paths = _normalize_watch_paths(app.get("watch_paths"))
    config_hash = app.get("config_hash")

    unresolvable = _unresolvable_reason(resolver, repo, this_repo)
    checks: dict[str, CheckResult] = {}

    # 1. non-immutable deploy ref
    if _SHA_RE.match(commit_sha_field.lower()):
        checks["commit_sha_immutability"] = CheckResult(True, "info", "git_commit_sha is a pinned 40-hex SHA")
    else:
        checks["commit_sha_immutability"] = CheckResult(
            False,
            "actionable",
            f"git_commit_sha={commit_sha_field!r} is not a pinned commit; deploys track a moving ref",
        )

    # 2. missing watch coverage of the app's own manifest
    if not watch_paths:
        checks["watch_coverage"] = CheckResult(False, "actionable", "no watch paths configured at all")
    elif compose_path and not _covers(watch_paths, compose_path):
        checks["watch_coverage"] = CheckResult(
            False,
            "actionable",
            f"configured manifest {compose_path!r} is not covered by any watch path",
            {"watch_paths": watch_paths},
        )
    else:
        checks["watch_coverage"] = CheckResult(True, "info", "manifest path is covered by a watch path")

    # 3. retired root compose references in watch paths
    root_compose_entries = [w for w in watch_paths if _ROOT_COMPOSE_RE.match(w)]
    if not root_compose_entries:
        checks["retired_watch_paths"] = CheckResult(True, "info", "no bare root compose.* watch-path entries")
    elif unresolvable:
        checks["retired_watch_paths"] = CheckResult(True, "skipped", unresolvable, {"entries": root_compose_entries})
    else:
        missing = []
        unresolved = []
        for entry in root_compose_entries:
            exists = resolver.path_exists_at_branch(branch, entry)  # type: ignore[union-attr]
            if exists is None:
                unresolved.append(entry)
            elif not exists:
                missing.append(entry)
        if missing:
            checks["retired_watch_paths"] = CheckResult(
                False,
                "actionable",
                f"watch path references retired root file(s) not present on {branch}: {missing}",
                {"missing": missing, "unresolved": unresolved},
            )
        elif unresolved:
            checks["retired_watch_paths"] = CheckResult(
                True, "skipped", f"branch {branch!r} not available locally; run `git fetch`", {"unresolved": unresolved}
            )
        else:
            checks["retired_watch_paths"] = CheckResult(True, "info", "all root compose watch entries exist on branch")

    # 4. compose/manifest path itself missing on its own branch
    if not compose_path:
        checks["compose_location_exists"] = CheckResult(False, "actionable", "no docker_compose_location configured")
    elif unresolvable:
        checks["compose_location_exists"] = CheckResult(True, "skipped", unresolvable)
    else:
        exists = resolver.path_exists_at_branch(branch, compose_path)  # type: ignore[union-attr]
        if exists is None:
            checks["compose_location_exists"] = CheckResult(
                True, "skipped", f"branch {branch!r} not available locally; run `git fetch`"
            )
        elif not exists:
            checks["compose_location_exists"] = CheckResult(
                False, "actionable", f"manifest {compose_path!r} does not exist at tip of {branch!r}"
            )
        else:
            checks["compose_location_exists"] = CheckResult(True, "info", "manifest path exists at tip of its branch")

    # 5. deployed artifact vs current remote commit
    finished = [d for d in deployments if d.get("status") == "finished"]
    if not finished:
        checks["deployment_commit_drift"] = CheckResult(
            False,
            "actionable",
            "no finished deployment found in recent history",
            {"recent_statuses": [d.get("status") for d in deployments]},
        )
    elif unresolvable:
        checks["deployment_commit_drift"] = CheckResult(
            True, "skipped", unresolvable, {"last_deployed_commit": finished[0].get("commit")}
        )
    else:
        remote_commit = resolver.resolve_branch_commit(branch)  # type: ignore[union-attr]
        deployed_commit = finished[0].get("commit")
        if remote_commit is None:
            checks["deployment_commit_drift"] = CheckResult(
                True,
                "skipped",
                f"branch {branch!r} not available locally; run `git fetch`",
                {"last_deployed_commit": deployed_commit},
            )
        elif deployed_commit != remote_commit:
            checks["deployment_commit_drift"] = CheckResult(
                False,
                "actionable",
                f"last finished deployment ({deployed_commit}) does not match tip of {branch!r} ({remote_commit})",
                {"deployed_commit": deployed_commit, "remote_commit": remote_commit},
            )
        else:
            checks["deployment_commit_drift"] = CheckResult(True, "info", "deployed commit matches current branch tip")

    drift = any(c.severity == "actionable" for c in checks.values())
    return {
        "app": name,
        "uuid": app.get("uuid"),
        "repository": repo,
        "branch": branch,
        "compose_path": compose_path,
        "config_hash": config_hash,
        "status": app.get("status"),
        "drift": drift,
        "checks": {k: v.to_json() for k, v in checks.items()},
    }


def build_receipt(
    applications: list[dict[str, Any]],
    deployments_by_uuid: dict[str, list[dict[str, Any]]],
    resolver: Optional[GitRefResolver],
    this_repo: str,
    apps_filter: Optional[list[str]] = None,
) -> dict[str, Any]:
    results = []
    for app in applications:
        if apps_filter and app.get("name") not in apps_filter:
            continue
        deployments = deployments_by_uuid.get(app.get("uuid", ""), [])
        results.append(check_app(app, deployments, resolver, this_repo))

    drift_apps = [r for r in results if r["drift"]]
    return {
        "checker": "check_deploy_drift",
        "gap": "GAP-019",
        "apps_checked": len(results),
        "apps_with_drift": len(drift_apps),
        "results": results,
    }


def render_summary(receipt: dict[str, Any]) -> str:
    lines = [
        f"GAP-019 deploy-drift check: {receipt['apps_checked']} apps, {receipt['apps_with_drift']} with actionable drift"
    ]
    for r in receipt["results"]:
        if not r["drift"]:
            continue
        actionable = [f"{name}: {c['detail']}" for name, c in r["checks"].items() if c["severity"] == "actionable"]
        lines.append(f"  - {r['app']} ({r['branch']}):")
        for a in actionable:
            lines.append(f"      * {a}")
    if receipt["apps_with_drift"] == 0:
        lines.append("  (none)")
    return "\n".join(lines)


def _load_fixture(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    apps = data.get("applications", [])
    deployments = data.get("deployments", {})
    return apps, deployments


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url", default=None, help="Coolify API base URL (default: env/secrets file, else built-in default)"
    )
    parser.add_argument("--token-env-file", type=Path, default=DEFAULT_COOLIFY_ENV)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--this-repo", default=THIS_REPO_DEFAULT, help="git_repository value this checkout can resolve refs for"
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Load applications+deployments from a JSON fixture instead of live Coolify",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Skip all local-git ref resolution (all ref-dependent checks report 'skipped')",
    )
    parser.add_argument("--apps", nargs="*", default=None, help="Limit to these app names")
    parser.add_argument("--out", type=Path, default=None, help="Write JSON receipt here (default: stdout)")
    args = parser.parse_args(argv)

    resolver = None if args.no_git else GitRefResolver(args.repo_root)

    if args.fixture:
        applications, deployments_by_uuid = _load_fixture(args.fixture)
    else:
        dotenv = load_dotenv(args.token_env_file)
        token = os.environ.get("COOLIFY_API_TOKEN") or dotenv.get("COOLIFY_API_TOKEN")
        if not token:
            print(f"FAIL: no COOLIFY_API_TOKEN found in env or {args.token_env_file}", file=sys.stderr)
            return 2
        base_url = (
            args.base_url
            or os.environ.get("COOLIFY_API")
            or dotenv.get("COOLIFY_API")
            or dotenv.get("COOLIFY_API_URL")
            or dotenv.get("COOLIFY_BASE_URL")
            or DEFAULT_BASE_URL
        )
        client = CoolifyClient(base_url, token)
        try:
            applications = client.list_applications()
            deployments_by_uuid = {}
            for app in applications:
                if args.apps and app.get("name") not in args.apps:
                    continue
                deployments_by_uuid[app["uuid"]] = client.list_deployments(app["uuid"], take=5)
        except Exception as exc:  # noqa: BLE001 - surfaced as a hard checker failure
            print(f"FAIL: Coolify API error: {exc}", file=sys.stderr)
            return 2

    receipt = build_receipt(applications, deployments_by_uuid, resolver, args.this_repo, args.apps)

    payload = json.dumps(receipt, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload)

    print(render_summary(receipt), file=sys.stderr)

    return 1 if receipt["apps_with_drift"] > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
