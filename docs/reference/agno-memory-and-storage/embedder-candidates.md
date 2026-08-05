> _Byline: Claude Code · Sonnet · 2026-07-11_

# Embedder candidates — kb_legal (legal-trained) and kb_timeline (multimodal)

Gates D-033 (collection-per-domain KBs: `kb_legal` / `kb_timeline` / `kb_code` / `kb_general`).
Milvus locks dims at collection creation, so this research must land before `kb_legal`/`kb_timeline`
collections exist. Baseline to beat: **bge-m3** (1024-d, symmetric, dense+sparse hybrid via
OpenRouter — the same lane D-031's real-sparse fix rides). A candidate that only nudges dense-only
quality up may still lose to bge-m3's hybrid recall — but see the Lane 1 finding below, which
complicates that assumption for the legal domain specifically.

## How to read the integration-effort column

Our embedding path today (`server/core/embedder.py`, `server/core/settings.py`) is agno's
`OpenAIEmbedder`/`openai_like` pointed at OpenRouter (symmetric models — bge-m3, codestral-embed) or
a custom `NimEmbedder` subclass for NVIDIA NIM's asymmetric query/passage split (overrides
`get_embedding`/`async_get_embedding` — the query-path methods PgVector/Milvus actually call at
search time — to inject `extra_body={"input_type": "query"}`, while the inherited document-path
methods keep `input_type="passage"` via base `request_params`). That subclass pattern generalizes to
**any** provider whose asymmetric switch is a per-call request param.

Checked what's already vendored in this repo's `.venv` (agno 2.6.13,
`agno/knowledge/embedder/`): agno ships **native** `VoyageAIEmbedder`, `CohereEmbedder`,
`GeminiEmbedder`, `JinaEmbedder`, `SentenceTransformerEmbedder` (local, CPU, sentence-transformers —
supports arbitrary local models including CLIP-family and takes a `prompt=` field for
instruction-style asymmetry), and `FastEmbedEmbedder` (local, ONNX-quantized, text-only). None of
the hosted-provider classes split query/document into two methods the way our `NimEmbedder` does —
`CohereEmbedder.input_type` and `GeminiEmbedder.task_type` are single dataclass fields applied to
every call — so **any** of them needs the same NimEmbedder-style subclass (override the query-path
methods only) to get correct asymmetric behavior once documents and queries are embedded
separately. Also: none of the native Voyage/Cohere/Gemini classes accept image input in their
`get_embedding` signature (`text: str`/`List[str]` only) — multimodal candidates from Lane 2 need a
thin custom subclass regardless of provider, or the SentenceTransformer path for local CLIP-family
models (which does accept arbitrary objects at runtime despite the narrow type hint).

Env keys already live in `server/core/settings.py`'s provider chain: `NVIDIA_API_KEY`,
`OPENROUTER_API_KEY`, `GOOGLE_API_KEY`. **Not** present: `VOYAGE_API_KEY`, `COHERE_API_KEY`,
an Isaacus key — any Voyage/Cohere/Isaacus candidate is a net-new secret plus a net-new SDK
dependency (`voyageai`, `cohere`, `isaacus` are all separate PyPI packages already vendored in
`.venv` for Voyage/Cohere but not Isaacus).

---

## Lane 1 — LEGAL-trained text embedders

**Headline finding, from the just-published Massive Legal Embedding Benchmark (MLEB — Isaacus,
Oct 2025, 10 expert-annotated datasets across US/UK/EU/Australia/Ireland/Singapore, arXiv
2510.19365): bge-m3 ranks 18th of 21 models at 69.44 NDCG@10 — a 16.6-point gap behind the
leader.** The "bge-m3 is often competitive on legal retrieval" prior floated in the task brief does
NOT hold on this benchmark. MTEB-general strength does not transfer: Gemini Embedding is #1 on MTEB
overall but only 7th on MLEB; Voyage 3.5 is 23rd on MTEB but 3rd on MLEB. Full top-of-leaderboard
(NDCG@10):

