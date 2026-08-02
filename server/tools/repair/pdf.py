"""Structural PDF repair via QPDF (pikepdf) — rebuild the file, not the text.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

This is REPAIR, not extraction. `server/tools/extractors/extract_text.py` reads
text out of a PDF that already opens; this module deals with a PDF that does
NOT open — a damaged cross-reference table, a missing trailer, a truncated
tail, a broken object stream. Extraction cannot run until this has.

WHY QPDF
--------
A PDF's cross-reference table maps object numbers to byte offsets and lives at
the END of the file. Damage it and every object becomes unreachable even though
the object bytes are still sitting there intact. QPDF's recovery scans the
whole file for object markers and REBUILDS that table from what it finds, which
is why a file that no reader will open often still yields all of its pages.
pikepdf is the Python binding and ships libqpdf in its wheels, so there is no
system package to install.

THE CUSTODY RULE THIS MODULE ENFORCES
-------------------------------------
Repairing a PDF necessarily produces DIFFERENT BYTES — unlike the XML/CSV/JSON
paths, where repair happens in the parse and the file on disk is never touched.
Different bytes mean a different H1, and H1 is the custody anchor.

So `repair_pdf()` REFUSES to write over its input. It always produces a new,
derived artifact, and it records the sha256 of both sides so the derivation is
provable: "exhibit N-repaired was produced from exhibit N (sha256 abc...) by
QPDF 12.x on this date, and here is what QPDF reported it had to reconstruct."
An in-place repair would destroy the original and silently break the chain.

Repair is therefore always LOSSY severity at the artifact level: not because
content is necessarily lost, but because the resulting file is a
RECONSTRUCTION and must never inherit the original's authority unexamined.
"""

from __future__ import annotations

import hashlib
import io


from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from server.tools.repair.types import LOSSY, STRUCTURAL, RepairEvent

#: Status values, worst last.
HEALTHY = "healthy"
RECONSTRUCTED = "reconstructed"  # opens, but QPDF had to rebuild something
ENCRYPTED = "encrypted"  # not damage — needs a password
UNRECOVERABLE = "unrecoverable"

#: Substrings QPDF emits when it has had to rebuild rather than read.
_RECONSTRUCTION_MARKERS = (
    "reconstruct",
    "cross-reference",
    "xref",
    "trailer",
    "recover",
    "damaged",
    "invalid stream length",
    "object stream",
)


@dataclass(slots=True)
class PdfHealth:
    path: Path
    status: str
    pages: int | None = None
    encrypted: bool = False
    linearized: bool | None = None
    has_eof: bool = True
    sha256: str = ""
    size: int = 0
    warnings: list[str] = field(default_factory=list)
    events: list[RepairEvent] = field(default_factory=list)
    error: str | None = None

    @property
    def needs_repair(self) -> bool:
        return self.status in (RECONSTRUCTED, UNRECOVERABLE)

    @property
    def openable(self) -> bool:
        return self.status in (HEALTHY, RECONSTRUCTED)

    def summary(self) -> dict[str, Any]:
        return {
            "file": self.path.name,
            "status": self.status,
            "pages": self.pages,
            "size": self.size,
            "sha256": self.sha256[:16],
            "encrypted": self.encrypted,
            "has_eof": self.has_eof,
            "warnings": len(self.warnings),
            "error": self.error,
        }


