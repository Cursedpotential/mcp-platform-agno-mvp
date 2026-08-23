# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""Atomic tool: SMS backup XML -> NormalizedRecords via SBV (PRIMARY parser).

SBV ("SMS Backup Viewer", ghcr.io/lowcarbdev/sbv) is the owner-chosen primary
SMS-XML engine: a Go service that parses "SMS Backup & Restore" XML (sms/mms +
call logs), converts MMS media (HEIC/3GP/AMR), and serves the result over a
session-authenticated REST API. This module streams the XML into one universal
import, validates import-scoped custody/accounting, fetches canonical records,
and maps them into the SAME NormalizedRecord shape (incl. forensic call-block flags) that the pure-Python
fallback server/tools/sms_xml.py produces — so Workflow A, store, and the
knowledge engine never care which parser ran.

DUAL-PARSER / MESH SUBSTITUTION (ADR-0023, owner architecture): this tool and
sms_xml.py BOTH register capability `parse.sms-xml`. SBV wins by an EXPLICIT
PRIORITY, not by import order: this module declares `priority=100` below,
sms_xml.py declares none (defaults to 0), and
`server/tools/registry.py:87` resolves a capability with

    sorted(matches, key=lambda tool: getattr(tool, "priority", 0), reverse=True)

sms_xml.py is the automatic fallback when SBV is unreachable/unhealthy or
rejects the input — note this module's `accept` predicate also requires
`_sbv_enabled()`, so when SBV is unwired it does not match at all and
resolution falls through to sms_xml.py, which performs NO custody hashing.

CAUTION: per-record custody reconciliation is additionally gated on the
`SBV_CUSTODY_ENABLED` env var (see `_reconcile_custody` below), which has no
default. Unset means custody reconciliation is skipped even on the SBV path.

Byline amendment: Claude Code · Opus 5 · 2026-08-23 — the previous version of
this paragraph explained precedence as alphabetical registration order
("`sbv_sms` sorts before `sms_xml`"). That was wrong: registry.py sorts by the
priority field, so renaming either file changes nothing. Outcome was the same,
mechanism was not.

Auth + endpoints: see server/tools/_sbv_client.py (session-cookie, /api/...).

Provenance: new module wrapping the SBV REST API (sbv-client.ts blueprint +
SBV_MCP_INTEGRATION.md). Forensic call-block logic mirrors sms_xml.py
(ported from dial-stack ConflictAnalysisApp).

