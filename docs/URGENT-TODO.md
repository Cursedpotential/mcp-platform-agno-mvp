# URGENT TODO

> _Byline: Claude Code · Opus 5 · 2026-08-20_
>
> Required by the **LIVE ONLY / SPRINT MODE** policy in `AGENTS.md`.
> Every stub, every known-broken thing, every deferred fix lands here **loudly**.
> A silent stub is a defect. Nothing here is allowed to go quiet.

## How to use

- Any stub you are forced to write gets an inline `# STUB:` / `// STUB:` **and** a row below.
- A stub is only permitted when the real data or upstream service does not exist yet.
- If it is a function, write the whole function. Do not park a placeholder here to avoid work.
- Clear rows the moment the real implementation lands. This list should shrink.

## Open stubs

| # | Item | File / location | Why it is a stub | Blocking on |
|---|------|-----------------|------------------|-------------|
| — | _(none recorded yet)_ | | | |

## Known broken / deferred

_Seeded 2026-08-20 from the fleet audit. Queued per the "mid-task feedback is queued" rule._

| # | Item | Impact | Status |
|---|------|--------|--------|
| 1 | **Docker subnet `192.168.0.0/20` collides with owner's home LAN `192.168.10.0/24`** on ovh-files AND ovh-app. `ip route get 192.168.10.141` on ovh-files resolves to a local docker bridge — the VPS can never reach the home LAN. | Blocks home-LAN subnet routing; latent blackhole | OPEN |
| 2 | **ovh-files and ovh-app use identical docker subnets** (both 172.17–172.31 + 192.168.0–128). Tailscale can only route one host per CIDR. | Blocks subnet-routing both hosts at once | OPEN |
| 3 | Fix: set `/etc/docker/daemon.json` `default-address-pools` to a distinct 10.x range per host (neither box has a daemon.json; both run Docker defaults). Requires recreating networks = restart all stacks. | Resolves #1 and #2 | OPEN |
| 4 | **Traefik binds `0.0.0.0` on all 4 hosts**, not the Tailscale IP — contradicts the standing "tailscale only, no open net" position. | Public exposure | OPEN |
| 5 | **Port 8080 published to `0.0.0.0` on all 4 hosts**, nothing behind it (`api.insecure=false`). | Needless public surface | OPEN |
| 6 | **`Secrets/PLATFORM_REFERENCE.md` badly stale.** `chat.` / `browser.` / `n8n.` / `milvus.` / `attu.` / `windmill.` .mitechconsult.com all return 503, containers absent. Milvus gone (Weaviate cutover). LiteLLM retired. ovh-data now dead. | Doc drift — misleads every agent | OPEN |
| 7 | **Coolify `*.sslip.io` domains are catalogued but NOT wired to Traefik** — no `traefik.*` labels, return 404. They are not working hostnames. | False assumption of reachability | OPEN |
| 8 | ~~Parallel stacks: TWO Weaviates AND TWO Graphiti stacks violate the no-parallel rule.~~ **CORRECTED 2026-08-20 (archaeology):** the two **Graphiti** stacks are **intentional and load-bearing** — the upstream `zepai/knowledge-graph-mcp` image drops the Neo4j `database=` field, so one image can only bind one Neo4j DB; the `cursedpotential` fork exists to target the `memory` DB for the case lane. Not duplication. The two **Weaviates** remain unexplained → see #15. | Graphiti = by design | PARTLY RESOLVED |
| 9 | **ovh-data VPS still needs terminating at OVH** (billing action, owner-only). Host powered off 2026-08-20; disk with 5.1G surreal data intact until terminated. | Ongoing cost | OWNER |
| 10 | ~~Global `~/.claude/CLAUDE.md` contradiction between the old "confirm before changes" rule and SPRINT MODE.~~ **RESOLVED 2026-08-20** — old rule struck through and marked superseded; destructive/outward-facing carve-outs retained. | — | DONE |
| 14 | 🔴 **SurrealDB is formally RETIRED (ADR-0043, owner ruling 2026-08-06) — yet `data-surreal-phase1-t0-r1` is live in Coolify production and was ordered promoted on 2026-08-20.** These cannot both be current intent. Needs an owner ruling before the promotion proceeds. | Contradicts canon | **OWNER — BLOCKING** |
| 15 | **Two Weaviate instances on ovh-files are unexplained in every session log.** `weaviate-o97r85b7` (8081) vs `weaviate-native-v1-v43tfq` (8082). No log states which is canonical. Do not touch either until owner decides. | Unknown canonical store | OWNER |
| 16 | **LiteLLM container was never actually torn down.** Every doc says "retired" (ADR-0042, owner 2026-07-29) but DECISION_LOG D-030 clarifies only docs/refs were retired. Port 4000 is dead but the container persists. | Doc says done, reality differs | OPEN |
| 11 | **OVH private network never came up.** `/etc/netplan/60-salem-private.yaml` configures `ens7`; actual second NIC is `ens4` (DOWN, unconfigured). Intended "Salem priv" range is 10.1.x. | Private net unavailable | OPEN |
| 12 | **Dead port mapping:** `gateway` container on ovh-app publishes 4000 with nothing listening (retired LiteLLM). Only `opencode` on 4096 is live. | Misleading published port | OPEN |
| 13 | **Historical hazard:** a previously advertised `10.1.x` subnet route once blackholed the owner's public IPv4 (2026-06-25). Re-check before advertising anything in 10.1.x. | Repeat-outage risk | NOTE |

