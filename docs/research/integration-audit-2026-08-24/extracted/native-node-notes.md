# Native node config snapshots — build set

> _Byline: stage-3 extract agent · Sonnet · 2026-08-24_
> Source: n8n-docs MCP (`getPage`/`searchDocumentation`) against docs.n8n.io, cross-checked
> against the version table on the "Deprecated nodes" page for current `typeVersion`s. Target
> instance: n8n 2.36.6 self-hosted (per lane-6 audit). Plain English, per node: what it is, the
> exact parameters/options Compose should set, and gotchas.

## Information Extractor
`@n8n/n8n-nodes-langchain.informationExtractor`, current version **1.2** (prior: 1, 1.1).

- Root (cluster) node — sits inside the LangChain AI layer, needs a Chat Model sub-node attached.
- **Text**: expression pointing at the chunk text, e.g. `{{ $json.chunkText }}`.
- **Schema Type** — three modes:
  - *From Attribute Descriptions* — hand-list attributes + descriptions (best for our
    classify/tag schema since we can hand-tune per-field guidance for cheap models).
  - *Generate From JSON Example* — every field becomes mandatory; fine for a fixed schema.
  - *Define using JSON Schema* — full JSON Schema; **no `$ref` support**, keep it flat.
- **Node option — System Prompt Template**: n8n auto-appends format-spec instructions after
  whatever you put here; don't duplicate that instruction yourself.