RETIRED 2026-08-09: the pre-universal-import `_map_message` mapper moved to
_stale/sbv_sms_map_message_legacy.py (zero production callers; see that
file's docstring) — this module's live path is `_map_universal_record`.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools._common import parse_timestamp, records_out
from server.tools._sbv_client import SBVClient, SBVError
from server.tools.registry import register
from ._source_parties import enrich_message_parties

OWNER = "owner"

# SBV call `type` (Android SMS Backup & Restore convention; same integers as
# sms_xml.py). _SMS_TYPE (the message-side twin) retired with _map_message —
# see _stale/sbv_sms_map_message_legacy.py; _map_call still needs this one.
_CALL_TYPE = {1: "incoming", 2: "outgoing", 3: "missed", 4: "voicemail", 5: "rejected", 6: "refused_list"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_dt(value: Any):
    """SBV returns `date` as epoch milliseconds (number or numeric string) or an
    ISO string. Normalize to a tz-aware datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        ms = _as_int(value)
        return parse_timestamp(ms / 1000.0) if ms > 0 else None
    return parse_timestamp(str(value))


def _counterparty(msg: dict[str, Any]) -> str:
    name = (msg.get("contact_name") or "").strip()
    if name and name.lower() not in ("", "unknown", "(unknown)", "null"):
        return name
    return (msg.get("address") or msg.get("number") or "unknown").strip() or "unknown"


# _map_message (per-record mapper for the pre-universal-import SBV path) was
# retired to _stale/sbv_sms_map_message_legacy.py on 2026-08-09 (S2
# build-and-test-green task 4c): zero production callers (parse() below has
# called _map_universal_record exclusively since the universal import engine
# landed, PR #18), and it carried two known bugs (bodyless-media drop,
# outbound-role gap on types 4/5/6) that the 2026-08-02 parser-gap review
# flagged — see the archived file's docstring for the full trace.


def _map_call(call: dict[str, Any]) -> NormalizedRecord:
    raw_type = _as_int(call.get("type"), 0)
    label = _CALL_TYPE.get(raw_type, "unknown")
    duration = _as_int(call.get("duration"), 0)
    other = _counterparty(call)

    # Forensic call-blocking indicators (mirrors sms_xml.py / ConflictAnalysisApp).
    flags: list[str] = []
    if raw_type == 5:
        flags.append("call actively rejected")
    if raw_type == 6:
        flags.append("number on refuse/block list")
    if raw_type == 2 and duration == 0:
        flags.append("outgoing call with 0 duration - did not connect")
    blocked = bool(flags)

    content = f"{label.capitalize()} call with {other} (duration: {duration}s)"
    if flags:
        content += f" [FORENSIC FLAG: {', '.join(flags)}]"

    role = OWNER if raw_type == 2 else other
    return NormalizedRecord(
        record_type=RecordType.call,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=content,
        occurred_at=_to_dt(call.get("date")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs={
            "channel": "call",
            "call_type": label,
            "raw_type": str(raw_type),
            "duration_seconds": duration,
            "address": call.get("number") or call.get("address") or "",
            "contact_name": call.get("contact_name") or "",
            "blocked": blocked,
            "forensic_flags": flags,
            "parser": "sbv",
            # H2 per-record custody hash of the RAW <call> element (see _map_message).
            "content_hash": call.get("content_hash") or "",
        },
    )


# Owner-authored type codes for the universal-import role fallback (see
# _role_for_universal_record). Same convention as sms_xml.py's _SMS_TYPE/
# _CALL_TYPE tables and the (retired, see _stale/) legacy _map_message: for
# messages 2/sent, 4/outbox, 5/failed, 6/queued are all owner-authored; for
# calls only 2/outgoing is.
_UNIVERSAL_SMS_OWNER_TYPES = {"2", "4", "5", "6"}
_UNIVERSAL_CALL_OWNER_TYPES = {"2"}


def _role_for_universal_record(kind: str, metadata: dict[str, Any], participants: list[str]) -> str:
    """Derive authorship role for one universal-import row.

    FIX 2026-08-09 (S2 build-and-test-green task 4 — RE-PIN outbound-role
    guarantee): prefers an explicit "role"/"sender" key from SBV's metadata,
    but SBV's SMS-XML importer (vendored/sbv/internal/sms_xml_importer.go
    `messageSourceRecord`/`callSourceRecord`) projects `Metadata` straight from
    the RAW XML entry struct (`structMetadata(source)`) — for this format that
    metadata has NO "role"/"sender" key at all, only the raw attributes
    (`Type`, `Address`, `Body`, ...). Falling through unconditionally to
    ``participants[0]`` (the prior behavior) therefore resolved EVERY message
    and call to the counterparty regardless of direction, because SMS Backup &
    Restore's `address`/`number` attribute is the OTHER party's identifier on
    BOTH received and sent records — there is no address-based signal for "who
    sent it". That silently demoted every owner-authored SMS/MMS/call (types
    2/4/5/6) to counterparty-authored: the exact bug the 2026-08-02
    parser-gap review found and fixed in the legacy `_map_message()` (now
    retired to _stale/, see sbv_sms.py header), just reappearing on the
    universal-import path that superseded it. The separate ``sender`` field
    is neutral and source-principal governed; this function intentionally
    preserves the established legacy ``role`` contract.
    """
    explicit = metadata.get("role") or metadata.get("sender")
    if explicit:
        return str(explicit)
    raw_type = str(metadata.get("Type") or metadata.get("type") or "")
    owner_types = _UNIVERSAL_CALL_OWNER_TYPES if kind == "call" else _UNIVERSAL_SMS_OWNER_TYPES
    if raw_type in owner_types:
        return OWNER
    return str(participants[0]) if participants else "unknown"


def _map_universal_record(
    row: dict[str, Any], import_id: int, attachments_by_seq: dict[int, list[dict[str, Any]]]
) -> NormalizedRecord:
    """Project one import-scoped neutral SBV record after custody validation."""
    metadata_raw = row.get("metadata")
    metadata: dict[str, Any] = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
    kind = str(row.get("kind") or "message").lower()
    participants = row.get("participants")
    if not isinstance(participants, list):
        participants = []
    participants = [str(value) for value in participants if value not in (None, "")]
    role = _role_for_universal_record(kind, metadata, participants)
    occurred = row.get("occurred_at")
    occurred_at = parse_timestamp(occurred) if occurred not in (None, "") else None
    attrs: dict[str, Any] = {
        "parser": "sbv-universal",
        "import_id": import_id,
        "source_pos": row.get("source_pos"),
        "record_hash": row.get("record_hash") or "",
        "record_hash_canon": row.get("record_hash_canon") or "",
        "format": row.get("format") or "smsbackuprestore-xml",
        "status": row.get("status") or "accepted",
        **metadata,
    }
    seq = row.get("seq")
    if isinstance(seq, int) and seq in attachments_by_seq:
        attrs["attachments"] = attachments_by_seq[seq]
        attrs["attachment_count"] = len(attachments_by_seq[seq])
    record_type = RecordType.call if kind == "call" else RecordType.message
    return NormalizedRecord(
        record_type=record_type,
        source="sms-xml",
        conversation_id=str(metadata.get("conversation_id") or metadata.get("address") or "unknown"),
        role=role,
        participants=participants,
        sender=str(row.get("sender")) if row.get("sender") else None,
        recipients=row.get("recipients") if isinstance(row.get("recipients"), list) else [],
        content=str(row.get("content") or ""),
        occurred_at=occurred_at,
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs=attrs,
    )


def _local_h1(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _validate_universal_import(
    path: Path, summary: dict[str, Any], client: SBVClient
) -> tuple[int, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch by-ID pages and verify custody/accounting before projection."""
    raw_id = summary.get("import_id")
    if not isinstance(raw_id, int) or raw_id <= 0:
        raise SBVError("SBV universal upload did not return a valid import_id")
    import_id = raw_id
    detail = client.import_detail(import_id)
    detail_id = detail.get("import_id")
    if str(detail_id) != str(import_id):
        raise SBVError(f"SBV import identity mismatch: requested {import_id}, got {detail_id!r}")
    if detail.get("status") == "error":
        raise SBVError(f"SBV import {import_id} failed: {detail.get('error') or 'unknown error'}")
    if detail.get("status") not in (None, "completed"):
        raise SBVError(f"SBV import {import_id} is not terminal: {detail.get('status')!r}")
    h1 = str(detail.get("file_hash") or summary.get("file_hash") or "").lower()
    if h1 != _local_h1(path):
        raise SBVError(f"SBV H1 mismatch for import {import_id}")

    expected_h1 = "h1-rawbytes-v1"
    expected_h2 = "h2-rawelement-v1"
    expected_h3 = "h3-chain-sbv-genesisempty-v1"
    if detail.get("file_hash_canon") != expected_h1:
        raise SBVError(f"SBV import {import_id} has unexpected H1 canon")
    if detail.get("record_hash_canon") != expected_h2:
        raise SBVError(f"SBV import {import_id} has unexpected H2 canon")
    if detail.get("chain_canon") != expected_h3:
        raise SBVError(f"SBV import {import_id} has unexpected H3 canon")

    records = client.import_records(import_id)
    rejections = client.import_rejections(import_id)
    attachments = client.import_attachments(import_id)
    all_rows = [*records, *rejections]
    for row in all_rows:
        if str(row.get("import_id")) != str(import_id):
            raise SBVError(f"SBV import {import_id} returned a row bound to another import")
    accepted = sum(1 for row in records if row.get("status", "accepted") == "accepted")
    dedup = sum(1 for row in records if row.get("status") == "deduplicated")
    rejected = len(rejections)
    encountered = accepted + dedup + rejected
    expected_encountered = detail.get("encountered_count")
    if isinstance(expected_encountered, int) and expected_encountered != encountered:
        raise SBVError(f"SBV import {import_id} encountered count mismatch")
    for field, actual in (
        ("accepted_count", accepted),
        ("rejected_count", rejected),
        ("deduplicated_count", dedup),
    ):
        expected = detail.get(field)
        if isinstance(expected, int) and expected != actual:
            raise SBVError(f"SBV import {import_id} {field} mismatch")
    claimed = detail.get("claimed_count")
    if isinstance(claimed, int) and claimed != encountered:
        raise SBVError(f"SBV import {import_id} claimed count mismatch")
    if detail.get("reconciliation") == "discrepancy":
        raise SBVError(f"SBV import {import_id} reports reconciliation discrepancy")
    if encountered != accepted + dedup + rejected:
        raise SBVError(f"SBV import {import_id} count reconciliation failed")

    h2_rows = sorted((row for row in all_rows if row.get("record_hash")), key=lambda row: _as_int(row.get("seq"), 0))
    for row in h2_rows:
        canon = row.get("record_hash_canon")
        if canon != expected_h2:
            raise SBVError(f"SBV import {import_id} contains an unexpected record canon")
    chain = ""
    for row in h2_rows:
        h2 = str(row["record_hash"]).lower()
        chain = hashlib.sha256((chain + "\n" + h2).encode("utf-8")).hexdigest()
    expected_chain = str(detail.get("chain_hash") or summary.get("chain_hash") or "").lower()
    if chain != expected_chain:
        raise SBVError(f"SBV H3 mismatch for import {import_id}")
    hashed_count = detail.get("record_count")
    if isinstance(hashed_count, int) and hashed_count != len(h2_rows):
        raise SBVError(f"SBV import {import_id} hashed count mismatch")
    return import_id, detail, records, rejections, attachments


