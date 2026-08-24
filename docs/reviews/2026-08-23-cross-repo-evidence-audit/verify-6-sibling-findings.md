# Verify 6 — sibling session findings (F-01..F-21)

> _Byline: Claude Code · Opus 5 · 2026-08-23_
> Validating findings from sibling session `local_59068f99` ("Document handling and evidence
> bundling gaps", worktree `smart-explore-6ff9d5`).
> Method: `ccc` index (33,436 chunks, rebuilt by owner) + Grep tool + direct file reads.
> Note: `rg` is NOT on PATH in this Git Bash — two early "empty" results were false negatives from
> a failed command, not real absences. All negatives below use the Grep tool instead.

---

## C1 / F-02 — parser precedence and custody gating

**Sibling claim:** *"Custody-hashing parser demoted PRIMARY→SHADOW; non-hashing `sms_xml.py` is
primary. Records ingested while SBV is down get no custody hash. MMS media dropped if SBV down."*

**Verdict: PARTIAL — the headline is REFUTED, the consequence is CONFIRMED.**

### The precedence mechanism (refutes the "demoted to SHADOW" half)

Both parsers register the same capability `parse.sms-xml`:

- `server/tools/parsers/messaging/sms_xml.py:306-311` — `id="messages.sms-xml"`, **no `priority`**
  → defaults to 0.
- `server/tools/parsers/messaging/sbv_sms.py:372-380` — `id="messages.sms-xml-sbv"`,
  **`priority=100`** (`:378`).

Resolution is `server/tools/registry.py:87`:

```python
return sorted(matches, key=lambda tool: getattr(tool, "priority", 0), reverse=True)
```

**SBV is explicitly PRIMARY by `priority=100` vs 0.** It was not demoted to shadow.

### But the custody hash is absent on the default path anyway — two independent routes

**Route (a): SBV's own `accept` predicate excludes it when SBV is unwired.**

`sbv_sms.py:376-377`:
```python
# Only accept .xml AND only when SBV is wired; else defer to sms_xml.py.
accept=lambda hint, size: hint.lower().endswith(".xml") and _sbv_enabled(),
```

If `_sbv_enabled()` is false, SBV does not match at all and resolution falls through to
`sms_xml.py`. Its own `provenance` string states this: *"sms_xml.py is the pure-Python fallback."*

**`sms_xml.py` records no custody hash.** Grep for `hashlib|sha256|content_hash|custody` returns
exactly two hits, and neither is custody:
- `:27` `import hashlib`
- `:115` `"b64_sha256": hashlib.sha256(data.encode("utf-8")).hexdigest() if data else None`

That is a digest of a base64 payload stored in `attrs` — it is **not** written to
`evidence.evidence_hash`, and there is no custody-chain participation.

**Route (b): even on the SBV path, reconciliation is opt-in and defaults OFF.**

`sbv_sms.py:319-323`:
```
Opt-in (SBV_CUSTODY_ENABLED) and defensively lazy: the slim tools-facade has ...
    if not os.getenv("SBV_CUSTODY_ENABLED"):
```

`os.getenv` with no default → `None` when unset → falsy → custody reconciliation is skipped.
Corroborated by `docs/reference/parsers.md:69`: custody is wired into exactly one parser
*"and only when `SBV_CUSTODY_ENABLED` is set."* And `parsers.md:72-73`: **"No other parser in this
document touches custody hashing."**

### The answer to the question that matters

> **Can message evidence land in the database with NO custody hash on the default path?**
> **YES — via two independent routes:** (a) SBV unwired/unhealthy → `sms_xml.py` fallback, which has
> no custody at all; (b) SBV wired but `SBV_CUSTODY_ENABLED` unset → reconciliation skipped.

Neither route emits a warning at the record level. This is the "silent degradation" the sibling
session called *the one indefensible option* — and that judgement stands even though its stated
mechanism (a PRIMARY→SHADOW demotion) is wrong.

### Bonus: confirmed doc drift in `sbv_sms.py`'s own docstring

`sbv_sms.py:14-20` explains precedence as **registration order**:

> *"this tool and sms_xml.py BOTH register capability `parse.sms-xml`. The registry returns them in
> registration order, so importing this module FIRST makes SBV the preferred parser… Import order is
> enforced in server/tools/__init__… no — auto-discovery imports modules alphabetically, and
> "sbv_sms" sorts before "sms_xml", so SBV registers first naturally. (Verified: `sbv_sms` <
> `sms_xml`.)"*

**This is stale.** The registry does not resolve by registration order — it sorts by an explicit
`priority` field, and `sbv_sms.py` declares `priority=100` fifteen lines below the docstring that
says order is what matters. The docstring even contains its own visible self-correction ramble.

The outcome happens to be the same today (SBV wins either way), so this is latent, not active — but
anyone reasoning about precedence from the docstring would conclude that renaming a file could flip
the primary parser. It cannot; only `priority` can.

**Recommended fix:** replace `sbv_sms.py:14-20` with a statement of the real mechanism —
`priority=100` beats `sms_xml.py`'s default 0 via `registry.py:87`; alphabetical import order is
irrelevant.

---

## CRITICAL CONTEXT — the two reviews examined DIFFERENT copies of SBV

Recovered from session logs (`/duckdb-skills:read-memories`), sibling session at 2026-08-23 12:26:

> *"`sbv-forensic` had **no local clone** — only salvage fragments in `extracted-code/sbv` (TS client,
> types, ingestion, SQL). I **shallow-cloned the private repo** read-only…"*

