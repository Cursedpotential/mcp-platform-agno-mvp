# Stage 2 — Discovery: ranked n8n candidates per shape

> _Byline: stage-2 discover agents (3 search branches) · Sonnet · compiled by Claude Code · Fable 5 · 2026-08-24_
> Method per `docs/plans/N8N-BUILDER-AGENT-GUIDE.md`: every candidate was FETCHED and verified to
> contain real workflow JSON / node config / installable code before listing. Preference order on
> ties: native > community npm > raw GitHub. Target instance: n8n 2.36.6 self-hosted (lane-6 audit).

## Shape 1 — Trigger / custody handoff

| Rank | Candidate | Shelf | Source | Why | Verified |
|---|---|---|---|---|---|
| 1 | Local File Trigger → HTTP Request combo | native | docs.n8n.io …/n8n-nodes-base.localfiletrigger + …/httprequest | Exact fit: drop-folder watch (add/change events, ignore patterns, depth) → POST JSON or binary to the platform custody door, parse returned record IDs | Both doc pages fetched; full param lists confirmed. Local File Trigger is disabled by default since 2.0, self-hosted only — matches us |
| 2 | "Monitor Dropbox folders for new files with DB comparison" | template | n8n.io/workflows/3297 | THE list→diff→dedupe→sub-workflow skeleton for storage n8n can't watch natively (adapt: S3 getAll against the R2 mount + PG seen-table) | Page fetched; real node sequence + field names (id, contentHash, pathDisplay) confirmed |
| 3 | "Organise your local file directories with AI" | template | n8n.io/workflows/2334 | Working Local File Trigger → downstream scaffold (downstream step swapped for our HTTP handoff) | Page fetched; node sequence confirmed; needs bind-mount config |

**Checked and confirmed ABSENT:** no `s3Trigger` node exists anywhere (native or community) — bucket intake is schedule + list + diff, full stop.
**Top pick:** #1 for the drop-dir; #2's pattern for bucket polling.

## Shape 2 — Semantic chunking

| Rank | Candidate | Shelf | Source | Why | Verified |
|---|---|---|---|---|---|
| 1 | Recursive Character Text Splitter | native | docs.n8n.io …/textsplitterrecursivecharactertextsplitter | Recommended default; keeps paragraph/sentence boundaries; metadata passthrough via Default Data Loader | Doc fetched (Chunk Size/Overlap params; caveat: metadata splits too if not separated upstream) |
| 2 | @bitovi/n8n-nodes-semantic-text-splitter | npm | npmjs.com/@bitovi/n8n-nodes-semantic-text-splitter | TRUE embedding-based semantic chunking (double-pass merging) | Raw npm registry JSON fetched — real installable community node, active maintainers |
| 3 | danblah/n8n-nodes-semantic-text-splitter | github | github.com/danblah/n8n-nodes-semantic-text-splitter | Same concept, richer documented params (breakpoint threshold types) | Raw README fetched; **gap: does not state whether arbitrary chunk metadata (timestamps/speakers) survives — test before adopting** |
| 4 | Token Splitter | native | n8n docs (same family) | Fallback when token budget outranks semantics | Existence confirmed via node search |

**Critical negative finding:** chat-transcript chunking that preserves timestamps/speaker/message
boundaries has NO community solution — the best forum thread ends unresolved with "chunk outside
n8n." **Conversation chunking therefore stays platform-side (our in-code chunker), exactly the
D-068 boundary.** n8n-side chunking applies to loose documents only.

## Shape 3 — Classify / tag / summarize per chunk (schema-enforced, batched)

| Rank | Candidate | Shelf | Source | Why | Verified |
|---|---|---|---|---|---|
| 1 | Information Extractor + Structured Output Parser | native | `@n8n/n8n-nodes-langchain.informationExtractor` v1.2 + `.outputParserStructured` v1.3 | Purpose-built schema-enforced extraction; 3 schema modes incl. real JSON Schema | Confirmed live on OUR instance via node search + full docs fetched |
| 2 | Text Classifier | native | `@n8n/n8n-nodes-langchain.textClassifier` v1.1 | One output branch per category — discrete tagging | Confirmed live on our instance |
| 3 | "Smart Gmail Labeling…Text Classifier" | template | n8n.io/workflows/7633 | Proven Loop Over Items → Text Classifier → action batch pattern | Page fetched; node list confirmed |
| 4 | awesome-n8n-templates repo | github | github.com/enescingoz/awesome-n8n-templates | 280+ real downloadable .json workflows incl. LLM extraction/classification folder — mining ground | Fetched; real .json files per folder, not a listicle |

Also confirmed: `splitInBatches` (Loop Over Items v3) native, with documented loop-back wiring; Basic LLM Chain + Structured Output Parser as general fallback.
**Top pick:** Information Extractor inside Loop Over Items; Text Classifier for discrete tags.