@dataclass(slots=True)
class PdfRepairResult:
    source: Path
    dest: Path | None
    ok: bool
    source_sha256: str = ""
    repaired_sha256: str = ""
    pages_before: int | None = None
    pages_after: int | None = None
    qpdf_version: str = ""
    events: list[RepairEvent] = field(default_factory=list)
    error: str | None = None

    def provenance(self) -> dict[str, Any]:
        """The derivation record. This is what belongs in the custody ledger."""
        return {
            "source": str(self.source),
            "source_sha256": self.source_sha256,
            "derived": str(self.dest) if self.dest else None,
            "derived_sha256": self.repaired_sha256,
            "method": f"qpdf {self.qpdf_version} structural repair (pikepdf)",
            "pages_before": self.pages_before,
            "pages_after": self.pages_after,
            "reconstructions": [e.as_row() for e in self.events],
            "ok": self.ok,
        }


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """Streaming digest — a corrupt PDF can still be enormous."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def qpdf_version() -> str:
    try:
        import pikepdf

        return str(pikepdf.__libqpdf_version__)
    except Exception:
        return "unavailable"


def _warnings_of(pdf: Any) -> list[str]:
    """QPDF's recovery report. `Pdf.get_warnings()` is the ONLY reliable source.

    A file whose xref was rebuilt opens CLEANLY: no exception, correct page
    count, and nothing on the `pikepdf` logger or in Python's `warnings`
    machinery. Both of those were tried here first and captured NOTHING on a
    file QPDF had demonstrably reconstructed — it reported `healthy` for a
    corrupted xref, which is the precise silent-repair failure this package
    exists to prevent.

    `get_warnings()` on the open Pdf returns the real list, e.g.
    "file is damaged" / "can't find startxref" /
    "Attempting to reconstruct cross-reference table". It must be read INSIDE
    the `with` block — the warnings die with the Pdf object.
    """
    try:
        return [str(w) for w in pdf.get_warnings()]
    except Exception:
        return []


def _tail_has_eof(path: Path, window: int = 2048) -> bool:
    """A well-formed PDF ends with %%EOF. Its absence means a truncated file."""
    size = path.stat().st_size
    with path.open("rb") as fh:
        fh.seek(max(0, size - window))
        return b"%%EOF" in fh.read()


def _classify(messages: list[str]) -> list[RepairEvent]:
    events: list[RepairEvent] = []
    for msg in messages:
        low = msg.lower()
        if any(m in low for m in _RECONSTRUCTION_MARKERS):
            events.append(
                RepairEvent(
                    kind="pdf_structure_reconstructed",
                    detail=msg[:400],
                    severity=STRUCTURAL,
                )
            )
        else:
            events.append(
                RepairEvent(kind="pdf_warning", detail=msg[:400], severity=STRUCTURAL)
            )
    return events


def inspect_pdf(path: Path, password: str = "") -> PdfHealth:
    """READ-ONLY triage. Never writes anything, never modifies the input.

    Answers the only question that matters before a bulk run: is this file
    fine, silently reconstructed, locked, or actually dead?
    """
    path = Path(path)
    health = PdfHealth(path=path, status=UNRECOVERABLE)

    try:
        health.size = path.stat().st_size
        health.sha256 = sha256_file(path)
        health.has_eof = _tail_has_eof(path)
    except OSError as exc:
        health.error = f"unreadable: {exc}"
        return health

    try:
        import pikepdf
    except ImportError:
        health.status = "unknown"
        health.error = "pikepdf not installed"
        return health

    try:
        # suppress_warnings=True only stops qpdf PRINTING to stderr; the
        # warnings are still retrievable via get_warnings(). Without it a sweep
        # over thousands of files buries its own report in qpdf chatter.
        with pikepdf.open(
            str(path), password=password, attempt_recovery=True, suppress_warnings=True
        ) as pdf:
            health.pages = len(pdf.pages)
            health.encrypted = bool(pdf.is_encrypted)
            try:
                health.linearized = bool(pdf.is_linearized)
            except Exception:
                health.linearized = None
            # Read INSIDE the context manager — the warnings go away with the Pdf.
            health.warnings = _warnings_of(pdf)
    except pikepdf.PasswordError:
        health.status = ENCRYPTED
        health.encrypted = True
        health.error = "password required"
        return health
    except Exception as exc:
        health.status = UNRECOVERABLE
        health.error = f"{type(exc).__name__}: {exc}"
        return health

    health.events = _classify(health.warnings)
    # ANY warning from qpdf means the file is not clean. An earlier version
    # gated this on _RECONSTRUCTION_MARKERS matching, which let a file that
    # made qpdf say "can't find PDF header" through as `healthy` — the marker
    # list decides what KIND of event to record, never WHETHER damage occurred.
    health.status = RECONSTRUCTED if (health.warnings or not health.has_eof) else HEALTHY

    if not health.has_eof:
        health.events.append(
            RepairEvent(
                kind="pdf_missing_eof",
                detail="no %%EOF marker in the file tail — truncated or still being written",
                severity=LOSSY,
            )
        )
    return health


def repair_pdf(
    path: Path,
    dest: Path,
    password: str = "",
    overwrite: bool = False,
    linearize: bool = False,
) -> PdfRepairResult:
    """Rebuild a damaged PDF into a NEW file. Refuses to touch the original.

    `dest` must not resolve to `path`. That check is not a convenience — an
    in-place repair would replace the custody-anchored bytes with a
    reconstruction and there would be no way back.
    """
    path = Path(path)
    dest = Path(dest)
    result = PdfRepairResult(source=path, dest=dest, ok=False, qpdf_version=qpdf_version())

    if path.resolve() == dest.resolve():
        raise ValueError(
            "repair_pdf refuses to write over its input: repairing changes the "
            "bytes, and the original is the custody anchor. Choose a new dest."
        )
    if dest.exists() and not overwrite:
        raise FileExistsError(f"{dest} exists; pass overwrite=True to replace the DERIVED file")

    health = inspect_pdf(path, password=password)
    result.source_sha256 = health.sha256
    result.pages_before = health.pages
    result.events = list(health.events)

    if not health.openable:
        result.error = health.error or f"status={health.status}"
        result.dest = None
        return result

    import pikepdf

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with pikepdf.open(
            str(path), password=password, attempt_recovery=True, suppress_warnings=True
        ) as pdf:
            pdf.save(str(dest), linearize=linearize, fix_metadata_version=True)
            result.pages_after = len(pdf.pages)
            save_warnings = _warnings_of(pdf)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        result.dest = None
        return result

    # Only add what inspect_pdf did not already record, so the derivation record
    # does not double-count the same reconstruction.
    known = {e.detail for e in result.events}
    result.events.extend(e for e in _classify(save_warnings) if e.detail not in known)
    result.repaired_sha256 = sha256_file(dest)
    result.ok = True
    result.events.append(
        RepairEvent(
            kind="pdf_derived_artifact",
            detail=(
                f"structural repair produced a NEW artifact "
                f"({result.source_sha256[:12]} -> {result.repaired_sha256[:12]}); "
                f"the original is unmodified and remains the evidence of record"
            ),
            severity=LOSSY,
        )
    )
    return result


def scan_pdfs(root: Path, recursive: bool = True, password: str = "") -> Iterator[PdfHealth]:
    """Triage every PDF under `root`. Read-only — repairs nothing."""
    root = Path(root)
    paths = root.rglob("*.pdf") if recursive else root.glob("*.pdf")
    if root.is_file():
        paths = iter([root])
    for p in sorted(paths):
        try:
            yield inspect_pdf(p, password=password)
        except Exception as exc:  # noqa: BLE001 - a triage sweep never dies on one file
            yield PdfHealth(path=p, status=UNRECOVERABLE, error=f"{type(exc).__name__}: {exc}")


def repaired_bytes(path: Path, password: str = "") -> bytes:
    """In-memory repair for callers that do not want a derived file on disk.

    Convenience for the extraction path: repair, hand the bytes to the
    extractor, keep nothing. Bounded by available RAM, so prefer `repair_pdf`
    for anything large.
    """
    import pikepdf

    buf = io.BytesIO()
    with pikepdf.open(str(path), password=password, attempt_recovery=True) as pdf:
        pdf.save(buf)
    return buf.getvalue()
