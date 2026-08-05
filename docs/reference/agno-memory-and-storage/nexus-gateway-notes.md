> _Byline: Claude Code · Sonnet · 2026-07-11_

# Nexus gateway — research notes (owner-named repos, location still TBD)

> Status: research complete on the two owner-named repos. Purpose: have everything ready to
> configure the moment the install location is confirmed, plus an honest trust read before real
> provider keys go anywhere near either project.
>
> Owner's ask, restated: embedding **models** stay fixed per collection (vector-space lock — never
> swap the model/dim for an existing Milvus collection), but the **same model** should be reachable
> through multiple rotating API keys / providers (e.g. `bge-m3` via OpenRouter key A → OpenRouter
> key B → NVIDIA) so a rate limit or outage on one key/provider fails over to the next without
> touching the embedding space.
>
> **Correction (2026-07-11):** the owner named the actual products — neither is Grafbase Nexus nor
> Nexusflow (both investigated in an earlier pass of this doc and now demoted to a one-paragraph
> baseline in §1). The two real candidates are:
> 1. **[Ranatoasted571/nexus-proxy](https://github.com/Ranatoasted571/nexus-proxy)** — already installed (location TBD).
> 2. **[AlphaBitCore/nexus-gateway](https://github.com/AlphaBitCore/nexus-gateway)** — owner is leaning toward this one instead ("has a GUI and seems like more features").
>
> **Bottom line up front:** `nexus-proxy` documents exactly the rotation mechanic the owner is
> asking for (round-robin key pool + 429 cooldown) but **explicitly has no embeddings endpoint** —
> a dead end for the actual use case. `nexus-gateway` claims to solve *both* halves (embeddings +
> multi-strategy routing/failover) and adds a GUI, but it is a much larger, much newer, much more
> invasive piece of software (it ships a TLS-intercepting "compliance proxy" and an OS-level traffic
> agent) from an organization with no visible public members, built almost entirely in the last
> ~7 weeks. **Both projects are too new and too small to hand real production API keys to without
> deliberate, isolated vetting first** — see §3 for the full trust/security read before acting on
> either. This is not "don't use them," it's "don't wire OpenRouter/NVIDIA/Anthropic/OpenAI
> production keys into either one yet."

## 1. Grafbase Nexus — kept as a mature-alternative baseline

For contrast only (full original deep-dive available in prior revision history of this file if
needed — trimmed here since it's not what the owner installed). **Grafbase Nexus**
(`nexusrouter.com` / `github.com/grafbase/nexus`) is a real, actively maintained, Rust-built,
MPL-2.0-licensed open-source AI router — chat/completions + tool-calling + MCP-server aggregation
via a single `nexus.toml`. Confirmed **no `/v1/embeddings` support** and **no multi-key
rotation/automatic cross-provider failover** as of its v0.6.0 release (docs + GitHub releases
checked directly). It is orders of magnitude more mature than either owner-named repo (real docs
site, real release cadence, a company behind it) but doesn't solve the owner's actual embeddings-
rotation requirement any better than the two repos below — it's included here purely as a "this is
what a mature version of this idea looks like" yardstick for §3's trust assessment, not as a
recommendation.

## 2. The two owner-named repos, deep-dive

### 2a. `Ranatoasted571/nexus-proxy`

**What it is:** A single Go binary (with embedded SQLite, no external runtime deps) that sits in
front of Claude Code / AI coding tools and routes requests to "the cheapest capable model" while
also acting as a local secrets-redaction firewall. Framed explicitly as a **cost/privacy tool for
coding agents**, not a general-purpose API gateway — the README's own tagline is "Route AI coding
requests to the cheapest capable model locally to save costs and keep your data private."

- **Stack:** Go 88.3%, Svelte 8.8% (dashboard), TypeScript 1.2%, plus Shell/Makefile/PowerShell.
- **Run:** `curl -fsSL <install-script-url> | sh` → installs a prebuilt binary from GitHub Releases
  into `/usr/local/bin` (falls back to `$HOME/.local/bin`, uses `sudo` only if needed) → `nexus
  start`. **The installer does not verify checksums or signatures on the downloaded binary** —
  confirmed by reading `install.sh` directly. Dashboard/UI on `http://localhost:2222`.
- **Config:** `~/.nexus/config.toml`; zero-config startup, providers added via CLI (`nexus add groq
  YOUR_KEY`) or TOML directly; env-var key references supported (`api_key = "env:GROQ_API_KEY"`).
- **Providers:** claims 30+ — Anthropic, OpenAI, xAI, DeepSeek, Mistral, Cohere, Together AI,
  OpenRouter, Groq, Gemini, Cerebras, SambaNova, NVIDIA NIM, Ollama, plus a generic
  `--type openai-compatible --base-url` escape hatch for anything else OpenAI-shaped.
- **Embeddings — the make-or-break question: NO.** The README makes no mention of `/v1/embeddings`
  or any embedding endpoint anywhere; its entire design center is chat/completions routing for
  coding-agent traffic (Anthropic-shape and OpenAI-shape chat APIs only, per "Universal gateway:
  speaks both Anthropic and OpenAI APIs"). **This rules it out for the owner's actual use case**
  (rotating keys behind a fixed embedding model) regardless of how good its rotation story is.
- **Key rotation / failover — YES, and it's exactly the owner's ask, for chat:** README states
  verbatim: *"NEXUS round-robins across a pool of keys and puts any key that returns `429` on a
  short cooldown — so several free keys behave like **one larger free quota**."* Configured via
  `nexus add groq "key1,key2,key3"` or a TOML array `api_keys = ["env:KEY_1", "env:KEY_2"]`.
  Automatic failover triggers on `429` or `5xx`. This is a genuinely well-matched mechanic for the
  owner's rotation ask — just gated on it being usable for embeddings at all, which it isn't.
- **MCP:** yes, but in the opposite direction from what we use ContextForge/Nexus-style routers
  for — nexus-proxy exposes *itself* as an MCP server over stdio (`nexus_stats`, `nexus_savings`,
  `nexus_recent`, `nexus_providers`, `nexus_cost_breakdown`), i.e. tools for introspecting its own
  routing decisions, not a general MCP-aggregation gateway.
- **Gateway auth:** none documented — "clients authenticate with `ANTHROPIC_API_KEY=nexus-local`"
  (a placeholder value, not a real gate). This is a **local, single-user tool posture**, not a
  hardened multi-tenant gateway — fine for a personal box, not something to expose past localhost
  without adding your own auth layer in front.
- **Maturity/trust signals** (see §3 for full table): created 2026-06-03 (~5.5 weeks old at research
  time), 1 star, 1 watcher, 0 forks, **issues disabled** (`has_issues: false` — no visible bug
  tracker/community feedback loop at all), single-repo account (`Ranatoasted571` has exactly one
  public repo), commits co-authored by "claude" (i.e., built with Claude Code) alongside a second
  human-looking username (`ludicolijn1985-blip`). Apache-2.0 licensed.

### 2b. `AlphaBitCore/nexus-gateway`

**What it is:** A much larger, "enterprise" framed system — README calls it an "Enterprise AI
traffic gateway — unified compliance, routing across 20+ LLM providers, semantic cache, quotas, and
audit," built as **five separate Go services plus a React control-plane UI**, intercepting traffic
at three layers (SDK, network, OS).

- **Stack:** Go 79.7% (Echo framework, `log/slog`, Prometheus metrics), TypeScript 14.4% (React +
  Vite control-plane console), CSS 2.1%, Python 1.5%, Shell 0.9%, Swift 0.6% (macOS desktop-agent
  piece). PostgreSQL 16 + Valkey 8 (Redis-compatible) + NATS JetStream backing services.
- **Services:** Nexus Hub (:3060, device/config registry), Control Plane (:3001, admin API/IAM/SSO),
  AI Gateway (:3050, the actual LLM routing/caching/quota layer), Compliance Proxy (:3128, a
  **transparent TLS-terminating MITM proxy**), and a Desktop Agent (macOS/Linux/Windows) that does
  **OS-level traffic interception**.
- **Run:** `./scripts/dev-start.sh` — needs Node 20+, Go 1.25+, Docker, OpenSSL; auto-generates
  `.env`, boots Docker Compose (Postgres/Valkey/NATS), applies DB schema/seed, generates a **dev CA
  for the TLS proxy**, launches the UI. **Default seeded admin credentials: `admin@nexus.ai /
  admin123`** — a real risk if a dev/demo instance is ever exposed off localhost before those are
  rotated. Console at `http://localhost:3000`.
- **Config:** YAML per service (`ai-gateway.dev.yaml` etc.) — the AI Gateway's dev config (read
  directly) is genuinely detailed: connection-pooled upstreams per provider, SHA-256 response
  caching with in-flight dedup, an NDJSON+zstd audit spool with a "no-loss, spill-to-disk" mode,
  per-provider header allow/deny lists, HMAC-signed admin keys and env-only secrets. This is
  more sophisticated than a weekend project's config would typically look like — a genuine point in
  its favor on **code quality**, independent of the trust/age concerns in §3.
- **Providers:** 20 adapters — 11 "first-class codecs" (openai, anthropic, gemini, vertex, azure,
  bedrock, cohere, minimax, glm, replicate, **voyage**) plus 9 OpenAI-compatible passthroughs
  (deepseek, moonshot, mistral, groq, fireworks, together, perplexity, xai, huggingface). OpenRouter
  and NVIDIA NIM specifically aren't named as first-class codecs, but both are OpenAI-compatible
  APIs so the passthrough path (or a custom `base_url` on the `openai` codec) should reach them —
  **UNVERIFIED against actual code**, worth a smoke test once installed.
- **Embeddings — the make-or-break question: YES, claimed.** The README lists `/v1/embeddings` as a
  standardized route alongside chat/completions, and the provider list includes `voyage` and
  `cohere` as first-class codecs — both dedicated embedding-capable vendors. This is the one of the
  two repos that actually claims to cover the owner's real use case end-to-end. **Not independently
  verified against a running instance in this pass** (no install performed per task scope) — treat
  as "documented" not "proven" until smoke-tested.
- **Key rotation / failover — YES, claimed, richer than nexus-proxy's:** seven named routing
  strategies — `single, fallback, loadbalance, conditional, absplit, policy, smart` — which reads as
  covering simple fallback, weighted load-balancing, A/B-style splitting, and policy-driven routing.
  The credential vault uses AES-256-GCM encryption with an explicit "key rotation" capability,
  though the README doesn't spell out the exact rotation trigger logic (rate-limit-aware? scheduled?
  manual?) — **UNVERIFIED mechanics**, would need the actual routing-strategy docs or source before
  configuring with confidence.
- **MCP:** not mentioned anywhere in the README — this repo's aggregation story is entirely
  LLM-provider-routing plus compliance/audit, not MCP-tool aggregation. No overlap with
  ContextForge, unlike Grafbase Nexus.
- **Gateway auth:** virtual keys (VKs) gate the `/v1/*` API; RBAC+ABAC IAM with an "NRN resource
  model," OIDC federation, organization hierarchy — a genuinely enterprise-shaped auth design, if it
  works as documented.
- **The compliance-proxy MITM component is the standout risk.** It performs transparent TLS
  termination on network traffic; the README does describe a trust-attestation escape hatch (an
  Ed25519-signed header from the Desktop Agent lets a verified flow become "pure passthrough — no
  MITM, no hooks"), but running *any* component that installs a local CA and intercepts TLS by
  design is a materially larger trust ask than a simple reverse-proxy gateway — this piece alone
  should get independent scrutiny (or simply not be enabled) regardless of what's decided about the
  AI-gateway piece.
- **Maturity/trust signals** (full table in §3): created 2026-05-26 (~7 weeks old), 18 stars, 3
  forks, 18 watchers, 8 open issues (issues *are* enabled here, unlike nexus-proxy), org
  (`AlphaBitCore`) has 4 public repos total (`nexus-gateway`, `llm-gateway-benchmark`,
  `nexus-loadtest`, `nexus-mock-provider`) and **"has no public members"** shown on its org page —
  i.e. no way to see who's actually behind it from the GitHub UI alone. Commits co-authored by
  "Claude" alongside a primary human-looking account (`Nexus-ABC`). Apache-2.0 licensed. Notably,
  three of the four org repos (`llm-gateway-benchmark`, `nexus-loadtest`, `nexus-mock-provider`) look
  like they exist to generate the org's own benchmark/credibility numbers for `nexus-gateway` itself
  — worth noting as a mild self-referential-credibility flag, not a damning one on its own.

## 3. Trust / security assessment

| Signal | `nexus-proxy` | `nexus-gateway` |
|---|---|---|
| Repo created | 2026-06-03 (~5.5 wks old) | 2026-05-26 (~7 wks old) |
| Stars / forks / watchers | 1 / 0 / 1 | 18 / 3 / 18 |
| Open issues | 0 (**issues disabled** — no bug tracker visible) | 8 (issues enabled, some activity visible) |
| Contributors visible in commit log | 2-3 handles (`Ranatoasted571`, `ludicolijn1985-blip`) + `claude` co-authoring | 2 handles (`Nexus-ABC`, `Claude` co-authoring) |
| Account/org public footprint | Single-repo personal account, 1 follower | Org with 4 repos, "no public members" shown |
| License | Apache-2.0 | Apache-2.0 |
| Install method | `curl \| sh`, prebuilt binary from Releases, **no checksum/signature verification** (confirmed by reading `install.sh`) | Multi-service Docker Compose + Go/Node source build, no single curl-pipe step |
| Attack surface | Local proxy, no gateway-level auth, no TLS interception | Local proxy **plus** a TLS-intercepting MITM compliance proxy **plus** an OS-level desktop traffic agent — substantially larger |
| Default credentials risk | None documented (no gateway auth at all — different but related risk: anyone with localhost access can use it) | **Yes** — seeded `admin@nexus.ai` / `admin123` default admin account, must be rotated before any non-localhost exposure |
| Self-referential credibility signals | None found | Org also publishes its own `llm-gateway-benchmark` and `nexus-loadtest` repos — plausibly legitimate tooling, but also exactly the pattern a project would use to manufacture its own credibility numbers; can't distinguish from here |
| Code-quality signal (independent of age/trust) | Reasonable — small, focused, single-purpose | Notably sophisticated for its age (real connection pooling, audit spooling with loss-mode guarantees, header allow/deny lists) — genuinely well-engineered *looking* config, which cuts both ways: either a skilled team moving fast, or a lot of AI-assisted scaffolding that hasn't been battle-tested |

**Candid read:** neither project has the community size, audit history, or independent track record
that would normally justify routing real production API keys (OpenRouter, NVIDIA, Anthropic, OpenAI
— the actual keys this platform pays for) through it today. Both are young enough that "built almost
entirely in the last two months, largely via AI-assisted commits, by one-or-two-person teams with
minimal public accountability" is a fair, literal description, not an insult. That doesn't make
either one *bad software* — the `nexus-gateway` config in particular reads as competently engineered
— but competent engineering and earned trust are different things, and supply-chain/credential risk
is about the latter. **Recommended posture regardless of which repo wins:** run it in an isolated
environment first (a throwaway VM/container, or at minimum a dedicated low-privilege API key with a
hard spend cap that isn't reused anywhere else), read the actual routing/embeddings/key-rotation
source (not just the README) before trusting the claims in §2 as fact, and — if `nexus-gateway`'s
compliance-proxy/MITM piece is ever enabled — treat that specifically as its own separate security
review, since it's structurally different (and riskier) from a plain reverse proxy.

## 4. Direct comparison + recommendation

| | `nexus-proxy` | `nexus-gateway` |
|---|---|---|
| Embeddings proxy (make-or-break) | **No** — chat/completions only, confirmed absent from README | **Yes, claimed** — `/v1/embeddings` + Voyage/Cohere codecs documented, not independently verified |
| Key rotation / failover | **Yes** — round-robin pool + 429 cooldown, simple and clearly documented | **Yes, claimed** — 7 routing strategies incl. `loadbalance`/`fallback`, mechanics less precisely documented |
| GUI | Yes — lightweight dashboard (`:2222`), cost/request visibility | Yes — full React control-plane console (`:3000`), config + traffic inspection, more feature surface |
| Scope | Narrow: a coding-agent cost/privacy proxy that happens to route LLM calls | Broad: enterprise gateway + compliance/audit + IAM + MITM proxy + desktop agent |
| Blast radius if compromised/buggy | Low — local proxy only, no TLS interception, no elevated OS hooks | High — TLS-intercepting proxy + OS-level agent means a compromise or bug here has a much bigger footprint than "my LLM calls route wrong" |
| Maturity | Smaller footprint, but *even less* community validation (0 issues visible, 1 star) | Slightly more traction (18 stars, active issues) but far more surface area to have gone wrong |

**Does the owner's lean toward `nexus-gateway` hold up?** Partially — **for the specific
requirement in this task (embeddings-proxy + rotation), yes, `nexus-gateway` is the only one of the
two that can plausibly do it at all**, since `nexus-proxy` is a hard no on embeddings regardless of
how good its rotation story is. On that narrow axis, the owner's instinct to prefer the
more-feature-complete option is correct — `nexus-proxy` simply doesn't clear the bar.

**Where I'd push back:** "has a GUI and seems like more features" is true but undersells how much
*more* is being taken on — a control plane, an IAM/SSO layer, an audit pipeline, and critically a
TLS-intercepting compliance proxy with an OS-level desktop agent are a different category of
software from "a proxy that rotates my embedding keys." None of that extra surface is needed for the
owner's stated goal, and each additional service is one more thing that could leak credentials, log
sensitive request bodies, or simply break in an unmaintained-project way. **Recommendation for
owner decision:** if `nexus-gateway` is adopted, adopt *only* the AI Gateway service (`:3050`) for
the embeddings-rotation use case — do not stand up the Compliance Proxy, Desktop Agent, or Nexus Hub
pieces unless there's a separate, deliberate reason to want TLS interception across this box's
traffic. And before wiring any real key into either project, do the isolated-smoke-test pass
described in §3's "recommended posture," specifically to confirm the embeddings claim actually
works end-to-end (point a throwaway/free-tier key at it, hit `/v1/embeddings`, confirm the response
shape and dimension match what was requested) rather than trusting the README.

## 5. Agno integration

Both repos, if they work as documented, are OpenAI-compatible HTTP endpoints — the integration
shape is the same regardless of which one is used, and doesn't require agno's native
`agno.models.nexus.Nexus` class (that class targets Grafbase Nexus's `/llm/v1/` path specifically —
per §1, not what's installed here; **don't use `agno.models.nexus.Nexus` for either owner-named
repo** unless its `base_url` param happens to line up, which is unverified and shouldn't be assumed).

- **Chat models**: point `OpenAILike(base_url="http://localhost:2222/v1", ...)` (nexus-proxy) or
  `OpenAILike(base_url="http://localhost:3050/v1", ...)` (nexus-gateway's AI Gateway service) —
  same pattern already used for OpenRouter/NIM in `server/core/settings.py`.
- **Embeddings**: only `nexus-gateway` is even a candidate. If verified working,
  `OpenAIEmbedder(base_url="http://localhost:3050/v1", api_key=<virtual-key>, id="bge-m3")` would be
  the shape — **but this needs the smoke test from §4 before trusting it for `kb_legal`/
  `kb_timeline`/Graphiti embed-text**, all of which are dimension-locked and would hard-error or
  silently corrupt search quality on any mismatch.
- **nexus-proxy is not a candidate for the embedder lanes at all** — its integration, if used, would
  be scoped to chat-model traffic only (e.g. the agent-reasoning provider chain), leaving the
  embedding lanes exactly where they are today (OpenRouter/NIM direct, or LiteLLM per §6).

## 6. Fleet fit — now potentially FOUR gateways

We already run **LiteLLM** (live, carries the Graphiti embed-text lane) and **Portkey** (deployed,
healthy, idle — switch deferred by owner 2026-07-04). Adding either owner-named repo makes a third;
Grafbase Nexus would make a fourth if ever reconsidered. Honest comparison, embeddings-focused:

| | LiteLLM | Portkey | `nexus-proxy` | `nexus-gateway` |
|---|---|---|---|---|
| Embeddings proxying | Yes, native, production-proven in this stack today | Yes, native | **No** | Yes, claimed, unverified |
| Multi-key rotation/failover | Yes, native (`model_list` pools, weighted failover, multiple strategies) | Yes, native (virtual keys, weighted load-balancing, configurable fallback triggers) | Yes, documented, simple (round-robin + 429 cooldown) — but moot given no embeddings | Yes, claimed (7 strategies), mechanics under-documented |
| Maturity / track record | Highest — already production-live here | High — self-hosted, healthy, not yet load-bearing here | Lowest — 1 star, 0 issues visible, single maintainer | Low — 7 weeks old, 18 stars, hidden org membership |
| Trust for production keys today | Established | Established | Not recommended without isolation | Not recommended without isolation |
| Unique value if adopted anyway | n/a (already the incumbent) | n/a (already deployed, idle) | Coding-agent-specific cost routing + secrets-redaction firewall — a genuinely different niche than "gateway for our embed lanes" | GUI + broader provider/codec list + audit/compliance tooling, if the extra surface is wanted |

**Recommendation, unchanged in substance from the original brief:** the owner's rotating-key
embedding requirement is **already best served by LiteLLM** — it's live, proven, and carries the
Graphiti embed-text lane today; extending its `model_list` with multiple deployments of the same
model/dim under one `model_name` (§7b) delivers the exact rotation behavior requested with zero new
trust exposure. Neither `nexus-proxy` nor `nexus-gateway` should replace that lane yet. If the
owner still wants to bring one of these in — `nexus-proxy` for its coding-agent cost-routing niche,
or `nexus-gateway` for its broader feature set once vetted — that's an *additive* decision for chat-
traffic experimentation or governance/audit tooling, not a required step to solve the embeddings-
rotation problem, which LiteLLM already solves today.

## 7. Draft config

### 7a. `nexus-proxy` — chat-only rotation pool (NOT for embeddings)

```toml
# ~/.nexus/config.toml — DRAFT. Chat-routing only; nexus-proxy has no embeddings endpoint.
# UNVERIFIED against a live install — confirm exact key names/flags against `nexus --help`
# and the actual installed version before relying on this.

[[providers]]
name = "openrouter"
type = "openai-compatible"
base_url = "https://openrouter.ai/api/v1"
api_keys = ["env:OPENROUTER_API_KEY_A", "env:OPENROUTER_API_KEY_B"]   # round-robin + 429 cooldown per README

[[providers]]
name = "nvidia_nim"
type = "openai-compatible"
base_url = "https://integrate.api.nvidia.com/v1"
api_keys = ["env:NVIDIA_API_KEY"]

[[providers]]
name = "anthropic"
type = "anthropic"
api_keys = ["env:ANTHROPIC_API_KEY"]

# strategy = "auto" | "cascade" | "adaptive" | "manual" — UNVERIFIED exact TOML key name,
# CLI shows `--strategy`; confirm whether it's also settable in config.toml directly.
```

### 7b. LiteLLM `model_list` — where the owner's actual rotation requirement is solved TODAY

Unchanged recommendation from the original research pass — this is the piece that already delivers
"same model, rotating keys/providers," live, today, with no new trust exposure:

```yaml
# litellm config.yaml — DRAFT addition, adapt to the real config file/location in use.
model_list:
  - model_name: bge-m3-embed          # fixed logical name kb_legal/kb_timeline/Graphiti call
    litellm_params:
      model: openai/bge-m3
      api_base: https://openrouter.ai/api/v1
      api_key: os.environ/OPENROUTER_API_KEY_A
  - model_name: bge-m3-embed           # SAME model_name = same rotation pool
    litellm_params:
      model: openai/bge-m3
      api_base: https://openrouter.ai/api/v1
      api_key: os.environ/OPENROUTER_API_KEY_B
  - model_name: bge-m3-embed
    litellm_params:
      model: openai/bge-m3             # UNVERIFIED: confirm NVIDIA NIM actually serves bge-m3 under
      api_base: https://integrate.api.nvidia.com/v1   # this id — our repo's provider chain today uses
      api_key: os.environ/NVIDIA_API_KEY               # NimEmbedder for NIM's *asymmetric* embed models,
                                                          # not bge-m3 itself; check the NIM catalog first.

router_settings:
  routing_strategy: usage-based-routing-v2   # or simple-shuffle; UNVERIFIED which strategy this platform already picked
  enable_weighted_failover: true             # retry same model_name pool before any cross-model fallback
  num_retries: 2
  fallbacks: []                              # deliberately empty at the model level — vector-space lock means
                                              # we must NEVER fall back to a *different* embedding model here;
                                              # only same-model/different-key/different-provider entries belong
                                              # in this pool.
```

**Vector-space-lock guardrail, stated explicitly for whoever configures this**: every entry in the
`bge-m3-embed` pool above MUST resolve to the identical model + dimension, regardless of which
gateway ends up carrying this lane (LiteLLM today, or `nexus-gateway` if/when vetted). Do not add a
"better" embedder as a fallback entry in the same pool — that would silently change the vector space
for whichever `kb_*`/Graphiti collection calls this `model_name`, and Milvus/pgvector will hard-error
(or silently corrupt search quality) on a dimension mismatch. A different model belongs in a
different `model_name`, never in this rotation pool.

### 7c. `nexus-gateway` AI Gateway — sketch only, NOT to be trusted until smoke-tested (§4)

```yaml
# Sketch of what pointing OUR embedder lane at nexus-gateway's AI Gateway (:3050) might look like,
# IF the embeddings claim is verified. Do not wire real production keys here until the isolated
# smoke test in §3/§4 passes. Provider-credential setup happens via the Control Plane UI per the
# README's example ("OpenAI Provider Credential... requires manual setup via the Control Plane
# UI") — not purely file-based like LiteLLM/nexus-proxy, so this is agno-side only:

# server/core/embedder.py — DRAFT, do not enable until §4's smoke test passes
# OpenAIEmbedder(
#     base_url="http://localhost:3050/v1",
#     api_key=getenv("NEXUS_GATEWAY_VIRTUAL_KEY"),   # a "virtual key" (nvk_...) minted via the Control Plane UI,
#     id="bge-m3",                                     # NOT a raw OpenRouter/NVIDIA key directly
# )
```

## Open questions / things to confirm once location + decision are known

- Where is whichever repo gets adopted actually installed/running (this box? a VPS? Coolify?) —
  confirms the `base_url`s used above.
- For `nexus-gateway`: does `/v1/embeddings` actually work end-to-end against a real provider
  (Voyage, Cohere, or an OpenAI-compatible passthrough for OpenRouter/NIM)? This is the single
  fact that decides whether §4-§7's recommendation to prefer LiteLLM-for-now still holds once
  vetted, or whether `nexus-gateway` becomes a real second option for this lane.
- For `nexus-gateway`: rotate the default `admin@nexus.ai`/`admin123` credentials immediately if
  any instance is ever run, even for testing, on anything other than an isolated localhost.
- For both repos: re-check star/issue/contributor counts periodically — trust posture should be
  revisited, not assumed static, especially for software this young.
- Confirm whether OpenRouter/NVIDIA NIM route cleanly through `nexus-gateway`'s "OpenAI-compatible
  passthrough" codec path (9 providers named, neither OpenRouter nor NIM explicitly among them) —
  worth a direct question to the project (issue/discussion) or a source read before assuming it
  works via a generic `base_url` override.
