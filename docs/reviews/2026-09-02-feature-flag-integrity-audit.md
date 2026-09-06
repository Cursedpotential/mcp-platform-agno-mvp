# Feature-Flag Integrity Audit — Audit Lane F1

> _Byline: Claude Code · Sonnet (audit lane F1) · 2026-09-02._
> Scope: every feature flag / gate / env toggle across `modules/engine/**` (excl. vendor),
> `server/**`, `scripts/**`, `modules/workbench/**`, `sql/**`, `deploy/**`, `.github/**`.
> Method: direct `Grep`/`Read` sweep by the audit lead plus two parallel research passes
> (Go engine; TS/deploy/CI) whose file:line citations were independently re-verified before
> inclusion here. READ-ONLY on code; this is the one report doc the lane was authorized to write.
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## Why this audit exists (read before the table)

Owner ruling D-127 (`docs/DECISION_LOG.md`, 2026-09-02, standing principle), quoted in full because
every verdict below is measured against it:

> "A feature flag is never a shortcut to skip building something. It is a shortcut to stop our own
> development-stage gates from blocking us — and the gated process must still be fully built, still
> function, and still be tested." … "(0) THE TEST: a development flag's default IS the production
> behavior, and dev inverts it temporarily — at go-live it flips back to the opposite of how it ran
> in development, and that inversion is the entire point. It follows that if the honest answer is
> 'we are never going to turn this on,' it is not a flag, it is deletion." … "(5) a flag must never
> suppress a check into silence — flag-on paths log loudly what is relaxed and why."

D-110 (2026-08-30) and D-128 (2026-09-02, amends D-110) govern the immutability-guard family
specifically: guards were deliberately left off during the 2026-08-30 rebuild, "not technical
debt," but D-128 is explicit that this is **owed work**, not closed work — "it must be exercised by
tests in BOTH states… an untested guard hidden behind an off switch violates D-127."