_Added 2026-08-23 (Claude Code · Opus 5) from the cross-repo document-handling audit. These are
ingest-capability gaps, not infra — the rows above are all fleet/networking._

| # | Item | Impact | Status |
|---|------|--------|--------|
| 17 | **DOCX / PPTX / XLSX / HTML ingest fails on a default install.** `server/ingest/service.py:_extract_document` registers `documents.extract-docling` for all of `_DOCUMENT_SUFFIXES`, but appends the `documents.extract-text` fallback **only for `.pdf`** (`service.py:155-158`). `docling` lives in the `document-ai` extra (`pyproject.toml:87`) and is **absent from `requirements.txt`**. The module import succeeds (docling is imported lazily *inside* `extract_docling`), so the extractor is registered and then raises at call time — `RuntimeError: Docling is unavailable; install the "document-ai" extra`. With no fallback for these five suffixes the loop exhausts and `service.py:181` raises `ValueError: document extraction failed for <name>: …`, giving receipt status `"failed"`. **Note:** `docling_extract.py`'s own docstring claims the caller "falls through to native/Tesseract" — that is true for `.pdf` only and wrong for the office formats. | 5 common document types cannot be ingested; docstring overstates coverage | OPEN |
| 18 | **Scanned / image-only PDFs do not OCR by default.** The OCR fallback in `server/tools/extractors/extract_text.py` needs `pytesseract` + `pdf2image`, which live in the `ocr` extra (`pyproject.toml:83`) and are **absent from `requirements.txt`** (only transitive `pillow==12.3.0` is present). Text-layer PDFs are fine — `pypdf==6.15.0` and `pdfplumber==0.11.10` are pinned in base. | Scanned exhibits ingest as empty/near-empty text, silently | OPEN |
| 19 | **The evidence lane cannot ingest PDFs or DOCX at all.** `server/ingest/service.py:197` skips the document-extraction branch entirely when `request.lane is IngestLane.evidence`. Combined with `_whole_file_text` being forbidden for evidence (`:130-131`, ADR-0044) and `_EVIDENCE_FORBIDDEN_PARSERS` (`:29,232-233`), the evidence lane accepts only chat/transcript/Go-registry formats. A scanned court order or a PDF exhibit has **no ingest path into the evidence lane**. | Court-facing document types cannot enter custody | OPEN — needs an owner ruling on whether this is intended (ADR-0044 scope) |

## 2026-08-24 — Coolify + fleet cleanup (owner order, queued mid-Temporal-deploy)
- Owner: "clean up Coolify and the servers — so many things running or dead or stale — BOTH OVH servers."
- Plan: full triage table per server (app, status, last deploy, branch, verdict running/dead/stale/duplicate),
  mine-before-retiring notes, then owner approves the kill/quarantine list. Known dead already: librechat +
  librechat-mongo (exited) vs librechat-app/-mongo-app pairs, nocodb + clone-of-nocodb vs nocodb-app,
  test project. NEVER delete without per-app owner sign-off.

