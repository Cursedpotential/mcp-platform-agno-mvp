> _Byline: Claude Code · Sonnet · 2026-07-19_

# Portkey gateway configs

Durable source of truth for the Portkey gateway's routing configs, in parity with how
`docker/gateway/litellm-config.yaml` is already git-tracked. Portkey itself
(`portkeyai/gateway:1.15.2`, Coolify app `portkey` / `z5787t1l7gl2zbrya8cxzapf`, port `8787` on
`ovh-app`) is a **stateless, no-DB, no-volume** deployment — it has no durable config of its own.
Every route is expressed as a JSON body sent per-request in the `x-portkey-config` header. These
files are that JSON, committed here so routing isn't only "whatever header a caller happened to
build" — see `Agno-MCP-Platform/../PROPOSAL-portkey-changeover.md`-class research doc (OneDrive AI
Space) for the full as-built research this was built from.

## Files

| Config | Lane | Design |
|---|---|---|
| `configs/embed.json` | Graphiti's `embed-text` (dimension-locked, 4096-d) | NVIDIA `nv-embed-v1` ONLY — no cross-provider fallback. Gemini embeddings top out at 3072-d and can't match the Neo4j-locked index; a silent wrong-dimension fallback would corrupt vectors, not just error. |
| `configs/embed-general.json` | Future/not-yet-dimension-locked knowledge-core collections | Gemini 4-key loadbalance primary, NVIDIA `nv-embed-v1` fallback. **See the dimension-truncation warning inside the file** — do not trust it blind. |
| `configs/classify.json` | Cheap/fast triage calls | Gemini `gemini-flash-latest` 4-key loadbalance primary, NVIDIA `meta/llama-3.1-8b-instruct` fallback. |
| `configs/chat.json` | rag+chat (mid-to-heavy reasoning) | glm-5.1 (Ollama Cloud) primary → Gemini `gemini-flash-latest` 4-key loadbalance middle tier → NVIDIA `nemotron-3-super-120b-a12b` final fallback. Collapsed from separate rag/chat drafts — they came out identical; split again later if they ever need independent tuning. |

