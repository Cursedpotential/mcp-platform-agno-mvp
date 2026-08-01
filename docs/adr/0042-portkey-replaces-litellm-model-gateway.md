# ADR-0042: Portkey replaces LiteLLM as THE model gateway; LiteLLM retired

> _Byline: Claude Code · Fable 5 · 2026-07-29_

**Status**: ACCEPTED — owner ruling 2026-07-29 (doc-patch pass, AskUserQuestion).
**Supersedes**: ADR-0015 (LiteLLM model gateway) and the canon §5 "Model gateway = LiteLLM" entries.
**Relates**: ADR-0039 (Graphiti extraction LLM — the lane where the Portkey changeover first shipped).

## Context

- The Portkey changeover was **executed and verified 2026-07-19**: Graphiti routes through a
  Portkey nginx sidecar (`graphiti-portkeyfix`), exec-tier lanes are wired, configs are committed
  under `docker/gateway/portkey/` (5 lanes), 11-provider failover with a 4-key Gemini rotation
  is live. Decoupling was proven when Graphiti stayed up through a 40-minute exec-tier outage.
- Since then the platform ran a **dual-gateway state**: Portkey carrying the active lanes,
  LiteLLM still alive ("doors" open) with retirement explicitly pending an owner decision.
- The 2026-07-29 doc-patch pass surfaced the drift (canon §5 still declared LiteLLM the locked
  model gateway) and put the ruling to the owner.

## Decision

**Portkey is THE model gateway.** LiteLLM is **retired**: deprecated immediately, marked for
teardown. Nothing new points at LiteLLM; existing references migrate to Portkey as they are
touched. The physical teardown of the LiteLLM container (and the `gateway` compose service's
`:4000` listener) is a **separate, owner-gated infra task** — this ADR retires the *role*, not
yet the process.

The two-gateway layering is unchanged in shape: **models = Portkey**, **tools = IBM
ContextForge** (ADR layering warning in canon §5 still applies — don't conflate them).

## Consequences

- Canon §5 and `AGENTS.md` updated in the same change (anti-drift rule #2).
- Every new agent/service wanting a model route gets it via Portkey config
  (`docker/gateway/portkey/`), never a new LiteLLM entry.
- OpenCode (in the `gateway` container) still references LiteLLM models until the teardown
  task remaps it — that remap is part of the teardown scope.
- A teardown task must be queued: stop/remove the LiteLLM service, remap any residual
  consumers (OpenCode model config), confirm nothing 5xx's, then strike this consequence.

## Alternatives considered

- **Document the dual-gateway state as-is** — rejected by owner ruling; prolongs a split-brain
  config surface and two places for provider keys to drift.
- **Keep LiteLLM as the gateway, treat Portkey as the Graphiti-only sidecar** — rejected;
  Portkey already carries the exec-tier and has the richer failover/rotation config; reverting
  would re-do the 07-19 work backwards.
