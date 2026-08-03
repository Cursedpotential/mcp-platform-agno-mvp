"""server/tools/repair — streaming repair + structural chunking for damaged text.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

Repairs the three text formats this corpus arrives in — XML, JSON, CSV (plus
HTML and NDJSON) — by routing each to a battle-tested engine and streaming
structural chunks out of it. See `AGENTS.md` in this directory for the design
rules; the short version:

    1. NEVER read a whole file. Every path here streams.
    2. NEVER write a repaired file back. Repair is in-memory, at parse time.
       The artifact of record stays the original bytes, because H1 is computed
       over them and a rewritten file breaks the custody chain.
    3. NEVER repair silently. Every fix is a RepairEvent with a severity, and
       `lossy` severity means evidence could have been lost.
    4. NEVER import a repair library at module scope (facade constraint —
       see engines.py).

Typical use:

    from pathlib import Path
    from server.tools.repair import detect, iter_chunks, RepairReport

    report = RepairReport()
    for chunk in iter_chunks(Path(p), report=report):
        if chunk.ok:
            handle(chunk.node)          # Element / dict / row
    print(report.summary())             # -> funnel counters for the ingest ledger

Import order below is dependency order on purpose: `engines` imports `chunkers`,
so binding `chunkers` first keeps the package's own partial initialisation from
mattering.
"""

from __future__ import annotations

from server.tools.repair import types as types  # noqa: F401  (re-export namespace)
from server.tools.repair.types import (
    COSMETIC,
    LOSSY,
    STRUCTURAL,
    Chunk,
    Detection,
    RepairEvent,
    RepairReport,
    Severity,
)
from server.tools.repair.encoding import (
    HEAD_BYTES,
    detect_encoding,
    open_binary,
    open_text,
    read_head,
)
from server.tools.repair.chunkers import (
    JSON_REPAIR_MAX_BYTES,
    iter_csv,
    iter_html,
    iter_json,
    iter_ndjson,
    iter_xml,
)
from server.tools.repair.engines import (
    ENGINES,
    EngineSpec,
    available,
    engine_for,
    iter_chunks,
    manifest,
    missing_for,
    spec_for,
)
from server.tools.repair.pdf import (
    ENCRYPTED,
    HEALTHY,
    RECONSTRUCTED,
    UNRECOVERABLE,
    PdfHealth,
    PdfRepairResult,
    inspect_pdf,
    qpdf_version,
    repair_pdf,
    repaired_bytes,
    scan_pdfs,
    sha256_file,
)
from server.tools.repair.cloud import (
    hydration_summary,
    is_cloud_only,
    partition_by_locality,
)
from server.tools.repair.quarantine import (
    DEFAULT_LEDGER,
    DEFAULT_REPORT_DIR,
    write_recovery_report,
    DamageEntry,
    DamageLedger,
    QuarantinePlan,
    flag_damaged,
    handle_damaged,
    plan_quarantine,
    quarantine_file,
    write_repaired,
)
from server.tools.repair.detect import detect

__all__ = [
    # routing / entry points
    "detect",
    "iter_chunks",
    # damaged-file lifecycle: flag (safe) -> rewrite -> quarantine (opt-in)
    "flag_damaged",
    "write_repaired",
    "handle_damaged",
    "plan_quarantine",
    "quarantine_file",
    "DamageLedger",
    "DamageEntry",
    "QuarantinePlan",
    "DEFAULT_LEDGER",
    "write_recovery_report",
    "DEFAULT_REPORT_DIR",
    # cloud placeholders — never hydrate a OneDrive tree by accident
    "is_cloud_only",
    "partition_by_locality",
    "hydration_summary",
    # structural PDF repair (QPDF/pikepdf) — distinct from text extraction
    "inspect_pdf",
    "repair_pdf",
    "repaired_bytes",
    "scan_pdfs",
    "sha256_file",
    "qpdf_version",
    "PdfHealth",
    "PdfRepairResult",
    "HEALTHY",
    "RECONSTRUCTED",
    "ENCRYPTED",
    "UNRECOVERABLE",
    # capability reporting
    "available",
    "manifest",
    "engine_for",
    "missing_for",
    "spec_for",
    "ENGINES",
    "EngineSpec",
    # per-format chunkers (use iter_chunks unless you are overriding routing)
    "iter_xml",
    "iter_html",
    "iter_json",
    "iter_ndjson",
    "iter_csv",
    # streaming IO
    "open_text",
    "open_binary",
    "detect_encoding",
    "read_head",
    "HEAD_BYTES",
    "JSON_REPAIR_MAX_BYTES",
    # types
    "Chunk",
    "Detection",
    "RepairEvent",
    "RepairReport",
    "Severity",
    "COSMETIC",
    "STRUCTURAL",
    "LOSSY",
    "types",
]
