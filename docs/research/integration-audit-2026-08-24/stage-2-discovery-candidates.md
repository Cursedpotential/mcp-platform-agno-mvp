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

## Shape 5 — LLM routing via Portkey — see addendum below
## Shape 6 — Rate-limit / quota tracking — see addendum below

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
