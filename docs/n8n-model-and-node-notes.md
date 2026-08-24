# n8n — Model Selection & Node Build Notes

_Claude Code · Opus 5 · 2026-08-24_

Working notes for the n8n 2.36.6 stack on **ovh2**. Live URLs:
`https://n8n.mitechconsult.com` (public) · `https://n8n.tilapia-skilift.ts.net` (tailnet, `svc:n8n`).

---

## 1. Model verdicts — tested live against NVIDIA NIM

All results below are from **real API calls this session**, not documentation claims.
Endpoint: `https://integrate.api.nvidia.com/v1/chat/completions` (OpenAI-compatible).

### Vision

| Model | Result | Verdict |
|---|---|---|
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` | Described a B/W split image correctly; counted bars correctly (4); extracted **5/5** invoice fields as clean JSON | ✅ **USE THIS** |
| `nvidia/nemotron-nano-12b-v2-vl` | **Hallucinated** — called a black/white split image "a long bridge that crosses a dark area". 37.5s | ❌ Rejected |
| `nvidia/nemotron-3-super-120b-a12b` | `HTTP 400 — Received multimodal data but multimodal processing is not enabled` | ❌ No vision |

**Omni is the vision model.** It beat the purpose-built VL model on accuracy, not just preference.

Latency observed: 1.3s (simple) → 5.1s (basic image) → **31.9s** (dense invoice + JSON extraction).
Budget for ~30s on document-heavy calls; set n8n node timeouts accordingly.

### Parsing — `nvidia/nemotron-parse` does NOT work as expected

Two hard constraints found by testing:

1. **Rejects any text part.** Sending `{"type":"text"}` alongside the image returns:
   `HTTP 400 — Content cannot be a plain string. The model does not support text input.`
   It only accepts a content array containing an image and nothing else.
2. **Returns empty output.** With a correctly-formed image-only payload against a real
   rendered invoice (24 KB PNG, actual glyphs), it returned `HTTP 200` with
   **`content: ""`** in 1.4s. Zero fields extracted.

> ⚠️ **Do not put `nemotron-parse` into production on the chat-completions path.**
> It responds 200-OK with nothing in it — a silent failure that would look like
> "no data found" rather than an error. It likely requires a different NIM invocation
> format (dedicated endpoint / response schema), which is **not yet investigated**.

**Omni does the parsing job today** — it returned the full invoice as structured JSON.
Use Omni for both vision *and* document extraction until parse is properly understood.

### Tool-calling (from earlier testing)

| Model | Tool calls |
|---|---|
| `nvidia/nemotron-3-super-120b-a12b` | ✅ 1.0s |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | ✅ 1.3s |
| `nvidia/llama-3.3-nemotron-super-49b-v1.5` | ❌ text only |

**Note on naming:** NIM model numbers are *not* chronological. `nemotron-4-340b` is the
older 2024 line; the current generation is `nemotron-3-*` / `nemotron-3.5-*`.

### Currently configured on the live instance

`N8N_INSTANCE_AI_MODEL=openai/mistralai/mistral-nemotron`
(provider split at the **first** slash → provider `openai`, model `mistralai/mistral-nemotron`).

---

## 2. Search

- **SearXNG** — ✅ live, internal-only at `http://searxng:8080`, `N8N_INSTANCE_AI_SEARXNG_URL` set.
  Patched to serve the JSON API (stock image is HTML-only).
- **Brave** — ❌ **dropped for now** (owner decision, 2026-08-24). `INSTANCE_AI_BRAVE_SEARCH_API_KEY`
  left unset. Relevant if revisited: **Brave takes priority over SearXNG when both are set**,
  so adding a Brave key later will silently displace SearXNG.

---

## 3. Node build queue

`credentials_entity` count = **0**. Nothing is wired yet; every node below needs a
credential created. Owner account is confirmed set up (`matt.salem85@gmail.com`,
`global:owner`, `instanceAi.setupCompletedAt` present).

### ✅ Credentials on hand — can be wired now