## 2026-08-24 — n8n upgrade + Postgres migration (Claude Code · Opus 5)

Deferred items from the n8n 2.26.8 → 2.36.6 upgrade. The instance is live and verified at
<https://n8n.mitechconsult.com>; these are the parts that could NOT be completed and why.

| # | Item | Impact | Status |
|---|------|--------|--------|
| 20 | ~~**Daytona sandbox not enabled — no credentials exist.**~~ **RESOLVED 2026-08-24 (owner order: "we aren't gonna do the Daytona sandbox we're gonna self host").** The self-hosted `n8n-sandbox` stack (`sandbox-certs` + `sandbox-api` + privileged DinD `sandbox-runner-1`, mutual TLS) now runs inside the same Coolify service compose. n8n boots with `Sandbox: enabled=true provider=n8n-sandbox (from env)`; `sandbox-api` is healthy and reachable from n8n by service name; `runner-1` registered over mTLS and pulled the sandbox image. Daytona is NOT used. | Code sandbox now available | RESOLVED |
| 21 | **AI web search still off — but SearXNG is NOT actually credential-blocked.** ~~no Brave key and no SearXNG URL exist anywhere in `~/.secrets/`~~ **Correction 2026-08-24:** SearXNG needs **no API key at all** — n8n's own compose guide bundles `ghcr.io/searxng/searxng:latest` with a single self-generated `SEARXNG_SECRET`, and n8n points at it via `N8N_INSTANCE_AI_SEARXNG_URL=http://searxng:8080`. That can be stood up at any time with no external credential. **Brave remains blocked** — `INSTANCE_AI_BRAVE_SEARCH_API_KEY` needs a real key, and Brave takes priority over SearXNG when both are set. | Assistant/agents cannot search the web | **SearXNG RESOLVED 2026-08-24** — deployed and verified returning JSON results from inside the n8n container (see section 31). **Brave still OPEN** — needs an owner-supplied key; Brave takes priority over SearXNG when both are set. |
| 22 | **Log streaming left UI-managed deliberately.** `N8N_LOG_STREAMING_MANAGED_BY_ENV=true` was NOT set: it requires `N8N_LOG_STREAMING_DESTINATIONS` (JSON), and no log endpoint exists. Setting the flag with no destinations would make the Log-streaming UI read-only **and** stream nowhere — strictly worse than leaving it UI-managed. | Objective "enable log streaming via env" not met | OPEN — needs a real destination URL (webhook/syslog/sentry) |
| 23 | **`N8N_AGENTS_AI_SANDBOX_PROVIDER` does not exist in 2.36.6.** It was in the requested target config but is not a real variable — the agents sandbox exposes only `N8N_AGENTS_AI_SANDBOX_ENABLED/_EPHEMERAL/_IMAGE/_SNAPSHOT/_TIMEOUT`. Only the instance-ai side has a `_SANDBOX_PROVIDER`. Verified by grepping `@n8n/config` in the running image. | Requested var would have been silently inert | RESOLVED — dropped from config, documented here |
| 24 | ~~**Postgres 16 is below n8n 2.36.6's supported range.**~~ **RESOLVED 2026-08-24 (owner: "Sixteen is being retired You're supposed to use 18").** The `n8n` database was moved from `casebible-db` (PG 16.15) to `casebible-pg18` (`fgz1n7useplhk0t91uk7k1aw`, **PostgreSQL 18.1**) by `pg_dump` → `psql` restore with n8n stopped. Verified identical: **129 tables, 246 migrations, 1 user**. The `Postgres 16 is outside the supported range` boot warning is now **absent**. The PG16 `n8n` database and role were left in place untouched as a rollback path; dump retained at `/root/n8n-pg16-dump-20260824.sql` on ovh2. | Now on a supported PG major | RESOLVED |
| 25 | **Owner account must be re-created.** The SQLite→Postgres cutover started a clean n8n DB, so the single pre-existing owner user did not carry over (0 workflows / 0 credentials / 0 executions were migrated — there was nothing to migrate). First visit to <https://n8n.mitechconsult.com> shows owner setup. Old SQLite file is retained untouched in the volume + backup tarball. | One-time manual setup | OWNER — action required |
| 26 | **Python task runner unavailable in the image.** Boot log: `Failed to start Python task runner in internal mode because Python 3 is missing from this system.` JS runner registered fine. Only matters if Python Code nodes are used. | Python Code nodes unavailable | NOTE |
| 27 | **The n8n docs' sandbox variable names are WRONG for 2.36.6.** `https://docs.n8n.io/deploy/host-n8n/configure-n8n/set-up-ai-assistant` and the Docker Compose guide both instruct `N8N_INSTANCE_AI_SANDBOX_API_URL` and `N8N_INSTANCE_AI_SANDBOX_API_KEY`. Both have **0 occurrences** in the entire installed 2.36.6 tree (verified by `grep -rl` over `/usr/local/lib/node_modules/n8n`). The names the code actually reads are **`N8N_SANDBOX_SERVICE_URL`** (13 hits) and **`N8N_SANDBOX_SERVICE_API_KEY`** (2 hits), declared in `@n8n/config/dist/configs/instance-ai.config.js` as `n8nSandboxServiceUrl` / `n8nSandboxServiceApiKey`. Following the docs verbatim yields a silently inert sandbox with **no error at boot**. | Docs would silently break the sandbox | NOTE — our compose uses the correct names |
| 28 | **The sandbox runner is a privileged Docker-in-Docker container on ovh2.** `sandbox-runner-1` runs `privileged: true` on a host that also runs Coolify, Postgres, Milvus, Neo4j, Temporal and Weaviate. n8n's own docs call `n8n-sandbox` "best suited to local development and testing" and recommend Daytona for production. Owner chose self-hosting deliberately on 2026-08-24. No ports are published for either sandbox container. | Privileged container shares the host with production data services | NOTE — accepted risk, owner decision |
| 29 | ~~**Tailscale `svc:n8n` created but not yet serving — needs admin approval.**~~ **RESOLVED 2026-08-24 (owner approved the ACL edit).** The console approval never took because the tailnet policy file had **no `autoApprovers` block at all** (top-level keys were only `grants`, `ssh`, `tagOwners`), so the control plane never authorized the node as a service proxy — `svc:n8n` was absent from the node's netmap and nothing bound the VIP. Fixed by adding, additively, `autoApprovers.services = {"svc:n8n": ["tag:docker"]}` via `POST /api/v2/tailnet/-/acl` (note: **`POST`, not `PUT`** — `PUT` returns HTTP 405), guarded with the `If-Match` ETag and a byte-diff assertion so `grants`/`ssh`/`tagOwners` were untouched (2563 → 2761 bytes). `ovh-files` carries `tag:docker`. A `tailscaled` restart was required for the node to re-register; `tailscale set --advertise-services` does **not** exist in 1.102.2. ~~Verified live:~~ **HTTP 200**, `/healthz` `{"status":"ok"}`, Let's Encrypt cert `CN=n8n.tilapia-skilift.ts.net` expiring **Nov 22 2026**.~~ **CORRECTION 2026-08-24 13:57 EDT (Claude Code · Opus 5):** that verification was run **from ovh2 itself**, where tailscaled answers its own VIP locally — it never proved tailnet reachability, and at the time the service was in fact **unreachable from every other node** (`tailscale ping 100.70.243.34` → `no matching peer` from both `ionos` and `ovh1`). An additive grant `{src:["*"], dst:["svc:n8n"], ip:["*"]}` was trialled as a suspected cause, did **not** fix it, and was **reverted** (policy back to 2760 bytes, `autoApprovers` retained, existing text byte-identical) — confirming the wildcard `dst:["*"]` already covers VIP services and no extra grant is needed. The service began working ~44 min later, most plausibly as console approval propagated; **the fix is not confidently attributable**. **Now properly verified cross-node** from `ionos` and `ovh1`: `https://n8n.tilapia-skilift.ts.net/` → **200** (`ssl_verify_result=0`), `/healthz` `{"status":"ok"}`, LE cert `CN=n8n.tilapia-skilift.ts.net` issuer `CN=YE1` exp **Nov 22 2026**, and `tailscale ping 100.70.243.34` → `pong from ovh-files`. **Two diagnostic caveats worth keeping:** (1) `tailscale debug netmap | grep svc:n8n` returns **0 hits even while the service works** — it is *not* a valid health signal, though it was cited as definitive earlier; use `tailscale ping <vip>` instead. (2) Hitting the raw IPv4 VIP (`curl -k https://100.70.243.34/`) returns `000` by design — VIP routing is **SNI-based** and requires the hostname. | n8n now reachable on its own tailnet service name | RESOLVED |
| 30 | **Node-root tailnet serve removed — it was structurally unreliable on this host.** After the `tailscaled` restart, `https://ovh-files.tilapia-skilift.ts.net/` began returning `CN=TRAEFIK DEFAULT CERT`: `:443` on the node's tailnet IP is bound by **coolify-proxy's `docker-proxy` on `0.0.0.0:443`**, which won the bind ordering race against tailscaled's node-root serve. It had worked earlier the same day purely by bind order. Since `svc:n8n` was by then verified, the broken node-root entry was removed with `tailscale serve --https=443 off`. The VIP service is immune to this because it listens on its **own dedicated address** (`100.70.243.34`), not the shared node IP. The pre-existing Postgres TCP serves on **5433/5434 were left intact** (verified after the change). | Tailnet access is now solely via `svc:n8n` | RESOLVED — by design |

