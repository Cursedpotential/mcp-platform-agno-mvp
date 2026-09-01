"""Execute the ADR-0033 server/ repack (Option A). Behavior-neutral; gated by tests.

    python scripts/repack_to_server_layout.py --check    # dry-run: print plan, no mutation
    python scripts/repack_to_server_layout.py --run       # git mv + rewrite imports + patch paths

Import rewrites are IMPORT-STATEMENT-SCOPED (only `from X`/`import X` lines) so we never
touch a variable named db/app/tools. Path-depth constants that break when a module moves
deeper are patched explicitly. After --run: ruff format/check, mypy, pytest, podman build.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---- 1. file/dir moves (src -> dst), relative to repo root. Order matters. ----
MOVES: list[tuple[str, str]] = [
    # app/ -> server/api + server/core
    ("app/main.py", "server/api/main.py"),
    ("app/mcp_main.py", "server/api/mcp_main.py"),
    ("app/config.yaml", "server/api/config.yaml"),
    ("app/README.md", "server/api/README.md"),
    ("app/__init__.py", "server/api/__init__.py"),
    ("app/settings.py", "server/core/settings.py"),
    # db/ -> server/core
    ("db/session.py", "server/core/session.py"),
    ("db/embedder.py", "server/core/embedder.py"),
    ("db/reranker.py", "server/core/reranker.py"),
    ("db/url.py", "server/core/url.py"),
    ("db/README.md", "server/core/README.md"),
    ("db/__init__.py", "server/core/__init__.py"),
    # agents/ -> server/agents
    ("agents", "server/agents"),
    # evidence spine -> server/evidence ; analysis modules -> server/analysis
    ("evidence/__init__.py", "server/evidence/__init__.py"),
    ("evidence/__main__.py", "server/evidence/__main__.py"),
    ("evidence/cli.py", "server/evidence/cli.py"),
    ("evidence/custody.py", "server/evidence/custody.py"),
    ("evidence/normalize.py", "server/evidence/normalize.py"),
    ("evidence/reference.py", "server/evidence/reference.py"),
    ("evidence/store.py", "server/evidence/store.py"),
    ("evidence/workflows.py", "server/evidence/workflows.py"),
    ("evidence/README.md", "server/evidence/README.md"),
    ("evidence/tools", "server/evidence/tools"),
    ("evidence/config", "server/evidence/config"),
    ("evidence/court_language.py", "server/analysis/court_language.py"),
    ("evidence/detection.py", "server/analysis/detection.py"),
    ("evidence/patterns.py", "server/analysis/patterns.py"),
    ("evidence/milvus_forensic.py", "server/analysis/milvus_forensic.py"),
    ("evidence/semantica_wiring.py", "server/analysis/semantica_wiring.py"),
    # gateway/ -> server/evidence/tool_finder
    ("gateway", "server/evidence/tool_finder"),
    # tools/ (cross-domain) -> server/evidence/tools  (merge; keep both files)
    ("tools/extract_text.py", "server/evidence/tools/extract_text.py"),
    ("tools/__init__.py", "server/evidence/tools/_platform_tools_init.py.DROP"),  # collides; drop
    # chatminer/ -> server/vendored/chatminer
    ("chatminer", "server/vendored/chatminer"),
]

# ---- 2. import rewrites: (old dotted prefix) -> (new dotted prefix). Longest first. ----
IMPORT_MAP: list[tuple[str, str]] = [
    ("app.main", "server.api.main"),
    ("app.mcp_main", "server.api.mcp_main"),
    ("app.settings", "server.core.settings"),
    ("agents.", "server.agents."),
    ("db.session", "server.core.session"),
    ("db.embedder", "server.core.embedder"),
    ("db.reranker", "server.core.reranker"),
    ("db.url", "server.core.url"),
    ("evidence.court_language", "server.analysis.court_language"),
    ("evidence.detection", "server.analysis.detection"),
    ("evidence.patterns", "server.analysis.patterns"),
    ("evidence.milvus_forensic", "server.analysis.milvus_forensic"),
    ("evidence.semantica_wiring", "server.analysis.semantica_wiring"),
    ("evidence.", "server.evidence."),
    ("gateway.", "server.evidence.tool_finder."),
    ("tools.extract_text", "server.evidence.tools.extract_text"),
    ("chatminer.", "server.vendored.chatminer."),
    ("chatminer", "server.vendored.chatminer"),
    # bare-module forms (import db / import agents / from db import / from app import)
    ("db import", "server.core import"),
    ("app import", "server.api import"),
]


# import-statement-scoped patterns: only rewrite on `from <old>` / `import <old>` boundaries
def rewrite_imports(text: str) -> tuple[str, int]:
    n = 0
    for old, new in IMPORT_MAP:
        if old.endswith(" import"):  # bare "from X import" / handled as literal
            mod = old[: -len(" import")]
            pat = re.compile(rf"(^\s*from\s+){re.escape(mod)}(\s+import\b)", re.M)
            text, c = pat.subn(rf"\1{new[: -len(' import')]}\2", text)
            n += c
            continue
        # from OLD... and import OLD...
        pat = re.compile(rf"(^\s*(?:from|import)\s+){re.escape(old)}", re.M)
        text, c = pat.subn(rf"\1{new}", text)
        n += c
    return text, n


# ---- 3. explicit path-depth / string-path fixes (module -> [(old, new), ...]) ----
PATH_FIXES: dict[str, list[tuple[str, str]]] = {
    # patterns.py moved evidence/ -> analysis/ : same depth (both 1 under a pkg), but _REPO
    # was parent.parent (evidence/patterns.py -> repo). Now server/analysis/patterns.py ->
    # parent.parent = server/. Need parent.parent.parent.
    "server/analysis/patterns.py": [
        ("_REPO = Path(__file__).parent.parent", "_REPO = Path(__file__).parent.parent.parent"),
    ],
    # registry auto-discovery string paths
    "server/evidence/reference.py": [
        (
            'importlib.import_module(f"evidence.tools.{mod.name}")',
            'importlib.import_module(f"server.evidence.tools.{mod.name}")',
        ),
        ("import evidence.tools as tools_pkg", "import server.evidence.tools as tools_pkg"),
        (
            'importlib.import_module(f"tools.{mod.name}")',
            'importlib.import_module(f"server.evidence.tools.{mod.name}")',
        ),
        ("import tools as platform_tools_pkg", "import server.evidence.tools as platform_tools_pkg"),
    ],
    # chatminer cli sys.path hack goes one level deeper under vendored/
    "server/vendored/chatminer/cli/main.py": [
        ("Path(__file__).parent.parent.parent", "Path(__file__).parent.parent.parent.parent"),
    ],
}


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=check)


def do_check() -> None:
    print("=== MOVES (git mv) ===")
    missing = []
    for src, dst in MOVES:
        exists = (REPO / src).exists()
        print(f"  {'OK ' if exists else 'MISSING'} {src} -> {dst}")
        if not exists:
            missing.append(src)
    py = list(REPO.glob("**/*.py"))
    py = [p for p in py if ".venv" not in p.parts and "docs" not in p.parts[:2]]
    total = 0
    for p in py:
        _, n = rewrite_imports(p.read_text(encoding="utf-8"))
        total += n
    print(f"\n=== IMPORT REWRITES: {total} substitutions across {len(py)} .py files ===")
    print("=== PATH FIXES ===")
    for f, fixes in PATH_FIXES.items():
        print(f"  {f}: {len(fixes)} constant(s)")
    if missing:
        print(f"\n!! {len(missing)} sources missing — fix MOVES before --run")
        sys.exit(1)
    print("\nDry-run OK. Re-run with --run to execute.")


def do_run() -> None:
    for src, dst in MOVES:
        d = REPO / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        if dst.endswith(".DROP"):
            run(["git", "rm", "-q", src])
            continue
        run(["git", "mv", src, dst])
    # package __init__ for new namespace dirs that lack one
    for pkg in ["server", "server/api", "server/core", "server/analysis", "server/vendored"]:
        init = REPO / pkg / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
            run(["git", "add", str(init.relative_to(REPO))])
    # rewrite imports across all first-party .py
    py = [p for p in REPO.glob("**/*.py") if ".venv" not in p.parts and "docs" not in p.parts[:2]]
    changed = 0
    for p in py:
        t = p.read_text(encoding="utf-8")
        nt, n = rewrite_imports(t)
        if n:
            p.write_text(nt, encoding="utf-8")
            changed += 1
    # explicit path fixes
    for f, fixes in PATH_FIXES.items():
        fp = REPO / f
        t = fp.read_text(encoding="utf-8")
        for old, new in fixes:
            if old not in t:
                print(f"!! path-fix target not found in {f}: {old[:50]}")
            t = t.replace(old, new)
        fp.write_text(t, encoding="utf-8")
    run(["git", "add", "-A"])
    print(
        f"moved {len(MOVES)} paths; rewrote imports in {changed} files; patched {len(PATH_FIXES)} path-constant files"
    )
    print(
        "NEXT (not done by this script): entrypoint (Dockerfile/compose), pyproject packages+mypy, gates, podman build"
    )


if __name__ == "__main__":
    if "--run" in sys.argv:
        do_run()
    else:
        do_check()