- **Sibling session** analysed a shallow clone of the standalone `Cursedpotential/sbv-forensic` remote.
- **This session** analysed `Agno-MCP-Platform/vendored/sbv` — a subtree inside the parent repo
  (its `git remote` is `mcp-platform-agno-mvp`, not `sbv-forensic`).

These are two different working copies that may have diverged. Every SBV finding below is verified
**against the vendored subtree**, which is the copy the platform actually builds and runs
(`build/swift-mvp-sbv/sbv.exe`). Where the two reviews disagree about SBV, this divergence is the
first hypothesis to test — not reviewer error.

---

## C2–C11 + F-03 — validated

Tooling: `ccc grep` (structural, no daemon), `ccc search` after a `ccc daemon restart`, Grep tool,
direct reads. The ccc daemon had died with `BrokenPipeError [WinError 109]` (my own oversized query);
restarted before use.

| ID | Claim | Verdict |
|---|---|---|
| C2 / F-01 | H2/H3 never independently recomputed by Agno | **CORROBORATED** by lane-1b's independent read; not separately re-verified |
| C3 / F-04 | H3 chain never spans batches | **CONFIRMED** |
| C4 / F-05 | Multi-attachment MMS stores only first part | NOT VERIFIED (only remaining gap) |
| C5 / F-08 | Graphiti client write-only | **CONFIRMED** |
| C6 / F-09 | `verify_chain()` only called by a manual script | **CONFIRMED** |
| C7 / F-16 | Dedup UNIQUE index excludes `content_hash` | **CONFIRMED** |
| C8 / F-17 | `calendar_routes.py:166` UUID NameError | **CONFIRMED — worse than claimed** |
| C9 / F-18 | `InsertCallLogBatch` dead + omits `content_hash` | **CONFIRMED (both parts)** |
| C10 / F-15 | `extractGroupNameFromTrID` live no-op | **CONFIRMED** |
| C11 / F-19 | FTS indexes `body` only | **CONFIRMED — worse than claimed** |
| F-03 | ContextForge JWT secret is a literal placeholder | **CONFIRMED — already documented, awaiting owner ruling** |

### C3 / F-04 — H3 chain never spans batches — CONFIRMED