- Uses Structured Output Parser under the hood (that's why v1.2 exists — simpler front-end).

## Text Classifier
`@n8n/n8n-nodes-langchain.textClassifier`, current version **1.1** (prior: 1).

- **Input Prompt**: expression, defaults to `text` field if left blank.
- **Categories**: name + description per category (description matters — it's the only signal
  the model gets for ambiguous categories). No hard cap on count.
- **Allow Multiple Classes To Be True**: off = exactly one output branch per item; on = model can
  fire more than one branch.
- **When No Clear Match**: `Discard Item` (default, silently drops) vs `Output on Extra 'Other'
  Branch` — **use the Other branch**, never silent-discard, so nothing vanishes from the pipeline.
- **System Prompt Template**: `{categories}` placeholder available.
- **Enable Auto-Fixing**: built into the node itself (separate from the Auto-fixing Output Parser
  sub-node) — turn this ON for free-tier models; it re-sends the schema error to the LLM once.

## Sentiment Analysis
`@n8n/n8n-nodes-langchain.sentimentAnalysis`, current version **1.1** (prior: 1).

- **Text to Analyze**: expression, defaults to `text` field.
- **Sentiment Categories** (option): default `Positive, Neutral, Negative` — comma list, fully
  customizable (e.g. 5-point scale).
- **Include Detailed Results** (option): adds strength/confidence scores — n8n's own docs flag
  these as LLM-estimated, not precise; don't treat them as calibrated probabilities.
- **Enable Auto-Fixing** (option): same mechanism as Text Classifier.
- **Model temperature**: docs explicitly recommend **temperature ≈ 0** on the attached Chat Model
  for determinism — set this on whichever cheap-tier model handles sentiment.

## Summarization Chain
`@n8n/n8n-nodes-langchain.chainSummarization`, current version **2.1** (prior: 1, 2).

- **Data to Summarize** picks the mode:
  - *Use Node Input (JSON/Binary)* + **Chunking Strategy**: `Simple` (set **Characters Per
    Chunk** + **Chunk Overlap (Characters)**) or `Advanced` (attach a text-splitter sub-node —
    use Recursive Character Text Splitter here for consistency with Shape 2).
  - *Use Document Loader* — feed it a Default Data Loader sub-node instead (matches the owner's
    Default Data Loader addition from Interview B).
- **Summarization Method** (option, under Add Option): `Map Reduce` (n8n's recommended default —
  handles arbitrarily many chunks), `Refine`, or `Stuff` (single-pass, only for short inputs).
- **Individual Summary Prompts** / **Final Prompt to Combine**: both customizable; **must contain
  the literal `"{text}"` placeholder** or the node errors.
- No built-in memory (true of all three n8n chain nodes) — fine for a per-chunk summarization
  step that doesn't need conversation continuity.

## Structured Output Parser
`@n8n/n8n-nodes-langchain.outputParserStructured`, current version **1.3** (prior: 1, 1.1, 1.2).

- Sub-node — attaches to a root node's "Require Specific Output Format" toggle.
- **Schema Type**: `Generate from JSON Example` (all fields become mandatory, values ignored, only
  shape/types matter) or `Define using JSON Schema` (**no `$ref`** — same restriction as
  Information Extractor).
- **Sub-node expression gotcha** (applies to every sub-node in this list): with multiple input
  items, an expression like `{{ $json.name }}` inside a sub-node always resolves to the **first**
  item only — never rely on per-item expressions inside a sub-node when Loop Over Items is
  feeding multiple items in.

## Auto-fixing Output Parser
`@n8n/n8n-nodes-langchain.outputParserAutofixing`, current version unspecified in docs (treat as
current default; wraps another parser).

- Wraps the Structured Output Parser (or Item List Output Parser). On a parse failure it calls a
  **second, separately-configurable LLM** with the schema error and asks for a corrected answer.
- No standalone parameters beyond picking (a) the parser it wraps and (b) the Chat Model sub-node
  to use for the fix-up call — **this is exactly the "one LLM-corrected retry" the owner specified
  for free-tier schema-constrained output** (Interview B). Point the fix-up Chat Model at a
  stronger/paid-tier model if the free-tier model is the one that failed, otherwise it can fail
  the same way twice.
- Same first-item-only sub-node expression caveat applies.

## Default Data Loader
`@n8n/n8n-nodes-langchain.documentDefaultDataLoader`, current version **1.1** (prior: 1).

- **Text Splitting**: `Simple` (hardcodes Recursive Character Text Splitter, chunk size 1000 /
  overlap 200 — **not configurable in Simple mode**) or `Custom` (attach your own splitter
  sub-node — use this to set our own chunk size/overlap on the Recursive splitter).
- **Type of Data**: Binary or JSON.
- **Mode**: `Load All Input Data` or `Load Specific Data` (expression-built custom document, can
  mix static text + expressions).
- **Data Format** (Binary only): pick a MIME type or `Automatically Detect by MIME Type` (falls
  back to text if no MIME match).
- **Metadata** (option): key/value metadata attached to every emitted Document — **this is the
  node-level mechanism for carrying timestamp/speaker fields through to the vector store's
  Metadata Filter**, distinct from and complementary to whatever a text splitter does or doesn't
  preserve on its own (see the semantic-splitter npm verification in the main report).

## Sort
`n8n-nodes-base.sort`, current version **2** (prior: 1, 1.1).

- **Type**: `Simple` (ascending/descending on named fields, dot-notation supported unless you
  toggle **Disable Dot Notation**), `Random`, or `Code` (custom JS comparator for anything the
  simple mode can't express).
- For the **temporal-ordering mandate** (chronological chunk ordering before persistence): Simple
  mode, sort field = the epoch-numeric timestamp field, Ascending.
- Caveat: Simple-mode array comparisons are JS's default string-coerced sort — fine for numeric
  epoch fields compared as numbers via the field picker, but don't rely on it for mixed types.

## Local File Trigger
`n8n-nodes-base.localFileTrigger` — **no version shown in docs; self-hosted only, not on n8n
Cloud, and disabled by default from n8n 2.0** (must explicitly remove it from `NODES_EXCLUDE`,
whose default list is `["n8n-nodes-base.executeCommand", "n8n-nodes-base.localFileTrigger"]`).

- **Trigger On**: `Changes to a Specific File` (**File to Watch** path) or `Changes Involving a
  Specific Folder` (**Folder to Watch** path + **Watch for** event type: add/change/delete).
- Options: **Include Linked Files/Folders**, **Ignore** (Anymatch-syntax patterns, tested against
  the whole path not just filename), **Max Folder Depth**.
- **Deployment action item**: confirm `NODES_EXCLUDE` on our instance actually enables this node
  (it's excluded by default) before wiring Shape 1's drop-folder watch.

## HTTP Request
`n8n-nodes-base.httpRequest`, current version **4.4** (prior: 1, 2, 3, 4, 4.1, 4.2, 4.3).

- **Method / URL** as usual. **Authentication**: prefer **Predefined Credential Type** when
  available; otherwise generic (Basic/Digest/Header/OAuth1/OAuth2/Query/Custom).
- **Send Query Parameters / Send Headers / Send Body** each independently toggled; Body supports
  Form-Urlencoded, Form-Data (incl. n8n Binary File), JSON, raw, or n8n Binary File passthrough.
- **Options relevant to our build**:
  - **Batching**: Items per Batch + Batch Interval (ms) — the built-in pacing knob for Shape 6.
  - **Response → Never Error**: leave OFF so non-2xx surfaces as a real node failure into the
    Error Trigger path, not a silently-accepted response.
  - **Pagination**: `Update a Parameter in Each Request` or `Response Contains Next URL`, with
    `$pageCount` / `$request` / `$response` expression variables available.
  - **Timeout**: applies to time-to-first-response-byte, not total transfer time.
- **As-a-tool options** (only when attached to an AI Agent): Optimize Response lets you cap JSON/
  HTML/Text payload size before it reaches the LLM — useful if this node is ever exposed as an
  agent tool rather than a plain workflow step.

## Postgres
`n8n-nodes-base.postgres`, current version **2.6** (prior: 1, 2, 2.1–2.5).

- Operations: Delete (Truncate/Delete/Drop), **Execute Query**, Insert, Insert or Update, Select,
  Update. Also usable as an AI-tool node (agent can drive parameters).
- **Execute Query** is the injection-safe write path: SQL text uses `$1`, `$2`, … placeholders;
  the **Query Parameters** option takes a comma-separated (or expression-built array) list of
  values — n8n sanitizes these, which is what prevents SQL injection. Table/schema identifiers
  can also be parameterized via `$1:name` for dynamic table targeting.
- **Query Batching** (all write operations): `Single Query` / `Independently` (one query per
  item) / `Transaction` (all-or-nothing rollback on failure) — use `Transaction` for any
  multi-row custody/result writes that must land atomically.
- **Output Large-Format Numbers As**: `Text` if any NUMERIC/BIGINT column can exceed 16 digits
  (epoch-millisecond timestamps are fine as Number, but a 64-bit hash/ID column should use Text).
- Has a dedicated **Postgres Trigger** node (insert/update/delete events) if the ledger table
  itself needs to fan out downstream — not currently in our build set but noted for later.

## Error Trigger
`n8n-nodes-base.errorTrigger`, **no version shown** (stable core node).

- Lives in a **separate** "Error Handler" workflow, wired via the parent workflow's
  Settings → **Error workflow** dropdown — one handler workflow can serve every parent workflow.
- Default error payload: `execution.{id,url,retryOf,error:{message,stack},lastNodeExecuted,mode}`
  + `workflow.{id,name}`. `execution.id`/`.url` are absent if the failure happens in the main
  workflow's own trigger node (workflow never actually executed) — the payload shape shifts to a
  `trigger{}` object with `error.name` (e.g. `WorkflowActivationError`), `.cause`, `.timestamp`
  (epoch ms) in that case. Compose should branch on presence of `execution` vs `trigger` in the
  handler.
- A workflow with no explicit Error workflow set, but that itself contains an Error Trigger node,
  uses **itself** as the error workflow by default.
- Pairs with the **Stop And Error** core node for deliberately raising a custom message that then
  flows into this trigger.

## Guardrails
`n8n-nodes-langchain.guardrails`, current version **2** (prior: 1).

- Two operations: **Check Text for Violations** (routes failures to a dedicated **Fail** output
  branch) and **Sanitize Text** (redacts matches in-place with placeholders, no branching).
- **Requires a Chat Model sub-node** connected to the Model input for any LLM-based guardrail
  (Jailbreak, NSFW, Topical Alignment, Custom) — non-LLM guardrails (Keywords, PII regex-style,
  Secret Keys, URLs, Custom Regex) don't need one.
- Guardrail catalog relevant to our confidence-gate use: **Custom** (name + prompt + 0.0–1.0
  threshold — this is the primitive stage-2 already flagged as the Shape-4 mechanism), **PII**
  (All or Selected entity types, e.g. `CREDIT_CARD`/`EMAIL_ADDRESS`/`US_SSN`), **Secret Keys**
  (Strict/Permissive/Balanced), **Jailbreak**/**NSFW**/**Topical Alignment** (each threshold-based
  LLM checks with an overridable default prompt).
- **Customize System Message** (global option): overrides the message the node uses to enforce
  thresholds + JSON-schema-shaped output across every enabled guardrail at once.

## Loop Over Items (splitInBatches)
`n8n-nodes-base.splitInBatches`, current version **3** (prior: 2).

- **Batch Size**: items returned per iteration via the **loop** output; all originally-input data
  is retained and re-emitted combined via the **done** output once every batch is processed.
- **Reset** (option): re-initializes with each loop's current input as a fresh dataset instead of
  continuing the original set — used for manual pagination loops (increment a page counter, exit
  via an IF node on a termination condition). **Must have a real termination condition** or the
  workflow loops forever.
- Useful expressions: `{{$("Loop Over Items").context["noItemsLeft"]}}` (boolean, true once
  exhausted) and `{{$("Loop Over Items").context["currentRunIndex"]}}` (current index).
- The node itself stops after all batches are dispatched — no extra IF node needed just to end
  the loop, only for early-exit/pagination logic.
- Canonical rate-limit pairing (per n8n's own rate-limit guide): Loop Over Items → API call →
  Wait node → loop back to Loop Over Items input.

## Recursive Character Text Splitter
`@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter` — **no version shown**
(sub-node, LangChain family).

- Exactly two parameters: **Chunk Size** (characters) and **Chunk Overlap** (characters).
- n8n's own "Simple" Default Data Loader mode hardcodes this splitter at chunk size 1000 /
  overlap 200 — attach it explicitly (Default Data Loader's "Custom" text-splitting mode) if
  Compose needs different chunk sizing for the SMS/chat-transcript build target.
- Recursively tries paragraph → sentence → word boundaries before falling back to a hard
  character cut — n8n docs recommend it as the default choice for most use cases over the plain
  Character Text Splitter or Token Splitter.
- Same first-item-only sub-node expression caveat applies if any parameter is expression-driven.
