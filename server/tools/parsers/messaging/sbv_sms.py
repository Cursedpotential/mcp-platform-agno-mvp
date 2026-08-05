"""Atomic tool: SMS backup XML -> NormalizedRecords via SBV.
~~(PRIMARY parser)~~ — DEMOTED to shadow/diagnostic 2026-08-02.

DEMOTION (2026-08-02, parser-gap review P0-1 —
docs/HANDOFF-2026-08-02-sbv-chatminer-parser-gap-review.md): after upload this
adapter reads `GET /api/activity`, which returns the service account's ENTIRE
persistent corpus, not the records of the new import — a second upload can
attribute the first upload's records to the new artifact's custody event
(affirmative false provenance). Until SBV's upload returns an immutable
import_id and an import-scoped activity read exists, this tool must not be the
auto-selected parser. It stays registered and callable BY ID
(`registry.get("messages.sms-xml-sbv")`) for shadow comparison and diagnostics,
but `accept()` additionally requires the env `SBV_PRIMARY_ENABLED` — default
unset — so `registry.resolve("parse.sms-xml")` returns the pure-Python
`messages.sms-xml` first. Restore conditions = the review's acceptance
criteria (import-scoped results, primary/fallback equivalence on the golden
corpus, mandatory custody binding).

SBV ("SMS Backup Viewer", ghcr.io/lowcarbdev/sbv) is a Go service that parses
"SMS Backup & Restore" XML (sms/mms + call logs), converts MMS media
(HEIC/3GP/AMR), and serves the result over a session-authenticated REST API.
This module uploads the XML to SBV, waits for processing, fetches the parsed
messages + calls, and maps them into the SAME NormalizedRecord shape (incl.
forensic call-block flags) that the pure-Python server/tools/parsers/messaging/
sms_xml.py produces — so Workflow A, store, and the knowledge engine never
care which parser ran.

DUAL-PARSER / MESH SUBSTITUTION (ADR-0023, owner architecture): this tool and
sms_xml.py BOTH register capability `parse.sms-xml`. The registry returns them
in registration order ("sbv_sms" sorts before "sms_xml" under alphabetical
auto-discovery), ~~so SBV registers first naturally and is preferred~~ — but
since the 2026-08-02 demotion the accept() gate keeps SBV out of resolve()
unless SBV_PRIMARY_ENABLED is set, making sms_xml.py the effective primary.

Auth + endpoints: see server/tools/_sbv_client.py (session-cookie, /api/...).

Provenance: new module wrapping the SBV REST API (sbv-client.ts blueprint +
SBV_MCP_INTEGRATION.md). Forensic call-block logic mirrors sms_xml.py
(ported from dial-stack ConflictAnalysisApp).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.tools.registry import register
from server.tools._common import parse_timestamp, records_out
from server.tools._sbv_client import SBVClient, SBVError

OWNER = "owner"

# SBV message `type` (Android SMS Backup & Restore convention; same integers as
# sms_xml.py): meaning differs sms vs call.
_SMS_TYPE = {1: "received", 2: "sent", 3: "draft", 4: "outbox", 5: "failed", 6: "queued"}
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


def _map_message(msg: dict[str, Any]) -> NormalizedRecord | None:
    text = (msg.get("body") or msg.get("text") or "").strip()
    if text == "null":
        text = ""
    has_media = bool(msg.get("media_type") or msg.get("content_type") or msg.get("message_type"))
    # Keep-rule mirrors sms_xml._map_sms (the 516-dropped-MMS lesson): a
    # bodyless record is still an EVENT. Drop only when there is nothing to
    # anchor it — no timestamp, no counterparty, no media.
    if not text:
        has_counterparty = _counterparty(msg) != "unknown"
        if not msg.get("date") and not has_counterparty and not has_media:
            return None
    raw_type = _as_int(msg.get("type"), 0)
    direction = _SMS_TYPE.get(raw_type, "unknown")
    other = _counterparty(msg)
    # Outbound-authored types per SMS Backup & Restore: 2 sent, 4 outbox,
    # 5 failed, 6 queued — all written by the owner (messaging_csv precedent;
    # was `raw_type == 2` only, fixed 2026-08-02 for primary/fallback parity).
    role = OWNER if raw_type in (2, 4, 5, 6) else other
    channel = "mms" if has_media else "sms"
    attrs: dict[str, Any] = {
        "channel": channel,
        "direction": direction,
        "raw_type": str(raw_type),
        "address": msg.get("address") or msg.get("number") or "",
        "contact_name": msg.get("contact_name") or "",
        "parser": "sbv",
        "media_type": msg.get("media_type") or "",
        "thread_id": msg.get("thread_id"),
        # H2 per-record custody hash (sha256 of the RAW source XML element,
        # h2-rawelement-v1) as computed by SBV BEFORE normalization. This is
        # the evidence hash — NOT a hash of this NormalizedRecord.
        "content_hash": msg.get("content_hash") or "",
    }
    if not text:
        # Same keys as sms_xml.py so downstream never cares which parser ran.
        # Transport-only divergence (documented, review §2): SBV's activity
        # shape has no per-<part> list, so no attachments[]/b64_sha256 here —
        # attachment_count=1 is the minimum honest signal that media exists.
        attrs["body_present"] = False
        if has_media:
            attrs["attachment_count"] = 1
        else:
            attrs["empty_body"] = True
    return NormalizedRecord(
        record_type=RecordType.message,
        source="sms-xml",
        conversation_id=other,
        role=role,
        participants=[OWNER, other],
        content=text,
        occurred_at=_to_dt(msg.get("date")),
        disclosure_tier=DisclosureTier.contemporaneous,
        attrs=attrs,
    )


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


def _reconcile_custody(
    path: Path, payload: dict[str, Any], client: SBVClient, records: list[NormalizedRecord]
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
    except Exception:
        return None

    try:
        hashes = client.hashes("latest")
    except SBVError:
        return None
    sbv_file_hash = (hashes or {}).get("file_hash")
    sbv_chain_hash = (hashes or {}).get("chain_hash")
    # Per-record H2s SBV computed over the raw source elements (from the records
    # we just built). These are recorded as-is; H3 is stored from SBV, not
    # re-derived here, so record order does not need to match the chain order.
    sbv_record_hashes = [str(r.attrs.get("content_hash")) for r in records if r.attrs.get("content_hash")]

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
    """SBV may be auto-selected ONLY when BOTH hold:

    * ``SBV_SERVICE_PASS`` — the service is actually wired (as before), and
    * ``SBV_PRIMARY_ENABLED`` — the 2026-08-02 demotion override. Default
      UNSET: the parser-gap review's P0-1 (unscoped ``/api/activity`` can
      attribute another import's records to this artifact) bars SBV from
      forensic-primary eligibility until import-scoped reads exist. Setting
      this env is an explicit owner decision, not deployment plumbing.

    With either missing, accept() returns False and registry.resolve() falls
    straight through to the pure-Python sms_xml.py. The tool remains fetchable
    by id for shadow/diagnostic runs regardless."""
    return bool(os.getenv("SBV_SERVICE_PASS")) and bool(os.getenv("SBV_PRIMARY_ENABLED"))


@register(
    id="messages.sms-xml-sbv",
    capability="parse.sms-xml",
    description="SMS Backup & Restore XML via SBV (shadow/diagnostic; demoted from primary 2026-08-02 pending import-scoped reads) -> normalized message + call records, with forensic call-block flags + MMS media handling",
    # Only accept .xml AND only when SBV is wired AND the demotion override is
    # explicitly set; else defer to sms_xml.py.
    accept=lambda hint, size: hint.lower().endswith(".xml") and _sbv_enabled(),
    provenance="SBV REST API wrapper (lowcarbdev/sbv) — demoted to shadow 2026-08-02 (gap-review P0-1); sms_xml.py is the effective primary",
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

    client.upload(str(path))
    # SBV ALWAYS processes asynchronously (HandleUpload returns immediately with
    # processing=true and parses in a background goroutine) — so always wait.
    client.wait_for_processing()

    # /api/activity is SBV's "everything" stream: []ActivityItem, each wrapping
    # either a `message` or a `call` (there is no list-all-messages endpoint —
    # /api/messages requires an address). This avoids per-conversation fan-out.
    records: list[NormalizedRecord] = []
    for item in client.all_activity():
        kind = (item.get("type") or "").lower()
        if kind == "call":
            call = item.get("call") or item  # call fields may be nested or flat
            records.append(_map_call(call))
        else:
            msg = item.get("message") or item  # message fields nested or flat
            rec = _map_message(msg)
            if rec is not None:
                records.append(rec)

    if not records:
        # Empty result from SBV on a non-empty file is suspicious -> let the
        # workflow try the fallback rather than silently storing nothing.
        raise SBVError("SBV returned 0 records — falling back to pure-Python parser")

    # Forensic custody cross-check (opt-in; no-op where custody/DB is unavailable).
    custody_result = _reconcile_custody(path, payload, client, records)

    messages = sum(1 for r in records if r.record_type == RecordType.message)
    calls = sum(1 for r in records if r.record_type == RecordType.call)
    blocked = sum(1 for r in records if r.attrs.get("blocked"))
    extra: dict[str, Any] = {"parser": "sbv"}
    if custody_result is not None:
        extra["custody"] = custody_result
    return records_out(records, messages=messages, calls=calls, blocked_calls=blocked, **extra)