_Items 20–33 added/updated 2026-08-24 by Claude Code · Opus 5 during the n8n upgrade, Postgres 18 move,
and self-hosted sandbox build._

## 31. SearXNG web search — RESOLVED 2026-08-24

Self-hosted `searxng` (`ghcr.io/searxng/searxng:latest`) added to the n8n stack on ovh2.
No API key required; only a self-generated `SEARXNG_SECRET` (in `~/.secrets/n8n-sandbox-ovh2.env`,
pushed to Coolify as a service env). n8n wired via `N8N_INSTANCE_AI_SEARXNG_URL=http://searxng:8080`.

Gotcha worth keeping: the stock SearXNG image serves **HTML only**. n8n needs the JSON API, which
requires a settings file (`search.formats: [html, json]`). It is mounted from
`/data/coolify/services/ddjgrmys36d9n8xwcwj0mml2/searxng-settings.yml` by **absolute** path, NOT the
docs' relative `./searxng-settings.yml` — under Coolify a relative path that fails to resolve makes
Docker silently create a *directory* at `/etc/searxng/settings.yml`, leaving SearXNG on stock
HTML-only settings with **no error**. Verified live: `wget -qO- 'http://searxng:8080/search?q=test&format=json'`
from inside the n8n container returned real JSON results.
SearXNG port is never published; it is reachable only on the compose network.

