"""Exercise server/tools/repair against real files, damaged files, and a big file.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

Sibling of scripts/parser_smoke.py. That one answers "does the parser produce
records?"; this one answers the three questions the repair layer exists for:

    --samples   does routing pick the right engine on REAL files?
    --damage    does a corrupted file still yield its intact records, and is
                the damage RECORDED rather than swallowed?
    --memory    does it actually stream, or does it quietly load the file?

`--memory` is the one that matters most and is the easiest to fake, so it does
not measure itself: it spawns two child processes, one reading with
`path.read_text()` and one with `iter_chunks()`, and reads each child's PEAK
WORKING SET from the OS. Peak working set is cumulative per process, which is
exactly why the two runs cannot share one.

Nothing here writes to a database, and nothing writes a repaired file.

    uv run --no-sync python scripts/repair_smoke.py            # all sections
    uv run --no-sync python scripts/repair_smoke.py --memory
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from server.tools.repair import (  # noqa: E402
    RepairReport,
    available,
    detect,
    iter_chunks,
    manifest,
)

SAMPLES: dict[str, str] = {
    "SMS B&R calls (xml)": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence"
    r"\SMS Backup and Restore\calls-20251203231638.xml",
    "SMS B&R sms/mms (xml)": r"D:\Backup\Case Bible BACKUP 2026-03-12"
    r"\Legal_Knowledge_Base_Obsidian\Evidence\Messaging\SMS\sms-2024-11-24.xml",
    "Messaging CSV": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence\Phone Records"
    r"\sms_conversations (5)\sms_conversations - KK Dump\18102818263 Matt Katrina..csv",
    "Facebook Messenger (json)": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence"
    r"\FB Exports\FB DATA\facebook-potentiallycursed85-2024-09-02-zSlyY1IT"
    r"\your_facebook_activity\messages\inbox\jenevandewater_899968593421031\message_1.json",
    "iMessage export (html)": r"C:\Users\matts\OneDrive\Case Bible\_SWEPT\Evidence"
    r"\documents\Export_18108455244.html",
}

RULE = "=" * 78


# --------------------------------------------------------------------- peak RSS

# A hand-rolled ctypes GetProcessMemoryInfo binding was tried first and
# silently returned 0 MiB for both arms — a measurement that fails open is
# worse than none, because it reads as a passing result. psutil is used
# instead: peak RSS on Windows, current RSS elsewhere.
_PEAK_SRC = r"""
import pathlib, sys, psutil

_P = psutil.Process()

def peak_mib():
    m = _P.memory_info()
    return getattr(m, 'peak_wset', m.rss) / 1048576

sys.path.insert(0, r'{repo}')
path = pathlib.Path(sys.argv[1])
mode = sys.argv[2]

if mode == 'stream':
    from server.tools.repair import iter_chunks, RepairReport
    base = peak_mib()
    rep = RepairReport()
    n = sum(1 for _ in iter_chunks(path, report=rep))
    print(f'{n}|{peak_mib():.1f}|{base:.1f}')
else:
    base = peak_mib()
    text = path.read_text(encoding='utf-8', errors='replace')
    n = text.count('<sms ') + text.count('<call ')
    print(f'{n}|{peak_mib():.1f}|{base:.1f}')
