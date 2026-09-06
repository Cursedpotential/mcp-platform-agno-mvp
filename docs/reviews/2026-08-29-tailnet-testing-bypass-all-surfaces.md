# Tailnet testing authentication bypass — all non-Workbench surfaces

> _Byline: Codex · GPT-5 · 2026-08-29._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

STATUS: PARTIAL — AgentOS platform-owned bearer routes implemented and locally verified; third-party
surface adapters and live deployment remain open.

## Owner contract

Every owner-facing surface must remain testable while Authentik/OAuth is unavailable, without
turning Tailnet membership into an implicit global authorization grant.

The bootstrap contract is:

- the per-application `<APP>_TAILNET_AUTH_BYPASS_ENABLED` flag defaults to `false`;
- normal authentication is attempted first and is unchanged while the flag is off;
- an enabled bypass trusts `X-Real-IP` only after the request's immediate peer matches an exact,
  configured Traefik proxy CIDR;
- allowed client CIDRs must be subsets of Tailscale CGNAT `100.64.0.0/10` (a narrower owner/device
  subnet is preferred in deployment configuration);
- the auditable identity is `principal=tailnet-owner`, `subject_uid=tailscale:<client-ip>`;
- no Basic-auth fallback, password environment variable, synthetic Authentik header, or client-
  supplied forwarding chain may establish the bypass;
- application/storage credentials remain in force for service-to-service and direct data access.

## Implemented slice

The AgentOS custom HTTP ingest and owner evidence-search bearer boundaries now evaluate their normal
credential first, then consult the shared Tailnet fallback in `server/api/tailnet_auth.py`.
`deploy/exec.yaml` carries:

```text
AGENTOS_TAILNET_AUTH_BYPASS_ENABLED=false
AGENTOS_TAILNET_AUTH_TRUSTED_PROXY_CIDRS=<exact Traefik peer CIDR>
AGENTOS_TAILNET_AUTH_ALLOWED_CIDRS=100.64.0.0/10
```

The implementation rejects missing/malformed proxy configuration, IPv6 in this IPv4-only contract,
multiple `X-Real-IP` values, untrusted peers, non-Tailnet clients, and configured ranges extending
outside `100.64.0.0/10`. Successful bypasses attach the principal, subject UID, and auth method to
request state and emit a structured `tailnet_testing_auth_bypass` log record.

This does **not** bypass signed agent walk capabilities. Those grants represent evidence-horizon
authority, not an owner login obstacle, and weakening them would contaminate the core deliverable.

## Surface implementation map

`Direct tailnet` means the checked-in manifest publishes a host port that never crosses Traefik.
Such a surface cannot safely consume proxy identity until its browser/API route is moved behind a
trusted proxy.