D-125/D-126 (both 2026-09-02) name one specific flag, `PLATFORM_DEV_AUTH_BYPASS`, meant to relax
auth on the UIW starter HTTP surface, the Workbench BFF, and (D-126's refinement) the UIW schema-
admission case-registry identity/receipt check — never by skipping a check, only by pointing it at
a fixed, obviously-fake DEV sentinel while every check itself keeps running.

### A note on how this audit was conducted: the repo changed under it

`modules/engine/postgres/uiw_schema_probe.go`, its test file, and `sql/0069_dev_case_registry_
identity.sql` were **actively being written by a concurrent session** (self-labeled "BUILD LANE S3")
while this audit ran. Two consecutive reads of the same file, minutes apart, returned materially
different content — a `devAuthBypassEnabled()` implementation appeared where none had existed, then
its query-binding wiring was completed. This is disclosed rather than hidden: findings below on
`PLATFORM_DEV_AUTH_BYPASS` reflect the state independently observed and confirmed via `git status`
(uncommitted working-tree changes, not yet on `main`) at the time this report was written. Anyone
reading this later should re-check `git log -1 -- modules/engine/postgres/uiw_schema_probe.go` and
`git status` before relying on the specifics — the direction and quality of the change is real and
verified (tests exist and pass), but its landed/committed status may have moved on.

---

## Flag inventory — full table

Columns match the six required questions. "Default" states whether the **unset** behavior is
strict/production-safe or permissive. "Both-state tests" names actual test functions or says none.

| # | Flag / gate | File:line | Capability gated | Built? | Tested both states? | Default when unset | Logs when relaxed? | Removal condition documented? | Rank |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `PLATFORM_DEV_AUTH_BYPASS` (schema-admission identity) | `modules/engine/postgres/uiw_schema_probe.go:87,140-169` (uncommitted working-tree change; `sql/0069_dev_case_registry_identity.sql` new, uncommitted) | Whether UIW startup admission checks the case-registry `matter_id`/`court_case_id` + import-receipt against the real go-live identity or a fixed, obviously-fake DEV sentinel (`deadbeef…`/`cafebabe…`) | **Built** — same SQL predicate runs in both modes, only bound values move | **Yes** — `TestProbeUIWSchemaDefaultBindsStrictAuthoritativeIdentity`, `TestProbeUIWSchemaDevBypassBindsSentinelIdentityNotSkipsIt`, `TestProbeUIWSchemaDevBypassLogsLoudWarning`, `TestProbeUIWSchemaDevBypassEnvSpellings` — all pass (`go test ./postgres/... -run TestProbeUIWSchema -v`, verified live) | **Strict** (real `authoritativeMatterID`/receipt, currently unmet until go-live) — correct per D-127(0) | **Yes** — `slog.Warn(...)` naming the flag, asserted by test | **Yes** — "remove this flag before go-live," inline + D-126 | **OK** (best-built flag in the repo; see caveat above on commit status) |
| 2 | `PLATFORM_DEV_AUTH_BYPASS` — UIW starter HTTP auth surface | *(does not exist)* — searched `modules/engine/temporal/cmd/starter/**`, `runtimeapi/**` | D-125's literal ask: relax bearer/Authentik checks on the starter's HTTP routes | **Not built** — but the STRICT enforcement it would relax already exists and is unconditional (tailnet-IP check on `httpapi.go:190-196`/`acquisition/upload.go:126`; tailnet-IP **+** `hmac`-compared bearer token from `UIW_SERVICE_TOKEN_FILE` on `runtimeapi/uiw_preview.go:402-418`, `source_context.go`, `parser_activities.go`, `repair_activities.go`, `router.go`) | N/A — no flag to test | N/A — strict is the *only* state; nothing is silently skipped | N/A | Named only in D-125's prose, not in code | **WEAK** — in-progress (tracked as W1/S3), not silently abandoned: nothing is skipped today, the convenience flag itself just isn't built yet on this surface |
| 3 | `TAILNET_AUTH_BYPASS_ENABLED` (Workbench BFF) | Python: `modules/workbench/api/app/config/settings.py:125` (`bool = False`), consumed by `modules/workbench/api/app/runtime/auth.py:80-111`. **Deploy: `deploy/workbench.yaml:58` — `TAILNET_AUTH_BYPASS_ENABLED: ${WORKBENCH_TAILNET_AUTH_BYPASS_ENABLED:-true}`** | Whether the Workbench requires Authentik identity headers, or accepts a Tailscale-Serve login header / tailnet-forwarded IP instead, with zero Authentik check | **Built** — full IP/CIDR-scoped, fail-closed-on-missing-config implementation; tested (`modules/workbench/api/tests/test_auth.py`, `TestFeatureGatedTailnetBypass` and siblings) | **Yes**, in the Python unit suite | **Code default: strict (`False`)**. **Deployed default: permissive (`true`)** — the compose manifest overrides the safe code default the wrong direction | Not verified in code (no logger call in `auth.py`'s bypass branches) | Comment says "Disable after Authentik activation" — Authentik is already wired live in the same file (lines 149-162), i.e. the stated precondition already appears met, yet the flag still defaults on | **VIOLATION of D-127 Rule 0** — see Finding 1 below, the single worst finding in this audit |
| 4 | `<APP>_TAILNET_AUTH_BYPASS_ENABLED` (Platform API / agentos-api) | `server/api/tailnet_auth.py:36-122`, consumed `server/api/main.py:58-90` with `app_prefix="PLATFORM_API"` | Same mechanism as #3, scoped to the Platform API | **Built**, fail-closed, logs a JSON event (`tailnet_auth.py:107-121`) naming the bypass | Not directly verified in this pass (out of the three swept subtrees' direct test evidence, but the mechanism is identical in shape to #3) | Code default `false` (safe). `PLATFORM_API_TAILNET_AUTH_BYPASS_ENABLED` **does not appear in `deploy/exec.yaml` at all** — falls through to the safe code default | **Yes** — structured JSON log line, `tailnet_auth.py:107-121` | Referenced in `docs/reviews/2026-08-29-tailnet-testing-bypass-all-surfaces.md`, though that doc's own "Implemented slice" section is stale (claims `AGENTOS_TAILNET_AUTH_BYPASS_ENABLED=false` is in `deploy/exec.yaml`; it is not — the var is simply absent under any prefix) | **OK**, with a doc-drift note |
| 5 | `MCP_DIRECT_BYPASS_ALLOWED` | `modules/workbench/api/app/config/settings.py:61,174`; deploy `deploy/workbench.yaml:92` | Whether Workbench's Tool Explorer may call an MCP server directly instead of only through the audited Portkey/ContextForge door | **Built** | **Yes** — `modules/workbench/api/tests/test_mcp_servers_config.py` (`test_default_exposes_no_direct_mcp_door`, `test_direct_server_is_rejected_without_explicit_diagnostic_bypass`, etc.) | `False` in both code and deploy manifest — correct | Not verified | None stated — framed as a permanent diagnostic escape hatch rather than a temporary dev-stage gate | **OK** |
| 6 | `SBV_CUSTODY_ENABLED` | `server/tools/parsers/messaging/sbv_sms.py:338-339` (see Finding 2 below for full quote) | Whether an SMS-XML import via the SBV (primary) parser path performs H1/H2/H3 custody-hash reconciliation against SBV's independently computed hashes | **Built and functionally complete** — `server/evidence/custody.reconcile_sbv_import()` | **Yes** — `tests/test_sbv_custody.py::test_sbv_sms_reconcile_disabled_by_default` and `::test_sbv_sms_reconcile_passes_sbv_hashes` | **Permissive** — unset means custody reconciliation is silently skipped; module docstring (`sbv_sms.py:26-28`) says outright "has no default. Unset means custody reconciliation is skipped even on the SBV path" | **No** — zero logging calls anywhere in `sbv_sms.py`; the skip is silent even at DEBUG level | **No** — a 2026-08-23 prior audit (`docs/reviews/2026-08-23-cross-repo-evidence-audit/verify-11-custody-mandate.md:97`) already flagged "not documented… current no-default is a build convenience, not policy," and no owner ruling has landed since | **WEAK** — see Finding 2, the coordinator's specifically-requested deep-dive |
| 7 | `app.evidence_live` (dev-mode immutability gate) | `sql/0009_raw_layer_and_derivation.sql:174` (`evidence.raw_no_mutate()`); `sql/0031_dev_mode_immutability_gate.sql:47,81,96` (`evidence.source_immutable_core()`, `evidence.forbid_mutation()`, `working.forbid_mutation()`) | Whether the append-only/immutability guard triggers on `evidence.*` (write-once source, custody events) and the `working.*` append-only ledgers actually block mutation | **Built** — trigger function bodies are complete, unconditionally installed, gated only by the `current_setting` check inside them | **No — zero.** See Finding 3 below | **Permissive** (unset/not `'on'` → guards pass through) — this is a **deliberately owner-ruled exception** to D-127(0), not an oversight: D-110/D-128 explicitly bless "off by default pre-launch, one-line arm at go-live" as the intended shape for this specific flag, and `docs/GUARD-TRIGGER-DISPOSITION.md` (2026-08-30) catalogs all 131 guard triggers by disposition bucket, confirming the deferral is deliberate and tracked, not silent | No log statement in the trigger bodies (a `RAISE EXCEPTION` fires only in the armed/strict branch) | **Yes**, explicit: `ALTER DATABASE <db> SET app.evidence_live = 'on'` is documented in both migrations as the one-line go-live switch; prerequisite is replaying the procedural half of migrations 0035-0054 (D-110) | **WEAK** — the permissive default is owner-sanctioned, but the test gap is exactly what D-128 itself calls a live violation of D-127 |
| 8 | `app.enforce_derived_guard` / `app.deriving` | `sql/0009_raw_layer_and_derivation.sql:281-295` (`analysis.derived_write_guard()`) | Whether writes to `analysis.*` derived tables are restricted to the deriving process (single-writer enforcement, ADR-0045 §B) | **Built** | **No — zero.** Same gap as #7, confirmed by the same searches (Finding 3) | **Permissive** — "inert until switched on," same family/rationale as #7 | No log statement | **Yes** — `ALTER DATABASE <db> SET app.enforce_derived_guard = 'on'`, documented inline | **WEAK** — same reasoning as #7 |
| 9 | `NATIVE_EVIDENCE_ENABLED` | `server/api/main.py:39-42,186`; `server/core/native_evidence_runtime.py:131-134`; deploy: `deploy/compose.yaml:73` (`:-false`), `deploy/exec.yaml:162` (`:?set true only after native evidence canaries pass`, i.e. no default — fails closed if unset) | Whether the native-evidence Weaviate search routes (`/v1/evidence/search`, `/v1/operator/evidence/search`) are registered at all | **Built** — full route registration path exists behind the flag | **Yes** — `tests/test_platform_api_host.py` (multiple `monkeypatch.delenv`/setenv cases) | **Strict/off** in both manifests (one via explicit `false` default, one via hard-fail-if-unset) — correct either way per D-127(0) | Not verified | **Yes** — `deploy/exec.yaml:162` inline requirement string is itself the go-live condition | **OK**, minor note: the two compose files use different mechanisms (silent default vs. required-var) for what should be one contract — worth reconciling under the doc-drift rule, not a violation |
| 10 | `LANGFUSE_ENABLED` | `server/observability/langfuse.py:19-26` | Whether Agno OTel spans (which can carry case content) are additionally mirrored to a Langfuse OTLP sink | **Built** | **No** — zero test references found anywhere in `tests/` | **Off** (safe) — and this is a documented, deliberate privacy decision: ADR-0054 §6, "Case-content safety is fail-closed. Langfuse export defaults off and requires `LANGFUSE_ENABLED=true` plus credentials" | Uses `logger.info`/`logger.warning` for configuration problems, but not a "you turned this on" announcement beyond the one info line on successful configure (`langfuse.py:62`) | Implicit — it's a permanent optional diagnostic sink, not a dev-stage gate that needs removing | **WEAK** (untested only) — capability, default, and intent are all clean |
| 11 | `HORIZON_SCRATCH_LIVE` | `tests/integration/test_ingest_scratch_live.py:29` (`@pytest.mark.skipif`); `.github/workflows/validate.yml:168` | Whether the live-Postgres/live-SBV neutral-ingest integration test runs, vs. being excluded from collection under the default `pytest -q -m 'not integration'` (`pyproject.toml:201`) | **Built** — this is a test-infrastructure opt-in marker, not a production behavior gate | Effectively **one state only ever runs**: the default `validate` CI job never collects this test at all (filtered pre-collection, not even reported skipped); only the `integration` job, which force-sets the var to `1`, ever executes it | N/A — off-state is "test doesn't run," which is correct/intended pytest behavior, not a production-safety concern | N/A | N/A — this is a test scope marker, not a feature flag subject to D-127 | **OK / out of D-127's scope** — flagged for completeness per the task's explicit ask about this var, not because it fits the audit's flag definition |
| 12 | `DISABLE_REGISTRATION` (SBV) | `modules/forks/sbv/internal/auth_handlers.go:31` | Whether new-account self-registration is open on the SBV service | **Built** (upstream/fork code) | Not verified | **Permissive** — default is registration OPEN, documented in that repo's own README as intended | Not verified | Not applicable — separate repository | **Out of scope** — `modules/forks/sbv` is its own independent git root with its own CI (`docs/AGENT_MEMORY.md`); noted for completeness only, not counted in this repo's rank tally |

### Hardcoded (non-flag) permissive postures found in passing

These are **not** environment-toggled dev/prod flags — they're fixed literals in deploy manifests —
so D-127's "both states must be tested / must invert at go-live" test doesn't directly apply. Listed
because the task asked for "any boolean config toggle," and because a reader auditing auth posture
should see them next to the real flags above:

- `deploy/data-weaviate.yaml:30`, `deploy/data-weaviate-native-v1.yaml:15` — `AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: "true"`, hardcoded, not overridable. Documented rationale: tailnet-only exposure, API-key hardening tracked as an open task. Not the cause of the 2026-07-29 public-exposure incident (that was a port-binding bug, since fixed), but it is a standing permissive posture with no toggle to test.
- `deploy/contextforge.yaml:63-71` — `CSRF_ENABLED`, `PASSWORD_CHANGE_ENFORCEMENT_ENABLED`, `PASSWORD_POLICY_ENABLED`, `SECURE_COOKIES` all hardcoded `"false"`, each with an inline rationale comment (tailnet-only, Bearer/Basic-fronted gateway).

---

## Ranked findings

### Finding 1 (worst finding) — `TAILNET_AUTH_BYPASS_ENABLED` defaults to bypass-ON in the deployed Workbench manifest, contradicting the owner's own written contract

**Evidence:**

- `modules/workbench/api/app/config/settings.py:125` — `tailnet_auth_bypass_enabled: bool = False` (safe default in code).
- `deploy/workbench.yaml:55-58`:
  ```yaml
  # Feature-gated owner testing path. Traefik remains the trusted socket
  # peer and X-Real-IP must be inside this Tailscale range. Disable after
  # Authentik activation without changing application code.
  TAILNET_AUTH_BYPASS_ENABLED: ${WORKBENCH_TAILNET_AUTH_BYPASS_ENABLED:-true}
  ```
  `git blame`: committed by Matt Salem, 2026-08-29 16:57:31 -0400 (commit `3a24ed75`) — this is a
  human commit, not an agent's, and it is **still the current state on `main`** (verified via
  `git log -1 --format=%h -- deploy/workbench.yaml` → `ee98b69`, 2026-08-30, which did not touch
  this line).
- The owner's own documented contract, written the *same day* (`docs/reviews/2026-08-29-tailnet-
  testing-bypass-all-surfaces.md:15`): *"the per-application `<APP>_TAILNET_AUTH_BYPASS_ENABLED`
  flag defaults to `false`."*
- This is the exact surface D-125 (2026-09-02) names as needing a dev-auth-bypass flag — meaning
  the mechanism the owner asked D-125 to have built for the Workbench BFF **already existed** since
  2026-08-29, but shipped with its default inverted relative to both its sibling implementation
  (`server/api/tailnet_auth.py`, correctly `false`) and the owner's own contract doc for the pattern.

**Why this is the worst finding:** every other issue in this audit is either an untested-but-
correctly-defaulted gate (custody, immutability) or a not-yet-built convenience flag where nothing
is silently skipped. This one is different in kind: it is a **live, currently-deployed** control on
an admin-facing surface whose *default* is the permissive state — precisely what D-127 Rule 0
prohibits ("a development flag's default IS the production behavior") — and it has been in that
state for four days as of this audit (2026-08-29 → 2026-09-02). Read literally, any Workbench
deployment that doesn't explicitly set `WORKBENCH_TAILNET_AUTH_BYPASS_ENABLED=false` in Coolify is
running with Authentik-header verification bypassable by any request that reaches the Workbench
through the trusted Traefik proxy from a Tailscale CGNAT address — which, given this is described as
a single-owner, tailnet-only platform, is a materially large slice of legitimate traffic, meaning
this "temporary testing path" is likely the *operative* auth path today rather than a rare fallback.

**What is NOT claimed:** this audit did not check the live Coolify environment-variable override for
`WORKBENCH_TAILNET_AUTH_BYPASS_ENABLED` — it is possible an explicit `false` override already exists
there, in which case the manifest default is merely a footgun (still worth fixing) rather than the
live-operative behavior. Per the verify-before-claiming rule, this needs a live Coolify check, not
an assumption either way — flagged as the first remediation item below.

### Finding 2 (coordinator's specific ask #1) — `SBV_CUSTODY_ENABLED`'s unset default silently skips custody hashing; exact loss quantified

**Code path, quoted verbatim** (`server/tools/parsers/messaging/sbv_sms.py:322-339`):

```python
def _reconcile_custody(
    path: Path,
    payload: dict[str, Any],
    client: SBVClient,
    records: list[NormalizedRecord],
    import_id: int | None = None,
) -> dict[str, Any] | None:
    """Forensic custody cross-check (Phase 4): pull SBV's independently-computed
    H1/H3 for this import + the per-record H2s, and reconcile against our OWN H1
    via the custody gate (verified vs integrity_violation, plus H2/H3 evidence
    rows). SBV holds no DB creds -- every write happens in custody.py.

    Opt-in (SBV_CUSTODY_ENABLED) and defensively lazy: ...
    """
    if not os.getenv("SBV_CUSTODY_ENABLED"):
        return None
```

Call site, `sbv_sms.py:441-453` — `_reconcile_custody(...)` is called unconditionally on every SBV
SMS-XML import; when it returns `None` (the unset-flag case), the caller simply omits the
`extra["custody"]` key and proceeds to `return records_out(records, ...)` — **the import completes
successfully, exactly as if custody had been checked and passed.** There is no error, no warning, no
distinguishing field in the returned payload's success case versus its custody-reconciled case. A
`grep -n "log\|warn\|Logger" server/tools/parsers/messaging/sbv_sms.py` (verified) returns zero
matches in the entire module — there is no logging statement anywhere in this file, at any level.

**Exactly what is lost when the flag is off** (tracing `server/evidence/custody.reconcile_sbv_import`,
`server/evidence/custody.py:582-`):

1. **No independent H1 cross-check.** SBV computes its own SHA-256 (H1) of the imported XML file
   independently of this platform; when the flag is on, that value is compared against this
   platform's own independently-computed H1 (`ingest_artifact`). This is the single check that would
   catch a tampered, corrupted, or substituted source file arriving through the SBV path — it never
   runs when the flag is unset.
2. **No `evidence.custody_event` row** (`verified` or `integrity_violation`) is ever written for
   these imports — there is no audit trail entry at all for whether custody was even considered.
3. **No H2 (per-record) evidence-hash rows** and **no H3 (chain) evidence-hash row** are recorded —
   the platform's own custody hash-chain simply has a gap for every message imported through this
   path while the flag is off.
4. Because nothing is logged, this loss is **invisible** at both the file level (no distinguishing
   payload field on success) and the operator level (no log line) — an operator watching the ingest
   run has no signal that custody reconciliation didn't happen.

**Default-intent status:** unowned. A prior audit (`docs/reviews/2026-08-23-cross-repo-evidence-
audit/verify-11-custody-mandate.md:97`) already surfaced this exact gap — *"Intended default of
SBV_CUSTODY_ENABLED? Not documented. Likely ON in production… but no owner ruling found. Current
no-default is a build convenience, not policy"* — and no owner ruling has landed in the ten days
since. Given D-128 frames immutability/custody as *"the property that makes it an EVIDENCE platform
at all,"* a silently-skippable custody check with no owner-set default and no log line is the
platform's own core-premise concern showing up concretely in a specific code path.

**Mitigating context, stated plainly:** per the ingest-day-board contract (`docs/reviews/2026-09-02-
ingest-day-board.md:20-22`), tonight's build scope is explicitly **context-only** — "We don't need to
be able to commit it to evidence. I just want to get it into context… custody/promotion is OUT of
tonight's scope" — so this gap is not currently live-risking evidence integrity for tonight's work.
It becomes load-bearing the moment SBV-parsed SMS imports are promoted toward evidence status.

**Rank: WEAK** (permissive default + silent + no owner ruling on intended default; the reconciliation
logic itself is fully built and tested in both states, which is why this isn't a VIOLATION under the
"capability missing" definition).

### Finding 3 (coordinator's specific ask #2) — zero tests exercise `app.evidence_live` or `app.enforce_derived_guard` in either state, anywhere in the repo

**Confirmed via exact-string search across the entire repository** (not just `tests/`):

```
Grep "evidence_live|enforce_derived_guard" across the whole repo -> 14 files, ALL of them either
sql/*.sql (the migrations themselves) or docs/**/*.md (audit/handoff prose). ZERO matches in any
*.py file anywhere in the repository, including tests/, modules/workbench/api/tests/, and scripts/.
```

The one test that comes closest, `tests/test_audit_ledger.py`, does **not** exercise this gate: its
`_PREREQ_SQL` (lines 60-71) hand-writes a **pre-0031, always-strict, ungated** copy of
`working.forbid_mutation()` —

```python
_PREREQ_SQL = """
CREATE SCHEMA IF NOT EXISTS working;
CREATE OR REPLACE FUNCTION working.forbid_mutation() RETURNS trigger AS
$fn$
BEGIN
    RAISE EXCEPTION '% is append-only: % blocked (corrections are new rows)',
        TG_TABLE_NAME, TG_OP;
END
$fn$ LANGUAGE plpgsql;
"""
```

— reproduced from `sql/0017_append_only_guards.sql`, explicitly *not* the actual `sql/0031`-gated
version that checks `current_setting('app.evidence_live', true)` first. This test therefore proves
the *unconditional* 0017-era guard still raises, which is a different function body than what's
actually deployed — it says nothing about `app.evidence_live` in either state.

`tests/test_matter_migration.py:66` only asserts the string `"execute function
working.forbid_mutation()"` appears in normalized migration SQL text — a syntax/wiring check, not a
behavioral one.

No file named `test_0009*.py` or `test_0031*.py` exists in `tests/` at all, despite the repo's own
established convention (`test_0036_context_import_foundation.py`, `test_0037_platform_runtime_
connect.py`, `test_0038_platform_runtime_schema_version_probe.py`, `test_0039_context_source_
retention_lock.py` — one test file per migration for exactly this kind of guard/contract migration).

**Test files that SHOULD exist, by the repo's own naming convention:**

1. **`tests/test_0031_dev_mode_immutability_gate.py`** — apply `sql/0031_dev_mode_immutability_
   gate.sql` (plus its `sql/0009` prerequisite) to a real/scratch Postgres (same pattern as
   `test_audit_ledger.py`'s `audit_engine` fixture: throwaway DB, read migration SQL from disk, not
   hand-copied) and assert, for **all three** gated functions
   (`evidence.source_immutable_core()`, `evidence.forbid_mutation()`, `working.forbid_mutation()`):
   - `app.evidence_live` unset/`'off'` → UPDATE/DELETE succeeds (dev mode, guard passes through).
   - `app.evidence_live = 'on'` → UPDATE/DELETE raises the documented exception (armed/strict mode).
   - the one legal mutation under `evidence.source_immutable_core()` (marking `superseded_by`) still
     succeeds even when armed.
2. **`tests/test_0009_raw_layer_and_derivation.py`** — same live-DB pattern, covering:
   - `evidence.raw_no_mutate()` under both `app.evidence_live` states (the raw-layer sibling of the
     0031 functions, gated identically but defined in 0009).
   - `analysis.derived_write_guard()` under all three states of `app.enforce_derived_guard` ×
     `app.deriving`: guard unarmed (write always succeeds), guard armed + `app.deriving='on'` (write
     succeeds), guard armed + `app.deriving` unset (write raises).

**Rank: WEAK**, per the task's own three-bucket rubric ("built but untested" is explicitly WEAK, not
VIOLATION) — but the owner's own D-128 language calls an untested guard behind an off switch a
*"violation of D-127,"* so this finding should not be read as low-priority merely because of its
bucket label. It is the most concretely actionable item in this audit: the fix is two well-scoped
test files following an existing, established pattern in the same repo.