## 32. AI model changed: mistral-nemotron is UNRELIABLE — RESOLVED 2026-08-24

`mistralai/mistral-nemotron` (the model configured since the original build) is **intermittent on this
NIM account**: it failed **6 consecutive calls** across two runs (HTTP 500 x4, client timeout x2, one
taking 85s), then **succeeded 2/2** on a later run. So it is not permanently down — it is unreliable,
which is worse to debug and still disqualifying for a production assistant.

Two corrections recorded honestly:
  1. The original verification only confirmed the model was **listed** in `/v1/models`, never that it
     could **complete a request**. Listing is not a liveness check.
  2. This item first stated the model was "non-functional / broken". That was too strong — a later
     sweep pass got clean tool calls from it. It is flaky, not dead.

Replaced with **`openai/nvidia/nemotron-3-super-120b-a12b`** (owner-preferred "Super", and the test winner).

Live-tested 21 NVIDIA/Nemotron models for tool calling (n8n Agents require it), 2 runs each:

| model | tool calling | note |
|---|---|---|
| nvidia/nemotron-3-super-120b-a12b | TOOL 1.2s / 1.7s | **selected** |
| nvidia/nemotron-3-ultra-550b-a55b | TOOL 2.3s / 2.1s | works, slower; headroom option |
| nvidia/nemotron-3.5-lightning-30b-a3b | TOOL 1.9s / 1.7s | works, fastest small |
| nvidia/nemotron-3-nano-omni-30b-a3b-reasoning | TOOL 2.9s / 2.5s | works |
| nvidia/llama-3.3-nemotron-super-49b-v1 | TOOL 0.8s / 4.0s | works, inconsistent latency |
| nvidia/llama-3.3-nemotron-super-49b-v1.5 | **text only** | never emits tool_call - unusable for Agents |
| nvidia/nemotron-3-nano-30b-a3b | **text only** | unusable for Agents |
| nvidia/llama-3.1-nemotron-ultra-253b-v1 | HTTP404 | not enabled on this account |
| nvidia/llama-3.1-nemotron-70b-instruct | HTTP404 | not enabled on this account |
| nvidia/llama-3.1-nemotron-51b-instruct | HTTP404 | not enabled on this account |
| nvidia/nemotron-4-340b-instruct | HTTP404 | not enabled on this account |
| mistralai/mistral-nemotron | HTTP500/timeout x6, then TOOL 3.8s / 0.7s | **flaky - was the live config** |