| Rank | Model | NDCG@10 | Legal-specific training? |
|---|---|---|---|
| 1 | **Kanon 2 Embedder** (Isaacus) | 86.03 | Yes |
| 2 | Voyage 3 Large | 85.71 | No (general, just very strong + recent) |
| 3 | Voyage 3.5 | 84.07 | No |
| 4 | Qwen3 Embedding 8B | 82.96 | No |
| 5 | Voyage 3.5 Lite | 82.41 | No |
| 6 | Qwen3 Embedding 4B | 81.96 | No |
| 7 | Gemini Embedding (001) | 80.90 | No |
| 8 | **Voyage Law 2** | 79.63 | Yes (2024-era) |
| 9 | OpenAI Text-Embedding-3-Large | 78.91 | No |
| 10 | Jina Embeddings v4 | 78.62 | No |
| ... | | | |
| 18 | **BGE-M3** | 69.44 | No |

**Second surprise**: `voyage-law-2` — Voyage's dedicated legal model, trained on 1T legal tokens,
still the model most people reach for when someone says "legal embedder" — ranks *below* three
general-purpose models released after it (Voyage 3 Large/3.5/3.5 Lite) and *below* the open-weight
Qwen3-Embedding-8B/4B. Domain-specific training from 2024 has been overtaken by scale + recency in
general models. Old domain fine-tunes have a shelf life; check the leaderboard date, not just the
model name, before trusting a "legal-trained" label.

### Candidates evaluated

