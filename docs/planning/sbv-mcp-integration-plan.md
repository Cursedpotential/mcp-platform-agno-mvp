# SBV Integration Plan — whole app usable + every function MCP-callable

> _Byline: Claude Code · Opus 4.8 · 2026-06-25 (PIPELINE lane)_
> Goal (owner): SBV usable as a **viewer/exporter** AND **every SBV function callable** from a
> workflow, an agent, another user, or any surface (API → MCP, ADR-0023). SBV ~~is~~ was the **primary** (DEMOTED 2026-08-02 (gap-review P0-1: unscoped /api/activity) — shadow until import-scoped reads)
> SMS-XML parser; the custom `evidence/tools/sms_xml.py` is the **fallback**.

## Live state (verified 2026-06-25, OVH-1 `platform-tools` container)
- ✅ SBV viewer/exporter UP: `sbv RUNNING` 2d, GUI `200` on `:8085`, tailnet `http://100.72.169.40:8085`.
- ⚠️ SBV `/api/v1/*` is **auth-gated (401)**; no `SBV_*` cred in env. GUI routes (`/`, `/messages`, `/health`) open. **Owner does NOT have the auth** (built by another agent) → must crack from source or disable.
- ❌ `tools-facade` (`:8090`) **FATAL**: `ModuleNotFoundError: No module named 'evidence.registry'` (evidence package not importable in the slim container). Down 2 days.
- ✅ ContextForge healthy (the federation point). SBV baked into `platform-tools` image (`ghcr.io/lowcarbdev/sbv:stable`).

## Decisions
- MCP exposure = **Facade + ContextForge REST-wrap** (lowest custom code, one surface, ADR-0023).
- SBV auth = crack from `extracted-code/sbv/sbv-upstream-main.zip` + the deployed frontend; if a config/env disables it (tailnet-only is safe), prefer that.

## Constraints (HARD)
- **Reversible/local code only.** Do NOT `git push` (this box has a tool-egress block) and do NOT execute prod deploys / live ContextForge registration / live SBV config changes — **PREPARE + queue to `C:\Users\matts\casebible-coordination\APPROVALS.md`** with exact cmd + reversibility.
- Don't disturb unrelated WIP in the dirty repo (new files / scoped edits only). NEVER delete (move-aside).
- exec-tier is read-only except prepared/queued cutovers (ADR-0029). Verify code locally (`py_compile`, stubbed logic tests).
- Log progress to the coordination board (`LOG.md`, `status/pipeline.md`) signed as PIPELINE.

## Build tasks
1. **Crack SBV auth** — unzip `extracted-code/sbv/sbv-upstream-main.zip`, inspect the Go API + frontend (+ read-only the live `/opt/sbv/frontend`, `version.json`); determine how `/api/v1/*` authenticates (token env / session-cookie login / default cred / header) and how MCP calls authenticate. If an env/config disables auth, document it. Output a crisp "auth = X, do Y" finding.
2. **Fix `docker/tools/tools/facade.py`** — resolve the `evidence.registry` import (PYTHONPATH/sys.path, or make `evidence/__init__.py` not import heavy agno deps at package import). Facade must start (`uvicorn facade:app`) and serve the registry parser tools as REST. Verify import locally.
3. **Add SBV REST proxy to the facade** + OpenAPI — `/sbv/upload|messages|conversations|analytics|export|progress|health` proxying SBV `localhost:8085` (handling the auth from #1), so ContextForge can REST-wrap it. Keep it one clean OpenAPI surface.
4. **`evidence/tools/sbv_sms.py`** — capability `parse.sms-xml`, calls SBV API (upload→wait→fetch→`NormalizedRecord`s incl. calls + forensic flags), registered **before** `sms_xml.py` so the registry prefers SBV; `sms_xml.py` stays the auto-fallback (mesh substitution).
5. **Workflow A (`sms-xml`)** in `evidence/workflows.py` — custody → parse.sms-xml (SBV primary, custom fallback) → normalize → store → knowledge; mirror `chat-transcript`. Use the **agno skill/docs** for the `agno.workflow` wiring.
6. **ContextForge registration prep** — script/steps to register the facade SBV REST surface as an MCP gateway/tools (every SBV function → MCP). Queue live registration to APPROVALS.
7. **Queue the cutover** (APPROVALS.md): (a) git push new/changed files to `main`; (b) redeploy `platform-tools` (fixes facade + SBV proxy); (c) ContextForge register the facade SBV surface; (d) if auth-disable chosen, the SBV config change. Exact cmds + reversibility.

## Deliverables
Fixed+extended facade (SBV proxy + OpenAPI), `sbv_sms.py` (primary parser), Workflow A, the SBV-auth finding, ContextForge registration prep, the queued cutover, board updates. End state after the queued cutover: SBV viewer usable + all SBV functions MCP-callable via ContextForge + SBV primary / custom fallback for SMS-XML.