---

## Everything else checked and found clean (stated plainly, not manufactured)

- **`NATIVE_EVIDENCE_ENABLED`** — capability fully built, defaults safely-off in both deploy
  manifests (via different mechanisms — see table note), tested in both states
  (`tests/test_platform_api_host.py`), removal condition is the manifest's own inline requirement
  string. This is the cleanest example in the codebase of a D-127-compliant cutover flag.
- **`MCP_DIRECT_BYPASS_ALLOWED`** — correct default, tested in both states, fail-closed.
- **`<APP>_TAILNET_AUTH_BYPASS_ENABLED` (Platform API / agentos-api variant)** — correctly defaults
  to `false` in both code and the live deploy manifest (the var is simply absent from
  `deploy/exec.yaml`, which falls through to the safe code default), logs a structured JSON event
  naming the bypass on every use. Only issue found: the doc describing it
  (`docs/reviews/2026-08-29-tailnet-testing-bypass-all-surfaces.md`) claims an "Implemented slice"
  that sets `AGENTOS_TAILNET_AUTH_BYPASS_ENABLED=false` in `deploy/exec.yaml`; that exact variable
  name is absent from the file today (doc drift, not a security issue, since absence has the same
  safe effect as an explicit `false`).
- **`LANGFUSE_ENABLED`** — capability real, default matches an explicit ADR (0054 §6) privacy
  decision, only gap is test coverage.
