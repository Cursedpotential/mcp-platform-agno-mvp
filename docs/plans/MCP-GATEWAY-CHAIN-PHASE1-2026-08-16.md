# MCP Gateway Chain — Phase 1 Design and Pre-Mortem

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **STATUS: LOCAL CONTRACT COMPLETE; ACTIVATION HELD**

## Slice

ContextForge is the single authored MCP registry. Each approved virtual server is published
one-way to Portkey MCP Gateway. Operators and agents consume the Portkey endpoint; Portkey
authenticates, authorizes, traces, and proxies to ContextForge. No tool schema is independently
authored in Portkey.

The first manifest entry is `platform-tools`. Graphiti publication remains held until its full
write surface, HorizonContext binding, ADR-0046 annotations, and R9 activation gates are proved.

## Implemented local controls

- `docker/gateway/mcp/publications.json` declares ContextForge authority, Portkey downstream,
  env-only URLs/credentials, exact-source parity, annotations, and trace correlation.
- `scripts/verify_mcp_chain.py` defaults to offline manifest validation. `--live` performs only
  MCP `initialize` and paginated `tools/list` against both endpoints, then compares tool names,
  schemas, descriptions, and annotations. It rejects cursor loops and duplicate tool names and
  cannot register a server or invoke a tool.
- Workbench exposes no MCP server by default. Normal entries require `gateway:"portkey"`;
  direct AgentOS/ContextForge entries require `MCP_DIRECT_BYPASS_ALLOWED=true`.
- `deploy/contextforge.yaml` requires a dedicated PostgreSQL DSN. The old SQLite bind is retained
  as migration/rollback input and is never deleted.

## Pre-mortem

This activation had failed because:

1. Portkey became a second authored registry and silently drifted from ContextForge.
2. The bare ContextForge `/mcp` root was published instead of `/servers/<uuid>/mcp`.
3. The OSS Portkey LLM container was mistaken for the hosted/enterprise MCP control plane.
4. SQLite was abandoned before every gateway, server, tool, resource, prompt, and credential
   reference was reconciled into the dedicated PostgreSQL database.
5. A destructive or horizon-unbound tool was made visible without all ADR-0046 annotations.
6. Portkey logged a call, but its trace could not be correlated with ContextForge and the
   hash-chained `ops.audit_ledger` entry.
7. Workbench automatically fell back to a direct MCP door during a gateway failure.
8. Credentials or raw tool-call payloads were committed to the repository.

The plan changed accordingly: activation requires exact catalog parity, fail-closed Workbench
configuration, PostgreSQL reconciliation, explicit Portkey MCP product proof, and a three-layer
trace exercise. No broad fallback is permitted.

## Owner activation packet

Separate approval must name or provide:

1. Dedicated ovh-files PostgreSQL database/role and `CONTEXTFORGE_DATABASE_URL`.
2. ContextForge image/version migration path plus a verified SQLite export/import/reconciliation
   procedure; the original bind remains recoverable.
3. Exact ContextForge virtual-server UUID and JWT for `platform-tools`.
4. Portkey hosted/enterprise MCP workspace, server slug, API key, and upstream header/JWT
   injection policy. The current OSS `portkeyai/gateway:1.15.2` LLM service is not accepted as
   proof of this control plane.
5. Approved tool allowlist after every tool passes annotations, pagination, error, horizon, and
   audit review.
6. Permission to register/publish, update Coolify envs/watch paths, redeploy ContextForge and
   Workbench, and run one non-sensitive tool call for correlated trace proof.

Until all six are approved, run only:

```powershell
uv run python scripts/verify_mcp_chain.py
```

`--live` remains held because it requires the exact endpoints and credentials above. It is
read-only, but its result is meaningful only after downstream publication exists.

## Validation evidence

- Offline manifest verifier: `manifest-valid` for `platform-tools`.
- MCP chain contract tests: 7 passed, including pagination, cursor-loop, duplicate-name,
  drift, annotation, and read-only-method guards.
- Full root unit suite: 799 passed, 24 skipped, 1 deselected.
- Full Workbench API suite: 105 passed.
- Root Ruff, format, and mypy: pass (223 formatted files; 144 typed source files).
- Workbench Ruff and format: pass (86 files); changed settings mypy: pass.
- Publication JSON and changed deployment YAML parse successfully.
- No live MCP endpoint, registry, database, model, corpus, migration, deployment, or tool was
  contacted or changed. Live publication parity and trace correlation remain UNKNOWN.
