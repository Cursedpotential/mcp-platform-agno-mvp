"""Parse ONE real file of each supported type and show what comes out.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

A test run, not an ingest. Nothing is written to the database — this answers the
only question worth answering first: for each format we claim to support, does the
parser produce records, and do those records look like the messages in the file?

Point it at a manifest of one sample per format:

    uv run python scripts/parser_smoke.py --manifest samples.json
    uv run python scripts/parser_smoke.py            # uses the built-in sample set

Manifest format: {"<label>": {"tool": "<tool id>", "path": "<file>"}, ...}
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
import traceback
from typing import Any

from server.tools.registry import load_builtin_tools, registry

# One real file per format. Deliberately the SMALLEST real example of each — the
# point is to see the shape, not to move volume.
DEFAULT_SAMPLES: dict[str, dict[str, str]] = {
    "SMS Backup & Restore (calls)": {
        "tool": "messages.sms-xml",
        "path": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence"
                r"\SMS Backup and Restore\calls-20251203231638.xml",
    },
    "SMS Backup & Restore (sms/mms)": {
        "tool": "messages.sms-xml",
        "path": r"D:\Backup\Case Bible BACKUP 2026-03-12\Legal_Knowledge_Base_Obsidian"
                r"\Evidence\Messaging\SMS\sms-2024-11-24.xml",
    },
    "Messaging CSV": {
        "tool": "messages.messaging-csv",
        "path": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence\Phone Records"
                r"\sms_conversations (5)\sms_conversations - KK Dump"
                r"\18102818263 Matt Katrina..csv",
    },
    "Facebook Messenger JSON": {
        "tool": "messages.facebook-json",
        "path": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence\FB Exports\FB DATA"
                r"\facebook-potentiallycursed85-2024-09-02-zSlyY1IT"
                r"\your_facebook_activity\messages\inbox"
                r"\jenevandewater_899968593421031\message_1.json",
    },
    "iMessage / SMS export HTML": {
        "tool": "messages.imessage-html",
        "path": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence\documents"
                r"\Export_18108455244.html",
    },
    "PDF document": {
        "tool": "documents.extract-text",
        "path": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence\documents"
                r"\_TO_SORT\a70a690eefd09b1d49c14508c08450ccf000601b.pdf",
    },
}

TRUNC = 90


def preview(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, default=str)
    s = " ".join(str(value).split())
    return s[:TRUNC] + ("..." if len(s) > TRUNC else "")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", help="JSON file of {label: {tool, path}}")
    ap.add_argument("--show", type=int, default=2, help="records to preview (default 2)")
    args = ap.parse_args()

    samples = DEFAULT_SAMPLES
    if args.manifest:
        samples = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))

    load_builtin_tools()

    ok = failed = skipped = 0
    for label, spec in samples.items():
        path = pathlib.Path(spec["path"])
        print("=" * 78)
        print(f"{label}   [{spec['tool']}]")
        print(f"  file: {path.name}")

        if not path.exists():
            print("  SKIP - file not found")
            skipped += 1
            continue
        print(f"  size: {path.stat().st_size / 1024:,.1f} KiB")

        try:
            tool = registry.get(spec["tool"])
        except Exception as e:
            print(f"  SKIP - no such tool: {e}")
            skipped += 1
            continue

        t0 = time.perf_counter()
        try:
            out = tool.run({"path": str(path)})
        except Exception as e:
            print(f"  FAILED - {type(e).__name__}: {preview(e)}")
            print("    " + traceback.format_exc(limit=1).splitlines()[-1])
            failed += 1
            continue
        dt = time.perf_counter() - t0

        records = out.get("records") or []
        stats = {k: v for k, v in out.items() if k not in ("records",)}
        print(f"  parsed {len(records):,} records in {dt:.2f}s")
        if stats:
            print(f"  stats: {preview(stats)}")

        for rec in records[: args.show]:
            r = rec if isinstance(rec, dict) else rec.__dict__
            print("  ---")
            for key in ("record_type", "occurred_at", "role", "conversation_id",
                        "content", "participants", "attrs"):
                if key in r:
                    print(f"    {key:16s} {preview(r[key])}")
        if not records:
            print("  (no records - the parser accepted the file and produced nothing)")
        ok += 1

    print("=" * 78)
    print(f"parsed OK: {ok}   failed: {failed}   skipped: {skipped}")


if __name__ == "__main__":
    main()
