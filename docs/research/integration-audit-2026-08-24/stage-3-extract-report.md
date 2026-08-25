# Stage 3 — Extract: verified artifacts for the n8n build

> _Byline: stage-3 extract agent · Sonnet · 2026-08-24_
> Method per `docs/plans/N8N-BUILDER-AGENT-GUIDE.md` (Stage 3). Every artifact below was actually
> fetched (raw JSON / npm registry JSON / GitHub API / docs.n8n.io) and inspected — nothing here
> is taken on a description alone. READ-ONLY: nothing was installed or imported into the live n8n
> instance; this is files-on-disk extraction only. All files live in
> `docs/research/integration-audit-2026-08-24/extracted/`.

## 1. Template JSON pulls

All five pulled from `api.n8n.io/api/templates/workflows/<id>` (HTTP 200, real workflow JSON
under a `workflow` key, not marketing copy). Saved as
`extracted/template-<id>-<slug>.json`.

### 3297 — `template-3297-dropbox-db-diff-intake-skeleton.json` (116 KB)
**"Monitor Dropbox folders for new files with DB comparison."** 19 nodes: `webhook` →
`dropbox` (list watched folder) → `switch` (file vs folder) ×2 → `nocoDb` (get known files to
exclude) → `merge` (keep only new items) → `respondToWebhook` ×2 (fast Dropbox webhook ack) →
`dropbox` (get files) → `nocoDb` (record the new file) → `set` ×2 (folder config) →
`executeWorkflow` ×2 (hand off to a per-file/folder sub-workflow) + 7 sticky notes.

