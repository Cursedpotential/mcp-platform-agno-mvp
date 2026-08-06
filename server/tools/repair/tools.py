# Byline: Codex · GPT-5 · 2026-08-03
"""Registry adapters for the repair library.

Every operation is discoverable through the platform tool mesh.  Imports of
optional repair engines remain function-local, preserving the dep-light facade.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from server.tools.registry import register

_PROVENANCE = "server/tools/repair (commits 0ccb107 + 2d3f8e4)"


def _file(payload: dict[str, Any]) -> Path:
    path = Path(str(payload["path"]))
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _safe_derived_destination(payload: dict[str, Any], source: Path) -> Path:
    root = Path(str(payload["artifact_root"])).resolve()
    dest = Path(str(payload["dest"])).resolve()
    if dest == source.resolve() or root not in dest.parents:
        raise ValueError("repair destination must be a new child of artifact_root")
    return dest


def _require_manual_approval(payload: dict[str, Any]) -> None:
    if payload.get("_execution_mode") != "manual" or payload.get("approved") is not True:
        raise PermissionError("manual execution with explicit approved=true is required")


@register(
    id="repair.capabilities",
    capability="repair.inspect",
    description="List repair engines, dependency readiness, versions, and formats",
    provenance=_PROVENANCE,
)
def capabilities(_: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import available, manifest

    return {"engines": manifest(), "libraries": available()}


@register(
    id="repair.detect",
    capability="repair.detect",
    description="Bounded-head format, encoding, engine, and cloud-placeholder detection",
    provenance=_PROVENANCE,
)
def detect_source(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import detect, is_cloud_only

    path = _file(payload)
    return {"detection": asdict(detect(path)), "cloud_only": is_cloud_only(path)}


@register(
    id="repair.preview",
    capability="repair.preview",
    description="Stream repaired structural chunks and return bounded samples plus a repair report",
    provenance=_PROVENANCE,
)
def preview(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import RepairReport, iter_chunks

    path = _file(payload)
    limit = max(1, min(int(payload.get("sample_limit", 25)), 250))
    report = RepairReport()
    samples: list[dict[str, Any]] = []
    for chunk in iter_chunks(path, fmt=payload.get("format"), report=report):
        if len(samples) < limit:
            node = chunk.node
            identity = getattr(node, "tag", None)
            if identity is None and isinstance(node, dict):
                identity = list(node)[:20]
            samples.append(
                {
                    "index": chunk.index,
                    "kind": chunk.kind,
                    "ok": chunk.ok,
                    "error": chunk.error,
                    "identity": identity,
                    "repairs": [event.as_row() for event in chunk.repairs],
                }
            )
    return {"report": report.summary(), "events": [event.as_row() for event in report.events], "samples": samples}


@register(
    id="repair.write-derived",
    capability="repair.derive",
    description="Write a new repaired artifact without modifying the custody original",
    provenance=_PROVENANCE,
    execution_policy="manual_approval_required",
    side_effect="derived_write",
)
def write_derived(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import sha256_file, write_repaired

    _require_manual_approval(payload)
    source = _file(payload)
    dest = _safe_derived_destination(payload, source)
    report = write_repaired(source, dest, fmt=payload.get("format"), overwrite=False)
    return {
        "source": str(source.resolve()),
        "source_sha256": sha256_file(source),
        "derived": str(dest),
        "derived_sha256": sha256_file(dest),
        "report": report.summary(),
        "events": [event.as_row() for event in report.events],
    }


@register(
    id="repair.pdf-inspect",
    capability="repair.inspect",
    description="Read-only QPDF structural health inspection",
    accept=lambda hint, size: hint.lower().endswith(".pdf"),
    provenance=_PROVENANCE,
)
def pdf_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import inspect_pdf

    health = inspect_pdf(_file(payload), password=str(payload.get("password", "")))
    result = asdict(health)
    result["path"] = str(health.path)
    return result


@register(
    id="repair.pdf-derived",
    capability="repair.derive",
    description="Rebuild a damaged PDF into a separately hashed derived artifact",
    accept=lambda hint, size: hint.lower().endswith(".pdf"),
    provenance=_PROVENANCE,
    execution_policy="manual_approval_required",
    side_effect="derived_write",
)
def pdf_derived(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import repair_pdf

    _require_manual_approval(payload)
    source = _file(payload)
    dest = _safe_derived_destination(payload, source)
    result = repair_pdf(source, dest, password=str(payload.get("password", "")), overwrite=False)
    return result.provenance()


@register(
    id="repair.flag-damaged",
    capability="repair.flag",
    description="Append a SHA-keyed damage-ledger entry after a complete streaming repair assessment",
    provenance=_PROVENANCE,
    execution_policy="manual_approval_required",
    side_effect="append_only_ledger",
)
def flag(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import DamageLedger, RepairReport, flag_damaged, iter_chunks

    _require_manual_approval(payload)
    path = _file(payload)
    report = RepairReport()
    for _ in iter_chunks(path, fmt=payload.get("format"), report=report):
        pass
    ledger = DamageLedger(Path(str(payload["ledger_path"])))
    return asdict(flag_damaged(path, report, ledger=ledger, note=str(payload.get("note", ""))))


@register(
    id="repair.quarantine-plan",
    capability="repair.quarantine-plan",
    description="Create a read-only, hashed quarantine-copy manifest",
    provenance=_PROVENANCE,
)
def quarantine_plan(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import plan_quarantine

    paths = [Path(str(value)) for value in payload["paths"]]
    plans = plan_quarantine(paths, Path(str(payload["quarantine_root"])), Path(str(payload["base"])))
    return {"plans": [{"src": str(p.src), "dest": str(p.dest), "size": p.size, "sha256": p.sha256} for p in plans]}


@register(
    id="repair.quarantine-copy",
    capability="repair.quarantine",
    description="Create a verified quarantine copy; original remains and is skipped through the damage ledger",
    provenance=_PROVENANCE,
    execution_policy="manual_approval_required",
    side_effect="verified_copy_and_ledger",
)
def quarantine_copy(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.repair import DamageLedger, QuarantinePlan, quarantine_file

    _require_manual_approval(payload)
    dest = Path(str(payload["dest"]))
    if "to_be_deleted" not in {part.lower() for part in dest.parts}:
        raise ValueError("quarantine destination must be inside to_be_deleted")
    plan = QuarantinePlan(src=_file(payload), dest=dest, size=int(payload["size"]), sha256=str(payload["sha256"]))
    entry = quarantine_file(plan, ledger=DamageLedger(Path(str(payload["ledger_path"]))), dry_run=False)
    return {"entry": asdict(entry) if entry else None}


@register(
    id="repair.audit-verify",
    capability="repair.audit",
    description="Verify the tool gateway's append-only execution hash chain",
    provenance=_PROVENANCE,
)
def audit_verify(payload: dict[str, Any]) -> dict[str, Any]:
    from server.tools.gateway.execution_audit import verify_ledger

    return verify_ledger(Path(str(payload["ledger_path"])))