## Shape 4 — Verification / confidence gate (owner-added)

Honest finding: the THINNEST shelf — no polished classify→judge→gate template exists end-to-end.

| Rank | Candidate | Shelf | Source | Why | Verified |
|---|---|---|---|---|---|
| 1 | Guardrails node (Custom LLM check) | native | `@n8n/n8n-nodes-langchain.guardrails` | Real confidence-gate primitive: custom prompt + 0.0–1.0 threshold + native Fail branch | Full docs fetched; threshold/custom/fail-branch confirmed |
| 2 | Evaluation node, Correctness (AI-judge) metric | native | docs.n8n.io …/n8n-nodes-base.evaluation | n8n's official LLM-as-judge — built for offline eval; usable inline only as a per-chunk sub-workflow | Docs + release notes confirmed |
| 3 | "Classify documents and score confidence" | template | n8n.io/workflows/15229 | Proven confidence-then-branch: extractor emits confidence_score, IF routes <0.5 to human review | Page fetched; IF-condition + field names confirmed |
| 4 | "OpenRouter council" multi-model consensus | template | n8n.io/workflows/12316 | N models answer independently → mutual ranking → chairman verdict — the multi-LLM-review half | Page fetched; structure confirmed |

**Top pick (composite):** judge-LLM (Basic LLM Chain) → Structured Output Parser emitting `confidence` → IF gate — borrowing #3's threshold routing and #1's mechanics; #4's council pattern reserved for high-stakes chunks.

## Shape 5 — LLM routing via Portkey

| Rank | Candidate | Shelf | Source | Why | Verified |
|---|---|---|---|---|---|
| 1 | Native OpenAI Chat Model node → Portkey base URL (official Portkey n8n guide) | native + vendor doc | portkey.ai/docs/integrations/libraries/n8n | No dedicated node needed: point the built-in OpenAI Chat Model credential at the Portkey gateway base URL (for us: OUR self-hosted gateway, not api.portkey.ai). Satisfies the native-first tier by using n8n's own node | Fetched; exact credential fields + provider-slug + `override_params` config JSON confirmed |
| 2 | Portkey Config Object — `loadbalance` strategy | vendor doc | portkey.ai/docs/api-reference/inference-api/config-object | THE rotation mechanism per Interview A: one n8n call, gateway rotates the pool (NIM, Gemini ×4 keys, OpenRouter free, Ollama) with per-target weights | Fetched; real JSON shape confirmed (`strategy.mode=loadbalance`, targets with weight/virtual_key/override_params) |
| 3 | n8n community thread (Portkey team member) | forum | community.n8n.io/t/76909 | Confirms state of the world: NO Portkey node exists; base-URL override is the sanctioned path; harmless "can't validate against OpenAI" credential warnings are expected | Fetched |
| ✗ | @port-labs/n8n-nodes-portio-experimental | npm (RULED OUT) | npmjs.com | **False positive — Port.io (dev portal), NOT Portkey.** Name collision only | Fetched + excluded |

**npm searched directly: no `n8n-nodes-portkey` package exists.**
**Top pick:** native chat-model node → our self-hosted Portkey gateway with a loadbalance config per model tier.

## Shape 6 — Rate-limit / quota tracking (owner reframe: quotas, NOT dollars)

| Rank | Candidate | Shelf | Source | Why | Verified |
|---|---|---|---|---|---|
| 1 | Portkey per-provider rate limits | vendor feature (the gateway we already route through) | portkey.ai/docs/product/ai-gateway/virtual-keys/rate-limits | Enforce per-provider/per-account caps (per minute/hour/day, request- OR token-based) at the gateway — no n8n counter infrastructure at all. **Caveat: a limit can't be edited once set — duplicate the provider to change it** | Fetched; intervals, rejection error, auto-reset confirmed |
| 2 | Native node knobs: Retry On Fail + Wait Between Tries; HTTP Request Batching (items/batch + interval) | native | docs.n8n.io/integrations/builtin/handle-rate-limits/ | Zero-infra pacing + backoff on every call site | Fetched; exact settings confirmed |
| 3 | Redis rate-limit template (increment→threshold→gate) | template | n8n.io/workflows/1236 | The counter-ledger pattern if per-account visibility is wanted — same shape drops onto native Postgres instead of Redis | Raw template JSON fetched via api.n8n.io; nodes confirmed |
| 4 | Advanced retry/delay template (custom exponential backoff) | template | n8n.io/workflows/5447 | Beats the built-in 5-retry cap; the retry layer behind whichever counter gates the call | Raw JSON fetched; max_tries/delay-doubling loop confirmed |

**Top pick:** Portkey-native limits as the enforcement point; native retry/batching knobs at call sites; the PG-counter ledger only if the owner wants usage visibility beyond enforcement.

