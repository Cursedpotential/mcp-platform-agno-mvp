# Matter MVP Activation Preflight — Pre-Mortem (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
> _Platform API auth cutover: Codex · GPT-5.6-Sol · 2026-08-29._

STATUS: COMPLETE LOCALLY — read-only release gate; no apply, deployment, or secret write

## Intended outcome

`scripts/_matter_activation_preflight.py` turns the remaining activation claims
into itemized, machine-readable checks. Static scope validates the checkout and
release contract. Database scope validates the canonical PostgreSQL 18 extension
set and a uniform migration state without pretending services are deployed.
Activation scope defaults to migrations present and additionally requires
the runtime-mounted Platform API bearer plus live Workbench/Platform/Weaviate read paths.

The preflight never applies migrations, writes database rows, changes Coolify,
or prints credential values. Any missing requirement returns `NOT READY` and a
nonzero exit code.

## Pre-mortem failures and controls

| Failure | Consequence | Control | Residual risk |
|---|---|---|---|
| A partial migration chain looks activated | 0030 runs over an inconsistent horizon schema | Inspect one marker per migration and require all five uniformly absent or present | Marker presence does not replace migration transaction logs |
| A stock PostgreSQL instance is accepted | Full-baseline rehearsal gives false confidence | Require PostgreSQL 18 plus `pg_duckdb`, `pgcrypto`, `postgis`, and `vector` | Extension presence does not prove the image digest |
| Workbench deploys without inbound auth | Privileged Platform proxy becomes exposed | Verify Authentik/Tailscale ingress plus the distinct runtime-file Platform API bearer | Named OIDC principals remain a separate rollout |
| Health checks pass while the product path fails | Deployment is called live without real dependencies | Probe Matter, evidence-only Knowledge, Platform Matter, and Weaviate readiness paths | A one-row/read probe is not a load or contamination test |
| Preflight leaks secrets | Credentials enter logs or durable reports | Accept only the non-secret bearer-file path and emit statuses/types, never values or DSNs | The mounted file still requires operator custody |
| A dirty or unpushed tree is released | Runtime cannot be traced to reviewed source | Static scope requires clean `HEAD == origin/main` | Remote branch protection remains external |

## Commands

Static checkout proof:

```powershell
uv run python scripts/_matter_activation_preflight.py --scope static --json
```

Activation proof reads the database DSN from its named environment variable and
the Platform bearer from its mounted file. Do not place secret values on the command line:

```powershell
$env:MATTER_PREFLIGHT_DATABASE_URL = '<reviewed target DSN>'
uv run python scripts/_matter_activation_preflight.py --scope activation `
  --expected-migrations present `
  --workbench-url '<workbench base URL>' `
  --platform-api-url '<private Platform API base URL>' `
  --platform-api-bearer-file '<mounted bearer file path>' `
  --weaviate-url '<weaviate base URL>' `
  --json
```

A disposable pre-apply baseline rehearsal uses `--scope database
--expected-migrations absent`; it does not require live service URLs or
credentials.

## Validation evidence

- Focused Ruff and format checks: **PASS**.
- Focused pytest exercises the repository contract, runtime-file credential boundary,
  uniform migration states, service-path coverage, extension/version failures,
  and secret-free report: **7 passed**. Full root suite: **750 passed / 24 skipped**.
- After commit/push, static scope returned **READY** with every check passing,
  including clean worktree and `HEAD == origin/main` at `6c37548`.
- Activation scope has not been run against a deployed target because bearer-file
  provisioning, migration application, and deployment remain owner-held.
- A deliberate read-only negative database run against the quarantined stock
  PostgreSQL 18 validator connected successfully, confirmed migrations 0026–0030
  uniformly absent, rejected the target for missing canonical extensions, and
  returned `NOT READY`. The server was stopped and port 55439 is closed.
