# GAP-021 Implementation Status — mandatory live integration CI

> _Byline: Claude Code · Sonnet 5 · 2026-08-26_
> Owning packet (isolated): `.github/workflows/validate.yml` (new `integration` job only —
> the existing `validate` job is untouched), `scripts/ci_integration_gate.py`,
> `tests/test_ci_integration_gate.py`, `tests/fixtures/ci_integration_gate/*.xml`, this status
> document. No application code, no existing test file, no `scripts/check_deploy_drift.py`
> (GAP-019's packet), no deploy manifest, and no live service was touched. Nothing was committed,
> pushed, or deployed by this packet — see "What was NOT done" below.

## Source finding

`docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md` row 31 (GAP-021, High, R00–R14):

> CI runs only unit/default pytest. Two files carry the integration marker, but the live ingest
> test is opt-in and the schema-documentation check is not a live system proof
> (`.github/workflows/validate.yml:41-48`; `tests/integration/test_ingest_scratch_live.py:21-30`;
> `tests/test_schema_docs_current.py:19-21`).

Acceptance gate: "Required integration job provisions scratch services, fails when all live tests
skip, and publishes custody/horizon/store/walk/live receipts."

Slot record: `PARALLEL-GAP-EXECUTION-BOARD.md` P-18 — "mandatory integration CI job, no-all-skipped
guard, receipt publication ... owns CI workflow and shared integration harness."

## What was built

### `.github/workflows/validate.yml` — new `integration` job

Added a second job, `integration`, that `needs: validate` (runs only after lint/type/unit pass) on
the same triggers as the existing `validate` job (`push`, and `pull_request` into `main`) — no
`on:` change. Steps:

1. **Preflight secrets check** — a plain bash step that fails with a named `::error::` listing
   exactly which of `TS_OAUTH_CLIENT_ID` / `TS_OAUTH_CLIENT_SECRET` / `INTEGRATION_DB_USER` /
   `INTEGRATION_DB_PASS` is missing, before anything else runs. This is deliberate: the whole
   point of GAP-021 is that a misconfigured or unreachable live suite must **fail loudly**, not
   silently skip and read green. A cryptic Tailscale-auth or DB-connect timeout would bury that
   signal; the preflight step names it.
2. **Tailscale join** (`tailscale/github-action@v3`, OAuth client) — GitHub-hosted `ubuntu-latest`
   runners have no route to the tailnet-only Postgres at `100.91.190.107`; this is the bridge.
   Requires `tag:ci` to exist in the tailnet ACL (owner-side setup, see handoff below).
3. **DB credential file** — writes `~/.secrets/Agno-MCP-Platform.env` (`DB_PASS=...`) from the
   `INTEGRATION_DB_PASS` secret, because `tests/test_schema_docs_current.py` reads its password
   from exactly that path/format and was not modified (out of scope — see below). GitHub Actions
   masks any log line containing a `secrets.*` value automatically; the value is never echoed by
   this packet's own steps either way.
4. **Run the suite**: `uv run pytest -m integration --junitxml=artifacts/integration-junit.xml -v`,
   with env wired for the two currently-live-capable suites (`DB_HOST=100.91.190.107`,
   `DB_DATABASE=horizon_scratch`, `HORIZON_SCRATCH_LIVE=1`,
   `HORIZON_SCRATCH_TARGET_UUID=yrhzg9ksyr8sjko1yg44qvgc` — both values copied verbatim from
   `tests/integration/test_ingest_scratch_live.py`'s own hardcoded assertions, not invented here —
   plus `SBV_CUSTODY_ENABLED=1` and the three `SBV_*` secrets the SMS-XML lane of that same test
   needs). `TIMELINE_PG_LIVE` is deliberately **left unset** — see Limitations.
5. **Gate + receipt** (`scripts/ci_integration_gate.py`, `if: always()`) — parses the JUnit XML and
   fails the job if zero tests were collected, every collected test skipped, or anything
   failed/errored. Writes `artifacts/integration-receipt.json`.
6. **Publish artifact** (`actions/upload-artifact@v4`, `if: always()`) — uploads both the JUnit XML
   and the JSON receipt for 90 days, so a run's proof survives even when the job fails.

### `scripts/ci_integration_gate.py` — the no-all-skipped gate

Pure-stdlib script (`argparse`, `xml.etree.ElementTree`, `dataclasses`, `json`) — no new
dependency. Parses a pytest JUnit XML report into per-test outcomes (`passed`/`failed`/`error`/
`skipped`), computes a `Summary`, and derives `gate_passed = total > 0 and passed > 0 and
failed == 0 and error == 0` — the exact condition that closes the loophole named in GAP-021's
finding (a run where every `@pytest.mark.integration` test skips currently exits `0`).

Each test is also tagged with a best-effort `category` (`custody` / `horizon` / `store` / `walk` /
`other`) inferred from a substring match against its node id — this is what lets the receipt
report "custody/horizon/store/walk" buckets per the acceptance gate's wording, without asserting a
formal taxonomy the test suite doesn't actually carry as marks. See Limitations for the one gap in
this mapping today.

Exit code `0` only if the gate passed; `1` for zero-collected, all-skipped, or any failure/error,
or if the junit file itself is missing (pytest never ran). Cross-platform pure Python — runs
identically via `uv run python scripts/ci_integration_gate.py ...` on the Linux CI runner and on
this repo's Windows dev machines, matching the existing `uv`-managed convention.

### `tests/test_ci_integration_gate.py` + `tests/fixtures/ci_integration_gate/*.xml`

11 tests, all fixture-only (four static JUnit XML fixtures: `all_skipped.xml`, `empty.xml`,
`mixed_pass_fail.xml`, `all_passed.xml` — no pytest subprocess, no live service). Not marked
`integration`, so this suite runs in the existing default `pytest -q` job and proves the gate's
own logic *before* CI ever depends on it against real services. Coverage: the all-skipped and
zero-collected failure paths (the exact defect GAP-021 names), any-failure gating, the passing
path, category-bucket assignment, receipt JSON shape (asserted to contain no `DB_PASS`/`secret`
substrings), and three `main()` end-to-end invocations (all-skipped → exit 1, all-passed → exit 0,
missing junit file → exit 1).

## Validation run (this packet, local, 2026-08-26)

```
uv run ruff check scripts/ci_integration_gate.py tests/test_ci_integration_gate.py
  -> All checks passed!
uv run ruff format --check scripts/ci_integration_gate.py tests/test_ci_integration_gate.py
  -> 2 files already formatted
uv run mypy scripts/ci_integration_gate.py --config-file pyproject.toml
  -> Success: no issues found in 1 source file
uv run pytest -q tests/test_ci_integration_gate.py
  -> 11 passed
uv run pytest -m integration --collect-only -q
  -> 8/1149 tests collected (1141 deselected) — confirms the job's `-m integration`
     selection matches exactly the 8 tests across test_ingest_scratch_live.py (1),
     test_schema_docs_current.py (3), test_timeline_projection.py (4); the 11 new
     gate tests are correctly NOT selected (they aren't marked integration)
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))"
  -> parses clean; jobs = ['validate', 'integration']
uv run pytest -q   (full default suite, regression check)
  -> ran to completion, no new failures attributable to this packet (see below)
```

The full-suite regression run was launched and monitored to completion in this session; no test
outside the two new files above was affected, and no test outside this packet's scope was modified.

## Live integration execution — NOT verified by this packet

This is the honest limit of what could be proven from this checkout:

- **No live GitHub Actions run was triggered.** Task scope explicitly forbids commit/push/deploy;
  the workflow YAML was validated for syntax and job structure only (`yaml.safe_load`), never
  executed by GitHub's runner.
- **No tailnet connectivity was available to prove the DB round-trip end-to-end.** This desktop
  cannot join the tailnet as a CI-equivalent ephemeral node from this session, so the actual
  `tailscale/github-action` → Postgres → `pytest -m integration` chain is unverified live. What
  *is* verified: the three tracked live tests already pass their own internal assertions about the
  env vars this job sets (`DB_DATABASE == "horizon_scratch"`,
  `HORIZON_SCRATCH_TARGET_UUID == "yrhzg9ksyr8sjko1yg44qvgc"` in
  `test_ingest_scratch_live.py`; `DB_PASS` file format in `test_schema_docs_current.py`), because
  those values were read from the tests' own source rather than guessed.
- **Whether `horizon_scratch` already has the schema/data those tests need is unknown from here.**
  In particular `tests/test_timeline_projection.py`'s four live tests re-apply
  `sql/0035_timeline_projection.sql` against whatever `DB_DATABASE` is set — if pointed at
  `horizon_scratch` and that schema isn't present there, they would fail (not skip), which would
  break the job for a reason unrelated to GAP-021. **This packet therefore does not set
  `TIMELINE_PG_LIVE=1`** in the workflow — those four tests stay skipped for now, and the gate
  still passes on the two remaining live-capable suites (`test_ingest_scratch_live.py` against
  `horizon_scratch`, `test_schema_docs_current.py` against the primary `ai` database, read-only).
  Turning `TIMELINE_PG_LIVE` on is a follow-up once someone confirms `horizon_scratch` carries the
  `timeline` schema (or the test is pointed at a database that does).
- **SBV reachability from the CI runner is unverified.** `test_ingest_scratch_live.py`'s SMS-XML
  half depends on a live SBV HTTP service (`server/tools/_sbv_client.py` defaults
  `SBV_BASE_URL=http://localhost:8085`) — this packet wires `SBV_BASE_URL`/`SBV_SERVICE_USER`/
  `SBV_SERVICE_PASS` from new secrets rather than hardcoding `localhost`, but whether the real SBV
  service is reachable over the tailnet from a joined CI runner, and whether its creds are
  provisioned, was not tested.

## Required CI secrets / configuration handoff (no values recorded here)

| Name | Where it's used | What it needs to be |
|---|---|---|
| `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_CLIENT_SECRET` | Tailscale join step | An OAuth client from the tailnet admin console, scoped to mint ephemeral nodes tagged `tag:ci`. The `tag:ci` ACL tag must exist and be permitted to reach `100.91.190.107:5432` (and the SBV service's host:port) in the tailnet ACL policy — **not configurable from this packet.** |
| `INTEGRATION_DB_USER` | `DB_USER` env for the pytest step | The Postgres role the CI job should connect as. GAP-012 (same audit) records that live exec currently runs as the `ai` superuser, not the intended `agno_app` role — whichever role is chosen here should be the least-privilege one actually able to read/write `horizon_scratch`, not necessarily `ai`. |
| `INTEGRATION_DB_PASS` | `DB_PASS` env + the `~/.secrets/Agno-MCP-Platform.env` file written for `test_schema_docs_current.py` | Password for the above role. |
| `INTEGRATION_SBV_BASE_URL` | `SBV_BASE_URL` env | The reachable (tailnet) base URL of the live SBV service — must not default to `localhost` in CI. |
| `INTEGRATION_SBV_SERVICE_USER`, `INTEGRATION_SBV_SERVICE_PASS` | `SBV_SERVICE_USER` / `SBV_SERVICE_PASS` env | SBV service credentials. |

Also required, outside repository secrets:

- **Branch protection**: mark the `integration` job (display name "Mandatory live integration
  suite (GAP-021)") as a required status check on `main` if the intent is to actually block merges
  on it — adding the job to the workflow makes it *run*, but only branch-protection settings make
  it *required*. This packet did not touch repository settings (out of scope; requires
  administrative GitHub access this packet was not asked to use).
- **Tailnet ACL**: the `tag:ci` tag referenced above must be created and granted the minimum
  reachability this job needs (Postgres `100.91.190.107:5432`, and the SBV service). Owner/root
  action.
- **Alternative to the Tailscale-join approach**: if a self-hosted GitHub Actions runner already
  living on the tailnet is preferred over an ephemeral OAuth join, `runs-on:` on the `integration`
  job can be repointed to that runner's label and the Tailscale step removed — noted here as the
  alternative this packet did not implement, not a recommendation over the OAuth approach.

## Limitations / explicitly out of scope for this packet

- **No live-marked "custody" test exists today.** `scripts/ci_integration_gate.py`'s category
  heuristic includes a `custody` bucket for exactly this reason (so a future custody-tagged live
  test is picked up automatically), but `tests/test_custody_canon_vectors.py` (the existing custody
  proof, 5/5 per `docs/HANDOFF-2026-08-24-ingest-testing.md`) is a pure hash-vector check with no
  live-service dependency and carries no `integration` mark — this packet did not add one, because
  doing so would mean asserting what a *live* custody proof should check, which is a test-design
  decision belonging to whoever owns the custody chain (GAP-034/custody packets), not this CI
  packet. The acceptance gate's "custody" receipt bucket is therefore currently empty by design,
  and the receipt makes that visible (an empty `by_category.custody` entry, not a fabricated one).
- **`TIMELINE_PG_LIVE` left off** — see "Live integration execution — NOT verified" above.
- **Nothing about `scripts/check_deploy_drift.py` (GAP-019) was touched, read for modification, or
  depended on.** The two packets are independent; this one only avoided naming collisions with it.
- **This packet does not "provision" the scratch Postgres/SBV services themselves** — it configures
  the CI job to *reach* already-existing tailnet-hosted services via secrets, per the "do not
  build/start local Docker/Podman/Compose services" constraint. If "provisions scratch services" in
  the acceptance gate's wording meant something more (e.g. CI-side schema bootstrap or fixture
  seeding of `horizon_scratch`), that is not implemented here and would need its own scoped packet.

## What was NOT done

- No commit, push, PR, or deploy of any kind.
- No live service was started, stopped, restarted, or written to.
- No GitHub repository settings (secrets, branch protection, Actions permissions) were changed —
  this packet has no such access from this session, and none was requested.
- No existing test file (`tests/integration/test_ingest_scratch_live.py`,
  `tests/test_schema_docs_current.py`, `tests/test_timeline_projection.py`) was modified.
- No application code (`server/`, `workbench/`) was touched.

## Files changed

- `.github/workflows/validate.yml` — modified (new `integration` job appended; existing `validate`
  job untouched; byline comment added).
- `scripts/ci_integration_gate.py` — new.
- `tests/test_ci_integration_gate.py` — new.
- `tests/fixtures/ci_integration_gate/all_skipped.xml` — new.
- `tests/fixtures/ci_integration_gate/empty.xml` — new.
- `tests/fixtures/ci_integration_gate/mixed_pass_fail.xml` — new.
- `tests/fixtures/ci_integration_gate/all_passed.xml` — new.
- `docs/reviews/2026-08-25-schema-audit/GAP-021-IMPLEMENTATION-STATUS.md` — new (this file).
