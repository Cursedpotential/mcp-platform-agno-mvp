# SBV immutable attachment sink implementation receipt

> _Byline: Codex · GPT-5.6 · 2026-08-29._
>
> **Status: SOURCE IMPLEMENTED / RUNTIME AND MANIFEST WIRED / NOT DEPLOYED / NOT LIVE-PROVEN.**

## Implemented boundary

- `streamMMSRecord` still walks every MMS part. It now also streams the exact original `<mms>` span
  into a bounded raw spool while decoding inline base64 parts; it does not reconstruct source XML or
  reuse the whole-file locator for an individual record.
- Inline MMS capture recognizes the XML grammar `data S* = S* quoted-value`, including tabs and
  newlines around `=`. Sanitized decoding must associate every captured marker exactly once, and any
  non-empty `part.Data` that escaped streaming capture rejects the record instead of producing an
  accepted zero-attachment result.
- The pre-existing `extractGroupNameFromTrID` stub no longer returns empty unconditionally. It safely
  walks protobuf wire types and general varint-length-delimited UTF-8 fields from a valid `proto:`
  value; no fixed byte offset or one-byte length remains. It rejects malformed, truncated, non-printable,
  or invalid UTF-8 values. No retained real `tr_id="proto:..."` fixture exists in this checkout, so the
  executable regression covers variable field positions and a multi-byte length but live retained-XML
  proof remains an explicit re-ingest gate.
- `pkg/parseonly` accepts a caller-owned `ImmutableArtifactSink`. Every parse receives a random,
  unique attempt identity. Decoder and publication intermediates live only in that attempt's
  protected directory, which is renamed whole to `completed` or `quarantine`; no cleanup path
  deletes interrupted files.
- The parse-only boundary verifies regular-file containment, byte count, and SHA-256 integrity before
  and after the sink write. These are object-integrity digests, not evidence H1/H2/H3 custody claims.
- Source-declared companion references whose bytes are absent remain structured native metadata; they
  are not misrepresented as persisted attachments.
- `FilesystemArtifactSink` requires a pre-existing protected root and a governed registrar. It copies
  to a unique attempt candidate, synchronizes and verifies it, then atomically hard-links the complete
  object into a logical source/kind/parent/ordinal path. The digest is deliberately excluded from
  logical identity. A retry reuses identical bytes; different bytes at that identity fail closed;
  no partial final object is exposed.
- Before inspecting any inflight directory, the sink acquires an exclusive cross-process runtime lock
  with owner token, PID, hostname, and start time. A second process fails closed. Graceful shutdown moves
  its verified lock into an append-only released archive; a crash leaves the active lock in place, so an
  operator must verify the recorded owner is dead and archive that lock before restart recovery can run.
  Every `ArtifactDir`, `Store`, `CompleteAttempt`, and `QuarantineAttempt` call holds synchronized shared
  ownership for its entire mutation and re-reads the exact owner record; closed sinks and missing or
  mismatched locks fail before touching attempt/object state. `Close` takes exclusive ownership, waits for
  active mutations, verifies the same full owner record, and only then archives the lock.
- `ParserStore.RegisterArtifact` atomically resolves/inserts `context.retained_object` and binds it to
  the retained source through `context.source_version_object` before returning a locator. Global
  content deduplication may return the already-governed URI; repeated identical attachments retain
  distinct source/kind/parent/ordinal occurrences in the membership JSON rather than losing the second
  occurrence to the source/object primary key. Every unused new path is moved into its own exclusively
  created random quarantine directory, so duplicate filenames cannot replace one another and no duplicate
  is deleted. Raw-generation persistence also
  resolves every attachment locator through this membership before accepting a bundle record.
- Malformed base64 never becomes a successful attachment. The raw record is rejected, exact source
  bytes remain locatable, the failed part retains ordinal/name/MIME/conversion status/error metadata,
  partial decoded bytes receive no locator, and captured attachments must equal successful references
  plus explicit failures exactly.
- The engine adapter maps the raw-record locator and every attachment into the common
  `RawRecordEnvelope`/`AttachmentRef` contract. Attachment metadata preserves source association,
  parent source position, ordinal, original name, MIME, digest, byte count, and locator.
- Adapter version is `1.3.0`. `SupportsAttachments` is `true` only for adapters constructed through
  `NewWithArtifactSink` or `NewAllWithArtifactSink`; legacy `New`/`NewAll` adapters remain truthfully
  `false` and fail closed on MMS because no immutable sink is configured.

The production parser Activity source now requires `PARSER_ARTIFACT_DIR`, constructs the sink with
the production `ParserStore`, and registers attachment-capable adapters. Its Coolify manifest binds
`/data/agno/volumes/universal-import/parser-artifacts` with `create_host_path: false`; the protected
0700 host directory must be provisioned before deployment. No SQLite authority, SBV HTTP/auth surface,
lane decision, or custody H1/H2/H3 construction was added to this parser slice.

## Exact source files

