"""Validate or live-verify ContextForge -> Portkey MCP publication parity.

Offline validation is the default. ``--live`` performs read-only MCP
initialize/tools-list calls using env-referenced URLs and credentials.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from server.tools.gateway.mcp_chain import (  # noqa: E402
    McpChainError,
    compare_catalogs,
    list_tools,
    load_manifest,
    validate_endpoints,
)

_DEFAULT_MANIFEST = _REPO_ROOT / "deploy/docker/gateway/mcp/publications.json"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise McpChainError(f"required environment variable {name} is not set")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--live", action="store_true", help="perform read-only tools/list parity checks")
    args = parser.parse_args(argv)

    try:
        publications = load_manifest(args.manifest)
        if not args.live:
            print(json.dumps({"status": "manifest-valid", "publications": [item.key for item in publications]}))
            return 0
        reports = []
        for publication in publications:
            source_url = _required_env(publication.source_url_env)
            downstream_url = _required_env(publication.downstream_url_env)
            validate_endpoints(source_url, downstream_url)
            source = list_tools(
                source_url,
                {"Authorization": f"Bearer {_required_env(publication.source_token_env)}"},
            )
            downstream = list_tools(
                downstream_url,
                {"x-portkey-api-key": _required_env(publication.downstream_token_env)},
            )
            reports.append(compare_catalogs(publication.key, source, downstream))
        output = {
            "status": "pass" if all(report.ok for report in reports) else "fail",
            "reports": [report.to_dict() for report in reports],
        }
        print(json.dumps(output, indent=2))
        return 0 if output["status"] == "pass" else 1
    except McpChainError as error:
        print(json.dumps({"status": "error", "detail": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