| Node | Credential | Source |
|---|---|---|
| **S3 → Cloudflare R2** | `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL` (also a separate case-bible set) | `~/.secrets/r2.env`, `r2-case-bible.env` |
| **S3 → Backblaze B2** | `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_S3_ENDPOINT`, `B2_REGION` | `~/.secrets/backblaze.env` |
| **Postgres Trigger** | n8n role on PG18 (`fgz1n7useplhk0t91uk7k1aw`), password at `/root/.n8n-pg-password` on ovh2 | live |
| **LLM sub-node (NIM)** | NVIDIA API key → use the **native `NVIDIA` credential** (`NvidiaApi`), not a generic OpenAI one | `~/.secrets/` |

S3 node notes: both R2 and B2 are S3-compatible, so both use the built-in **S3** node with a
custom endpoint — **force path-style addressing**; virtual-host style will fail against R2.

Postgres Trigger notes: the node needs either `LISTEN/NOTIFY` or table triggers. The `n8n`
role owns the `n8n` DB only — **watching `casebible` tables will require extra grants**.

### ⚠️ Blocked — needs something from you

| Node | Blocker |
|---|---|
| **Google Drive** | `GOOGLE_API_KEY` exists but **an API key will not work** — the Drive node requires **OAuth2 (client ID + secret)** or a **service-account JSON**. Needs a Google Cloud Console credential. |
| **Mailgun** | **No Mailgun key anywhere** in `~/.secrets/`. Needs API key + sending domain. |
| ~~**Weaviate Vector Store**~~ | ~~No endpoint known. Fleet scan was cut short — status genuinely unverified.~~ **RESOLVED 2026-08-24:** owner confirmed instances exist; scan completed. **Two Weaviate 1.38.7 + Milvus on ovh2, anonymous auth, no key needed.** Full connection values in section 6. |

### 🔗 LangChain cluster root nodes — no own credentials

These four all attach an **LLM sub-node** and share one decision:

- Text Classifier
- Information Extractor
- Summarization Chain
- Sentiment Analysis

~~They need the NIM model exposed as an **OpenAI-compatible Chat Model** sub-node.~~

> **CORRECTION — 2026-08-24:** Use the built-in **NVIDIA Chat Model** sub-node
> (`LmChatNvidia`) with the **`NvidiaApi`** credential. Its Base URL already defaults to
> `https://integrate.api.nvidia.com/v1`, so only the API key is needed. One credential
> serves all four root nodes. The generic-OpenAI workaround is unnecessary.

Model fit: use a **tool-calling capable** model — `nemotron-3-super-120b-a12b` or
`nemotron-3.5-lightning-30b-a3b`. Information Extractor in particular relies on
structured output, so avoid `llama-3.3-nemotron-super-49b-v1.5` (text-only).

---

## 4. Reference workflows supplied

- **1748** — *Pulling data from services n8n doesn't have a pre-built integration for*
  (`n8n.io/workflows/1748-...`). This is the pattern for calling NIM directly: **HTTP Request**
  node + `Item Lists` to split the body, plus pagination via Set→If→increment loop.
  ~~Relevant because there is no built-in NVIDIA node.~~

  > **CORRECTION — 2026-08-24 (Claude Code · Opus 5):** The struck sentence was **wrong**, and
  > was written without checking. Verified against the **live 2.36.6 image** on ovh2:
  > `@n8n/n8n-nodes-langchain/dist/nodes/llms/**LmChatNvidia**` and
  > `dist/credentials/**NvidiaApi.credentials.js**` both exist, as does
  > `dist/nodes/embeddings/**EmbeddingsNvidia**`. NVIDIA NIM is a **first-class built-in
  > integration** — no HTTP Request hack is required for chat or embeddings.
  > Workflow 1748 remains a useful reference for *non-integrated* REST APIs generally,
  > but it is **not** the path for NIM.
- **8867** — *Analyze images with OpenAI vision while preserving binary data for reuse.*
  The binary-preservation pattern is the one to copy for the Omni vision node.

---

## 5. Next actions