- `vendored/sbv/internal/importer.go`
- `vendored/sbv/internal/sms_xml_importer.go`
- `vendored/sbv/internal/parser.go`
- `vendored/sbv/internal/parser_test.go`
- `vendored/sbv/pkg/parseonly/parseonly.go`
- `vendored/sbv/pkg/parseonly/parseonly_test.go`
- `engine/adapters/sbv/artifact_sink.go`
- `engine/adapters/sbv/sbv.go`
- `engine/adapters/sbv/sbv_test.go`
- `engine/postgres/parser_activity_store.go`
- `engine/postgres/parser_activity_store_test.go`
- `engine/postgres/raw_pipeline_repository.go`
- `engine/cmd/parser-activity-runtime/main.go`
- `deploy/parser-activity-runtime.yaml`
- `tests/test_universal_import_deploy_contract.py`
- this receipt

## Verification

- `cd vendored/sbv && go test -tags fts5 ./pkg/parseonly` — passed.
- `cd vendored/sbv && go test -tags fts5 ./internal/... -run
  "TestExtractGroupNameFromTrID|TestSMSXMLImporterKeepsAttachmentOnlyMMS|TestSMSXMLImporterStreamsAttachmentLargerThanWorkBuffer|TestAttachmentReferenceSafetyStates"`
  — passed, including the existing 8 MiB bounded-streaming regression.
- The retained-source-style contract fixture contains three non-SMIL MMS parts and proves each appears
  exactly once with exact bytes, name, MIME, digest, byte count, parent record, source association, and
  a locator contained within the supplied immutable root. It also proves exact raw MMS bytes—not the
  sanitized decode spool—are independently locatable.
- A separate XML-grammar regression proves `data \t=\r\n "..."` is captured losslessly rather than
  bypassing attachment accounting. Malformed data and unassociated markers fail closed.
- Executable engine tests prove exclusive runtime ownership/release, startup quarantine only after lock
  acquisition, collision-free preservation of multiple deduplicated objects, and two identical-byte
  attachment occurrences producing distinct digest-free registrar identities/member locators.
- A stale-sink regression closes runtime A, starts runtime B, rejects all four mutating operations through
  A, then proves B can still store and complete its own attempt. Separate negative coverage preserves and
  removes the active lock from view, substitutes a mismatched owner, and proves both states fail closed.
- `cd engine && go test ./...` — passed.
- `cd engine && go vet ./...` — passed.
- `uv run pytest -q tests/test_universal_import_deploy_contract.py` — 11 passed.
- `git diff --check` over the owned files — passed.

The mandatory combined vendored command was also run. `pkg/parseonly` passed, but the unrelated
SQLite-backed `internal` tests cannot execute in this Windows environment: `go env CGO_ENABLED` is `0`,
and forcing `CGO_ENABLED=1` fails because `gcc` is absent. With CGO disabled, those tests consistently
report go-sqlite3's documented stub error (`Binary was compiled with 'CGO_ENABLED=0'`). This is an
environment gate, not an attachment assertion failure; the focused non-SQLite `internal` tests above
are green.

## Remaining deployment, live proof, and quarantine gates

1. Provision the root-owned `0700` parser-artifact host directory named in the manifest; then commit,
   push, and deploy through Coolify. No deployment action occurred in this lane.
2. Run the full fts5-tagged vendored suite in CI or another Go 1.25 environment with CGO and a C compiler.
3. Re-ingest retained XML—not historical SBV SQLite. Prove multi-part counts,
   bytes, metadata, locators, restart/retry idempotency, and the platform read path against real retained
   sources, including database membership and an intentionally malformed base64 part.
4. Keep retained XML and historical SBV stores out of quarantine until caller wiring, deployment, live
   completeness proof, and explicit quarantine authorization are all recorded.

## Authority and upstream custody boundary

- Re-ingest authority is retained source XML. Acceptance must enumerate every XML MMS part and compare
  exact bytes, SHA-256, original name, MIME, ordinal, parent record, and platform locator. Historical
  SBV SQLite `media_data` retained only the first non-SMIL MMS part, so it is a lossy secondary comparison
  and can never be the parity target.
- H3 remains an upstream Temporal custody Activity, not parser behavior. The required separate follow-up
  belongs in `engine/activities/custody.go` with `engine/activities/custody_test.go`: continue the prior
  governed H3 across batches, use the exact construction-specific tag, and never call
  `ChainH3(recordHashes, "")` independently for every batch. This lane did not edit custody authority.
- Owner-supplied evidence says `tests/test_c26_resilience.py -k dedupe` passes all three dedupe branches;
  this lane preserved that evidence but did not rerun or modify the resilience test.
- No isolated PostgreSQL test DSN or `psql` client is available in this checkout environment, and the
  repository forbids inventing a local container stack. The executable `ParserStore` contract test covers
  two identical-byte/distinct-ordinal registrations and the occurrence-append SQL shape, but it is not a
  PostgreSQL execution proof. The remaining exact gate is an ephemeral PostgreSQL 18 database with SQL
  `0036_context_import_foundation.sql` applied, then two registrations asserting one retained object and
  two `artifact_occurrences` for the same source before live deployment.

No stage, commit, push, deployment, live re-ingest, or quarantine operation occurred in this lane.
