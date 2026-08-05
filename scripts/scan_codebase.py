# Byline: Codex · GPT-5 · 2026-08-02
"""Create a privacy-safe inventory and dependency health report for this repository.

The scanner intentionally records paths, sizes, hashes, and static metadata only;
it never stores source text or environment values.  Its default output location is
ignored by Git so scans remain local diagnostic artifacts.

Usage:
    uv run python scripts/scan_codebase.py [--out-dir .migration-passes]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / ".migration-passes"
MAX_SIZE = 5 * 1024 * 1024
EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".claude",
        ".codex",
        ".migration-passes",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".memsearch",
        ".remember",
        ".serena",
        ".osgrep",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "target",
        "bin",
        "obj",
        ".cache",
        ".turbo",
        "coverage",
        ".idea",
        ".vs",
        ".vscode",
        "content_store",
        "context_ingest",
    }
)
PROJECT_PYTHON_PREFIXES = frozenset({"server", "tests", "scripts", "evals", "workbench"})
SOURCE_EXTENSIONS = {".py", ".ts", ".js", ".go", ".rs", ".java", ".rb", ".php", ".cs", ".swift"}
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".ico", ".gif", ".woff", ".woff2", ".ttf"}
SCHEMA_EXTENSIONS = {".proto", ".graphql"}
CONFIG_NAMES = {"package.json", "makefile", "justfile"}


def git_paths(*args: str) -> set[Path]:
    """Return repository-relative paths reported by Git, preserving spaces."""
    result = subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True)
    return {Path(item) for item in result.stdout.splitlines() if item}


def is_eligible(path: Path) -> bool:
    """Apply the agreed product-repository scan boundary to a relative path."""
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False
    if path.name.startswith(".env"):
        return False
    return (REPO / path).is_file() and (REPO / path).stat().st_size <= MAX_SIZE


def classify(path: Path) -> str:
    path_string = path.as_posix().lower()
    name = path.name.lower()
    if path_string.startswith("sql/") or "migration" in path.parts or "alembic" in path.parts:
        return "migration"
    if (
        "tests" in path.parts
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.py")
    ):
        return "test"
    if path.suffix.lower() in SCHEMA_EXTENSIONS or any(
        marker in name for marker in (".openapi.", ".swagger.", ".schema.")
    ):
        return "schema"
    if path.suffix.lower() in SOURCE_EXTENSIONS:
        return "source"
    if name.endswith((".sh", ".bat", ".ps1")) or name in {"makefile", "justfile"}:
        return "script"
    if (
        name in CONFIG_NAMES
        or name.startswith("dockerfile")
        or name.startswith("tsconfig")
        or name.startswith(".env")
        or name.startswith("compose")
        or path.suffix.lower() in {".yml", ".yaml", ".toml", ".ini", ".cfg"}
    ):
        return "config"
    if (
        path_string.startswith("docs/")
        or path.suffix.lower() == ".md"
        or name.startswith(("readme", "architecture", "contributing", "changelog"))
    ):
        return "doc"
    if path.suffix.lower() in ASSET_EXTENSIONS:
        return "asset"
    return "other"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def python_tree(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


def module_name(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def public_symbol_count(tree: ast.Module | None) -> int:
    if tree is None:
        return 0
    explicit_exports: int | None = None
    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            symbols.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            symbols.update(
                alias.asname or alias.name.split(".")[0]
                for alias in node.names
                if not (alias.asname or alias.name).startswith("_")
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, (ast.List, ast.Tuple))
                ):
                    explicit_exports = sum(
                        isinstance(element, ast.Constant) and isinstance(element.value, str)
                        for element in node.value.elts
                    )
    return explicit_exports if explicit_exports is not None else len(symbols)


def hot_spot_reasons(path: Path, category: str, tree: ast.Module | None) -> list[str]:
    reasons: list[str] = []
    text = ""
    if path.suffix == ".py":
        try:
            text = (REPO / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            pass
        if public_symbol_count(tree) > 5:
            reasons.append("exports more than five public symbols")
        if re.search(r"\b(FastAPI|APIRouter)\s*\(", text):
            reasons.append("web route/controller")
        if re.search(r"if\s+__name__\s*==\s*[\"']__main__[\"']", text) or re.search(r"^def main\(", text, re.M):
            reasons.append("CLI entry point")
        if path.name == "__init__.py":
            reasons.append("package barrel module")
    if category in {"schema", "migration"}:
        reasons.append(category)
    if category == "doc" and (
        path.name.lower().startswith(("readme", "architecture", "contributing", "changelog"))
        or "/adr/" in f"/{path.as_posix().lower()}"
        or "decision" in path.name.lower()
    ):
        reasons.append("architecture documentation")
    return reasons


def resolve_import(importer: Path, node: ast.ImportFrom, known_modules: set[str]) -> str | None:
    if node.level == 0:
        candidate = node.module or ""
    else:
        package = module_name(importer).split(".")
        if importer.name != "__init__.py":
            package.pop()
        if node.level > 1:
            package = package[: -(node.level - 1)]
        candidate = ".".join([*package, *(node.module or "").split(".")]).strip(".")
    parts = candidate.split(".") if candidate else []
    while parts:
        current = ".".join(parts)
        if current in known_modules:
            return current
        parts.pop()
    return None


def collect_imports(files: list[Path]) -> dict[str, Any]:
    python_files = [path for path in files if path.suffix == ".py" and "vendored" not in path.parts]
    modules = {module_name(path): path for path in python_files}
    graph: dict[str, set[str]] = {module: set() for module in modules}
    unresolved: list[dict[str, str]] = []
    external: Counter[str] = Counter()
    standard: Counter[str] = Counter()
    stdlib = sys.stdlib_module_names

    for path in python_files:
        importer = module_name(path)
        tree = python_tree(REPO / path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                relative = False
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
                relative = node.level > 0
            else:
                continue
            for name in names:
                first = name.split(".")[0]
                target = resolve_import(path, node, set(modules)) if isinstance(node, ast.ImportFrom) else None
                if target is None and not isinstance(node, ast.ImportFrom):
                    parts = name.split(".")
                    while parts:
                        candidate = ".".join(parts)
                        if candidate in modules:
                            target = candidate
                            break
                        parts.pop()
                if target:
                    graph[importer].add(target)
                elif first in stdlib:
                    standard[first] += 1
                elif relative or first in PROJECT_PYTHON_PREFIXES:
                    unresolved.append({"importer": path.as_posix(), "module": name or "."})
                elif name:
                    external[first] += 1

    cycles = find_cycles(graph)
    return {
        "internal": {module: sorted(targets) for module, targets in sorted(graph.items()) if targets},
        "external": sorted(external),
        "standard_library": sorted(standard),
        "unresolved_internal": sorted(unresolved, key=lambda item: (item["importer"], item["module"])),
        "circular": cycles,
    }


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Return strongly connected components that represent import cycles."""
    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in graph[node]:
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])
        if lowlinks[node] == indexes[node]:
            component: list[str] = []
            while True:
                target = stack.pop()
                on_stack.remove(target)
                component.append(target)
                if target == node:
                    break
            if len(component) > 1 or node in graph[node]:
                cycles.append(sorted(component))

    for node in sorted(graph):
        if node not in indexes:
            visit(node)
    return sorted(cycles)