**1. Kanon 2 Embedder (Isaacus)** — #1 on MLEB, purpose-built legal model.
- Dims: 1,792 default/max; **Matryoshka-aware**, truncatable to 1024/768/512/256 (stays #1 at 768).
- Symmetric/asymmetric: **asymmetric via `task` param** (`"retrieval/document"` vs
  `"retrieval/query"`) on the standard `/v1/embeddings`-shaped endpoint — same call-time mechanism
  as NIM's `input_type`, just a different field name.
- Context length: 16,384 tokens (handles full-length legal filings/opinions without chunking as
  aggressively as bge-m3's shorter window forces).
- Availability: Isaacus direct API only (`api.isaacus.com`), or AWS Marketplace / SageMaker for a
  fully air-gapped deploy (no data leaves the AWS account) — **not on OpenRouter, not on NIM**.
- Price: $0.35/M tokens via Isaacus API.
- Local-CPU: not open-weight — API-only or AWS-hosted, no local-CPU path.
- Integration effort: **new provider**. The REST shape is OpenAI-embeddings-compatible enough that
  `OpenAIEmbedder(base_url="https://api.isaacus.com/v1", ...)` might work directly with `task` passed
  via `extra_body` (worth a 10-minute smoke test before reaching for the `isaacus-python` SDK); if
  that fails, a `KanonEmbedder(OpenAIEmbedder)` subclass mirroring `NimEmbedder`'s pattern (override
  `get_embedding`/`async_get_embedding` for the query-path `task="retrieval/query"`) is the fallback
  — same shape of work as the existing NIM subclass, roughly an hour.
- Gotchas: brand-new company/benchmark (both from the same vendor — Isaacus publishes MLEB AND wins
  it, so treat the #1 ranking as vendor-reported until an independent eval confirms it); no Milvus
  hybrid/sparse story (pure dense) — loses bge-m3's sparse lane entirely unless paired with a
  separate sparse signal; new API key + new secret to provision; jurisdiction coverage in MLEB
  leans US/UK/EU/AU/IE/SG — verify it has meaningfully more Michigan/US-family-law-specific training
  signal than a strong generalist before trusting the domain claim for *this* case's document mix
  (family law / custody, not commercial contracts or case law research, which is MLEB's actual
  distribution).

**2. Voyage Law 2 (Voyage AI)** — the "obvious" pick, now 8th on MLEB.
- Dims: not explicitly published in the docs surfaced (Voyage's other 2024-era models default to
  1024); no Matryoshka support documented for this specific (older) model.
- Symmetric/asymmetric: **asymmetric via `input_type="query"|"document"`** — Voyage auto-prepends a
  fixed instruction string per type ("Represent the query for retrieving supporting documents: " /
  "Represent the document for retrieval: "). Confirmed compatible with embeddings generated without
  the param (safe to backfill later).
- Context length: 16,000 tokens.
- Availability: Voyage direct API only — **not on OpenRouter** (OpenRouter's embedding collection
  lists Voyage 4 family generally but not this specific legacy model as of this check).
- Price: $0.12/M tokens; first 50M tokens free per account.
- Local-CPU: no, API-only.
- Integration effort: agno ships **`VoyageAIEmbedder`** natively already (`.venv` confirmed) — but
  it applies one fixed `request_params` to every call, so correct query/document asymmetry still
  needs a `NimEmbedder`-shaped subclass overriding the query-path methods to swap `input_type`.
  Needs `VOYAGE_API_KEY` (new secret) — `voyageai` package is already vendored.
- Gotchas: rank-8 on the newest independent legal benchmark despite the "law" name — pay the
  legal-specialization premium and price only if a same-vendor newer general model (Voyage 3
  Large/3.5, ranked #2/#3) doesn't already beat it, which per MLEB it does.

**3. Voyage 3 Large (general, not legal-branded, but #2 on MLEB)** — worth a line because it beats
every legal-labeled model except Kanon 2.
- Dims: configurable, Matryoshka down to 256 (2048 max, per Voyage's newer-generation docs).
- Symmetric/asymmetric: same `input_type` mechanism as voyage-law-2.
- Availability/price: Voyage direct, same $0.12/M pricing tier family; not confirmed on OpenRouter.
- Integration effort: same as voyage-law-2 (native `VoyageAIEmbedder` + subclass for correct
  asymmetry).
- Takeaway: if Voyage is in play at all, benchmark this before the "legal" model — it's cheaper to
  reason about (one embedder for kb_legal AND kb_general lanes, if the general lane ever needed an
  upgrade off bge-m3) and currently outperforms the domain-branded option.

**4. Qwen3-Embedding (8B / 4B / 0.6B, Alibaba, open-weight)** — best open-weight legal showing (4th
and 6th on MLEB for the 8B/4B variants) and the only Lane-1 candidate with a real CPU path.
- Dims: MRL/Matryoshka, truncatable e.g. 32–1024 for the 0.6B variant (larger variants scale
  higher, exact ceiling model-size-dependent).
- Symmetric/asymmetric: **instruct-prefix, not a request param** — an instruction string is
  prepended to queries only (no prefix on documents); Qwen's own docs note skipping the query
  instruction costs ~1-5% retrieval quality. This is a **prompt-template mechanism, not an
  `input_type` field** — zero code changes beyond templating the query string differently from the
  document string before calling `.encode()`/the API.
- Context length: up to 32K tokens.
- Availability: **on OpenRouter** (8B and 4B listed, flagged legal #10 in OpenRouter's own
  collection ranking) — no new secret needed, rides the existing `OPENROUTER_API_KEY`. Also
  fully open-weight (Apache-licensed) with a GGUF-quantized 0.6B build for **local CPU** via
  llama.cpp.
- Price: OpenRouter token pricing (typically cents/M for open-weight embedders) or free if
  self-hosted.
- Local-CPU: **yes** — the 0.6B GGUF variant is the one Lane-1 candidate that's realistically CPU-
  viable on this box's no-GPU constraint, at a real quality cost (0.6B ranks 11th on MLEB, 77.13,
  still ahead of bge-m3).
- Integration effort: OpenRouter path = same as bge-m3 today (`OpenAIEmbedder(base_url=openrouter)`,
  zero new code, just prepend the instruction string to queries at call time in the ingestion/
  retrieval code, not in the embedder class). Local path = agno's `SentenceTransformerEmbedder`
  natively, pointed at the GGUF/HF model id, `prompt=` field carries the instruction.
- Gotchas: not legal-specific at all — it's a strong generalist that happens to rank well on MLEB;
  same caveat as Voyage 3 Large above (base rate: recent, large, well-trained generalists are
  closing the gap with — and beating — 2024-era domain fine-tunes).

**5. bge-m3 (baseline, already live)** — for completeness/honesty per the task brief.
- 1024-d, symmetric, dense+sparse hybrid, live via OpenRouter today, zero integration cost (it's
  the existing lane).
- MLEB: 69.44 NDCG@10, rank 18/21 — a real, measured 16-17 point gap below the top legal-specialized
  and top general-recent models. This is NOT "competitive" on this benchmark, contrary to the
  general reputation bge-m3 has from MTEB. Its saving grace remains the **native sparse lane**
  (D-031's hybrid fix), which none of the Lane-1 legal candidates above replicate — a hybrid
  bge-m3 search may still out-recall a dense-only Kanon 2/Voyage search on short exact-phrase/
  citation-style legal queries even though its dense-only NDCG is lower. This is exactly the
  "hybrid may beat a dense-only winner" scenario the task brief flagged — worth testing, not
  assuming either way.

**6. NIM/NeMo Retriever legal-specific model** — checked, **doesn't exist**. NVIDIA's NeMo Retriever
NIM catalog (llama-3.2-nv-embedqa-1b-v2, nv-embedqa-e5-v5 — the latter deprecating Nov 2026) is
domain-*customizable* (fine-tune your own) but ships no pre-trained legal variant. Not a real Lane-1
candidate as-is; only relevant if a from-scratch NIM fine-tune were in scope, which it isn't for a
half-day bench.

**7. Legal-BERT-family (local, CPU)** — `nlpaueb/legal-bert-base-uncased` and similar, trained on
the Harvard Law case corpus (3.4M decisions).
- Dims: 768 (standard BERT-base).
- Symmetric, no query/doc split, no Matryoshka.
- Local-CPU: yes, trivially — it's a 110M-parameter BERT, the most CPU-friendly option in either
  lane by far.
- Integration effort: agno's `SentenceTransformerEmbedder` natively (point `id` at the HF model).
- Gotchas: this is a **2020-era encoder** with no retrieval-specific contrastive training (it's a
  masked-LM checkpoint, not a sentence-embedding model) — expect it to badly underperform every
  model above on retrieval NDCG; useful only as a zero-cost, zero-dependency CPU fallback if API
  access is ever unavailable, not as a quality contender. Not benchmarked on MLEB (predates it).

---

## Lane 2 — MULTIMODAL embedders (timeline: text + photos/media)

Hard constraint restated: timeline text (messages, records, notes) and photo/media content need to
land in **one vector space** for cross-modal search ("find photos near this date/event" /
"find messages about this photo") — ruling out any "separate CLIP index + separate text index,
fuse at query time" design unless that's an explicit fallback, since D-033 calls for one
`kb_timeline` collection with one embedder.

**1. Gemini Embedding 2 (Google, `gemini-embedding-2-preview`)** — natively multimodal, unifies
text/image/video/audio/PDF in one space; the strongest "single model, one vector space" fit.
- Dims: 3,072 max, **flexible 128–3,072** (Matryoshka-style truncation supported, per OpenRouter's
  listing and Google's docs).
- Symmetric/asymmetric: **this is a real gotcha** — for the *predecessor* `gemini-embedding-001`
  (text-only, GA), `task_type` (`RETRIEVAL_QUERY`/`RETRIEVAL_DOCUMENT`) is a real per-call param
  agno's native `GeminiEmbedder` already exposes as a dataclass field. For **Gemini Embedding 2**
  (the multimodal one, still `-preview` as of this check), Google has **deprecated `task_type` — the
  backend silently ignores it**, per a still-open llama-index GitHub issue (#21535) and Google's own
  guidance to "add the task instruction in your prompt" instead. So the asymmetric mechanism for the
  model this lane actually needs is **manual instruction-prefixing of the text content itself**, not
  a request param — functionally identical effort to Qwen3's prompt-template approach, just
  undocumented/surprising if you assume the old `task_type` field still works. No documented
  equivalent instruction mechanism exists yet for the image side of a query (i.e., "image-as-query"
  asymmetry) — treat image queries as symmetric until tested.
- Context length: 8,192 tokens (text side).
- Availability: **on OpenRouter** (confirmed, flagged multimodal) — rides `OPENROUTER_API_KEY`,
  zero new secret. Also available direct via `GOOGLE_API_KEY`, which is **already provisioned** in
  this project (used by the `document_digest` agent per `AGENTS.md`).
- Price: not confirmed in this pass (preview pricing not published in the sources found) — check
  before committing.
- Local-CPU: no, API-only, and it's Google's largest embedding model — no local path exists.
- Integration effort: agno's native `GeminiEmbedder` handles text; **image/video/audio input is not
  wired into agno's `GeminiEmbedder.get_embedding(text: str)` signature at all** — needs a small
  subclass adding a `contents` path that accepts `genai.types.Part`/inline image bytes instead of a
  bare string, plus manual instruction-prefixing since `task_type` is inert. Moderate effort, maybe
  2-4 hours including the subclass and prompt-template plumbing.
- Gotchas: still `-preview` (not GA) — check ToS/quota stability before betting a whole KB lane on
  it; owner floated "Gemini or Nemo," so this is one of the two options explicitly in scope; privacy
  note (not deciding, just flagging per the task brief) — Google API, same trust boundary as the
  `document_digest` agent already crosses.

**2. NVIDIA llama-nemotron-embed-vl-1b-v2 (NIM)** — smallest, cheapest, best integration fit; the
"Nemo" half of the owner's "Gemini or Nemo" framing.
- Dims: 2,048.
- Symmetric/asymmetric: **`input_type="query"|"passage"` + a separate `modality` field**
  (`"text"|"image"|"text_image"`, single value or per-item array for batches) — this is **the exact
  mechanism our `NimEmbedder` subclass already implements** for the text-only NIM lane
  (`server/core/embedder.py`). A `NemotronVLEmbedder(NimEmbedder)` subclass adding the `modality`
  field to the request dict is a very small diff on top of code that already exists and is already
  proven correct against agno 2.6.9's query-path/document-path method split. Note: query-side images
  are **not supported** ("input_type='query' is text-only") — image queries would need to go through
  the document/passage embedding path instead, a real design constraint for "search by example
  photo."
- Context length: 8,192 tokens; images up to 8192×16384px, <25MB, auto-resized.
- Availability: **on OpenRouter, currently flagged `:free`**, and natively on NIM via
  `NVIDIA_API_KEY` (already provisioned). Two independent paths to the same model, no new secret
  either way.
- Price: free tier on OpenRouter as of this check; NIM native pricing not confirmed but this
  project already has NIM credentials/usage patterns established.
- Local-CPU: no (1B-parameter VLM-based embedder, not CPU-realistic), but the API-cost story is the
  best of any Lane-2 candidate (free tier).
- Integration effort: **lowest of any Lane-2 candidate** — extends code that already exists and is
  already battle-tested in this repo, same provider (NVIDIA) already in the model chain.
- Gotchas: 1B-parameter model — likely weaker absolute retrieval quality than Gemini Embedding 2 or
  Cohere Embed v4 on hard cross-modal queries (no independent benchmark found in this pass comparing
  it against those); "free" OpenRouter tier may have rate limits worth checking before bulk-
  indexing a large Takeout photo corpus; 8,192-token context is tighter than Gemini's if timeline
  entries carry long text.

**3. Cohere Embed v4** — multimodal, interleaved text+image, most flexible dims.
- Dims: **Matryoshka**, configurable [256, 512, 1024, 1536] plus multiple quantization formats
  (float/int8/uint8/binary/ubinary) for storage compression.
- Symmetric/asymmetric: `input_type` param (`search_document`/`search_query`/`classification`/
  `clustering`) — same shape of mechanism as bge-m3's Cohere-family sibling. Required for embed
  models v3+.
- Context length: not confirmed in this pass for the multimodal path specifically.
- Availability: **not on OpenRouter** — Cohere direct API, AWS Bedrock, Azure AI Foundry, or OCI.
- Price: $0.12/M text tokens, $0.47/M image tokens.
- Local-CPU: no.
- Integration effort: agno ships native `CohereEmbedder`, but (a) its `response()` method only
  passes `texts=[text]` — no image parameter exists in agno's wrapper today, so multimodal input
  needs a subclass adding an image-capable request path, and (b) the single `input_type` field
  needs the same NimEmbedder-style query/document split. Needs new `COHERE_API_KEY` secret (package
  already vendored). Moderate-to-high effort — the most code of any Lane-2 candidate given agno's
  current Cohere wrapper doesn't touch images at all.
- Gotchas: not currently in the provider chain at all (new vendor relationship); best fit if the
  Matryoshka dim flexibility + quantization matters more than raw integration speed.

**4. voyage-multimodal-3** — interleaved text+image, PDF/slide/table-aware.
- Dims: 1024 default, configurable [256, 512, 1024, 2048].
- Symmetric/asymmetric: same `input_type` mechanism as Voyage's text models.
- Availability: Voyage direct API only, not on OpenRouter.
- Price: $0.12/M input tokens; image cost $0.00003–$0.0012/image depending on resolution (images
  <50K px upscaled and billed as 50K px); first 200M text tokens + 150B pixels free per account.
- Local-CPU: no.
- Integration effort: agno's native `VoyageAIEmbedder.embed()` call only takes `texts=[...]` —
  Voyage's multimodal endpoint is a **separate API method** (`multimodal_embed`, not `embed`), so
  this needs its own subclass regardless of the text-only wrapper already present. Similar
  effort class to Cohere Embed v4.
- Gotchas: strong PDF/slide/table story is more "document layout" than "personal photo/timeline" —
  may be optimized for a different content mix than a Takeout photo+text corpus; new secret needed
  (shared with any Lane-1 Voyage choice, which is a mild point in its favor if Voyage ends up
  serving both lanes).

**5. jina-clip-v2 (open-weight, local-CPU-capable)** — the one Lane-2 candidate with a real local
path, and the smallest.
- Dims: 1024 default, **Matryoshka down to 64**.
- Symmetric (CLIP-style contrastive — no query/document distinction; both text and image encode
  through the same untyped forward pass).
- Multilingual (89 languages), 512×512 image resolution.
- Architecture: 865M params total (561M text tower + 304M vision tower) — heavy for "CPU-viable" but
  lighter than jina-embeddings-v4 or the Gemini/Cohere API giants.
- Availability: open weights (Hugging Face/GitHub), Jina AI hosted API, or Replicate; not seen on
  OpenRouter.
- Price: free if self-hosted; Jina API has its own pricing (not confirmed this pass).
- Local-CPU: yes, but 865M params on CPU-only hardware will be slow for bulk indexing a large photo
  corpus (ONNX export can help — SigLIP2/JinaCLIP ONNX conversions reportedly cut latency 20-40% on
  modern hardware, but that's benchmarked on Ampere/Hopper GPUs, not CPU; expect materially slower
  on this box's no-GPU constraint — budget for an overnight/background bulk-index job, not
  interactive).
- Integration effort: agno's `SentenceTransformerEmbedder` supports CLIP-family models natively via
  `sentence-transformers`' own CLIP support (which does accept PIL Images despite the wrapper's
  `text: Union[str, List[str]]` type hint — Python won't stop you) — cheapest Lane-2 local option,
  but likely needs a thin subclass to make the image path explicit/typed rather than relying on duck
  typing through an annotation that says "text."
- Gotchas: the one candidate that's genuinely privacy-preserving (no case content leaves the box) —
  matters if the owner's privacy weighting (flagged, not decided, per task brief) favors local for
  timeline/photo content specifically. Retrieval quality on personal-photo-style content (vs. the
  captioned/web-image data most CLIP-family benchmarks measure) is unverified — this is exactly what
  the half-day bench should test.

**6. jina-embeddings-v4** (mention, not a full profile) — larger (3.8B params) unified text+image
model with task-specific LoRA adapters (retrieval/text-matching/code), asymmetric via `prompt_name`
distinguishing query vs. passage. Ranks 10th on MLEB as a side-benefit if ever reused for Lane 1.
Too large for realistic CPU deployment on this hardware; would be an API-only choice (Jina's hosted
API), and at that point Gemini Embedding 2/Cohere Embed v4/nemotron-embed-vl are likely stronger
multimodal options at similar-or-lower integration cost. Included for completeness since it appeared
repeatedly in both lanes' research.

**7. Open CLIP / SigLIP2 (bare, no agno wrapper)** — considered and set aside. Standalone
CLIP/SigLIP2 checkpoints are vision-tower-only (or vision+short-text) contrastive encoders without
the long-form text handling a timeline needs for message/document content — they're normally paired
with a separate text tower (which is exactly what jina-clip-v2 already packages). Using bare
SigLIP2 would mean building the "one unified space" integration ourselves; jina-clip-v2 is strictly
less work for the same underlying idea. Not carried forward as an independent candidate.

---

## Shortlist recommendations

**Lane 1 (legal) — two finalists:**
1. **Kanon 2 Embedder (Isaacus)** — if the half-day bench confirms the MLEB #1 ranking holds on
   *this* case's actual document mix (family-law filings/orders/correspondence, not MLEB's
   commercial-contract/case-law skew), and the vendor-reports-its-own-benchmark caveat doesn't spook
   the owner. Best quality signal found, worst provider diversification (new vendor, dense-only, no
   sparse-hybrid fallback).
2. **Voyage 3 Large** (not voyage-law-2) — if quality parity with Kanon 2 is good enough (85.71 vs
   86.03 NDCG@10 is close) and the owner prefers not adding an unfamiliar/new vendor (Isaacus) for
   one KB lane; also gives an option to eventually use the same Voyage account for
   voyage-multimodal-3 in Lane 2, consolidating to one new vendor relationship instead of two.
   Runner-up: **Qwen3-Embedding-8B** if avoiding new vendor keys/secrets entirely matters more than
   the last few NDCG points — it's on OpenRouter today, zero new secrets, and still beats bge-m3 by
   ~13 points on MLEB.

**Lane 2 (multimodal) — two finalists:**
1. **NVIDIA llama-nemotron-embed-vl-1b-v2** — lowest integration cost by a wide margin (extends the
   `NimEmbedder` subclass that already exists and is already correct), free OpenRouter tier, no new
   secrets, satisfies the owner's "Nemo" option directly. Main risk: unverified absolute quality
   against the bigger multimodal models, and no image-as-query support (would need same-modality
   passage-path workaround for "search by example photo").
2. **Gemini Embedding 2** — satisfies the owner's "Gemini" option directly, natively multimodal
   across the widest modality set (text/image/video/audio/PDF — useful if Takeout media ever
   includes video), already has a live API key in this project. Main costs: still preview/not-GA,
   `task_type` deprecation means asymmetry has to be hand-rolled via prompt prefixing, and agno's
   native wrapper needs a real subclass to accept image input at all (more code than the NIM path).

### Half-day bench design (both lanes, same shape)

**Sample corpus per lane:**
- Lane 1 (legal): pull ~150-300 chunks from actual case documents already in the platform — mix of
  filing/motion text, court order language, correspondence with counsel, and at least one long
  document to test the 16K-token-context candidates' advantage over bge-m3's shorter window. Keep a
  held-out slice never seen by anyone tuning gold queries.
- Lane 2 (timeline): pull ~150-300 items from the Google Takeout corpus already inventoried
  (`Takeout Timeline` per the memory index) — mix of photos with EXIF/JSON sidecar metadata, plain
  text/message entries, and a few date-adjacent photo+text pairs specifically chosen to test
  cross-modal retrieval (the reason this lane needs one vector space at all).

**Gold queries:** 15-25 hand-written queries per lane, each with a manually-verified relevant-item
set (not just "the first result that looks right" — actually read the corpus and confirm). Lane 1
queries should include at least a few exact-citation/phrase-style queries specifically because
that's where bge-m3's sparse/hybrid lane is expected to still win even if its dense NDCG loses.
Lane 2 queries should include both same-modality (text query → text result, image query → image
result) and cross-modal (text query → photo result, e.g. "photos from [event]") pairs.

**Metrics:** recall@5 and MRR per candidate, compared against the bge-m3 baseline run through the
same gold set (bge-m3 as dense-only AND as full hybrid, to isolate how much of its baseline strength
is the sparse lane specifically — directly answers the task brief's "may still lose to bge-m3's
hybrid" question rather than assuming it). Report per-query-type breakdowns (exact-phrase vs.
semantic vs. cross-modal) since the aggregate number can hide exactly the failure mode each lane
cares about.

**Mechanics:** one Milvus scratch collection per candidate (dims vary — can't share a collection
across candidates), embed the same corpus + query set through each, no reranker in this pass (keep
it apples-to-apples against the current no-reranker baseline), half a day is enough for the 2
finalists per lane (4 candidate runs total) plus the bge-m3 baseline — not enough to re-run all 7-13
candidates surveyed above.

---

## Is specialization worth it?

**Lane 1 (legal):** Yes, but the *how* matters more than the brief assumed. The data says
domain-specific training is real and measurable (Kanon 2's 16-point NDCG lead over bge-m3 on MLEB is
not noise), but "specialization" turned out to mean "a newer/larger general model" almost as often
as it meant "a model actually fine-tuned on legal text" — voyage-law-2, the most legal-branded
option evaluated, lost to three general Voyage models released after it. The actionable takeaway
isn't "always pick the domain label," it's "check a recent, honest, domain-specific benchmark (MLEB,
not a vendor's own blog post) before trusting a domain label at all" — which is exactly why this
research existed as an explicit gate rather than a rubber-stamp on "legal-trained embedder,
obviously." The remaining open question the half-day bench should resolve is narrower than "is
specialization worth it" — it's "does Kanon 2's edge survive contact with family-law content
specifically, given MLEB skews toward commercial/case-law text," and "does losing bge-m3's sparse
lane cost more than the dense-quality gain buys back."

**Lane 2 (multimodal):** Different question entirely, because this isn't really about
"specialization" the way Lane 1 is — bge-m3 has **no multimodal capability at all**, so there's no
generalist baseline to specialize away from; every real candidate here is multimodal by necessity,
not by choice. The actual decision is between three genuinely different architectures: a NIM-hosted
1B VLM-embedder (cheap, fast to integrate, unverified ceiling), a frontier lab's largest embedding
model (Gemini Embedding 2 — highest modality breadth, real integration + stability cost from being
preview-stage), and a locally-runnable open-weight CLIP-family model (jina-clip-v2 — the only
privacy-preserving option, real CPU-throughput cost on this hardware). None of the three has
independent cross-modal benchmark evidence for personal-photo-style content in the research surfaced
here (all the benchmark data found — MTEB, MLEB, CLIP-family papers — measures web/captioned-image
or legal-text distributions, not "a decade of a family's Google Photos + text messages"). This lane
is genuinely un-derisked without the half-day bench; recommend running it before locking dims, more
so than Lane 1 where the benchmark evidence is already fairly strong.