Second inference test on the selected model (beyond single tool call):
full agent round-trip (tool_call -> tool result -> final answer citing the data) **OK**;
streaming SSE **OK** (21 chunks, 0.1s TTFB); JSON mode (`response_format: json_object`) **OK**.

Note: model numbering is NOT chronological. `nemotron-4-340b` is the older 2024 line; the current
line is `nemotron-3-*` / `nemotron-3.5-*`.

## 33. Vision / parsing models — no action needed

n8n 2.36.6 `instance-ai` exposes exactly **one** model slot: `N8N_INSTANCE_AI_MODEL` (+ `_URL`, `_API_KEY`).
Verified by enumerating every `N8N_INSTANCE_AI_*` var in the image - there is no vision or parsing slot.
Vision (`nvidia/nemotron-nano-12b-v2-vl`) and document parsing (`nvidia/nemotron-parse`) are available on
the same NIM account and get wired **later, per workflow, as credentials** - not as instance config.

**Verified 2026-08-24** that the per-workflow approach works: an OpenAI-compatible node can reuse the
SAME NVIDIA key and the SAME base URL (`https://integrate.api.nvidia.com/v1`) and only change the model.
Tested with a real base64 `image_url` payload:

| model | result |
|---|---|
| nvidia/nemotron-nano-12b-v2-vl | **VISION-OK 0.7s** - correctly identified the image color |
| nvidia/llama-3.1-nemotron-nano-vl-8b-v1 | VISION-OK but slow (28.9s) |
| nvidia/cosmos-reason2-8b | HTTP404 - not enabled on this account |
| nvidia/nemotron-3-super-120b-a12b | **HTTP400** - "multimodal processing is not enabled" |

That last row matters: the main chat model **cannot** accept images, so vision requires its own node
with its own model. It cannot ride on `N8N_INSTANCE_AI_MODEL`.

## 2026-08-24 — EvidenceChunkV1 (+ chat-lane collections): add numeric epoch mirror fields BEFORE backfill
- The n8n Weaviate node's range filters (greaterThan/lessThan) take NUMBERS only — its typed-date
  fields are invisible to it (docs page n8n-nodes-langchain.vectorstoreweaviate, verified 2026-08-24).
- Add `occurred_at_epoch` + `source_available_from_epoch` (int, epoch seconds) to the native
  collection schema(s) now, while activation/backfill is still held (D-066) — retrofit later = full
  re-projection. Applies to any collection n8n-side agents will query (D-068 architecture).
- Standing rule from the same review: n8n gets READ-ONLY retrieval against evidence collections —
  its Insert mode carries a "Clear Data" wipe option and must never point at them.

## 2026-08-24 — Consolidate duplicate folders (owner order, queued)
- Owner: duplicate folders need consolidating — TESTS, EVALS, and BUILD folders in particular.
- Approach when picked up: inventory duplicates first (mine-before-retiring), propose merge
  targets, owner approves, then consolidate — never-delete applies (quarantine, don't remove).
- Context note: owner personally moved compose.data-surreal.yaml + compose.surreal-phase1.yaml
  out of the repo root same night ("they don't belong there") — those deletions are the owner's
  to commit, not an agent's.