def _reconcile_custody(
    path: Path,
    payload: dict[str, Any],
    client: SBVClient,
    records: list[NormalizedRecord],
    import_id: int | None = None,
) -> dict[str, Any] | None:
    """Forensic custody cross-check (Phase 4): pull SBV's independently-computed
    H1/H3 for this import + the per-record H2s, and reconcile against our OWN H1
    via the custody gate (verified vs integrity_violation, plus H2/H3 evidence
    rows). SBV holds no DB creds — every write happens in custody.py.

    Opt-in (SBV_CUSTODY_ENABLED) and defensively lazy: the slim tools-facade has
    no sqlalchemy, so importing custody there would fail — we skip cleanly. This
    is why the custody import is INSIDE the function, never at module top (which
    load_builtin_tools() imports to register the parser)."""
    if not os.getenv("SBV_CUSTODY_ENABLED"):
        return None
    try:
        from server.evidence import custody  # lazy: pulls in sqlalchemy — facade lacks it
    except Exception:  # noqa: BLE001 - facade intentionally degrades without SQLAlchemy
        return None

    try:
        # Universal imports are always attributed by their returned ID.  The
        # ``latest`` fallback remains only for old callers that invoke this
        # opt-in helper directly before the universal cutover.
        requested_id = import_id or payload.get("import_id")
        if requested_id is None:
            requested_id = "latest"
        hashes = client.hashes(requested_id)
    except SBVError:
        return None
    sbv_file_hash = (hashes or {}).get("file_hash")
    sbv_chain_hash = (hashes or {}).get("chain_hash")
    # Per-record H2s SBV computed over the raw source elements (from the records
    # we just built). These are recorded as-is; H3 is stored from SBV, not
    # re-derived here, so record order does not need to match the chain order.
    sbv_record_hashes = [
        str(r.attrs.get("record_hash") or r.attrs.get("content_hash"))
        for r in records
        if r.attrs.get("record_hash") or r.attrs.get("content_hash")
    ]

    source_meta = dict(payload.get("source_meta") or {})
    source_meta.setdefault("source_type", "chat_export")
    source_meta.setdefault("source_platform", "sms-backup-restore")
    source_meta.setdefault("acquisition_source", "sbv")
    return custody.reconcile_sbv_import(
        path,
        source_meta,
        sbv_file_hash=sbv_file_hash,
        sbv_record_hashes=sbv_record_hashes,
        sbv_chain_hash=sbv_chain_hash,
    )


