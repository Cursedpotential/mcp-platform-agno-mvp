> _Byline: Codex · GPT-5 · 2026-08-29._

<task>
Implement retained-XML SMS/MMS attachment completeness through the common Go parser contract. Current
vendored SBV `streamMMSRecord` already iterates and emits every MMS part; do not rewrite or regress it.
The actual blocker is `vendored/sbv/pkg/parseonly`: ArtifactDir always errors and Record rejects
attachments, while `engine/adapters/sbv` declares SupportsAttachments false. Implement an immutable,
source-scoped attachment sink/locator in the parse-only facade, map every emitted artifact into the
engine parser contract's AttachmentRef, and declare truthful attachment support. Preserve parser
atomicity: parser emits raw envelopes plus immutable attachment refs; it does not hash custody, store
canonical records, choose lanes, or approve evidence.

Exclusive allowlist: vendored/sbv/pkg/parseonly/** and its tests; vendored/sbv/internal SMS XML parser
tests/fixtures only when needed for multi-attachment proof; engine/adapters/sbv/** and its tests; new
SBV-specific contract fixtures under engine/adapters/sbv/testdata; and one new bylined review receipt.
Do not touch engine activities/postgres/uiw/httpapi, SQL, Workbench, deploy files, Python parser registry,
or docs/HANDOFF/ADR files.

Tests must use retained-source-style XML with multiple non-SMIL MMS parts and prove: every part appears
once, locators stay within the supplied immutable sink/root, hashes/byte lengths/MIME/name/parent record
are preserved where the contract supports them, missing/unwritable sink fails closed, and no SQLite or
SBV HTTP/auth dependency exists. Do not reintroduce the obsolete first-attachment-only path.
</task>

<verification_loop>
Run and make green before finishing:
  cd vendored/sbv; go test -tags fts5 ./pkg/parseonly/... ./internal/...
  cd ../../engine; go test ./adapters/sbv/... ./parser/...
  go vet ./adapters/sbv/... ./parser/...
  cd ..; git diff --check
Confirm only allowlisted files changed.
</verification_loop>

<action_safety>
Shared dirty worktree. Never reset, clean, stash, move, delete, broad-stage, git add, commit, push, deploy,
or modify another lane. Never hard-delete. Read applicable AGENTS.md and vendored/sbv/DEVELOPMENT.md.
</action_safety>

<structured_output_contract>
End with: 1. implementation and why; 2. exact files touched; 3. exact test/build results; 4. anything
still blocking source-XML re-ingest/quarantine. Leave edits uncommitted.
</structured_output_contract>