- **Keep**: the whole list→diff→dedupe→record→sub-workflow-handoff skeleton. The NocoDB
  "known files" table is the reusable idempotent-poll pattern — swap NocoDB for our Postgres
  seen-table, swap Dropbox's `list`/`get` calls for an S3/R2 `getAll` against the R2 mount.
  The `executeWorkflow` handoff nodes are exactly the D-068 boundary point (small n8n chunk,
  hands off, doesn't do the heavy work itself).
- **Discard**: the Dropbox-specific auth/webhook-validation nodes (`respondToWebhook` ack,
  Dropbox challenge-response) — Dropbox isn't our source; keep only as a reference for how a
  push-based intake source should ack fast and defer work.

### 1326 — `template-1326-error-alert-skeleton.json` (7 KB)
**"Get a Slack alert when a workflow went wrong."** 2 nodes: `errorTrigger` → `slack`.

- **Keep**: entire skeleton as-is. It's the minimal Error Trigger → notify pattern stage-2
  already flagged as the Shape-7 alert skeleton. Confirms the Error Trigger's default payload
  fields (`$json.workflow.name`, `$json.execution.error.message`, `$json.execution.url`) are
  exactly what the Slack message expression references — matches the native-node-notes.md
  payload shape documented from docs.n8n.io.
- **Discard**: nothing — swap the Slack credential/channel for ours, that's the only edit needed.

### 15229 — `template-15229-confidence-gate-pattern.json` (28 KB)
**"Classify documents and score confidence with easybits Extractor and Slack."** 12 nodes:
`formTrigger` (upload doc) → `@easybits/n8n-nodes-extractor.easybitsExtractor` (classify &
score) → `if` (empty or low confidence) → `slack` (notify needs-review) / `noOp` (continue) +
6 sticky notes.

- **Keep**: the **shape**, not the extractor node. `easybits/n8n-nodes-extractor` is a
  third-party paid/hosted extraction service (not verified as part of this pass, not in our
  npm pick list, and not needed — Information Extractor + Structured Output Parser already
  covers the same job natively per Interview B). What's worth keeping is the IF-gate wiring:
  a single confidence/empty check branching to a human-review notify path vs. a silent
  continue — this is the literal skeleton for our Shape-4 gate, just re-pointed at our own
  Structured Output Parser's `confidence` field instead of easybits' output field.
- **Discard**: the `@easybits/...` node itself and its form-upload trigger (we're not building
  a manual-upload flow for this build target).

### 12316 — `template-12316-multi-model-council.json` (44 KB)
**"Synthesize and compare multiple LLM responses with OpenRouter council."** 25 nodes across
4 stages: Stage 1 (`splitOut` by model → `httpRequest` query each model → `aggregate`),
Stage 2 (anonymize responses → `httpRequest` cross-ranking per model → `splitOut`/aggregate
rankings), Stage 3 (`code` node computes aggregate rankings → `httpRequest` chairman-model
synthesis), Stage 4 (format output → `emailSend`). Also has a `@n8n/n8n-nodes-langchain
.chatTrigger` as an alternate entry point.

- **Keep**: the 3-stage pattern (independent answers → mutual anonymized ranking → chairman
  synthesis) as the reference design for the "council" path Interview B reserved for
  high-stakes chunks in the Shape-4 gate — i.e., only invoked when the cheap-tier confidence
  gate is inconclusive, not on every chunk. The anonymization step before cross-ranking (Stage
  2) is a genuinely useful de-biasing detail worth carrying over.
- **Discard**: the raw `httpRequest` calls to arbitrary model endpoints and the `emailSend`
  output — our equivalent calls go through Portkey (native Chat Model node), and results
  persist to Postgres, not email.

### 7633 — `template-7633-batch-classify.json` (21 KB)
**"Smart Gmail Labeling Automation with Text Classifier and GPT-5."** 14 nodes:
`scheduleTrigger` → `gmail` (get emails) → `splitInBatches` (Loop Over Items) →
`@n8n/n8n-nodes-langchain.textClassifier` (fed by `lmChatOpenAi`) → 3× `gmail` (add label,
one branch per category) + 6 sticky notes.

- **Keep**: the exact wiring pattern stage-2 called out — `Loop Over Items` feeding the native
  **Text Classifier** node, one output branch per category driving a distinct downstream
  action. This is the literal skeleton for Shape 3's discrete-tagging half; swap the Gmail
  label-add actions for our Postgres/record-ID persistence action, and swap `lmChatOpenAi` for
  our Portkey-routed Chat Model node.
- **Discard**: all three `gmail` action nodes and the Gmail-specific schedule trigger.

## 2. Owner npm picks — verified

### `n8n-nodes-roundrobin` — **MISMATCH, do not use as intended**
- Registry: real `n8n-community-node-package`, MIT, single maintainer (`james-fincher`).
  **Last published 2025-04-05** (36 versions total, but nothing since) — stale relative to
  2026-08-24 (~16 months with zero updates). Registers two nodes: `RoundRobin.node.js` and
  `RecallMemory.node.js`.
- **What it actually does** (confirmed from the README, not the name): it's a **stateful
  multi-persona conversation message store/retrieve node** — "store and retrieve messages in a
  round-robin fashion, particularly for LLM conversation loops with multiple personas." It
  holds conversation turns (User/Assistant/System-style "spots") in binary data threaded
  between node executions, with formatting helpers for OpenAI/Claude/Gemini message shapes.
  There is **no provider/API-key/model rotation logic anywhere in it.**
- **Verdict**: this is a false lead from the package name alone. It solves a completely
  different problem (multi-persona conversation state) than what Interview B asked it to
  supplement (Portkey's `loadbalance` provider rotation for Shape 5). **Do not wire this in
  as a Shape-5 supplement** — it wouldn't do anything relevant to rate-limit/key rotation.
  If a genuine multi-persona conversation-loop need ever comes up (not currently in this
  build), it would be worth a second look then, with its staleness re-checked.

### `n8n-nodes-claude-cli` — verified, real but very young; ToS caveat is explicit
- Registry: real `n8n-community-node-package`, MIT, single maintainer (`tranmani`). First
  published 2026-07-09, latest 0.1.5 on 2026-07-10 (6 versions, ~6 weeks old at audit time).
  GitHub repo (`tranmani/n8n-claude-cli-bridge`): 0 stars, 0 forks, not archived — essentially
  unadopted outside its author.
- **What it does**: wraps the actual `claude` CLI binary via `spawn('claude', …)` — argv array,
  not a shell string (there's a documented test against a `"; rm -rf /` injection case).
  Registers two nodes (`ClaudeSubscription` for Chat/Agentic operations, `ClaudeChatModel` as a
  LangChain-compatible chat-model sub-node) plus a `ClaudeSubscriptionApi` credential that
  **holds no secret** — auth lives entirely in `~/.claude` on the host running the CLI.
  **This is API-key-free by design**: it authenticates via a Claude Pro/Max **subscription**,
  not the Anthropic API.
- **Long-lived-token match confirmed**: the package's own `deploy/README.md` documents exactly
  the mechanism Interview B described — for auth methods that don't survive a container bind
  mount (e.g. OS-keychain-based logins), "mint a long-lived token on the host with
  `claude setup-token`" and feed it to the container via the CLI's documented token env var.
  So "the Claude SDK with the owner's long-lived token" maps directly onto this package's
  documented long-lived-token path, not onto a plain Anthropic API key.
- **Deployment implication — CONFIRMED, real infra change**: this node requires the `claude`
  CLI binary to exist **inside the same container/environment as n8n**, authenticated. The
  package ships a ready-made `deploy/Dockerfile` (custom n8n image with the CLI baked in) and
  a compose snippet that bind-mounts `${HOME}/.claude:/home/node/.claude:ro` (or uses the
  long-lived-token env var). This is the same shape as the existing "custom graphiti-mcp
  image" pattern already in use on this infra — a custom n8n image built and deployed via
  Coolify, not a stock `n8nio/n8n` image. **This needs to be scoped as its own deploy task
  before the Shape-4 top-tier judge can go live.**
- **ToS flag — the package author states this themselves**: "Driving a Claude Pro/Max
  subscription through automation may conflict with Anthropic's subscription terms —
  subscriptions are intended for interactive use; the API is the sanctioned path for
  programmatic/high-volume use." This is worth a conscious owner sign-off before relying on
  it for a recurring automated pipeline, not just a one-off manual trigger.
- **Alternative pattern checked**: `@chrishdx/n8n-nodes-codex-cli-lm` (OpenAI Codex CLI as a
  LangChain chat model) exists on npm — same architecture (spawns `codex exec`, needs the
  binary + `CODEX_HOME/auth.json` on the n8n host, self-hosted only). Published 2026-01-01,
  single version, empty repository URL in its own package.json — **less mature/maintained
  than n8n-nodes-claude-cli**, useful only as confirmation that "CLI-wrapper community node,
  same host, same container" is the general shape this kind of integration takes across
  vendors, not a better option in itself.
- **Verdict**: real, does what it claims, and the long-lived-token flow the owner specified is
  documented and supported — but it's a single-maintainer, zero-star, 6-week-old package with
  an explicit ToS caveat from its own author. Fine to use for the top-tier judge given the
  owner's explicit ruling, but flag both the container-image deploy work and the ToS
  conversation before it goes live on a recurring schedule.

### `n8n-nodes-semantic-splitter-with-context` — verified; GitHub repo is now dead
- Registry: real `n8n-community-node-package`, MIT, 13 versions, latest 0.6.2 published
  2025-10-20 (reasonably fresh — ~10 months old, not abandoned-looking from version history
  alone). Two maintainers listed (`braidn`, `resettech`).
- **Repo-link rot**: `package.json`'s `repository` field points at
  `github.com/ResetNetwork/n8n-nodes` (subdirectory `n8n-nodes-semantic-splitter-with-context`)
  — that repo now returns **404** on the GitHub API and in-browser. The npm package itself is
  still intact and installable (pulled the actual `dist/` source via unpkg since the repo is
  gone). **Maintenance verdict: source-of-truth repo is gone; treat as effectively
  orphaned even though the npm tarball still installs.** Re-verify before depending on it long
  term, and don't expect upstream fixes.
- **Metadata-survival finding (the specific gap this package was flagged to check)**: source
  confirms `metadata: { ...document.metadata }` on every emitted chunk in
  `splitDocuments()` — the parent LangChain Document's metadata object **is spread onto every
  chunk it produces**. So if timestamps/speaker fields are attached to the document (e.g. via
  Default Data Loader's own Metadata option) before it reaches this splitter, those fields
  **do survive** onto every resulting chunk. Caveat: it's whole-document metadata cloned
  identically onto every chunk — there is **no per-chunk differentiation** (no chunk-specific
  offset/speaker-at-this-point tracking) if a single input document actually contains a
  multi-speaker, multi-timestamp transcript block. The node's real value-add (its "context")
  is an LLM-generated global-summary-plus-chunk-context string prepended to each chunk's
  content — a different, complementary concept to raw metadata survival, not a substitute for
  it.
- **Verdict**: does what the metadata question asked (survives), with the one caveat above; the
  dead upstream repo is the bigger concern for adoption than the splitting logic itself.

### `@bitovi/n8n-nodes-semantic-text-splitter` — verified; different metadata story
- Registry: real `n8n-community-node-package`, MIT, active org (`bitovi`, 16 listed
  maintainers — a real company's OSS team, not a solo hobby package), 4 versions, created
  2024-12, latest metadata touch 2026-05-21. GitHub repo confirmed alive
  (`bitovi/n8n-nodes-semantic-text-splitter`).
- **Source structure**: `SemanticTextSplitter` extends LangChain's base `TextSplitter` class
  and implements **only** `splitText(text): Promise<string[]>` (sliding-window sentence
  embeddings + cosine-distance breakpoints) — it does **not** override `splitDocuments()`.
  That means metadata handling isn't custom code in this package at all; it inherits
  LangChain's base-class default `splitDocuments`/`createDocuments` implementation, which
  (per LangChain's own standard behavior, same as the native Recursive Character Text
  Splitter) clones the source Document's metadata onto each resulting chunk. **Inferred, not
  directly observed in this package's own source** — flagged as such rather than stated as
  independently verified, since the metadata-copying logic lives in the LangChain dependency,
  not in this package's ~140 lines.
- **Verdict**: real, actively maintained, better organizational backing than the
  "with-context" package above. Metadata survival is very likely (same mechanism the native
  splitter relies on) but wasn't independently re-derived from this package's own code the way
  it was for `semantic-splitter-with-context`.

### `n8n-nodes-nvidia-nim` — verified; registers chat + vision, NOT an LangChain sub-node
- Registry: real `n8n-community-node-package`, MIT, single maintainer, 19 versions, latest
  2.4.0 published 2026-05-10 (~3.5 months old at audit — actively maintained relative to the
  others here). Registers two nodes: `NvidiaNim` (chat completions) and `NvidiaNimImage`
  (vision/image analysis) plus an `NvidiaNimApi` credential (API key + base URL, default
  `https://integrate.api.nvidia.com/v1`).
- **Confirms the ask**: yes, it's chat completions (plus a bonus vision-analysis node) — no
  embeddings operation. Model list in the README (`meta/llama-3.1-*`, `nvidia/nemotron-4-*`,
  `deepseek-ai/deepseek-r1`, etc.) matches NIM's public catalog.
- **Architectural flag**: both nodes are **plain action nodes** (`n8n-nodes-base`-style, direct
  HTTP call), **not** `@n8n/n8n-nodes-langchain.lmChat*`-family sub-nodes. That means they
  can't be plugged into an AI Agent / Chain / Text Classifier / Sentiment Analysis node as the
  attached language model the way the native OpenAI Chat Model or Anthropic Chat Model nodes
  can — they only work as standalone workflow steps. Since stage-2's Shape-5 pick is "native
  OpenAI Chat Model node pointed at our Portkey gateway," which already covers NIM as one of
  Portkey's `loadbalance` targets, **this package doesn't currently have a slot to fill in the
  chosen architecture** — it would only matter if something needed to call NIM directly,
  bypassing Portkey, which isn't the design.

## 3. Native-node config snapshots

Full per-node parameter notes (typeVersion, exact options, gotchas) for all 15 requested native
nodes are in `extracted/native-node-notes.md`. Headline items worth surfacing here:

- **Auto-fixing Output Parser** has no parameters of its own beyond which parser it wraps and
  which Chat Model handles the fix-up call — point that fix-up model at a stronger tier than
  whatever free-tier model produced the malformed JSON in the first place, or it can fail the
  same way twice.
- **Local File Trigger is excluded by default** (`NODES_EXCLUDE` ships with
  `n8n-nodes-base.localFileTrigger` in the default block-list from n8n 2.0) — confirm this is
  actually enabled on our instance before Shape 1 can use it.
- **Guardrails' "Custom" guardrail type** (name + prompt + 0.0–1.0 threshold) is the literal
  Shape-4 confidence-gate primitive already identified in stage-2; it needs a Chat Model
  sub-node attached, same as the LLM-based checks.
- **Postgres Query Parameters + `$1:name`** table-identifier parameterization covers both
  value-injection-safety and dynamic-table-targeting in one mechanism.
- Every LangChain **sub-node** (Structured Output Parser, Auto-fixing Output Parser, Default
  Data Loader, Recursive Character Text Splitter) shares one gotcha: expressions inside them
  always resolve to the **first item only**, even when multiple items are flowing through —
  relevant anywhere Loop Over Items feeds a sub-node-configured chain per batch.

## 4. Mandatory community check

One targeted sweep per named shape, plus the awesome-n8n-templates skim, per the standing rule.

- **Summarization**: no npm search for "n8n summarize" surfaced anything resembling a community
  summarization node — results were all unrelated (`@telnyx/n8n-nodes-telnyx-ai`, an n8n-MCP
  bridge, etc.). **Checked, none better than the native Summarization Chain node.**
- **Sentiment**: npm search for "n8n sentiment" surfaced only generic non-n8n JS sentiment
  libraries (`sentiment` — AFINN lexicon, `vader-sentiment`) — not n8n nodes at all, and
  lexicon-based rather than LLM-based, which is a downgrade from the native node's LLM
  reasoning. Cross-checked against a real community **template**
  (`awesome-sentiment-analysis.json`, pulled from awesome-n8n-templates — "AI Customer feedback
  sentiment analysis") which itself just uses the legacy `n8n-nodes-base.openAi` node for
  classification, not even a LangChain node — **confirms the native Sentiment Analysis node
  (LangChain-family, purpose-built, with confidence-score option) is already the more
  purpose-built choice. Checked, none better.**
- **Rate-limit guard nodes**: npm search for "n8n rate limit" / "n8n-nodes-ratelimit" returned
  only generic Express/Fastify/Koa/GraphQL middleware packages — nothing n8n-specific beyond
  what stage-2 already found (the native Loop Over Items + Wait pacing pattern, and Portkey's
  own per-provider limits). **Checked, none better.**
- **Curated evidence/legal/forensic n8n workflow collections**: npm searches for "n8n-nodes
  evidence", "forensic", "chain of custody", and "legal" all returned the same handful of
  unrelated boilerplate packages (`n8n-nodes-openpix`, `n8n-nodes-serpapi`,
  `@devlikeapro/n8n-nodes-chatwoot`, `n8n-mcp`) with no relevance at all — **no such curated
  collection exists on npm.** This matches the D-068 custody-boundary design already in place:
  custody/hashing is explicitly platform-side, never n8n-side, so the absence of an n8n-native
  evidence-handling ecosystem isn't a gap for this build, it's the expected shape.
- **awesome-n8n-templates / OpenAI_and_LLMs skim**: listed 90 files; pulled 3 promising matches
  as real JSON into `extracted/`:
  - `awesome-sentiment-analysis.json` — see Sentiment finding above (legacy OpenAI node, not an
    upgrade).
  - `awesome-hallucination-detection.json` — **"Detect hallucinations using specialised Ollama
    model bespoke-minicheck."** 18 nodes: `Basic LLM Chain` × 2 wired to `Ollama Chat Model` /
    `Ollama Model` running the `bespoke-minicheck` fact-checking model, with `filter`/`merge`/
    `aggregate` nodes assembling a claim-vs-source verification pass. **This is a genuine
    upgrade candidate for Shape 4**, not previously surfaced in stage-2: `bespoke-minicheck` is
    a small purpose-built hallucination-detection model (not a general chat model asked to
    self-judge), and Ollama Cloud is already in the owner's free-tier model pool from
    Interview A. Worth evaluating as a cheap-tier pre-filter *before* the free-model judge
    layer, or as a second independent check alongside it — flagged for Compose/owner
    discussion, not adopted unilaterally here.
  - `awesome-multimodel-fallback.json` — **"DaoXE Multi-Model Chat with Automatic Fallback."**
    7 nodes: a plain primary-model → (on failure) fallback-model `httpRequest` pair, no gateway
    involved. Confirms the community-level pattern is simpler than what Portkey's
    `loadbalance`/fallback config already gives us natively — **not an upgrade over the
    existing Shape-5 pick, evidence that the chosen approach is already ahead of the DIY
    pattern.**

## Flags / deployment implications summary

1. **`n8n-nodes-claude-cli` requires a custom n8n Docker image** (CLI baked in) plus either a
   read-only `~/.claude` credential mount or a `claude setup-token` long-lived token env var —
   same operational shape as the existing custom graphiti-mcp image, but a new build/deploy
   task, not a plain community-node install. Needs Coolify image work before the Shape-4 top
   judge tier can go live.
2. **ToS risk on `n8n-nodes-claude-cli`**: the package's own author documents that driving a
   Claude Pro/Max subscription through recurring automation may conflict with Anthropic's
   subscription terms. Worth an explicit owner decision, not a silent adoption.
3. **`n8n-nodes-roundrobin` does not do what its name implies** — it's conversation-state
   storage for multi-persona chats, not provider/key rotation. Do not wire it into Shape 5;
   Portkey `loadbalance` remains the sole rotation mechanism as stage-2 already concluded.
4. **`n8n-nodes-semantic-splitter-with-context`'s GitHub repo is gone (404)** — the npm package
   still installs and its metadata-survival behavior was confirmed straight from the unpkg'd
   source, but there is no live upstream to file issues against or expect fixes from.
5. **`n8n-nodes-nvidia-nim` doesn't plug into the LangChain chat-model slot** — it's a plain
   action node, so it has no role in the chosen Shape-5 architecture (native Chat Model node →
   Portkey gateway, which already fronts NIM). Not a wasted verification — it rules the package
   out cleanly rather than leaving it as an open question.
6. **Local File Trigger needs `NODES_EXCLUDE` confirmed/edited on the live instance** before
   Shape 1 can use it — it ships excluded by default from n8n 2.0.
7. **`bespoke-minicheck` hallucination detection (via Ollama)** is a real, previously-unsurfaced
   upgrade candidate for the Shape-4 verification gate — flagged for Compose/owner discussion,
   not adopted here.

## Not committed
Per the task instructions, none of this extraction work has been committed to git.
