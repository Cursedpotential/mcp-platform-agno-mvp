"""What to DO with a damaged file: rewrite it clean, flag it, quarantine it.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

Owner directive 2026-08-02: *"Write a new repaired file and quarantine the
damaged file. Or at the very least flag it as damaged so that it doesn't
continue being parsed out."*

Three escalating actions, and the DEFAULT IS THE SAFEST ONE:

    flag       append to a damage ledger. Touches nothing on disk. Ingest
               consults the ledger and skips/routes flagged artifacts, so a
               damaged file stops being silently re-parsed on every run.
    rewrite    stream the repaired chunks into a NEW clean file elsewhere.
               The original is not modified.
    quarantine MOVE the damaged original into a quarantine tree. Opt-in,
               dry-run by default, manifest first — see below.

WHY QUARANTINE IS NOT THE DEFAULT
---------------------------------
Two standing rules collide with moving evidence around:
  * never delete — quarantine, never remove (so this MOVES, never unlinks);
  * a full recursive manifest precedes any move job, and approval is explicit
    and never inferred.
So `quarantine_file()` refuses to act unless `dry_run=False` is passed
deliberately, and `plan_quarantine()` exists to produce the manifest first.

Moving an artifact also breaks every recorded path that points at it, which is
why flagging — which changes nothing — is what ingest actually needs in order
to stop re-parsing a known-bad file.

THE LEDGER IS KEYED BY sha256
-----------------------------
Paths move; content does not. Keying on the hash means a flagged artifact stays
flagged after a reorganisation, and re-flagging the same bytes under a new path
updates one entry rather than creating a phantom second damaged file.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from server.tools.repair.encoding import read_head
from server.tools.repair.pdf import sha256_file
from server.tools.repair.types import LOSSY, RepairEvent, RepairReport

#: Default ledger location. Under docs/reports/, which is gitignored — a damage
#: ledger carries real filenames and those can carry PII.
DEFAULT_LEDGER = Path("docs/reports/damaged-artifacts.jsonl")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class DamageEntry:
    sha256: str
    path: str
    size: int
    fmt: str
    status: str  # "damaged" | "repaired" | "quarantined" | "unrecoverable"
    flagged_at: str = field(default_factory=_now)
    repaired_path: str | None = None
    repaired_sha256: str | None = None
    quarantined_to: str | None = None
    chunks_ok: int = 0
    chunks_failed: int = 0
    lossy: int = 0
    truncated: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    @property
    def skip_ingest(self) -> bool:
        """Whether ingest should refuse this artifact and use the repair instead."""
        return self.status in ("damaged", "unrecoverable", "quarantined")


class DamageLedger:
    """Append-only JSONL of known-damaged artifacts, keyed by sha256.

    Append-only on purpose: a superseded verdict stays in the file and the
    latest entry for a hash wins on read. Rewriting history in a custody
    context is exactly the thing that cannot be allowed.
    """

    def __init__(self, path: Path | str = DEFAULT_LEDGER) -> None:
        self.path = Path(path)

    def _read_all(self) -> Iterator[DamageEntry]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield DamageEntry(**json.loads(line))
                except (ValueError, TypeError):
                    continue  # a malformed ledger line must not kill a sweep

    def entries(self) -> dict[str, DamageEntry]:
        """{sha256: latest entry}. Later lines supersede earlier ones."""
        out: dict[str, DamageEntry] = {}
        for entry in self._read_all():
            out[entry.sha256] = entry
        return out

    def append(self, entry: DamageEntry) -> DamageEntry:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def by_sha(self, sha256: str) -> DamageEntry | None:
        return self.entries().get(sha256)

    def by_path(self, path: Path | str) -> DamageEntry | None:
        """Cheap lookup that does NOT hash the file.

        Hashing every candidate on every ingest would cost a full read of the
        corpus, which defeats the point of flagging.
        """
        target = str(Path(path).resolve())
        latest: DamageEntry | None = None
        for entry in self._read_all():
            if entry.path == target:
                latest = entry
        return latest

    def should_skip(self, path: Path | str, verify_hash: bool = False) -> bool:
        """True when ingest should not parse this artifact as-is.

        `verify_hash=True` re-hashes and matches on content instead of path —
        correct after a reorganisation, but it costs a full read.
        """
        entry = self.by_path(path)
        if entry is None and verify_hash:
            entry = self.by_sha(sha256_file(Path(path)))
        return bool(entry and entry.skip_ingest)


# ------------------------------------------------------------------- rewrite


def _xml_root_tag(path: Path, default: str = "records") -> str:
    """Root tag from a bounded head read — needed to wrap a rewritten document."""
    import re

    head = read_head(path, 8192)
    match = re.search(rb"<\s*([A-Za-z_][\w.:-]*)[\s>/]", head.replace(b"<?xml", b"", 1))
    return match.group(1).decode("ascii", "replace") if match else default


def write_repaired(
    src: Path,
    dest: Path,
    fmt: str | None = None,
    report: RepairReport | None = None,
    overwrite: bool = False,
) -> RepairReport:
    """Stream the repaired chunks of `src` into a NEW clean file at `dest`.

    Writes incrementally — the repaired output is never assembled in memory,
    so this holds for a multi-gigabyte export exactly as it does for a small one.

    Refuses to write over its input for the same reason `repair_pdf` does: the
    original bytes are the custody anchor.
    """
    from server.tools.repair.detect import detect
    from server.tools.repair.engines import iter_chunks

    src, dest = Path(src), Path(dest)
    if src.resolve() == dest.resolve():
        raise ValueError("write_repaired refuses to overwrite its input")
    if dest.exists() and not overwrite:
        raise FileExistsError(f"{dest} exists; pass overwrite=True")

    detection = detect(src)
    fmt = fmt or detection.fmt
    rep = report if report is not None else RepairReport(fmt=fmt, encoding=detection.encoding)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "pdf":
        from server.tools.repair.pdf import repair_pdf

        result = repair_pdf(src, dest, overwrite=overwrite)
        rep.events.extend(result.events)
        if not result.ok:
            rep.chunks_failed += 1
        return rep

    if fmt in ("xml", "html"):
        root = _xml_root_tag(src)
        from lxml import etree

        with dest.open("wb") as fh:
            fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            fh.write(f"<{root}>\n".encode())
            for chunk in iter_chunks(src, fmt=fmt, report=rep):
                if chunk.ok and chunk.node is not None:
                    fh.write(etree.tostring(chunk.node, encoding="utf-8"))
                    fh.write(b"\n")
            fh.write(f"</{root}>\n".encode())
        return rep

    if fmt in ("json", "ndjson"):
        with dest.open("w", encoding="utf-8") as fh:
            if fmt == "json":
                fh.write("[\n")
            first = True
            for chunk in iter_chunks(src, fmt=fmt, report=rep):
                if not chunk.ok or chunk.node is None:
                    continue
                line = json.dumps(chunk.node, ensure_ascii=False, default=str)
                if fmt == "json":
                    fh.write(("" if first else ",\n") + "  " + line)
                    first = False
                else:
                    fh.write(line + "\n")
            if fmt == "json":
                fh.write("\n]\n")
        return rep

    if fmt == "csv":
        import csv as _csv

        # TWO PASSES, deliberately. A CSV header must be written before any row,
        # but overflow columns are only discovered when a ragged row shows up —
        # which may be the last line. Deriving fieldnames from the first row and
        # relying on extrasaction dropped the extras silently, which is exactly
        # the truncation iter_csv refuses to do.
        # Pass 1 is streaming and holds only two integers, so memory is flat;
        # it costs a second read of a file we are already rewriting.
        widest = 0
        base_fields: list[str] = []
        for chunk in iter_chunks(src, fmt="csv", report=RepairReport(fmt="csv")):
            if not chunk.ok or not isinstance(chunk.node, dict):
                continue
            if not base_fields:
                base_fields = [k for k in chunk.node if k != "__overflow__"]
            widest = max(widest, len(chunk.node.get("__overflow__") or ()))

        fields = base_fields + [f"__overflow_{i}__" for i in range(widest)]

        with dest.open("w", encoding="utf-8", newline="") as fh:
            writer = _csv.DictWriter(fh, fieldnames=fields, restval="")
            writer.writeheader()
            for chunk in iter_chunks(src, fmt="csv", report=rep):
                if not chunk.ok or not isinstance(chunk.node, dict):
                    continue
                row = dict(chunk.node)
                for i, extra in enumerate(row.pop("__overflow__", []) or []):
                    row[f"__overflow_{i}__"] = extra
                writer.writerow(row)
        return rep

    raise ValueError(f"write_repaired: no rewriter for format {fmt!r}")


# ------------------------------------------------------------------ flagging


def flag_damaged(
    path: Path,
    report: RepairReport,
    ledger: DamageLedger | None = None,
    repaired_path: Path | None = None,
    status: str | None = None,
    note: str = "",
) -> DamageEntry:
    """Record an artifact as damaged so ingest stops re-parsing it blindly.

    Changes nothing on disk beyond the ledger. This is the minimum the owner
    asked for and the safest of the three actions.
    """
    path = Path(path)
    ledger = ledger or DamageLedger()

    if status is None:
        if report.chunks_ok == 0:
            status = "unrecoverable"
        elif repaired_path is not None:
            status = "repaired"
        else:
            status = "damaged"

    entry = DamageEntry(
        sha256=sha256_file(path),
        path=str(path.resolve()),
        size=path.stat().st_size,
        fmt=report.fmt,
        status=status,
        repaired_path=str(Path(repaired_path).resolve()) if repaired_path else None,
        repaired_sha256=sha256_file(Path(repaired_path)) if repaired_path else None,
        chunks_ok=report.chunks_ok,
        chunks_failed=report.chunks_failed,
        lossy=report.lossy_count,
        truncated=report.truncated,
        events=[e.as_row() for e in report.events[:50]],
        note=note,
    )
    return ledger.append(entry)


# -------------------------------------------------------- recovery reports


DEFAULT_REPORT_DIR = Path("docs/reports/recovery")


def write_recovery_report(
    src: Path,
    status: str,
    events: list[Any],
    out_dir: Path | str = DEFAULT_REPORT_DIR,
    sha256: str = "",
    repaired_path: Path | None = None,
    repaired_sha256: str = "",
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write ONE report file per recovered artifact.

    Owner directive 2026-08-02: *"recovery should not be silent — I should
    create a new file in the report."* A console line scrolls away and a JSONL
    ledger is for machines; a recovery that altered how an exhibit reads needs a
    standalone, human-readable artifact that says what was changed and why.

    One file per artifact, named with the source stem plus a hash prefix, so two
    files with the same name in different folders cannot overwrite each other's
    report.
    """
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    digest = sha256 or sha256_file(src)
    dest = out_dir / f"{src.stem}.{digest[:12]}.recovery.md"

    lines: list[str] = [
        f"# Recovery report — {src.name}",
        "",
        f"> _Byline: server/tools/repair · {_now()}_",
        "",
        "## Artifact",
        "",
        f"- **Source:** `{src}`",
        f"- **sha256:** `{digest}`",
        f"- **Size:** {src.stat().st_size:,} bytes",
        f"- **Status:** **{status}**",
    ]
    if repaired_path:
        lines += [
            f"- **Repaired copy:** `{repaired_path}`",
            f"- **Repaired sha256:** `{repaired_sha256}`",
            "",
            "> The original is unmodified and remains the evidence of record.",
            "> The repaired copy is a RECONSTRUCTION and does not inherit its authority.",
        ]
    for key, value in (extra or {}).items():
        lines.append(f"- **{key}:** {value}")

    lines += ["", "## What was reconstructed", ""]
    if not events:
        lines.append("_No repair events recorded._")
    else:
        lines += ["| Severity | Kind | Detail |", "|---|---|---|"]
        for e in events:
            row = e.as_row() if hasattr(e, "as_row") else dict(e)
            detail = str(row.get("detail", "")).replace("|", "\\|")[:300]
            lines.append(f"| {row.get('severity','')} | `{row.get('kind','')}` | {detail} |")

    lossy = sum(
        1
        for e in events
        if (e.as_row() if hasattr(e, "as_row") else dict(e)).get("severity") == "lossy"
    )
    lines += [
        "",
        "## Verdict",
        "",
        (
            f"**{lossy} lossy event(s).** Content may have been discarded or "
            "machine-reconstructed; review before relying on this artifact."
            if lossy
            else "No lossy events — repairs were structural only, no content discarded."
        ),
        "",
    ]

    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