## Shape 7 — Output / persistence + error handling

| Rank | Candidate | Shelf | Source | Why | Verified |
|---|---|---|---|---|---|
| 1 | Postgres node — Execute Query + Query Parameters | native | docs.n8n.io …/n8n-nodes-base.postgres | THE injection-safe write: `$1,$2` tokens + sanitized parameter list (never string-built SQL) | Doc fetched; worked example + sanitization statement confirmed |
| 2 | Error Trigger + workflow-level Error Workflow setting | native | docs.n8n.io …/n8n-nodes-base.errortrigger + handle-errors guide | One shared error-handler workflow for ALL parents; standard failure payload (message/stack/workflow/execution URL) | Both docs fetched; payload + wiring confirmed |
| 3 | "Slack alert when a workflow went wrong" | template | n8n.io/workflows/1326 | Minimal 2-node importable skeleton of exactly that pattern | Raw template JSON fetched via api.n8n.io; both nodes + expressions confirmed |
| ⚠ | "Maintain RAG embeddings…auto drift rollback" | template (ANTI-EXAMPLE) | n8n.io/workflows/14036 | 41 nodes, string-built SQL in all 6 Postgres nodes, ZERO error handling — documented as what NOT to copy; its golden-question drift-gate logic is still worth mining for Shape 4 ideas | Full JSON fetched; all 41 nodes enumerated |

**Top pick:** natives #1 + #2, with #3 as the alert skeleton.

## Cross-shape finds

- **Dropbox DB-comparison template (3297)** — the reusable idempotent poll-intake skeleton for ANY list-based source (R2, sister-project exports).
- **"Sitemap crawling to vector storage" (8707, 28 nodes, JSON verified)** — full trigger→chunk→embed→insert→status chain worth cannibalizing wholesale (swap embeddings to Portkey, Supabase writes to Postgres).
- **n8n Evaluations feature** (docs.n8n.io/advanced-ai/evaluations) — native judge pipeline to study when building the Shape-4 gate.
- Unverified leads (flagged, NOT candidates): RAG Starter Template 5010, Context-Aware Chunking 2871.

## Owner-sourced npm leads (tab export, 2026-08-24 — NOT yet verified; verify at Extract)

The owner's own npm research session surfaced ~120 community packages. Standouts mapped to shapes
(all UNVERIFIED — Extract stage must fetch each package and confirm real, maintained, installable
before adoption):

| Package | Maps to | Why it matters here |
|---|---|---|
| `n8n-nodes-nvidia-nim` | Shape 5 | A dedicated NIM chat node — our primary free provider, first-class |
| `n8n-nodes-roundrobin` | Shape 5 | A literal round-robin node — fallback if Portkey-side rotation ever doesn't fit |
| `n8n-nodes-multi-model` / `n8n-nodes-universal-chatmodel` / `n8n-nodes-openrouter-*` family | Shape 5 | Multi-model + OpenRouter-specific chat nodes (several variants — pick ONE if any) |
| `n8n-nodes-semantic-splitter-with-context` | Shape 2 | A THIRD semantic splitter — "with context" suggests metadata/context preservation, the exact gap flagged on the other two |
| `n8n-nodes-ollama-reranker` | Retrieval stack | Reranker node backed by Ollama — the rerank hook on the Weaviate node needs a reranker; this could be the free local one |
| `n8n-nodes-cognee` | Agent-memory bake-off (TODO-211) | Community node for Cognee — the bake-off frontrunner gets an n8n door for free |
| `n8n-nodes-tesseractjs(7)` | Doc/OCR lane | Tesseract OCR node — matches the standing "Tesseract is the free local OCR tier" routing rule |
| `n8n-nodes-exif-data` | Evidence media | EXIF extraction — media metadata (timestamps, GPS!) for the media evidence lane |
| `n8n-nodes-zip` | Shape 1 | Archive handling at intake (chat exports arrive as ZIPs) |
| `n8n-nodes-pdf-extractor` / `@custom-js/n8n-nodes-pdf-toolkit(-v2)` / `@mazix/n8n-nodes-converter-documents` / `n8n-nodes-document-embedding` | Doc lane | Document parsing/conversion/embedding shelf |
| `@langfuse/n8n-nodes-langfuse` / `n8n-nodes-openai-langfuse` | Observability | LLM tracing for the n8n-side calls |
| `n8n-nodes-mcp` / `n8n-nodes-a2a` | Agent plumbing | MCP client + agent-to-agent protocol nodes |
| `n8n-nodes-smb2` / `n8n-nodes-sqlite3` / `n8n-nodes-milvus-db` | Misc integrations | File-share intake; sqlite; Milvus (NOTE: Milvus is deliberately DOWN — do not wire) |

Also noted from the same session: the free registered-community license key email (unlocks
selected paid features — folders etc.); worth activating on the instance.