"""


def _run_child(path: pathlib.Path, mode: str) -> tuple[int, float, float]:
    src = _PEAK_SRC.replace("{repo}", str(REPO))
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        script = fh.name
    try:
        out = subprocess.run(
            [sys.executable, script, str(path), mode],
            capture_output=True, text=True, timeout=900,
        )
        if out.returncode != 0:
            raise SystemExit(f"child ({mode}) failed:\n{out.stderr[-2000:]}")
        n, peak, base = out.stdout.strip().splitlines()[-1].split("|")
        return int(n), float(peak), float(base)
    finally:
        pathlib.Path(script).unlink(missing_ok=True)


# ------------------------------------------------------------------- sections


def section_samples() -> None:
    print(RULE)
    print("REAL FILES - routing + chunking")
    print(RULE)
    for label, raw in SAMPLES.items():
        path = pathlib.Path(raw)
        print(f"\n{label}")
        print(f"  file: {path.name}")
        if not path.exists():
            print("  SKIP - not found")
            continue

        det = detect(path)
        print(f"  detected: {det.fmt} / {det.encoding} / engine={det.engine} "
              f"(confidence {det.confidence:.2f})")
        for note in det.notes:
            print(f"    note: {note}")
        if not det.usable:
            print("  SKIP - no engine")
            continue

        rep = RepairReport()
        try:
            chunks = list(iter_chunks(path, report=rep))
        except Exception as exc:  # noqa: BLE001 - smoke test reports, never masks
            print(f"  FAILED - {type(exc).__name__}: {exc}")
            continue

        s = rep.summary()
        print(f"  chunks: {len(chunks):,}  ok={s['chunks_ok']:,} failed={s['chunks_failed']:,} "
              f"repairs={s['repairs']} lossy={s['lossy']} clean={s['clean']}")
        if s["by_kind"]:
            print(f"  repairs by kind: {s['by_kind']}")
        for c in chunks[:1]:
            preview = c.node if isinstance(c.node, dict) else getattr(c.node, "attrib", c.node)
            print(f"  first {c.kind}: {str(preview)[:120]}")


def section_damage() -> None:
    """Corrupt a copy three ways and confirm intact records still land."""
    print(f"\n{RULE}")
    print("DAMAGED FILES - recovery + reporting  (copies only; originals untouched)")
    print(RULE)

    src = pathlib.Path(SAMPLES["SMS B&R calls (xml)"])
    if not src.exists():
        print("  SKIP - source sample not found")
        return

    good = src.read_bytes()
    baseline = len(list(iter_chunks(src)))
    print(f"\n  undamaged baseline: {baseline:,} chunks")

    cases: dict[str, bytes] = {
        "truncated mid-element (last 800 bytes cut)": good[:-800],
        "bare ampersand injected": good.replace(b"<call ", b'<call note="Tom & Jerry" ', 1),
        "NUL + control chars injected": good.replace(b"<call ", b"<call \x00\x0b\x1f", 1),
        "unclosed root element": good.replace(b"</calls>", b""),
    }

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="repair-damage-"))
    for label, blob in cases.items():
        p = tmp / "damaged.xml"
        p.write_bytes(blob)
        rep = RepairReport()
        try:
            n = sum(1 for _ in iter_chunks(p, fmt="xml", report=rep))
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {label}\n    RAISED {type(exc).__name__}: {exc}")
            continue
        s = rep.summary()
        kept = f"{n:,}/{baseline:,}"
        print(f"\n  {label}")
        print(f"    recovered {kept} chunks  lossy={s['lossy']} truncated={s['truncated']}")
        for e in rep.events[:3]:
            print(f"      [{e.severity}] {e.kind}: {e.detail[:90]}")
        if not rep.events and n == baseline:
            print("      (no events - libxml2 absorbed it with no information loss)")


def section_memory(size_mib: int = 400) -> None:
    print(f"\n{RULE}")
    print(f"STREAMING PROOF - synthetic {size_mib} MiB XML, peak working set per process")
    print(RULE)

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="repair-mem-"))
    big = tmp / "big.xml"
    row = (
        '  <sms protocol="0" address="+15551234567" date="1700000000000" type="1" '
        'body="the quick brown fox jumps over the lazy dog and keeps on going" '
        'readable_date="Nov 14, 2023 5:33:20 PM" contact_name="Test Person" />\n'
    ).encode()
    target = size_mib * 1024 * 1024
    print(f"\n  writing {big} ...")
    with big.open("wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<smses count="0">\n')
        written = 0
        block = row * 512
        while written < target:
            fh.write(block)
            written += len(block)
        fh.write(b"</smses>\n")
    actual = big.stat().st_size / 1048576
    print(f"  wrote {actual:,.0f} MiB")

    try:
        print("\n  [1/2] path.read_text()  - what nine parsers do today ...")
        n1, peak1, base1 = _run_child(big, "readtext")
        print(f"        records {n1:,}   peak working set {peak1:,.0f} MiB "
              f"(baseline {base1:,.0f})")

        print("  [2/2] iter_chunks()    - the repair layer ...")
        n2, peak2, base2 = _run_child(big, "stream")
        print(f"        records {n2:,}   peak working set {peak2:,.0f} MiB "
              f"(baseline {base2:,.0f})")

        print(f"\n  file size            {actual:,.0f} MiB")
        print(f"  read_text peak       {peak1:,.0f} MiB   ({peak1 / actual:.2f}x file)")
        print(f"  iter_chunks peak     {peak2:,.0f} MiB   ({peak2 / actual:.2f}x file)")
        if peak2 > 0:
            print(f"  reduction            {peak1 / peak2:.1f}x")
    finally:
        big.unlink(missing_ok=True)
        try:
            tmp.rmdir()
        except OSError:
            pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--damage", action="store_true")
    ap.add_argument("--memory", action="store_true")
    ap.add_argument("--size-mib", type=int, default=400)
    args = ap.parse_args()

    run_all = not (args.samples or args.damage or args.memory)

    print(RULE)
    print("REPAIR LAYER CAPABILITY")
    print(RULE)
    for lib, ver in available().items():
        print(f"  {'OK  ' if ver else 'MISS'} {lib:20s} {ver or '(not installed)'}")
    print()
    for m in manifest():
        print(f"  {'OK  ' if m['ready'] else 'MISS'} {m['format']:7s} -> {m['engine']:20s} "
              f"[{m['chunk_kind']}]")

    if run_all or args.samples:
        section_samples()
    if run_all or args.damage:
        section_damage()
    if run_all or args.memory:
        section_memory(args.size_mib)


if __name__ == "__main__":
    main()
