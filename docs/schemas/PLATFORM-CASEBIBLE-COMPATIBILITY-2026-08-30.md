# Platform / Case Bible intake and job compatibility

> _Byline: Codex · GPT-5.6-Sol · 2026-08-30._

The versioned semantic source is
`docs/schemas/platform-intake-job-contract-v1.openapi.yaml`. Case Bible may generate client types
from that artifact; it must not copy browser types by hand.

| Semantic contract | Current Platform route/type | Compatibility status |
|---|---|---|
| `IntakeCandidate` | `POST /api/uiw/source-inspection` plus `UIWSourceInspection` | Implemented for one fixed `casebible-sorted` object. The SHA-256 is explicitly preview-only. |
| `SourceField` | `observed_source` and `assertions` in `SourceContextCreateRequest` | Implemented as separate immutable observed values and operator assertions. |
| `HumanCorrection` | `POST /api/uiw/source-contexts`; `context.uiw_source_context_revision` | Actor-bound initial and successor revisions are implemented. `supersedes_ref` must own the same request, matter, case, source, and immutable preview observation; PostgreSQL receipts every revision. |
| `JobRequest` | `UIWStartRequest` | Implemented for single-source UIW with exact source ref, request idempotency, and optional `source_context_ref`. The starter validates the context scope before start, and registration binds the exact revision to `context.source_version`. Temporal transports only its reference. |
| `JobRun` | opaque `preview_handle`; `GET /api/uiw/previews/{preview_handle}` | Implemented for intake status. Temporal workflow/run IDs remain server-side. |
| `JobReceipt` | source-context receipt plus UIW preview receipts/result refs | Implemented for source metadata and workflow projections. |
| validation/error envelope | FastAPI `detail`; starter `{detail}` | Compatible minimal envelope. Structured issue codes remain additive. |

Case Bible's provisional generic `JobGateway` should adapt its intake job kind to these routes.
Generic registered job kinds and cancellation are not falsely mapped to UIW today: the current
Workbench `monitored-actions` client remains capability-gated until the Platform exposes a real
Temporal-backed registered-job surface. No direct MCP call, raw command, provider credential,
native path, or evidence byte is an acceptable fallback.
