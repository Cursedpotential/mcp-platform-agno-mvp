# n8n Builder-Agent Guide (owner-supplied methodology)

> _Byline: owner-authored process, recorded verbatim-in-substance by Claude Code · Fable 5 · 2026-08-24_
> Governs how n8n workflows/agents get built under the D-068 architecture: reuse existing
> template shapes, never write from scratch; two mandatory human checkpoints.

## Pipeline

| Stage | Goal | Type |
|---|---|---|
| 1. Decompose | Break goal into shape categories + contracts | Agent (autonomous) |
| 1.5 HITL Interview A | Confirm/adjust shape list and priorities before searching | Human checkpoint (mandatory) |
| 2. Discover | Search n8n/GitHub/npm for candidate templates per shape | Agent (autonomous) |
| 2.5 HITL Interview B | Review ranked candidates, pick winners or reject/redirect | Human checkpoint (mandatory) |
| 3. Extract | Pull JSON/config for chosen candidates | Agent (autonomous) |
| 4. Compose | Splice into one workflow JSON — unique node IDs, rewired connections, validated | Agent (autonomous) |

| 5. Platform injection | Claude adapts the composed workflow to THIS platform (owner-added stage, 2026-08-24) | Agent (Claude, autonomous, then owner review) |

**Stage 5 — Platform injection (what "adapts" means, owner's words: "inject the necessary
platform additions"):**
- Break the composed flow at the RIGHT logical points into **Temporal activity boundaries** —
  each n8n chunk small, fast-completing, reporting results back to the durable spine (D-068).
- Insert **human-in-the-loop breaks at the right spots** — Temporal Signal gates, with n8n as
  the notify/approve surface; never an n8n Wait holding state.
- Ensure **hashing/custody is done correctly and by convention** — raw material goes through
  the platform custody door (canon-tagged recipes, registry + doc + vector tests) before any
  n8n node touches content; the workflow consumes record IDs, never raw evidence.
- Apply the standing conventions: temporal-awareness fields on every chunk/prompt/query,
  epoch-numeric time metadata, idempotent run IDs from object keys, read-only against evidence
  collections, results persisted through the platform doorway.

Output contract: the final importable workflow JSON **plus a source-attribution table**
(shape → chosen candidate → URL).

## Tool mapping in THIS environment

| Guide tool | Actual tool here |
|---|---|
| human_interview | AskUserQuestion (structured options, blocks until answered) |
| web_search / searxng_search | WebSearch + n8n template gallery + n8n-docs MCP |
| github_code_search | `gh api` / `gh search code` |
| npm_registry_search | registry.npmjs.org queries via fetch |
| http_fetch | WebFetch / curl |
| code_execution | Bash/python locally; import via n8n API only after Compose validates |

## Standing constraints every build inherits (D-068 + rulings)

- Custody path (ingest → hash → store) is NEVER n8n-side: the ingestion shape's contract is
  "hand raw file to the platform door, receive record IDs back."
- n8n is read-only against evidence Weaviate collections; epoch-numeric timestamps required
  for range filters.
- Temporal-awareness mandate: chunks/prompts carry timestamps; every retrieval carries a window.
- Idempotency: trigger-derived workflow/run IDs come from object keys (at-least-once polling).
- Model calls ride the Portkey gateway (THE model gateway) unless the owner rules otherwise
  per-build.
- First real build target (owner, 2026-08-24): SMS + AI-chat conversation workflow — ingest →
  semantic chunk → classify/tag/summarize per chunk → cheap-LLM round-robin → cost logging.
- **Sourcing rule (owner, same night, refined):** pull templates/recipes/cookbooks/patterns
  from ANYWHERE — but preference ORDER when candidates tie:
  **native built-in > community npm node > raw GitHub template/code.**
  (Native = maintained by n8n, survives upgrades; npm community node = versioned + installable;
  GitHub JSON = copy-in, we own its drift.) Every adopted piece lands in the
  source-attribution table regardless of shelf.

## Interview A outcomes (owner, 2026-08-24 — binding for build #1)

- **Shape list confirmed, plus ONE ADDED SHAPE:** a **verification/confidence gate** after
  classification — at least two LLMs review (or a confidence-scoring pass); "something has to
  happen to make sure it's good, right, accurate" before results persist.
- **Classification is the fan-out point:** classify/tag/summarize is precisely the work that
  spreads across many models — volume is high, so usage-spreading is the point of routing.
- **Cost logging reframed → RATE-LIMIT management.** Owner pays subscriptions, not per-token:
  the ledger's job is quota/rate-limit tracking per provider+account so free tiers never trip,
  not dollars.
- **Model pool (all effectively free):** NIM catalog; Ollama Cloud (≤3 concurrent, session
  limits; glm-5.1 EXCLUDED for schema-constrained output); Gemini free tier ×4 accounts
  (4 keys to rotate); OpenRouter free models. Schema-JSON conformance must be verified
  per-model before a model joins the classification pool (standing lesson).
- **Round-robin implementation: Portkey loadbalance** — the gateway rotates keys/providers,
  handles fallbacks, meters usage; n8n makes one call per task. Multi-account Gemini rotation
  lives in Portkey config, not workflow logic.
- **Priority: the custody handoff (shape 1) is the must-be-production-grade piece**; the rest
  may start as rough drafts and iterate.

## Interview B outcomes (owner, 2026-08-24 — binding; discovery was ruled "narrow and shallow", scope widened)

**Owner-added NATIVE nodes the discovery pass missed — all now IN the build set:**
- Summarization Chain (`chainsummarization`) — the summarize leg of shape 3
- Sentiment Analysis node — joins Information Extractor + Text Classifier in the classification suite
- **Auto-fixing Output Parser** (`outputparserautofixing`) wrapped around the Structured Output
  Parser — malformed JSON gets one LLM-corrected retry before failing; essential with free-tier
  models on schema-constrained output
- Default Data Loader (metadata passthrough) and the **Sort node** (chronological ordering —
  temporal mandate applied inside n8n flows)
- LangChain-layer leads to evaluate at Extract: code splitter, message serialization (maybe),
  OpenAI metadata tagger (maybe), LLM caching (maybe), LangGraph short-term memory

**Decisions:**
- Shape 2: native Recursive splitter NOW; semantic upgrade later via (a) the community
  semantic-splitter nodes OR (b) **wrapping chonkie/our own chunker in a Code node** — decided
  at upgrade time, not now.
- Shape 5: Portkey loadbalance primary. **Verify + test `n8n-nodes-roundrobin`** as supplement.
- **NEW TIER (owner): the Claude SDK with the owner's long-lived token joins as the
  HIGHEST-LEVEL judge** — used ONLY for the most consequential decisions/checks (top of the
  verification gate, above the free-model judges). Verify `n8n-nodes-claude-cli` from the
  owner's npm list as the integration path; token lives in Coolify env storage, never in git.
- Shape 6: Portkey caps only; no PG ledger for now.
- Shapes 1/3/4/7 winners stand, with the additions above folded in.

## Standing rule — the community check (owner, 2026-08-24)

**Always check the community — even when you think you have everything you need.** Before
finalizing any shape/stage, run one targeted sweep for a better, more precise,
community-curated library/node/template than what's in hand. Rationale: the owner's own npm
session out-discovered the dedicated discovery pass (auto-fixing parser, roundrobin, claude-cli,
semantic-splitter-with-context were all sitting on npm). This check is part of EVERY stage's
definition-of-done, not just Discover.

## Classification expectations (owner, 2026-08-24 — design consequence, not mood)

The previous classification/ontology/flagging attempt was "horrendously problematic — flagged
every fucking thing." The new lane is EXPECTED TO SUCK AT FIRST and is built for iteration:

- **Every classification output is a DRAFT by design** — labeled rows carry the classifier
  version (prompt/config/model) that produced them; nothing downstream treats early labels as
  authoritative and NOTHING auto-promotes off a classification alone.
- **Re-classification must be cheap and total** — same philosophy as re-ingest-from-originals:
  bump the classifier version, re-run the corpus through the (free) model pool, compare. Old
  labels superseded, not overwritten.
- **Anti-over-flagging bias:** low confidence routes to "unreviewed", NOT to a flag. A flag
  fired wrongly a thousand times is worse than no flag — that was the exact failure mode.
- **The iteration fuel is the example table** (analysis.human_label): owner-labeled examples
  accumulate → few-shot prompts improve → eventually DSPy compiles against the gold set. The
  verification gate (free judges + Claude-SDK top tier) filters what reaches human eyes.
- **Small batches, always (owner, same night):** never giant runs — process in small batches
  (bounded Loop-Over-Items batch sizes + Portkey caps + batch-interval pacing), then STOP:
  test, look at output together, adjust, run the next batch. Rate-limit safety AND review
  cadence in one rule; batch size is a tunable start-small parameter, not a throughput target.
- **Chunking-upgrade tiebreak (owner check, 2026-08-24):** chonkie confirmed ACTIVELY
  MAINTAINED (updated days ago) while the community semantic-splitter's upstream is DEAD
  (extract finding) → the semantic upgrade path is (b): expose chonkie through a thin
  platform `chunk` endpoint (it already ships in the worker image) and call it from n8n as a
  tool — NOT literally inside a Code node (Pyodide can't run Python native deps). Same
  wrap pattern as Semantica; chunk boundaries stay identical across n8n and the pipeline.
