# Platform / Case Bible intake and job compatibility

> _Byline: Codex · GPT-5.6-Sol · 2026-08-30._
> _Contract reconciliation: Codex · GPT-5.6-Sol · 2026-08-30._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

The versioned client source is `docs/schemas/platform-intake-job-contract-v1.openapi.yaml`. It is
generated from the actual FastAPI routes and Pydantic models by
`scripts/generate_platform_intake_contract.py`; Case Bible may generate client types from that
artifact, but must not copy browser types by hand. `--check` is the drift gate.

| Semantic contract | Current Platform route/type | Compatibility status |
|---|---|---|
| `SourceInspectionRequest` / `SourceInspectionResponse` | `POST /api/uiw/source-inspection` | Implemented for one fixed `casebible-sorted` object. The SHA-256 is explicitly preview-only. |
| `ObservedSource` / `HumanSourceAssertions` | `POST /api/uiw/source-contexts` | Implemented as separate immutable observed values and operator assertions. |
| `SourceContextCreateRequest` / `SourceContextReceipt` | `context.uiw_source_context_revision` | Actor-bound initial and successor revisions are implemented. `supersedes_ref` must own the same request, matter, case, source, and immutable preview observation; PostgreSQL receipts every revision. |
| `UIWStartRequest` / `UIWStartResponse` | `POST /api/uiw/start` | Implemented for single-source UIW. The only browser-visible start identity is `preview_handle`; Temporal workflow/run IDs remain server-side. |
| `UIWPreviewResponse` | `GET /api/uiw/previews/{preview_handle}` | Implemented as the durable preview projection, including correlation, parser, receipts, digest, and repair-assessment state when available. |
| validation/error envelope | FastAPI `detail`; starter `{detail}` | Compatible minimal envelope. Structured issue codes remain additive. |

Case Bible's provisional generic `JobGateway` should adapt its intake job kind to these routes.
Generic registered job kinds and cancellation are not falsely mapped to UIW today: the current
Workbench `monitored-actions` client remains capability-gated until the Platform exposes a real
Temporal-backed registered-job surface. No direct MCP call, raw command, provider credential,
native path, or evidence byte is an acceptable fallback.