def dependency_inventory(files: list[Path]) -> list[dict[str, Any]]:
    inventories: list[dict[str, Any]] = []
    for path in files:
        absolute = REPO / path
        if path.name == "pyproject.toml":
            try:
                project = tomllib.loads(absolute.read_text(encoding="utf-8")).get("project", {})
            except tomllib.TOMLDecodeError:
                continue
            dependencies = list(project.get("dependencies", []))
            for group in project.get("optional-dependencies", {}).values():
                dependencies.extend(group)
            inventories.append({"path": path.as_posix(), "ecosystem": "python", "dependencies": sorted(dependencies)})
        elif path.name.startswith("requirements") and path.suffix == ".txt":
            lines = [line.strip() for line in absolute.read_text(encoding="utf-8", errors="replace").splitlines()]
            dependencies = [line for line in lines if line and not line.startswith(("#", "-"))]
            inventories.append({"path": path.as_posix(), "ecosystem": "python", "dependencies": sorted(dependencies)})
        elif path.name == "package.json":
            try:
                package = json.loads(absolute.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            inventories.append(
                {"path": path.as_posix(), "ecosystem": "node", "dependencies": dict(sorted(dependencies.items()))}
            )
        elif path.name == "go.mod":
            dependencies = re.findall(r"^\s*([^\s()]+)\s+v[^\s]+", absolute.read_text(encoding="utf-8"), re.M)
            inventories.append({"path": path.as_posix(), "ecosystem": "go", "dependencies": sorted(set(dependencies))})
    return inventories


def markdown_report(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    dependencies = manifest["dependencies"]
    hotspots = [path for path, item in manifest["files"].items() if item["hot_spot"]]
    lines = [
        "# Codebase Scan Report",
        "",
        "> _Byline: Codex · GPT-5 · 2026-08-02_",
        "",
        "## Scope",
        "",
        f"- Generated: {manifest['timestamp']}",
        f"- Files: {summary['total_files']} eligible product-repository files ({summary['total_bytes']:,} bytes)",
        f"- Excluded oversized files: {len(manifest['excluded_oversized'])} (cap: 5 MiB)",
        f"- Hot spots: {len(hotspots)}",
        "",
        "## Categories",
        "",
    ]
    lines.extend(f"- {category}: {count}" for category, count in sorted(summary["by_category"].items()))
    lines.extend(["", "## Dependency Health", ""])
    lines.append(f"- Internal importers with dependencies: {len(dependencies['internal'])}")
    lines.append(f"- External Python packages referenced: {len(dependencies['external'])}")
    lines.append(f"- Unresolved internal imports: {len(dependencies['unresolved_internal'])}")
    lines.append(f"- Circular dependency components: {len(dependencies['circular'])}")
    if dependencies["circular"]:
        lines.append("")
        lines.extend(f"- {' → '.join(cycle)}" for cycle in dependencies["circular"])
    if dependencies["unresolved_internal"]:
        lines.extend(["", "### Unresolved Internal Imports", ""])
        lines.extend(f"- `{item['importer']}` → `{item['module']}`" for item in dependencies["unresolved_internal"])
    lines.extend(["", "## Priority Targets", ""])
    for path in hotspots:
        item = manifest["files"][path]
        lines.append(f"- `{path}` — {', '.join(item['hot_spot_reason'])}")
    lines.extend(["", "## Dependency Manifests", ""])
    for inventory in manifest["dependency_manifests"]:
        lines.append(
            f"- `{inventory['path']}` ({inventory['ecosystem']}): {len(inventory['dependencies'])} declared dependencies"
        )
    return "\n".join(lines) + "\n"


def validate(manifest: dict[str, Any], expected: set[Path]) -> None:
    entries = manifest["files"]
    actual = {Path(path) for path in entries}
    if actual != expected:
        raise ValueError("manifest paths do not match the eligible file enumeration")
    if len(entries) != manifest["summary"]["total_files"]:
        raise ValueError("manifest file count does not match its summary")
    if sum(item["size"] for item in entries.values()) != manifest["summary"]["total_bytes"]:
        raise ValueError("manifest byte total does not match its summary")
    if any(not re.fullmatch(r"sha256:[0-9a-f]{64}", item["hash"]) for item in entries.values()):
        raise ValueError("manifest contains an invalid SHA-256 hash")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUTPUT, help="Directory for ignored local scan artifacts."
    )
    args = parser.parse_args()
    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO / args.out_dir

    candidates = git_paths("ls-files") | git_paths("ls-files", "--others", "--exclude-standard")
    eligible = sorted((path for path in candidates if is_eligible(path)), key=lambda path: path.as_posix())
    oversized = sorted(
        (path for path in candidates if (REPO / path).is_file() and (REPO / path).stat().st_size > MAX_SIZE),
        key=lambda path: path.as_posix(),
    )
    files: dict[str, dict[str, Any]] = {}
    for path in eligible:
        absolute = REPO / path
        category = classify(path)
        tree = python_tree(absolute) if path.suffix == ".py" else None
        reasons = hot_spot_reasons(path, category, tree)
        files[path.as_posix()] = {
            "hash": sha256(absolute),
            "size": absolute.stat().st_size,
            "category": category,
            "hot_spot": bool(reasons),
            "hot_spot_reason": reasons,
        }

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    manifest: dict[str, Any] = {
        "root": str(REPO),
        "timestamp": timestamp,
        "scope": "Git-tracked files plus non-ignored work-in-progress files; excludes secrets, generated data, caches, agent state, nested worktrees, and files over 5 MiB.",
        "max_size_bytes": MAX_SIZE,
        "excluded_directories": sorted(EXCLUDED_PARTS),
        "summary": {
            "total_files": len(files),
            "total_bytes": sum(item["size"] for item in files.values()),
            "by_category": dict(sorted(Counter(item["category"] for item in files.values()).items())),
        },
        "files": files,
        "excluded_oversized": [{"path": path.as_posix(), "size": (REPO / path).stat().st_size} for path in oversized],
        "dependencies": collect_imports(eligible),
        "dependency_manifests": dependency_inventory(eligible),
    }
    validate(manifest, set(eligible))
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "codebase-scan-manifest.json"
    report_path = out_dir / "codebase-scan-report.md"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(markdown_report(manifest), encoding="utf-8")
    print(f"Wrote {manifest_path.relative_to(REPO)}")
    print(f"Wrote {report_path.relative_to(REPO)}")
    print(
        f"Scanned {manifest['summary']['total_files']} files; found {len(manifest['dependencies']['circular'])} cycle(s)."
    )


if __name__ == "__main__":
    main()
