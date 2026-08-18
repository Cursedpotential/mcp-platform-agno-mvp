# Byline: Codex · GPT-5 · 2026-08-18
"""Neutral sender/recipient projection shared by messaging parsers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from server.contracts.records import MessageCorpus, MessageParticipant, NormalizedRecord, RecordType

_SELF_LABELS = {"self", "me", "you", "owner", "ownerrole"}


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def source_principal(payload: Mapping[str, Any] | None) -> str | None:
    """Return only an explicitly supplied source device/account principal."""
    if not payload:
        return None
    direct = _text(payload.get("source_principal"))
    meta = payload.get("source_meta")
    nested = _text(meta.get("source_principal")) if isinstance(meta, Mapping) else None
    return direct or nested


def message_corpus(payload: Mapping[str, Any] | None) -> MessageCorpus | None:
    if not payload:
        return None
    value = payload.get("message_corpus")
    meta = payload.get("source_meta")
    if value is None and isinstance(meta, Mapping):
        value = meta.get("message_corpus")
    try:
        return MessageCorpus(str(value)) if value else None
    except ValueError:
        return None


def _is_self(value: str | None) -> bool:
    return bool(value and value.casefold().replace("_", "") in _SELF_LABELS)


def _unique(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        clean = _text(value)
        if clean and clean not in result:
            result.append(clean)
    return result


def enrich_message_parties(
    records: Iterable[NormalizedRecord], payload: Mapping[str, Any] | None
) -> list[NormalizedRecord]:
    """Project actual parties without treating the case owner as a participant.

    Directional exports use the explicitly supplied source principal for their
    local ``Me``/``self``/outbound coordinate.  When it is absent, the record is
    retained but marked review-required with that coordinate omitted.
    """
    principal = source_principal(payload)
    corpus = message_corpus(payload)
    output: list[NormalizedRecord] = []
    for record in records:
        if record.record_type is not RecordType.message:
            output.append(record)
            continue

        attrs = dict(record.attrs)
        direction = _text(attrs.get("direction"))
        direction = direction.casefold() if direction else None
        role_identity = _text(record.role)
        if role_identity and role_identity.casefold() in {"user", "assistant", "system", "tool"}:
            role_identity = None
        raw_sender = (
            _text(record.sender) or _text(attrs.get("sender_label")) or _text(attrs.get("sender")) or role_identity
        )
        directional = direction in {"inbound", "outbound", "sent", "received"}
        outbound = direction in {"outbound", "sent"} or _is_self(raw_sender)

        sender = principal if outbound else raw_sender
        if _is_self(sender):
            sender = principal

        explicit_recipients = attrs.get("recipient_roles")
        recipients: list[MessageParticipant] = list(record.recipients)
        if isinstance(explicit_recipients, list):
            for item in explicit_recipients:
                if not isinstance(item, Mapping):
                    continue
                identity, role = _text(item.get("identity")), _text(item.get("role"))
                if _is_self(identity):
                    identity = principal
                if identity and role in {"to", "cc", "bcc", "group"}:
                    recipients.append(MessageParticipant(identity=identity, role=role))

        roster = _unique(record.participants)
        actual_roster = [principal if _is_self(value) and principal else value for value in roster]
        actual_roster = _unique(value for value in actual_roster if not _is_self(value))
        if not recipients:
            if outbound:
                targets = [value for value in actual_roster if value != sender]
            elif directional:
                targets = [principal] if principal else []
            else:
                targets = [value for value in actual_roster if value != sender]
            recipient_role = "group" if len(targets) > 1 else "to"
            recipients = [MessageParticipant(identity=value, role=recipient_role) for value in targets]

        review_reasons: list[str] = []
        if (outbound or directional) and principal is None:
            review_reasons.append("source_principal_required")
        requires_party_projection = directional or corpus is not None or raw_sender is not None
        if (sender is None or _is_self(sender)) and requires_party_projection:
            review_reasons.append("sender_unresolved")
            sender = None
        if directional and not recipients:
            review_reasons.append("recipient_unresolved")
        if review_reasons:
            attrs["source_party_review_required"] = True
            attrs["source_party_review_reasons"] = sorted(set(review_reasons))

        output.append(
            record.model_copy(
                update={
                    "sender": sender,
                    "recipients": recipients,
                    "message_corpus": corpus or record.message_corpus,
                    "attrs": attrs,
                }
            )
        )
    return output