# --------------------------------------------------------------- quarantine


@dataclass(slots=True)
class QuarantinePlan:
    src: Path
    dest: Path
    size: int
    sha256: str


def plan_quarantine(paths: list[Path], quarantine_root: Path, base: Path) -> list[QuarantinePlan]:
    """THE MANIFEST. Build and review this before any move is executed.

    Standing rule: a full recursive manifest precedes any move job and approval
    is explicit, never inferred.
    """
    quarantine_root, base = Path(quarantine_root), Path(base)
    plans: list[QuarantinePlan] = []
    for p in paths:
        p = Path(p)
        try:
            rel = p.resolve().relative_to(base.resolve())
        except ValueError:
            rel = Path(p.name)
        plans.append(
            QuarantinePlan(src=p, dest=quarantine_root / rel, size=p.stat().st_size,
                           sha256=sha256_file(p))
        )
    return plans


def quarantine_file(
    plan: QuarantinePlan,
    ledger: DamageLedger | None = None,
    dry_run: bool = True,
) -> DamageEntry | None:
    """MOVE a damaged original into the quarantine tree. Never deletes.

    `dry_run=True` is the default and returns None without touching anything.
    Pass dry_run=False only against a reviewed manifest.

    The move is copy-then-verify-then-remove, not `os.replace`: the source and
    quarantine tree are routinely on different drives here, and a failed move
    that has already unlinked the source is unrecoverable.
    """
    if dry_run:
        return None

    ledger = ledger or DamageLedger()
    plan.dest.parent.mkdir(parents=True, exist_ok=True)
    if plan.dest.exists():
        raise FileExistsError(f"quarantine target already exists: {plan.dest}")

    shutil.copy2(plan.src, plan.dest)
    moved_sha = sha256_file(plan.dest)
    if moved_sha != plan.sha256:
        os.unlink(plan.dest)  # remove the bad COPY, never the source
        raise OSError(f"quarantine copy mismatch for {plan.src}; source left untouched")

    entry = DamageEntry(
        sha256=plan.sha256,
        path=str(plan.src.resolve()),
        size=plan.size,
        fmt="",
        status="quarantined",
        quarantined_to=str(plan.dest.resolve()),
        note="original moved to quarantine after verified copy",
    )
    ledger.append(entry)
    os.unlink(plan.src)  # only after the copy is byte-verified
    return entry


# ------------------------------------------------------------- orchestration


def handle_damaged(
    path: Path,
    report: RepairReport,
    repaired_dir: Path | None = None,
    ledger: DamageLedger | None = None,
    quarantine_root: Path | None = None,
    execute_quarantine: bool = False,
) -> DamageEntry:
    """Flag, optionally rewrite, optionally quarantine — in that order.

    Flagging happens FIRST and unconditionally, so that an artifact is marked
    known-bad even if the rewrite then fails.
    """
    path = Path(path)
    ledger = ledger or DamageLedger()

    repaired: Path | None = None
    if repaired_dir is not None:
        repaired = Path(repaired_dir) / path.name
        try:
            write_repaired(path, repaired, fmt=report.fmt, overwrite=True)
        except Exception as exc:  # noqa: BLE001 - a failed rewrite must not lose the flag
            repaired = None
            report.events.append(
                RepairEvent(
                    kind="rewrite_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                    severity=LOSSY,
                )
            )

    entry = flag_damaged(path, report, ledger=ledger, repaired_path=repaired)

    if quarantine_root is not None and execute_quarantine:
        plan = plan_quarantine([path], Path(quarantine_root), path.parent)[0]
        quarantine_file(plan, ledger=ledger, dry_run=False)

    return entry