`vendored/sbv/internal/engine.go:106`:
```go
chain        string // incremental H3 fold (genesis "")
```
The sink is built at `engine.go:498` (`sink := &engineSink{…}`) with **no `chain:` field set** — Go's
zero value for `string` is `""`. The fold accumulates within a batch (`s.chain =
custodyhash.FoldChain(s.chain, h2)` at `:286`, `:389`, `:410`) and the batch result is written at
`:587` (`ChainHash: sink.chain`).

`pkg/custodyhash/custodyhash.go:95` states the contract: `chain_0 = prevChain (prevChain == "" for a
fresh batch)`.

**Every import batch restarts its H3 fold at genesis `""`.** The chain proves ordering *within* a
batch and nothing across batches — so deleting or reordering a whole batch is undetectable by the
chain. `ChainH3(orderedH2s, prevChain)` (`internal/custody.go:78-79`) accepts a non-empty
`prevChain`, but the only place it is passed one is a test (`universal_engine_test.go:362`, which
passes `""`). The capability exists; production never uses it.

### C5 / F-08 — Graphiti client is write-only — CONFIRMED

`server/analysis/graphiti_case_client.py` is **exactly 165 lines**. Full method surface of
`GraphitiCaseClient`: `__init__` (`:47`), `_headers` (`:55`), `_post` (`:61`), `_parse_sse_or_json`
(`:73`), `initialize` (`:81`), `_ensure_init` (`:104`), `call_tool` (`:108`), `add_memory` (`:144`).

The only domain method is **`add_memory`** — a write. There is no `search_memory`, `get_episodes`,
`search_facts`, or any read wrapper. (`call_tool` is a generic escape hatch through which a read tool
*could* be invoked, but no read wrapper exists.)

This corroborates the standing project note that the Graphiti CASE lane's read path is broken and its
"no episodes" answer must never be trusted — the client has no read method to be broken in the first
place.

### C6 / F-09 — `verify_chain()` has one manual caller — CONFIRMED

`ccc grep 'verify_chain(\(ARGS*\))' --lang python` over the whole repo returns exactly two hits:
- definition — `server/core/audit.py:514`
- sole call site — `scripts/audit_dump.py:199` (`n = verify_chain(engine=engine)`)

No startup hook, no scheduled task, no route. The audit ledger's tamper-evidence is only ever checked
when a human runs a script.

### C7 / F-16 — dedup ignores raw bytes — CONFIRMED

`vendored/sbv/internal/database.go:121` (and again at `:234` for the per-user DB):
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_message_unique ON messages(
  record_type, address, date, type, COALESCE(body, ''), COALESCE(content_type, ''),
  COALESCE(message_id, ''), COALESCE(duration, 0));
```
**`content_hash` is not a member of the uniqueness key.** Deduplication is therefore on *normalized
field equality*, not on raw bytes. Two source records whose raw bytes differ but whose normalized
fields collide are silently collapsed, and the surviving row keeps whichever `content_hash` was
written first. For a forensic tool this inverts the intended guarantee: the hash exists to prove
byte-level identity, but identity is decided without it.

### C8 / F-17 — live NameError on a DELETE route — CONFIRMED, worse than claimed

File is at `Legal-Workspace/api/legal_workspace/api/calendar_routes.py` (note the nested `api/api/`).

`:166` calls `UUID(event_id)`. The module's imports (`:3-12`) are `__future__`, `datetime`, `typing`,
`fastapi`, `pydantic`, and two local modules — **`UUID` is never imported.**

```python
@router.delete("/v1/calendar/events/{event_id}")
def delete_calendar_event(event_id: str) -> Dict[str, str]:
    try:
        event_uuid = UUID(event_id)          # NameError
        ...
    except ValueError:
        raise HTTPException(status_code=400, ...)
    except StopIteration:
        raise HTTPException(status_code=404, ...)