def _sbv_enabled() -> bool:
    """SBV is the primary ONLY when explicitly wired (URL reachable + service
    creds present). Without creds, accept() returns False so the registry falls
    straight through to the pure-Python sms_xml.py fallback — no hard dep on a
    running SBV for SMS-XML to work."""
    return bool(os.getenv("SBV_SERVICE_PASS"))


@register(
    id="messages.sms-xml-sbv",
    capability="parse.sms-xml",
    description="SMS Backup & Restore XML via SBV (primary) -> normalized message + call records, with forensic call-block flags + MMS media handling",
    # Only accept .xml AND only when SBV is wired; else defer to sms_xml.py.
    accept=lambda hint, size: hint.lower().endswith(".xml") and _sbv_enabled(),
    priority=100,
    provenance="SBV REST API wrapper (lowcarbdev/sbv) — primary SMS-XML parser; sms_xml.py is the pure-Python fallback",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    if not path.is_file():
        raise FileNotFoundError(f"sbv: file not found: {path}")

    client = SBVClient(
        base_url=payload.get("sbv_base_url"),
        username=payload.get("sbv_user"),
        password=payload.get("sbv_pass"),
    )

    # Fail loudly so the workflow's substitution layer moves to sms_xml.py.
    if not client.health():
        raise SBVError("SBV not healthy/reachable — falling back to pure-Python parser")

    summary = client.import_file(str(path), filename=path.name, format="smsbackuprestore-xml")
    import_id, detail, rows, rejections, attachments = _validate_universal_import(path, summary, client)
    attachments_by_seq: dict[int, list[dict[str, Any]]] = {}
    for item in attachments:
        raw_seq = item.get("record_seq")
        if raw_seq in (None, ""):
            continue
        seq = _as_int(raw_seq, -1)
        if seq < 0:
            continue
        # Only safe manifest metadata crosses into the normalized projection;
        # binary bytes are available through SBVClient.download_attachment_stream.
        attachments_by_seq.setdefault(seq, []).append(
            {
                "id": item.get("id"),
                "original_name": item.get("original_name"),
                "mime_type": item.get("mime_type"),
                "decoded_hash": item.get("decoded_hash"),
                "byte_count": item.get("byte_count"),
                "record_hash": item.get("record_hash"),
            }
        )

    records = enrich_message_parties(
        [_map_universal_record(row, import_id, attachments_by_seq) for row in rows], payload
    )
    if not records and not rejections:
        raise SBVError("SBV returned no canonical records or rejections for a non-empty import")

    # Forensic custody cross-check (opt-in; no-op where custody/DB is unavailable).
    custody_result = _reconcile_custody(path, payload, client, records, import_id)

    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    blocked = sum(1 for r in records if r.attrs.get("blocked"))
    extra: dict[str, Any] = {
        "parser": "sbv-universal",
        "import_id": import_id,
        "rejections": len(rejections),
        "attachments": len(attachments),
        "reconciliation": detail.get("reconciliation"),
        "chain_hash": detail.get("chain_hash") or summary.get("chain_hash"),
    }
    if custody_result is not None:
        extra["custody"] = custody_result
    return records_out(records, messages=messages, calls=calls, blocked_calls=blocked, **extra)
