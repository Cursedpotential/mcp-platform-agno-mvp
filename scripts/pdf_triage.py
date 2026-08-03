"""Triage and repair damaged PDFs with QPDF. Read-only unless you pass --repair.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

    # look, change nothing (default)
    uv run --no-sync python scripts/pdf_triage.py "C:\\path\\to\\pdfs"

    # repair the damaged ones into a SEPARATE tree
    uv run --no-sync python scripts/pdf_triage.py "C:\\path" --repair --out "D:\\repaired"

    # one file
    uv run --no-sync python scripts/pdf_triage.py "C:\\path\\broken.pdf" --repair --out "D:\\repaired"

STATUSES
  healthy        opens cleanly, nothing rebuilt
  reconstructed  OPENS, BUT QPDF HAD TO REBUILD STRUCTURE TO DO IT. This is the
                 dangerous one: readers show it as fine, so it looks healthy
                 while actually being damaged. Repair these to get a stable file.
  encrypted      not damage — needs a password (--password)
  unrecoverable  QPDF could not rebuild it

Originals are NEVER modified and NEVER written to. `--repair` writes new files
under --out, mirroring the source tree, and prints the sha256 of both sides so
the derivation is recorded rather than assumed.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from server.tools.repair.pdf import (  # noqa: E402
    CLOUD_ONLY,
    EMPTY,
    ENCRYPTED,
    HEALTHY,
    NOT_PDF,
    RECONSTRUCTED,
    UNRECOVERABLE,
    qpdf_version,
    repair_pdf,
    scan_pdfs,
)
from server.tools.repair.quarantine import (  # noqa: E402
    DEFAULT_REPORT_DIR,
    write_recovery_report,
)

RULE = "=" * 78
_ORDER = [UNRECOVERABLE, RECONSTRUCTED, NOT_PDF, EMPTY, ENCRYPTED, HEALTHY, CLOUD_ONLY, "unknown"]
_MARK = {
    HEALTHY: "ok  ",
    RECONSTRUCTED: "WARN",
    ENCRYPTED: "LOCK",
    UNRECOVERABLE: "DEAD",
    EMPTY: "VOID",
    NOT_PDF: "WRNG",
    CLOUD_ONLY: "skip",
    "unknown": "?   ",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="PDF file, or a directory to sweep")
    ap.add_argument("--repair", action="store_true", help="write repaired copies (never in place)")
    ap.add_argument("--out", help="destination root for repaired files (required with --repair)")
    ap.add_argument("--password", default="", help="password for encrypted PDFs")
    ap.add_argument("--no-recurse", action="store_true")
    ap.add_argument("--csv", help="write the full triage table to this CSV")
    ap.add_argument("--limit", type=int, default=0, help="stop after N files (0 = all)")
    ap.add_argument(
        "--hydrate",
        action="store_true",
        help="ALSO inspect cloud-only files. This DOWNLOADS them from OneDrive. "
             "Off by default: an unguarded sweep hydrates the whole corpus onto local disk.",
    )
    ap.add_argument(
        "--report-dir",
        default=str(DEFAULT_REPORT_DIR),
        help=f"one recovery report file per damaged artifact (default {DEFAULT_REPORT_DIR})",
    )
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    if not root.exists():
        raise SystemExit(f"not found: {root}")
    if args.repair and not args.out:
        raise SystemExit("--repair needs --out (originals are never written to)")

    print(RULE)
    print(f"PDF TRIAGE   qpdf {qpdf_version()}   root: {root}")
    print(f"cloud-only files: {'INSPECTED (downloads them)' if args.hydrate else 'SKIPPED (no downloads)'}")
    print(RULE)

    results = []
    for n, health in enumerate(
        scan_pdfs(root, recursive=not args.no_recurse, password=args.password, hydrate=args.hydrate)
    ):
        if args.limit and n >= args.limit:
            print(f"\n  ... stopped at --limit {args.limit}; more files remain")
            break
        results.append(health)
        if health.status == CLOUD_ONLY:
            continue  # counted in the summary; not worth 1,500 identical lines
        mark = _MARK.get(health.status, "?   ")
        pages = f"{health.pages:>4}p" if health.pages is not None else "   -"
        size = f"{health.size / 1024:>8,.0f}K"
        print(f"  [{mark}] {pages} {size}  {health.path.name[:52]}")
        if health.error:
            print(f"           error: {health.error[:88]}")
        for e in health.events[:2]:
            print(f"           [{e.severity}] {e.kind}: {e.detail[:72]}")

    if not results:
        print("\n  no PDFs found")
        return

    print(f"\n{RULE}")
    print("SUMMARY")
    print(RULE)
    counts = {s: sum(1 for r in results if r.status == s) for s in _ORDER}
    for status in _ORDER:
        if counts[status]:
            print(f"  {_MARK[status]}  {status:16s} {counts[status]:>6,}")
    print(f"  {'':4}  {'total':16s} {len(results):>6,}")

    skipped = [r for r in results if r.status == CLOUD_ONLY]
    if skipped:
        print(f"\n  {len(skipped):,} cloud-only file(s) were NOT inspected.")
        print("  Reading them would download them from OneDrive onto local disk.")
        print("  Add --hydrate only if you want that.")

    damaged = [r for r in results if r.needs_repair]

    # One report file per damaged artifact. Recovery must never be silent:
    # a console line scrolls away, so each one gets a standalone artifact.
    if damaged:
        report_dir = pathlib.Path(args.report_dir)
        for health in damaged:
            written = write_recovery_report(
                health.path,
                status=health.status,
                events=health.events,
                out_dir=report_dir,
                sha256=health.sha256,
                extra={"pages": health.pages, "has_eof": health.has_eof,
                       "qpdf_warnings": len(health.warnings)},
            )
            print(f"  report -> {written}")

    if damaged and not args.repair:
        print(f"\n  {len(damaged):,} file(s) need repair. Re-run with:")
        print('    --repair --out "<destination>"')

    if args.csv:
        out = pathlib.Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(
                fh,
                fieldnames=["path", "status", "pages", "size", "sha256", "encrypted", "has_eof", "error"],
            )
            w.writeheader()
            for r in results:
                w.writerow({
                    "path": str(r.path), "status": r.status, "pages": r.pages,
                    "size": r.size, "sha256": r.sha256, "encrypted": r.encrypted,
                    "has_eof": r.has_eof, "error": r.error or "",
                })
        print(f"\n  triage table -> {out}")

    if not args.repair:
        return

    out_root = pathlib.Path(args.out)
    base = root if root.is_dir() else root.parent
    print(f"\n{RULE}")
    print(f"REPAIR -> {out_root}   (originals untouched)")
    print(RULE)

    ok = failed = 0
    for health in damaged:
        try:
            rel = health.path.relative_to(base)
        except ValueError:
            rel = pathlib.Path(health.path.name)
        dest = out_root / rel

        try:
            res = repair_pdf(health.path, dest, password=args.password, overwrite=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {health.path.name}: {type(exc).__name__}: {exc}")
            failed += 1
            continue

        if res.ok:
            ok += 1
            # Same deterministic filename as the pre-repair report, so this
            # supersedes it with the derivation now recorded.
            written = write_recovery_report(
                health.path,
                status=f"{health.status} -> repaired",
                events=res.events,
                out_dir=pathlib.Path(args.report_dir),
                sha256=res.source_sha256,
                repaired_path=dest,
                repaired_sha256=res.repaired_sha256,
                extra={"pages_before": res.pages_before, "pages_after": res.pages_after,
                       "qpdf": res.qpdf_version},
            )
            print(f"  OK   {health.path.name}")
            print(f"       {res.source_sha256[:16]} -> {res.repaired_sha256[:16]}  "
                  f"pages {res.pages_before} -> {res.pages_after}")
            print(f"       {dest}")
            print(f"       report -> {written}")
        else:
            failed += 1
            print(f"  FAIL {health.path.name}: {res.error}")

    print(f"\n  repaired {ok:,}   failed {failed:,}")
    print("  the originals are unmodified and remain the evidence of record")


if __name__ == "__main__":
    main()
