# SMS Backup & Restore XML — field reference & schema mapping (AUTHORITATIVE)

> _Byline: Claude Code · Fable 5 · 2026-07-02 · Source: official SyncTech field documentation (provided by owner 2026-07-02)_

The contract for every SMS-XML parser (SBV primary, `sms_xml.py` fallback):
**every XML attribute lands in `raw_data` verbatim under its original name** (the
capture guarantee), and the fields below additionally map to typed columns.
Java `date` values are **epoch milliseconds** → `to_timestamp(date/1000.0)`.

## `<sms>` → `analysis.message` (platform='sms')

| XML field | Meaning (official) | Typed destination | Notes |
|---|---|---|---|
| `protocol` | mostly 0 for SMS | raw_data only | |
| `address` | sender/recipient phone | `sender_raw/sender_e164` or `recipient_raw/recipient_e164` **by direction** | normalize to E.164 |
| `date` | epoch-ms sent/received | `ts_utc` | |
| `type` | 1=Received 2=Sent 3=Draft 4=Outbox 5=Failed 6=Queued | 1→`direction='inbound'` · 2→`'outbound'` · 3/4/5/6→`direction='outbound'` + `message_type`='draft'/'outbox'/'failed'/'queued' | failed/queued sends are evidence too |
| `subject` | always null for SMS | — | |
| `body` | message content | staging `content` + `content_sha256`, `word_count`, `char_count` | body itself stays on normalized_record (core holds hash+metrics) |
| `toa` / `sc_toa` | n/a | raw_data only | |
| `service_center` | SMSC for received msgs | `platform_attrs.service_center` | exposed via `vw_message_sms` |
| `read` | 1=read 0=unread | **`is_read`** (0008 promotion) | forensically significant |
| `status` | −1 None · 0 Complete · 32 Pending · 64 Failed | `status_code` (raw int) + `delivery_status` ('none'/'complete'/'pending'/'failed') | |
| `sub_id` | SIM subscription index | `platform_attrs.sub_id` | |
| `readable_date` | human-readable date | `raw_ts` | the original-format string, kept verbatim |
| `contact_name` | contact name at export time | `platform_attrs.contact_name` | also future `entity_alias` evidence — name-as-saved at a point in time |

## `<mms>` → `analysis.message` + `analysis.attachment` + `analysis.message_participant`

| XML | Typed destination | Notes |
|---|---|---|
| `mms.date` | `ts_utc` | epoch-ms |
| `mms.msg_box` 1/2/3/4 | `direction` (1 in / 2 out) + `message_type` | |
| `mms.m_id` | `external_id` | the platform Message-ID — real dedup key |
| `mms.read` | `is_read` | |
| `mms.rr` / `read_status` | `platform_attrs.read_report` / `.read_status` | delivery+read receipts |
| `mms.sub` | `platform_attrs.subject` | |
| `mms.ct_t`, `m_size`, `m_type`, `sim_slot` | `platform_attrs.*` | |
| `mms.readable_date` | `raw_ts` | |
| `part.ct` / `name` / `data` | `attachment.mime_type` / `filename` / decoded binary → object store + `file_sha256` + `file_size` | `part.seq` → platform_attrs.seq; `text/plain` part = message body |
| `part.chset`, `cl` | attachment `platform_attrs` | |
| `addr.type` **137=From · 151=To · 130=CC · 129=BCC** | `message_participant.role` `'from'/'to'/'cc'/'bcc'` | maps 1:1 onto the live CHECK set |
| `addr.address` / `charset` | `participant_raw`+`participant_e164` / raw_data | |

## `<call>` → `analysis.call_log`

| XML field | Meaning | Typed destination | Notes |
|---|---|---|---|
| `number` | phone | `from_*` or `to_*` by direction | E.164 normalize |
| `duration` | seconds | `duration_s` | |
| `date` | epoch-ms | `started_at` | |
| `type` | 1=Incoming 2=Outgoing 3=Missed 4=Voicemail 5=Rejected **6=Refused List** | `call_type` ('incoming'/'outgoing'/'missed'/'voicemail'/'rejected'/'blocked_list') + `direction` (2→outbound, else inbound) | **type 6 = caller was on the BLOCK LIST → also set `is_blocked=true`.** This is the direct blocked-evidence signal the owner asked about — it lives in call logs, not SMS records. Type 5 (rejected) = manually declined, ≠ blocked. |
| `presentation` | 1=Allowed 2=Restricted 3=Unknown 4=Payphone | `presentation` | caller-ID presentation |
| `subscription_id` | SIM | `platform_attrs.subscription_id` | |
| `readable_date` | human string | `platform_attrs.readable_date` | original-format string |
| `contact_name` | name at export | `platform_attrs.contact_name` | |

## Cross-cutting rules

1. **Capture guarantee**: `raw_data` = the complete original element, attribute
   names unchanged. Views (`vw_message_sms`) and later promotions read from it —
   never re-ingest to get a "new" field.
2. **Blocked evidence, three levels**: per-call `call_log.is_blocked` (from type 6),
   per-message `message.is_blocked`, per-contact `phone/handle.is_blocked` with
   `validity` time ranges (fed by block-list exports/screenshots, not this XML —
   SMS elements carry NO blocked flag).
3. **Acceptance check per ingest batch**: count of XML attributes present in source
   vs keys present in `raw_data` must match, per element type — "did we capture
   everything" is verified, not assumed.
4. **Parser contract**: SBV primary, fallback only via `allow_fallback=True`, and
   any fallback run + its records are flagged `alt_parse` (+`alt_parse_detail`)
   — no silent substitution (owner mandate 2026-07-02).
5. This doc seeds `analysis.format_resolver` rows (migration 0008) for
   `sms-backup-restore-xml` sms/mms/call — the mapping above as data.
