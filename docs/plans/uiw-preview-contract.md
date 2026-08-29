# UIW pipeline-preview contract

> _Byline: Codex · GPT-5.6 · 2026-08-29._

STATUS: IMPLEMENTED LOCALLY; UPSTREAM GO SURFACE, DEPLOYMENT, AND LIVE PROOF REMAIN

## Boundary

Workbench is the only operator shell, case-context boundary, and authentication boundary. The
SBV-derived interface is a storage-free viewing client at `/evidence/preview`. It reads only
UIW-native platform projections through the Workbench BFF. It does not own SQLite, authentication,
ingestion, parser selection, custody, or canonical data.

An opaque `preview_handle` is the only browser-visible join key. The BFF must compare every
upstream snapshot, message page, decision response, and event to the exact requested handle and fail closed on a
mismatch or malformed JSON. Workflow IDs and run IDs are not preview handles and must never be
relabeled or sent to legacy record/event APIs.

## Decision gate

Approve/reject exists only on the pipeline-preview route. Intake may open the preview but may not
submit a decision. The client enables a decision only when all of the following belong to the same
active handle generation:

- the snapshot handle exactly matches the requested handle;
- the decision response must return that same handle before the browser accepts it;
- at least one normalized platform message has loaded;
- every message has a source locator, every attachment has a source locator, and every referenced
  participant resolves in the returned participant projection;
- custody, parser-selection, parser-execution, normalization, storage, and completeness receipts
  are present with `completed` status;
- neither the snapshot nor message request has failed.

Changing handles aborts outstanding reads, advances a client generation, clears accumulated state,
and closes the old event stream. Late responses from an earlier generation cannot update the new
preview. Pagination permits only one request per cursor at a time and deduplicates messages by
`message_id` before ordinal ordering.

## Rendered proof fields

The operator surface renders request/source/raw-generation/normalized-generation correlation,
parser identity and config digest, preview digest, receipt type/ref/status/digest/time, message ID,
ordinal/time/body/source locator, participant IDs/display name/canonical address, and attachment
ID/name/MIME/size/SHA-256/source locator. These are preview references and metadata, not evidence
promotion.

## Retained-source and port requirements

Retained source XML is the migration and completeness authority for historical MMS. SBV SQLite is
lossy because the historical decoder stored only the first non-SMIL MMS part. A row-count or BLOB
comparison against SQLite can therefore pass while preserving an incomplete corpus. Re-ingest proof
must enumerate every MMS part in retained XML and prove its bytes, digest, name, MIME type, and
platform locator.

Before any SMS/RCS re-ingest or port is accepted, the shared Go-selected parser/custody path must
resolve all three known defects:

1. decode every MMS attachment, not only the first part;
2. preserve RCS group names instead of `extractGroupNameFromTrID` returning an empty value;
3. continue the separately tagged H3 custody chain across batches instead of restarting with
   `ChainH3(recordHashes, "")` for each batch.

Custody remains its own upstream activity rather than browser logic or parser selection. Extraction
and preview never confer evidence status.

## Verification boundary

Focused BFF tests and Workbench smoke/lint/build validate the local boundary. Completion additionally
requires the Go preview surface, a pushed clean integration commit, Coolify deployment, Authentik
access proof, a real retained-source workflow, correlated normalized messages and receipts, SSE
resume proof, and a live approve/reject/resume result.