1. Wire the **NIM OpenAI-compatible** credential — unlocks the four LangChain root nodes.
2. Build the **Omni vision** node using the 8867 binary-preservation pattern.
3. Create **R2** and **B2** S3 credentials (path-style endpoints).
4. Decide **Postgres Trigger** scope — `n8n` DB only, or grant access to `casebible`.
5. Get **Mailgun** key + **Google Drive** OAuth client from owner.
6. ~~Re-run the vector-store fleet scan.~~ **DONE** — reuse the existing
   `weaviate-o97r85b7…` (see section 6). Nothing new to stand up.
7. Investigate the correct invocation format for `nemotron-parse`, or formally drop it.

---

## 6. Verified node + credential inventory — n8n 2.36.6 (live image, ovh2)

_Method: `ls`/`grep` inside the running container against
`@n8n/n8n-nodes-langchain/dist`. Not from memory, not from docs._
_Claude Code · Opus 5 · 2026-08-24_

**NVIDIA is first-class.** `LmChatNvidia`, `EmbeddingsNvidia`, `NvidiaApi` credential.
The `NvidiaApi` credential takes exactly two fields:

| Field | Default |
|---|---|
| Base URL (`url`) | `https://integrate.api.nvidia.com/v1` |
| API Key (`apiKey`) | _(empty)_ |

Node default model: `nvidia/llama-3.3-nemotron-super-49b-v1`. The shipped model list
**already contains `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning`** — the Omni model
chosen for vision — plus `nvidia/nemotron-nano-12b-v2-vl` and `nvidia/nemotron-3-super-120b-a12b`.

**Present and confirmed:** `EmbeddingsGoogleGemini`, `LMOpenHuggingFaceInference`,
`MemoryManager`, `MemoryBufferWindow`, `MemoryPostgresChat`, `OutputParserAutofixing`,
`RetrieverMultiQuery`, `RetrieverVectorStore`, `ToolWorkflow`, `VectorStoreWeaviate`,
`ModelSelector`, **`ToolSearXng`** (native SearXNG tool — pairs with the SearXNG
instance already standing).

### Weaviate — self-hosted, already running

Owner confirmed multiple instances; fleet scan located them (ionos: none, ovh1: none):

| Container | Version | HTTP | gRPC | Docker network |
|---|---|---|---|---|
| `weaviate-o97r85b7…` | 1.38.7 | `100.91.190.107:8081` | `:50051` | `o97r85b7…` |
| `weaviate-native-v1-v43tfq25…` | 1.38.7 | `100.91.190.107:8082` | `:50052` | `v43tfq25…` |
| `milvus-d725i1io…` | 3.0 | `:9091` | `:19530` | — |

All bound **tailnet-only** (`100.91.190.107`) — consistent with the no-public-Postgres/
no-public-data-service policy.

**Two gotchas found before they bit:**

1. Each Weaviate sits on **its own isolated Coolify network**; n8n is on `coolify`.
   There is **no container-name reachability** — the credential must use the tailnet
   host IP. Verified reachable from inside the n8n container: HTTP 8081/8082 → **200**,
   TCP 50051/50052 → **OPEN**.
2. `weaviate-native-v1` maps host `50052 → container 50051` while its own env sets
   `WEAVIATE_GRPC_PORT=50052`. That mapping is internally inconsistent.
   **Prefer `weaviate-o97r85b7…`** (clean `50051→50051`).

Both instances run `AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true` with **no API key set**.
Confirmed against `WeaviateApi.credentials.js`: the **API Key field is NOT `required`**,
while every `custom_connection_*` field **is**. So anonymous works with an empty key.

Credential values to enter (Connection Type = **Custom Connection**):

```
Weaviate Api Key            : (leave empty)
Custom Connection HTTP Host : 100.91.190.107
Custom Connection HTTP Port : 8081
Custom Connection HTTP Secure : false
Custom Connection gRPC Host : 100.91.190.107
Custom Connection gRPC Port : 50051
Custom Connection gRPC Secure : false
```

### Docs access

`n8n-docs` MCP server registered at **user scope** (`claude mcp add n8n-docs --scope user
--transport http https://docs.n8n.io/~gitbook/mcp`) — status **✔ Connected**.
Tools: `searchDocumentation`, `getPage`, `sendFeedback`.