Each `$VAR` placeholder is substituted with a real secret value at request-construction time by
whatever consumer builds the outgoing `x-portkey-config` header — Portkey itself does **not** read
these from its own container env (confirmed: `Mounts: []`, and env-substitution inside an inline
header isn't a documented Portkey feature). The values live in `C:\Users\matts\.secrets\Agno-MCP-Platform.env`
locally and were also upserted into the Portkey Coolify app's stored env
(`NVIDIA_API_KEY`, `GEMINI_API_KEY`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, `GEMINI_API_KEY_4`) on
2026-07-19 so they're available server-side for whatever future substitution mechanism picks them
up (e.g. a small router/sidecar service, or a wrapper script) — see the Coolify env upsert note
below. `GOOGLE_API_KEY` is deliberately **not** part of this rotation pool (owner: reserved, stays
separate) even though as of 2026-07-19 it happens to hold the same value as `GEMINI_API_KEY`.

## Verified live (2026-07-19, real API calls through `http://100.72.169.40:8787`)

- **Embed lane**: `POST /v1/embeddings` with `configs/embed.json` (NVIDIA `nv-embed-v1` via
  `custom_host`) → **HTTP 200, 4096-d vector**. Confirms the dimension-lock-safe path works
  end-to-end through Portkey.
- **Gemini provider slug**: `"google"` is correct (not `"google-ai-studio"` — that 400s with
  "Invalid 'provider' value"; the pinned image's valid list is `anthropic, anyscale, azure-openai,
  cohere, google, vertex-ai, mistral-ai, openai, palm, perplexity-ai, ...`). A real chat completion
  through `provider: "google"` returned real content.
- **Nested loadbalance-inside-fallback**: accepted by this pinned image — verified against the
  actual `classify.json` file (not a hand-rolled shape), got a real completion back.
- **3-tier fallback chain**: verified against the actual `chat.json` file, glm-5.1 primary tier
  answered directly (no fallthrough needed for a healthy primary).
- **Gemini key pool — per-key verification matrix** (this is why `classify.json`/`chat.json` pin
  `gemini-flash-latest` instead of the proposal's original `gemini-2.5-flash`/`gemini-2.5-pro`
  drafts):

  | Key | Format | `gemini-2.5-flash` | `gemini-2.5-pro` / `gemini-pro-latest` | `gemini-flash-latest` |
  |---|---|---|---|---|
  | `GEMINI_API_KEY` | `AIzaSy...` (standard AI Studio key) | 200 | 429 (quota, see note) | 200 |
  | `GEMINI_API_KEY_2` | `AQ.Ab8RN6...` (non-standard token format) | **404** "no longer available to new users" | 429 (quota) | 200 |
  | `GEMINI_API_KEY_3` | `AQ.Ab8RN6...` (non-standard token format) | **404** "no longer available to new users" | 429 (quota) | 200 |
  | `GEMINI_API_KEY_4` | `AIzaSy...` (standard AI Studio key) | 200 | not fully retested (timeout during test run) | 200 |

  The `gemini-2.5-pro`/`gemini-pro-latest` 429s hit **every** key including the two standard-format
  ones, under rapid repeated test traffic in a short window — this looks like it's most likely a
  free-tier RPM/quota ceiling triggered by the verification pass itself, not a standing "pro tier is
  broken" fact, but it was NOT re-verified at a slower request rate before this commit. Treat "is the
  pro tier actually usable at real traffic rates" as an open question, not a closed one.

  `GEMINI_API_KEY_2`/`_3` use a token format (`AQ.Ab8RN6...`) that doesn't look like a normal Google
  AI Studio API key (those are `AIzaSy...`, 39 chars). These two are longer (~70 chars incl. a `.`
  separator) and behave like they're tied to accounts Google has migrated off the pinned `2.5`
  model family onto `*-latest` aliases only. Flagging for the owner to double check these two
  accounts/keys are what was intended for the rotation pool — they work, but only on `*-latest`
  aliased models, not the pinned generation the other two keys can reach.

- **`embed-general.json`'s `gemini-embedding-001`**: all 4 keys returned 200, but **the
  `output_dimensionality`/`outputDimensionality`/top-level `dimensions` override was not honored by
  this pinned Portkey image** — every combination tried still returned the model's native 3072-d
  output, not the requested 1536-d. This is flagged inline in `embed-general.json` itself; treat the
  1536 figure in that file as aspirational until re-verified, and lock any real Milvus collection to
  the dimension actually observed at creation time, not the config's stated intent.

## Coolify env durability (Phase 1 of the 2026-07-19 changeover)

As part of this same pass, the exec-tier (LiteLLM) Coolify app's stored env was found to have a
genuine drift: `GROQ_API_KEY` was present in the local `.secrets` file but empty in both the live
gateway container and Coolify's own rendered compose (i.e. never actually reached Coolify's env
store) — fixed via `coolify-write-upsert-application-envs`. `NVIDIA_API_KEY` was already correctly
synced (a prior redeploy had already fixed it) but was upserted again anyway to guarantee it, since
`upsert` is idempotent. See `C:\Users\matts\OneDrive\AI Space\portkey-standup-result.md` for the
full Phase 1 writeup.

While doing this, a real bug was found and fixed in the `coolify-write` MCP server itself
(`~/.claude/skills/coolify-write/server.py`, `upsert_application_envs`): its bulk-PATCH body shape
was `{"envs": [...]}` with `is_runtime`/`is_buildtime`/`is_literal` fields, but Coolify's actual API
(`PATCH /applications/{uuid}/envs/bulk`, verified live against v4.1.2) wants `{"data": [...]}` with
`is_preview`. The wrong shape 400'd, was swallowed silently (no exception raised on non-2xx), and
fell through to a per-key `POST` fallback that can only **create** — so it 409'd on every
already-existing key, meaning **this tool could never actually update an existing env var** before
this fix. Corrected in-place; verified against the live API (create → in-place update, confirmed by
matching `uuid` + changed `updated_at` → cleanup delete) before relying on it for the real upserts
in this pass.

## Doors policy

LiteLLM (`gateway:4000`, `docker/gateway/litellm-config.yaml`) is untouched by any of this — it
stays live as the working fallback path per the workspace's doors policy until whatever Portkey
cutover is attempted (Graphiti first, see the Phase 3 writeup in the result doc above) is verified
working end-to-end, and for an owner-set soak period after that.