- **`modules/workbench/web/**` (the whole TypeScript frontend)** — genuinely zero feature flags of
  any kind: no `process.env.*` behavior gates, no flag-service SDK, no conditional route/component
  gating. Nothing to find here is itself a clean result, independently confirmed.
- **`RegisterStructuredELTActivities` (`modules/engine/activities/register.go:222-230`) and
  `NewParserActivities`/`RegisterParserActivities` (same file)** — these are **not** flags (no env
  var, no boolean), but they match the exact "capability declared, never activated" shape the task
  asked auditors to watch for: the Activity bodies exist and compile, but neither is called from
  `uiwworker.RegisterAll` (`modules/engine/uiwworker/worker.go:44-60`), so they can never run on the
  deployed worker. This is **self-disclosed, not hidden** — the code comment at `register.go:222-227`
  states plainly it is "not yet called… the exact remaining step the BUILD LANE E1 handoff reports as
  outstanding," and production parsing already has a working path (n8n webhook activities registered
  directly in `RegisterAll`). Listed here for completeness per the audit's mandate, not counted
  against the flag tally since it isn't a flag and isn't silently skipped — it's an openly tracked
  wiring gap.
- **The immutability-guard deferral itself (D-110/D-128), as a *decision*** — is not a violation.
  `docs/GUARD-TRIGGER-DISPOSITION.md` (2026-08-30) catalogs all 131 guard triggers across 84 tables
  into four dispositions (0 to replay now, 3 wrong-place/delete, 8 moot, 120 correctly left off for
  active development), which is exactly the kind of accounting D-127/D-128 demand — the gap this
  audit found is specifically the *test* coverage (Finding 3), not the disposition decision.

