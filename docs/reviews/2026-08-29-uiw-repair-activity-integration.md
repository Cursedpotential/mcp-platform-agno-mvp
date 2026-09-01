# UIW repair activity integration

> _Byline: Codex · GPT-5 · 2026-08-29._

## Result

The existing `server.tools` repair modules remain the single implementation and registry. The Go
engine now models repair as two explicit pre-parser Temporal stages:

1. `assess_source_repair_activity` calls the existing `repair.detect` and `repair.preview` tool IDs,
   persists the bounded output outside Temporal, and returns only assessment/receipt references.
2. Temporal waits on `repair_decision`. The signal carries only a durable decision reference.
   `resolve_source_repair_activity` reloads and revalidates the exact actor-bound approval, either
   preserves the original or calls one of the two allowed derived-write tools, and returns the
   active-original/receipt references consumed by parser execution.

`repair.write-derived` and `repair.pdf-derived` are the only mutation-capable tool IDs admitted by
the Go activity. The activity injects the facade's required manual-execution fields only after the
stored approval has been validated. Quarantine, flagging, parser selection, custody promotion, and
raw persistence remain separate responsibilities.

Temporal owns sequence, bounded retries, the 24-hour durable wait, resume, and workflow identity.
n8n owns two visual, inactive-by-default Activity wrappers and calls the existing import runtime;
it does not select parsers or store approval state. The exports reuse the already-validated n8n
Webhook -> exact-envelope Code -> authenticated HTTP Request -> compact-result Code -> Respond
pattern. No operation-specific repair community node is currently proven against n8n 2.36.6, so
live node import/activation remains a deployment acceptance gate rather than a source claim.

## Production closure added in this lane

`sql/0051_uiw_repair_activity_store.sql` adds append-only PostgreSQL assessment, actor-bound
decision, and resolution tables tied to the existing `activity_execution` / `activity_receipt`
idempotency boundary. The production `engine/postgres.RepairActivityStore` now:

- resolves only a retained object that is an exact member of the stated source version;
- admits only `file:` locators below an explicitly configured shared root;
- rebinds the source path from PostgreSQL immediately before an approved mutation, so a decision
  cannot substitute a different input path;
- independently re-hashes a derived output before registering it as a retained object and source
  `derived_reference`; and
- makes the derived object eligible for parser execution only through an approved repair-resolution
  row. The original retained object remains immutable and remains the provenance parent.

The parser Activity runtime mounts both repair handlers under its existing bearer boundary. It
uses the existing platform-tools facade URL, never a second tool registry. Because the runtime is
on ovh-files while platform-tools is on OVH-1, both sides use the same R2-backed `/r2` namespace;
`deploy/parser-activity-runtime.yaml` now mounts that volume and requires the facade URL explicitly.

Workbench/UIW remains the single human-decision authority. The PostgreSQL store exposes
`PersistRepairDecision` so that lane can atomically bind the assessment, actor, approval, exact
tool payload, and idempotency key before signaling Temporal with only the returned decision
reference. There is deliberately no second repair-decision HTTP endpoint: n8n may host pluggable
HITL interactions, but it does not own or independently persist canonical workflow state.

## Verification and honest boundary

- Focused Go packages pass: activities, postgres, runtimeapi, and the parser runtime command.
- `go vet ./...` completed without a diagnostic.
- Repair migration/workflow tests: 4 passed; the PostgreSQL 18 rollback proof is opt-in and skipped
  unless `PLATFORM_0051_TEST_SERVICE` names the disposable service.
- The full Go suite currently fails in concurrent UIW projection work: Temporal integration tests
  do not register the newly introduced `publish_uiw_preview_activity`, and one rejection assertion
  observes parser execution before that newer preview gate. Those failures are outside the repair
  store and were not hidden or edited around here.

No live n8n import/activation, migration application, Coolify deployment, or end-to-end source
repair is claimed yet. Those remain deployment acceptance gates. No `docker/tools` source was
changed.
