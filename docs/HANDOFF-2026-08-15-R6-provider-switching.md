# HANDOFF — R6 Live Model and Provider Switching (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: COMPLETE
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Server selection | `server/core/settings.py` can construct explicit providers/models, but normal AgentOS boot shares one constructed model graph |
| Registry behavior | AgentOS model registry populates a picker/catalog but does not override the model on an existing run |
| OpenCode Workbench | Existing Copilot code can select provider/model per message in one OpenCode session |
| Drift risk | Provider construction is duplicated between server core, Workbench API, OpenCode, and Portkey configs |

## Findings / work done

- Build a platform-owned `ProviderRegistry`, `CapabilityProfile`, `ModelRoute`, `RouteRequest`, and `ResolvedRoute`.
- Use stable task routes by default; advanced UI may select an exact provider/model.
- Hard horizon/data/billing/security policy filters precede overrides and fallback.
- Changes apply at the next invocation/turn/checkpoint, never mid-stream or during a pending tool call.
- Capability eligibility must be based on observed probes for evidence-critical tools/structured output.
- Portkey remains preferred; OpenCode provides subscription/OAuth/local access; direct providers are policy-gated escape paths.

## UNRESOLVED (mandatory)

- Exact model capability canary matrix and route catalog.
- Credential/billing policy for unattended subscription/OAuth use.
- Portkey self-hosted config/guardrail parity for every desired rule.

## Pending owner decisions

- Adopt route-first GUI — WHAT: show task profiles first and raw models under Advanced · WHY: fast switching without unsafe/incompatible choices · APPROACHES: raw picker, Portkey-only configs, or neutral registry · SHORTCOMINGS: registry requires probes and catalog maintenance. Recommendation: neutral registry with Portkey adapter.

## Next steps (work in order)

1. Freeze route/capability/registry contracts and precedence.
2. Consolidate divergent model catalogs.
3. Build model capability and health canaries.
4. Add next-turn/session/agent-default GUI scopes.
5. Capture requested/effective route, attempts, cost, tokens, latency, and fallback.
6. Test concurrent-route isolation, context overflow, billing denial, and partial-stream restart.

## Owner working-style contract

- Browser never sees secrets; unknown billing is denied for unattended work; no silent context truncation or semantically incompatible fallback.