---

## Remediation list, ordered by severity

1. **Live-check and, if needed, correct `WORKBENCH_TAILNET_AUTH_BYPASS_ENABLED` in the actual
   Coolify environment for the Workbench app.** If no explicit override is set, the deployed
   Workbench is running with Authentik bypass ON by default. Either way, fix
   `deploy/workbench.yaml:58`'s manifest default from `:-true` to `:-false` to match the owner's own
   2026-08-29 contract doc and the Python code's own safe default — the manifest should never be the
   thing that has to be remembered to be overridden.
2. **Write `tests/test_0031_dev_mode_immutability_gate.py` and `tests/test_0009_raw_layer_and_
   derivation.py`** per the exact scope in Finding 3, using the live-scratch-Postgres pattern already
   established in `tests/test_audit_ledger.py`. This directly closes the gap D-128 itself names as an
   open D-127 violation.
3. **Get an owner ruling on `SBV_CUSTODY_ENABLED`'s intended default**, and add a log line (`logger.
   info`/`warning`) to `_reconcile_custody`'s early return so a skipped custody check is visible in
   ops/audit logs even while the ruling is pending. This is cheap, immediate, and directly serves
   D-127(5) ("a flag must never suppress a check into silence") regardless of which way the default
   ruling eventually goes.
4. **Finish the `PLATFORM_DEV_AUTH_BYPASS` wiring on the UIW starter's actual HTTP auth layer**
   (`runtimeapi/uiw_preview.go`, `source_context.go`, `httpapi.go`, `acquisition/upload.go`) to match
   D-125's original scope — today only the schema-admission probe implements it (well); the HTTP
   surfaces D-125 explicitly named remain unconditionally strict with no relax path at all, which is
   safe but incomplete relative to the ruling. Land and commit the in-flight `uiw_schema_probe.go` /
   `sql/0069` work first (currently uncommitted working-tree changes as of this audit).
5. **Reconcile `NATIVE_EVIDENCE_ENABLED`'s two different unset-mechanisms** (`deploy/compose.yaml`'s
   silent `:-false` vs. `deploy/exec.yaml`'s hard-fail `:?`) into one documented contract — both are
   safe, but they're inconsistent, which is exactly the doc/config-drift pattern the platform's own
   standing rules flag as the enemy.
6. **Correct `docs/reviews/2026-08-29-tailnet-testing-bypass-all-surfaces.md`'s stale "Implemented
   slice" section** — it names `AGENTOS_TAILNET_AUTH_BYPASS_ENABLED` as present in `deploy/exec.yaml`;
   that exact variable is absent today (safe by accident, not by the documented mechanism).