| Surface | Source boundary | Current authentication/exposure | Tailnet testing status and required adapter |
|---|---|---|---|
| AgentOS API/MCP | `deploy/exec.yaml`, `server/api/**` | Traefik domain plus direct tailnet `:8000`; OS and operator bearer credentials | **PARTIAL:** custom ingest/operator evidence routes implemented. TODO: verify whether Agno-owned routes apply `OS_SECURITY_KEY` outside the base app and add an upstream-supported hook before claiming full API/MCP coverage. |
| ContextForge admin UI/MCP | `deploy/contextforge.yaml` | Traefik domain plus direct tailnet `:4444`; native Basic/JWT/admin session | **TODO-CF:** add a supported external-identity adapter or proxy-only owner route. Do not set `AUTH_REQUIRED=false`, manufacture a JWT, or fake Authentik response headers. |
| Authentik console | `deploy/authentik.yaml` | Traefik domain; native Authentik login | **TODO-AK:** retain native recovery/bootstrap access. Authentik cannot depend on its own forward-auth outpost; document and test its supported break-glass owner flow separately. |
| OpenCode server | `deploy/gateway.yaml` | Direct tailnet `:4096`; native HTTP Basic | **TODO-OC:** route through Traefik and implement a supported trusted-identity adapter. Do not map the Tailnet flag to an empty `OPENCODE_SERVER_PASSWORD`. Retired port `:4000` is not a surface. |
| Kasm desktop | `deploy/desktop.yaml` | Direct tailnet HTTPS `:6901`; native `kasm_user`/VNC password | **TODO-KASM:** proxy the web surface and use Kasm-supported external auth. Remove the unsafe `changeme-desktop` fallback in a separately reviewed credential-hardening change. |
| SBV GUI | `deploy/platform-tools.yaml`, vendored SBV auth | Direct tailnet `:8085`; native session cookie | **TODO-SBV:** legacy surface is being absorbed by Workbench/UIW. Until cutover, add a supported bypass in the SBV session boundary or keep its login; do not synthesize a session cookie. |
| Platform-tools facade | `deploy/platform-tools.yaml`, `docker/tools/tools/facade.py` | Direct tailnet `:8090`; no inbound auth | **OPEN/UNPROTECTED:** testing is not blocked, but there is no auth boundary to bypass. TODO-TOOLS: put it behind Traefik and apply this contract when inbound auth is added. |
| LibreChat | `deploy/librechat.yaml`, `docker/librechat/librechat.yaml` | Direct tailnet `:3080`; native account/JWT session | **TODO-LC:** use a LibreChat-supported OAuth/OIDC or trusted external-auth adapter after routing through Traefik. Do not mint LibreChat JWTs in the proxy. Reconcile duplicate/legacy Coolify resources first. |
| NocoDB | `deploy/nocodb.yaml` | Direct tailnet `:8570`; native account/session | **TODO-NC:** route through Traefik and use a NocoDB-supported SSO/external-auth boundary. Reconcile duplicate/legacy Coolify resources first. |
| LLM Probe API/UI | `deploy/llm-probe.yaml`, `deploy/llm-probe-ui.yaml`, `llm_probe/**`, `llm_probe_ui/**` | Direct tailnet `:8030/:8031`; no inbound auth | **OPEN/UNPROTECTED:** testing is not blocked. TODO-PROBE: add normal Authentik/OIDC and the shared fallback together; API write/execute routes must not remain anonymous. Deployment is not currently proven. |
| n8n UI | `docker/n8n/compose.yaml`, current live configuration not checked in | Domain reported in runbooks; native owner login/API keys and webhook header auth | **BLOCKED-INVENTORY/TODO-N8N:** recover the actual Coolify manifest and distinguish UI login from machine webhook credentials. Apply the bypass only to the UI identity boundary; never bypass workflow webhook/API credentials. |
| Temporal UI | `deploy/temporal/compose.temporal.yaml` | Direct tailnet `:8233`; no auth configured | **OPEN/UNPROTECTED:** TODO-TEMPORAL: route UI through Traefik and add normal auth plus fallback. Temporal service/API credentials are a separate machine boundary. |
| Neo4j/DozerDB Browser | `deploy/data-neo4j.yaml` | Direct tailnet `:7474`; database username/password | **NO BYPASS:** this is a data-store administration boundary, not an app login. Keep database auth. A future read-only operator projection may use the UI contract without weakening Bolt/DB credentials. |
| Attu | `deploy/data-vector.yaml` | Direct tailnet `:3001`; no Attu auth in manifest | **OPEN/UNPROTECTED / VERIFY ACTIVE:** determine whether the memsearch-only Milvus/Attu app is active. If retained, route UI through Traefik; do not treat Milvus connection credentials as browser identity. |
| Timesketch preview | `deploy/timesketch.yaml`, `timesketch-fork/**` | Direct tailnet `:5000`; native Timesketch login/session | **NOT DEPLOYED / TODO-TS:** add supported external identity and the flag before first deployment. Host assignment and existing preview acceptance remain separate gates. |
| Weaviate API | `deploy/data-weaviate.yaml` | Direct tailnet REST/gRPC; anonymous access currently enabled | **NOT OWNER UI:** no bypass exists because there is no auth. Authentication hardening must preserve service credentials; do not use the owner-testing identity for storage access. |
| Coolify UI | external control plane | Outside this repository | **OUT OF SCOPE HERE:** implement in Coolify/Traefik control-plane configuration with the same contract. |
| Legal Workspace | sibling repository | Outside this repository | **OUT OF SCOPE HERE:** implement in that repository; do not cross-edit from Platform. |

Workbench and the unified operator surface are intentionally omitted from implementation ownership
in this receipt; the root Workbench lane owns their exact integration. They still fall under the
same owner directive.

## Central proxy target

The consistent end state is one trusted Traefik entry path per browser/API surface:

1. Traefik overwrites `X-Real-IP` and connects from an exact socket CIDR.
2. The application first evaluates its normal Authentik/OIDC/session/bearer credential.
3. If and only if the application flag is enabled, its adapter evaluates the trusted peer, client
   address, and allowed Tailnet subset.
4. The application records the real/synthetic bootstrap subject in the same audit field used by
   normal identities.

A higher-priority Traefik `ClientIP` router without application participation is insufficient for
apps that enforce their own login. It also does not provide the required application audit subject.

## Feature-flag lifecycle and Unleash migration

Environment flags are the bootstrap mechanism while the feature service is unavailable. After
Unleash is installed:

- create one disabled-by-default server-side flag per surface, named
  `<app>.tailnet-testing-auth-bypass`;
- keep the trusted proxy and allowed CIDR values in deploy configuration, not Unleash context or
  browser code;
- evaluate flags server-side only and fail closed when Unleash is unavailable;
- require an explicit owner-controlled environment/strategy and log the Unleash flag version with
  the bypass audit event;
- retain the environment flag only as an emergency bootstrap kill switch during migration, then
  remove it after live parity and rollback tests;
- never expose the flag in `NEXT_PUBLIC_*`, client JavaScript, request query parameters, or cookies.

## Verification boundary

Local verification completed on 2026-08-29:

```text
uv run ruff check server/api/tailnet_auth.py server/api/ingest_routes.py \
  server/api/native_evidence_search_routes.py tests/test_tailnet_auth.py
PASS

uv run pytest -q tests/test_tailnet_auth.py tests/test_ingest_routes.py \
  tests/test_native_evidence_search_routes.py
27 passed, 1 warning
```

No commit, push, Coolify configuration mutation, deployment, or live Tailnet/Traefik verification
was performed in this lane. Therefore this is not production-complete and must not be represented as
a deployed universal bypass.