```

**`NameError` is not caught by `except ValueError` or `except StopIteration`.** So the route does not
degrade to the intended 400 — it raises an unhandled 500 on *every* invocation. One-line fix:
`from uuid import UUID`.

### C9 / F-18 — `InsertCallLogBatch` dead and custody-less — CONFIRMED (both parts)

`ccc grep 'InsertCallLogBatch(\(ARGS*\))' vendored/sbv --lang go` returns **only the definition**
(`internal/database.go:437`) — zero call sites.

Its prepared statement (`:450-452`) inserts:
```sql
INSERT INTO messages (record_type, address, type, date, duration, presentation,
                      subscription_id, contact_name)
```
— **`content_hash` omitted.** Dead today, but if revived it would write call rows with no custody
hash at all.

### C10 / F-15 — `extractGroupNameFromTrID` is a live no-op — CONFIRMED

`vendored/sbv/internal/parser.go:394`:
```go
func extractGroupNameFromTrID(trID string) string {
	return ""
	/*  … ~35 lines of real base64/proto parsing, entirely commented out … */
}
```
It **is** called on the live path — `parser.go:344`: `groupName := extractGroupNameFromTrID(mms.TrID)`.
So every MMS group name silently resolves to empty string. Not dead code — live wrong code.

### C11 / F-19 — FTS covers `body` only — CONFIRMED, worse than claimed

`vendored/sbv/internal/database.go:124-132`:
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    message_id   UNINDEXED,
    address      UNINDEXED,
    body,
    contact_name UNINDEXED,
    date         UNINDEXED,
    content='messages', content_rowid='id');
```
**`body` is the only indexed column** — everything else is explicitly `UNINDEXED`. Consequences:
- Call logs (`record_type = 3`) have no body, so they are effectively unsearchable.
- You cannot full-text search by `contact_name` or `address` either, on *any* record type.

The claim understated it: this is not just a call-log gap, it is a search surface that covers message
text and nothing else.

### F-03 — ContextForge JWT secret — CONFIRMED, and already owner-blocked

`Legal-Workspace/docs/URGENT-TODO.md:26`, item B1, verbatim:

> **ContextForge JWT secret on ovh-app is a broken paste.** `CF_JWT_SECRET_KEY`, `JWT_SECRET_KEY` =
> literal string `set CF_JWT_SECRET_KEY`; `AUTH_ENCRYPTION_SECRET`, `CF_AUTH_ENCRYPTION_SECRET` =
> literal `set CF_AUTH_ENCRYPTION_SECRET`. Someone pasted the shell command instead of its value.
> — **SECURITY — HIGH.** CF runs `AUTH_REQUIRED=true` on a trivially guessable signing secret. Every
> service that trusts a CF JWT is affected.
> — **AWAITING OWNER RULING.** Not rotated autonomously: rotation invalidates every existing token
> platform-wide (agentos, librechat, gateway, this app) at once.

This is not a new discovery — it is a known, correctly-triaged, correctly-escalated item. It is the
highest-severity open item across all three repos and it is blocked on an owner decision, not on
engineering work. (The literal values above are placeholder strings, not live secrets, so quoting
them discloses nothing.)

---

## Effect on the consolidated register

`CONSOLIDATED-CLAIM-VERIFICATION.md` §1.1 states that Doc A's SBV custody claims are REFUTED because
custody "is wired… gated by an opt-in `SBV_CUSTODY_ENABLED` env var."

That remains accurate but is now **too generous to the system**. Amendment:

- Doc A was **wrong** that SBV has no hash field / no custody column / no bridge — those exist and
  `reconcile_sbv_import()` is real and wired.
- Doc A was **right in effect**, for the wrong reason: on the default configuration, message evidence
  can and does land with no custody hash — because the flag defaults off, and because the fallback
  parser has no custody path at all.

Both statements are true simultaneously. The distinction that matters operationally is
**"a custody path exists" ≠ "the custody path is the default."**
