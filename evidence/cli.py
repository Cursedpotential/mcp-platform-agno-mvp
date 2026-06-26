"""
evidence/cli.py — `python -m evidence ...` (the spine's command surface).

Commands:
  import <path> [--workflow chat-transcript] [--domain platform_design]
                [--no-knowledge] [--meta k=v ...]
  tools                       list registered atomic tools
  workflows                   list named workflows
  verify <artifact_id> <path> re-hash a file against its custody row
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _cmd_import(args: argparse.Namespace) -> int:
    from evidence.workflows import NAMED_WORKFLOWS, run_chat_transcript, run_sms_xml

    if args.workflow not in NAMED_WORKFLOWS:
        print(f"unknown workflow {args.workflow!r}; available: {sorted(NAMED_WORKFLOWS)}", file=sys.stderr)
        return 2

    # workflow name -> (runner, default domain). The CLI --domain overrides only
    # when explicitly passed (argparse default differs per workflow below).
    runners = {
        "chat-transcript": run_chat_transcript,
        "sms-xml": run_sms_xml,
    }
    runner = runners[args.workflow]
    domain = args.domain
    if domain is None:  # not passed -> sensible per-workflow default
        domain = "timeline_relationship" if args.workflow == "sms-xml" else "platform_design"

    meta = {}
    for kv in args.meta or []:
        k, _, v = kv.partition("=")
        meta[k] = v

    knowledge = None
    if not args.no_knowledge:
        from db import create_knowledge

        knowledge = create_knowledge("platform", "platform_knowledge")

    summary = asyncio.run(
        runner(args.path, source_meta=meta, domain=domain, knowledge=knowledge)
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0 if summary.get("records_stored") is not None and "FAILED" not in str(summary.get("status", "")).upper() else 1


def _cmd_tools(_args: argparse.Namespace) -> int:
    from evidence.registry import load_builtin_tools, registry

    load_builtin_tools()
    print(json.dumps(registry.manifest(), indent=2))
    return 0


def _cmd_workflows(_args: argparse.Namespace) -> int:
    from evidence.workflows import NAMED_WORKFLOWS

    print(json.dumps(NAMED_WORKFLOWS, indent=2))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from evidence.custody import verify_artifact

    ok = verify_artifact(args.artifact_id, args.path)
    print(json.dumps({"artifact_id": args.artifact_id, "path": args.path, "integrity_ok": ok}))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence", description="Evidence spine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_imp = sub.add_parser("import", help="ingest a file through a named workflow")
    p_imp.add_argument("path")
    p_imp.add_argument("--workflow", default="chat-transcript")
    p_imp.add_argument("--domain", default=None,
                       help="knowledge domain tag (timeline_relationship|personal_history|platform_design|legal_strategy); "
                            "defaults to timeline_relationship for sms-xml, platform_design otherwise")
    p_imp.add_argument("--no-knowledge", action="store_true", help="skip the knowledge-engine step")
    p_imp.add_argument("--meta", nargs="*", help="source metadata k=v pairs")
    p_imp.set_defaults(fn=_cmd_import)

    p_tools = sub.add_parser("tools", help="list registered atomic tools")
    p_tools.set_defaults(fn=_cmd_tools)

    p_wf = sub.add_parser("workflows", help="list named workflows")
    p_wf.set_defaults(fn=_cmd_workflows)

    p_ver = sub.add_parser("verify", help="re-hash a file against its custody row")
    p_ver.add_argument("artifact_id")
    p_ver.add_argument("path")
    p_ver.set_defaults(fn=_cmd_verify)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
