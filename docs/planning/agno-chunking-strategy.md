> _Byline: Claude Code · Opus 4.8 · 2026-07-10_

# Agno Chunking Strategy — Decision-Grade Report

**Scope:** Chunking for the AI-transcript knowledge-base ingest pipeline.
**Framework version verified:** `agno==2.6.13` (installed at `.venv/Lib/site-packages/agno`, dist-info `agno-2.6.13.dist-info`).
**Owner decision under review:** use CHUNKING, with a HYBRID of SEMANTIC + FIXED, reasoning "hybrid is better than starting with pure semantic, because semantic needs to be tweaked and tuned."
**Verdict (short):** Endorsed, with a sharpened rationale and one refinement (turn-aware pre-split). Details in §6.

**Source basis:** Every class/param below was read directly from the vendored source in this repo's venv (paths cited inline). Live docs were pulled via the `agno-docs` MCP for corroboration. Where the published docs disagree with the installed source, I flag it explicitly (see §7 — there are three real doc bugs that will bite us if copy-pasted).

---

## 1. Every chunking strategy Agno 2.x ships

Agno's chunkers all subclass `ChunkingStrategy` (ABC) and implement `chunk(document: Document) -> List[Document]` (plus an async `achunk`). A chunker is attached to a **reader**, not to the vector DB, e.g. `PDFReader(chunking_strategy=...)`.

- Base class: `agno.knowledge.chunking.strategy.ChunkingStrategy`
  (source: `.venv/Lib/site-packages/agno/knowledge/chunking/strategy.py`)
- Document type: `agno.knowledge.document.base.Document`
- The base provides two inherited helpers you get for free in custom strategies: `clean_text()` (collapses repeated whitespace/newlines) and `_generate_chunk_id()` (deterministic chunk IDs).

The enum `ChunkingStrategyType` (strategy.py:58) lists the eight shipped strategies. Actual class + real constructor signature for each, read from source:

| # | Class | Real import path (2.6.13) | Constructor signature (from source) | Embedder/LLM at chunk time? | Size unit |
|---|-------|---------------------------|--------------------------------------|-----------------------------|-----------|
| 1 | `FixedSizeChunking` | `agno.knowledge.chunking.fixed` | `(chunk_size=5000, overlap=0)` | No | characters |
| 2 | `RecursiveChunking` | `agno.knowledge.chunking.recursive` | `(chunk_size=5000, overlap=0)` | No | characters |
| 3 | `DocumentChunking` | `agno.knowledge.chunking.document` | `(chunk_size=5000, overlap=0)` | No | characters |
| 4 | `MarkdownChunking` | `agno.knowledge.chunking.markdown` | `(chunk_size=5000, overlap=0, split_on_headings=False)` | No | characters |
| 5 | `SemanticChunking` | `agno.knowledge.chunking.semantic` | `(embedder=None, chunk_size=5000, similarity_threshold=0.5, similarity_window=3, min_sentences_per_chunk=1, min_characters_per_sentence=24, delimiters=[". ","! ","? ","\n"], include_delimiters="prev", skip_window=0, filter_window=5, filter_polyorder=3, filter_tolerance=0.2, chunker_params=None)` | **Yes — embedder** | **tokens** |
| 6 | `AgenticChunking` | `agno.knowledge.chunking.agentic` | `(model=None, max_chunk_size=5000, custom_prompt=None)` | **Yes — LLM** | characters |
| 7 | `CodeChunking` | `agno.knowledge.chunking.code` | `(tokenizer="character", chunk_size=2048, language="auto", include_nodes=False, chunker_params=None)` | No (uses tree-sitter AST) | tokens |
| 8 | `RowChunking` | `agno.knowledge.chunking.row` | `(skip_header=False, clean_rows=True)` | No | rows |
| — | Custom | subclass `ChunkingStrategy` | implement `chunk()` | your choice | your choice |

Per-strategy behavior and key params (all read from source):

1. **FixedSizeChunking** (`fixed.py`) — hard character windows with optional `overlap`. Word-boundary aware: it walks `end` back to the nearest space/newline so it doesn't split a word (unless a single word is longer than `chunk_size`). `overlap` must be `< chunk_size` (raises `ValueError` otherwise). Deterministic, pure string ops. Doc: `knowledge/concepts/chunking/fixed-size-chunking`.

2. **RecursiveChunking** (`recursive.py`) — like fixed, but before cutting it looks *within* the window for a natural break, trying `"\n"` first then `"."`, and cuts there. `overlap` supported; warns (`RuntimeWarning`) if `overlap > 15%` of `chunk_size`. **Note:** in 2.6.13 the only kwargs are `chunk_size` and `overlap` — there is **no `separators=` parameter** despite what one docs page shows (see §7). Doc: `knowledge/concepts/chunking/recursive-chunking`.

3. **DocumentChunking** (`document.py`) — splits on paragraphs (`\n\n`), greedily packs paragraphs up to `chunk_size`; a paragraph larger than `chunk_size` is further split by sentence regex `(?<=[.!?])\s+`. Optional `overlap` prepends the tail of the previous chunk. Preserves structural boundaries. Doc: `knowledge/concepts/chunking/document-chunking`.

4. **MarkdownChunking** (`markdown.py`) — structure-aware for Markdown. `split_on_headings` can be `False` (size-based), `True` (split on all H1–H6), or an `int` 1–6 (split at/above that heading level). Requires the `unstructured` + `markdown` packages (`ImportError` at import if missing). Doc: `knowledge/concepts/chunking/markdown-chunking`.

5. **SemanticChunking** (`semantic.py`) — wraps the **Chonkie** `SemanticChunker`. Embeds sentence windows and cuts where cosine similarity drops below `similarity_threshold`. **Requires `numpy` and `chonkie[semantic]`** (hard `ImportError` at import otherwise) and an embedder. `embedder` may be: a **string** model id (→ Chonkie AutoEmbeddings), a **Chonkie `BaseEmbeddings`** instance, or an **Agno `Embedder`** (wrapped). If `embedder=None`, it defaults to `OpenAIEmbedder()`. **`chunk_size` here is measured in TOKENS, not characters** — and when you hand it an Agno `Embedder`, Chonkie's tokenizer is a naive `text.split()` word counter (see `_get_chonkie_embedder_wrapper`, semantic.py:37-39), so `chunk_size` is effectively *words*. This unit mismatch vs. the character-based chunkers is the single biggest footgun when composing a hybrid (see §3/§4). Doc: `knowledge/concepts/chunking/semantic-chunking`.

6. **AgenticChunking** (`agentic.py`) — an **LLM decides each breakpoint**. Loops: feeds the model up to `max_chunk_size` chars and asks for the integer character position to cut, then repeats on the remainder. `model` defaults to `OpenAIChat(DEFAULT_OPENAI_MODEL_ID)`; `custom_prompt` lets you steer boundary logic. One LLM completion per boundary → slowest and most expensive, and **non-deterministic** (falls back to `max_chunk_size` on any model error). Doc: `knowledge/concepts/chunking/agentic-chunking`.

7. **CodeChunking** (`code.py`) — Chonkie `CodeChunker`, AST/tree-sitter based, splits at function/class boundaries. `language="auto"` detects. Requires `chonkie[code]` + a tokenizer backend (`tiktoken`/`transformers`/`tokenizers`). Not embedding-based. Doc: `knowledge/concepts/chunking/code-chunking`.

8. **RowChunking** (`row.py`) — one chunk per line/row; `skip_header`, `clean_rows`. For CSV/tabular. Doc: `knowledge/concepts/chunking/csv-row-chunking`.

**Custom** — subclass `ChunkingStrategy`, implement `chunk()`. Confirmed pattern from the live example (`examples/knowledge/chunking/custom-strategy-example`): import base from `agno.knowledge.chunking.strategy` and `Document` from `agno.knowledge.document.base`, reuse `self.clean_text()`. This is the mechanism we use for the hybrid (§3).

---

## 2. Which strategies embed/LLM at chunk time — cost & latency

**Two distinct embedding moments exist.** Every strategy's output is embedded **once at store time** by the vector DB's embedder. Only *some* strategies *additionally* embed (or call an LLM) **at chunk time** to decide boundaries:

| Strategy | Extra work at chunk time | Cost/latency profile | Determinism |
|----------|--------------------------|----------------------|-------------|
| Fixed, Recursive, Document, Markdown, Row | None (pure CPU string ops) | ~Free, fast | Deterministic |
| Code | tree-sitter AST parse (CPU) | Fast, local | Deterministic |
| **Semantic** | **Embeds every sentence window** | Adds ~one embedding per sentence/window at ingest → roughly O(#sentences). Roughly **doubles ingest embedding load** vs. a non-embedding chunker (embed-to-split, then embed-to-store). | Deterministic given fixed embedder+threshold |
| **Agentic** | **One LLM completion per boundary** | Most expensive and slowest by a wide margin; rate-limit and latency exposure; **non-deterministic** | No |

**Implication for a transcript corpus:** Semantic chunking's embed-at-chunk cost is real but bounded and cacheable-adjacent; Agentic's per-boundary LLM cost scales badly across a large transcript archive and is non-reproducible. **Agentic is out of scope for bulk transcript ingest** — reserve it (if ever) for small, high-value curation. Semantic's overhead is the price the owner is knowingly paying, and the fixed guardrail (below) does not add embedding cost.

Agno's own guidance corroborates the speed/quality tradeoff (doc `knowledge/concepts/performance-tips` §4): Fixed = Fast/Good, Semantic = Slower/Best, Recursive = Fast/Good.

---

## 3. Composing a HYBRID semantic + fixed approach

**There is no native "hybrid" chunker in Agno 2.6.13.** The enum has exactly the eight strategies above; the reader accepts exactly one `chunking_strategy`. A hybrid is therefore built as a **custom `ChunkingStrategy` that composes two shipped chunkers**. The right composition for us is **semantic-primary with a fixed-size hard-cap guardrail**:

1. Run `SemanticChunking` to get meaning-coherent chunks.
2. Any chunk that exceeds a hard character cap (e.g., a long uninterrupted monologue where similarity never drops) is re-split by `FixedSizeChunking` as a deterministic safety net.

This is exactly the failure mode the owner intuited: untuned semantic can emit pathological, oversized chunks; the fixed cap bounds the worst case **without** waiting to perfect the threshold. Crucially — **fixed is a safety net, not a substitute for tuning** (see §6).

### Runnable configuration sketch (transcript-tuned)

```python
# agno==2.6.13  |  deps: pip install "chonkie[semantic]" numpy
from typing import List

from agno.knowledge.chunking.strategy import ChunkingStrategy
from agno.knowledge.chunking.semantic import SemanticChunking
from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.document.base import Document


class SemanticFixedHybridChunking(ChunkingStrategy):
    """
    Transcript hybrid:
      1) turn-aware semantic grouping (primary)
      2) fixed-size hard cap as a deterministic guardrail

    NOTE ON UNITS: SemanticChunking.chunk_size is in TOKENS (words when an Agno
    Embedder is passed); FixedSizeChunking.chunk_size is in CHARACTERS. They are
    intentionally different knobs here: the semantic size is the *target*, the
    fixed cap is the *ceiling*. Keep hard_cap_chars comfortably above the
    expected char-length of semantic_chunk_tokens so the cap only fires on
    genuine runaways.
    """

    def __init__(
        self,
        embedder=None,                 # pass the SAME domain embedder used for storage
        semantic_chunk_tokens: int = 400,     # ~a few speaker turns
        similarity_threshold: float = 0.5,     # start here, then tune
        similarity_window: int = 2,
        hard_cap_chars: int = 2000,            # runaway guardrail (~350-450 tokens)
        cap_overlap_chars: int = 150,          # context bleed across a forced cut
    ):
        self.semantic = SemanticChunking(
            embedder=embedder,
            chunk_size=semantic_chunk_tokens,
            similarity_threshold=similarity_threshold,
            similarity_window=similarity_window,
            min_sentences_per_chunk=1,
            # "\n" as a delimiter makes speaker-turn line breaks first-class
            # split points, so chunks tend to land on turn boundaries.
            delimiters=[". ", "! ", "? ", "\n"],
            include_delimiters="prev",
        )
        self.fixed = FixedSizeChunking(
            chunk_size=hard_cap_chars,
            overlap=cap_overlap_chars,
        )
        self.hard_cap_chars = hard_cap_chars

    def chunk(self, document: Document) -> List[Document]:
        out: List[Document] = []
        for i, sem in enumerate(self.semantic.chunk(document), start=1):
            if len(sem.content) <= self.hard_cap_chars:
                out.append(sem)
            else:
                # runaway semantic chunk -> deterministic fixed re-split
                out.extend(self.fixed.chunk(sem))
        return out
```

Wired into ingest exactly like any other strategy:

```python
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.text_reader import TextReader   # or your transcript reader
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.pgvector import PgVector

domain_embedder = OpenAIEmbedder(id="text-embedding-3-small")  # swap per domain

knowledge = Knowledge(
    vector_db=PgVector(table_name="transcripts", db_url=db_url, embedder=domain_embedder),
)
knowledge.insert(
    path="transcripts/",
    reader=TextReader(
        chunking_strategy=SemanticFixedHybridChunking(embedder=domain_embedder),
    ),
)
```

**Why semantic-primary + fixed-cap (and not the reverse):** a fixed-first coarse pre-split then semantic-within loses the very cross-turn coherence semantic is meant to capture. Semantic-first preserves meaning; the cap only intervenes on genuine outliers.

**Even better for transcripts (optional refinement):** add a *turn-aware pre-split* as a first pass so a chunk can never straddle two speakers — split the raw text on the speaker/turn delimiter (e.g. a `^\w+:` or timestamp regex) into per-turn `Document`s, run the hybrid within each, and let semantic merge *adjacent same-context turns* up to the token target. In the sketch above this is approximated cheaply by putting `"\n"` in `delimiters` (turn lines become hard split candidates). Promote to an explicit pre-split only if the corpus has clean, machine-readable speaker labels.

---

## 4. Tuning knobs that matter for transcripts — and sane starting values

Transcripts are conversational: short sentences, speaker turns, highly variable turn length, topic drift within a session. Knobs that matter, with starting values:

| Knob | Where | Start value (transcripts) | Rationale |
|------|-------|---------------------------|-----------|
| `similarity_threshold` | Semantic | **0.5** (raise → more, smaller chunks; lower → fewer, larger) | Primary tuning dial. This is the thing that "needs tweaking." Sweep 0.4–0.7 and measure retrieval. |
| `chunk_size` (tokens) | Semantic | **300–500** (≈ a few turns) | Small enough for precise retrieval of a specific exchange, large enough to keep a Q→A pair together. |
| `similarity_window` | Semantic | **2–3** | Short conversational sentences: a small window reacts to real topic shifts without over-smoothing. |
| `delimiters` | Semantic | include **`"\n"`** | Makes speaker-turn line breaks first-class split points. |
| `min_sentences_per_chunk` | Semantic | **1** | Some turns are a single sentence ("Yes, exactly."). Don't force-merge unrelated turns. |
| `min_characters_per_sentence` | Semantic | **24** (default) | Filters filler/backchannel fragments. |
| `hard_cap_chars` | Fixed guardrail | **1500–2000** | Bounds worst-case chunk so an untuned threshold can't blow the embedder's context or wreck granularity. Keep comfortably above the char-equivalent of the token target. |
| `overlap` (cap re-split) | Fixed guardrail | **100–150 chars** | Small context bleed so a forced mid-monologue cut doesn't orphan a referent. Must be `< chunk_size`. |

Baseline-first tactic worth flagging: **`RecursiveChunking(chunk_size=~1500, overlap=150)` is a fast, deterministic, zero-embed-cost baseline.** Ship it, measure retrieval, then switch on the semantic hybrid and A/B. This de-risks the "semantic needs tuning" problem by giving a known-good reference point.

---

## 5. Interaction with per-domain embedding models & separate vector DBs

Plan: separate vector DBs per domain (legal, codebase, historical-timeline) with specialized embedders each. How chunking interacts:

- **Embedder is set on the vector DB, chunker on the reader — they are separate objects but must be reasoned about together.** In Agno, `PgVector(..., embedder=domain_embedder)` controls **store-time** embedding; the semantic chunker takes its **own** `embedder` for **boundary detection**. **Pass the same domain embedder to both** so semantic boundaries are computed in the same vector space the corpus is stored in. Using a generic embedder to chunk and a specialized one to store still works, but boundaries won't reflect the domain's notion of similarity.

- **Mixed embedding dimensions cannot share a store — hard constraint (matches the owner's standing rule).** `Embedder.dimensions` (base default 1536; `embedder/base.py`) must match the vector index width. Separate DBs per domain is the correct design precisely because legal/code/timeline embedders will differ in dimension and semantics. Re-embedding = rebuild the store; you cannot mix dims in one index.

- **Chunk strategy should vary by domain** (Agno's own "Choosing a Strategy" table, `chunking/overview`, corroborates):

  | Domain | Recommended chunker | Why |
  |--------|--------------------|-----|
  | **AI transcripts** (this project) | **Semantic + fixed hybrid** (turn-aware) | Conversational, variable-length turns, topic drift; meaning-coherent chunks with a runaway guard. |
  | **Legal** | Semantic (legal embedder) or Document | Long structured prose; preserve clause/section coherence. Consider `DocumentChunking` if the source has clean section structure. |
  | **Codebase** | **`CodeChunking`** (AST) | Splits at function/class boundaries; embeddings-agnostic, deterministic. Do **not** semantic-chunk code. Pair with a code embedder (e.g. codestral-embed). |
  | **Historical timeline** | `RowChunking` or `DocumentChunking` | If events are row/record structured, one event per chunk keeps dates/entities atomic. |

- **Embedder-choice caveats already in our house rules apply at chunk time too.** The owner's note about NIM asymmetric `embedqa` models (missing `input_type` → 400s; gateway-injected blanket `input_type` collapses retrieval margin) applies to the **semantic chunker's** embedder just as much as the store embedder — prefer **symmetric** models (`nv-embed-v1`, `bge-m3`, codestral-embed) for anything used at chunk time. Also: with an Agno `Embedder`, Chonkie's tokenizer is word-split, so `chunk_size` tokens ≈ words — don't expect model-accurate token accounting.

---

## 6. Recommendation — endorse or refine the owner's hybrid instinct

**Endorsed, with a sharpened rationale and one refinement.**

**The instinct is correct, but the stated reasoning slightly mis-frames *why*.** "Hybrid is better than pure semantic because semantic needs tuning" is true in outcome but the mechanism matters:

- Fixed does **not** reduce the need to tune semantic. You still tune `similarity_threshold` (and `chunk_size`) regardless.
- What fixed actually buys you is a **deterministic worst-case bound**. Pure semantic has two concrete failure modes on transcripts: (a) **runaway chunks** — a long monologue where similarity never drops below threshold becomes one enormous chunk that can exceed the embedder's context window and destroy retrieval granularity; and (b) **corpus-specific threshold sensitivity** — the "right" threshold differs by content, so an untuned pipeline produces erratic chunk sizes. A fixed hard-cap **neutralizes (a) immediately** and **de-risks (b)** by guaranteeing bounded chunks while you tune. So: **fixed is the safety net that lets you ship semantic before it's perfectly tuned.** That is a genuinely better starting posture than pure semantic — the owner is right.

**Refinements I recommend layering on:**
1. **Make it turn-aware** (3 layers, not 2): turn-boundary respect → semantic grouping (primary) → fixed char cap (guardrail). Cheap version = put `"\n"` in `delimiters`; strong version = explicit speaker-regex pre-split. Transcripts have structure that pure semantic ignores.
2. **Ship a `RecursiveChunking` baseline first**, measure, then A/B the hybrid. This directly answers "semantic needs tuning" by giving a zero-cost, deterministic reference to tune *against*.
3. **Drop Agentic** for bulk ingest (cost + non-determinism). Keep it only for tiny curated sets, if ever.
4. **Pass the domain embedder to the semantic chunker**, not a generic one, so boundaries live in the storage vector space.

Net: build the `SemanticFixedHybridChunking` custom strategy in §3, start at the §4 values, keep separate per-domain vector DBs with matched embedders (§5), and treat `similarity_threshold` + `chunk_size` as the live tuning surface with the fixed cap as the seatbelt.

---

## 7. Verified vs. inferred — and three docs bugs to avoid

**Verified from installed source (`agno==2.6.13`):** all class names, import paths, constructor signatures, default values, embedder/LLM requirements, and unit semantics in §1–§2 were read directly from the `.py` files cited. The `SemanticFixedHybridChunking` sketch uses only real, verified APIs (`ChunkingStrategy`, `SemanticChunking`, `FixedSizeChunking`, `Document`).

**Inferred (not machine-verified, flagged):** the specific starting values in §4 are reasoned from transcript characteristics + Agno's defaults, not benchmarked on our corpus — they are starting points to sweep, not settled numbers. The turn-aware pre-split's exact speaker regex depends on the actual transcript format (unseen here). The "roughly doubles ingest embedding load" figure for semantic is an order-of-magnitude characterization, not a measured multiplier.

**Three published-docs discrepancies that will break copy-paste against 2.6.13** (installed source is authoritative — use it):
1. **`RecursiveChunking(separators=[...])` does NOT exist.** The docs "Configuration" block (`knowledge/concepts/chunking/overview`) shows `RecursiveChunking(separators=["\n\n","\n",". "," "], chunk_size=4000)`. The installed `recursive.py` `__init__` accepts only `(chunk_size, overlap)` and has no `**kwargs` → passing `separators` raises `TypeError`. Use `RecursiveChunking(chunk_size=..., overlap=...)` only.
2. **Stale import paths in the Custom Chunking reference page.** `knowledge/concepts/chunking/custom-chunking` imports `from agno.knowledge.chunking.base import ChunkingStrategy` and `from agno.knowledge.content import Document`. Neither exists in 2.6.13. Correct paths (used in this report and in the live *example* page): `agno.knowledge.chunking.strategy.ChunkingStrategy` and `agno.knowledge.document.base.Document`.
3. **Wrong module names in a couple of doc snippets.** Some pages import `agno.knowledge.chunking.fixed_size_chunking` / `...semantic_chunking`. Installed module files are `fixed.py` / `semantic.py` → import from `agno.knowledge.chunking.fixed` and `agno.knowledge.chunking.semantic`.

---

### Source index
- Installed source (authoritative): `.venv/Lib/site-packages/agno/knowledge/chunking/{strategy,fixed,recursive,document,markdown,semantic,agentic,code,row}.py`; embedder base `.../knowledge/embedder/base.py`; version `agno-2.6.13.dist-info`.
- Live docs (agno-docs MCP): `knowledge/concepts/chunking/overview`, `.../semantic-chunking`, `.../fixed-size-chunking`, `.../recursive-chunking`, `.../document-chunking`, `.../markdown-chunking`, `.../agentic-chunking`, `.../code-chunking`, `.../csv-row-chunking`, `.../custom-chunking`, `knowledge/concepts/performance-tips`, `examples/knowledge/chunking/custom-strategy-example`.

---

## 8. Chonkie direct integration — decision + verified state (2026-08-10)

> _Section byline: Claude Code · Opus 4.8 · 2026-08-10._ Owner directive this session: wrap Chonkie
> directly (not only the 2 chunkers Agno surfaces) and build it into the platform, with a
> CPU-friendly-local / heavy-remote split. GUI claim was checked and **corrected**: Chonkie has NO
> GUI — its `Visualizer` is a terminal (Rich console) component. Chonkie ships a REST API
> (`chonkie[api]`), so **any GUI we want, we build ourselves** on that API (or surface chunk
> previews in the SBV GUI, which already exists per ADR-0049).

### 8.1 Verified install (torch-free)

`uv pip install "chonkie[semantic,code,table]"` → **chonkie 1.7.0**, 18 packages, **NO torch /
nvidia / transformers** (confirmed via `uv pip list`). Semantic embeddings come from **model2vec**
(static, numpy-based `potion` models) — CPU-fast, no torch. Runtime smoke test passed torch-free:
`RecursiveChunker`, `SentenceChunker`, and `SemanticChunker` (model2vec potion-base-8M, auto-
downloaded once, cached) all produced chunks on a transcript snippet.

### 8.2 Execution split — the load-bearing decision

Chonkie 1.7.0 ships **11 chunkers**. All classes *import* torch-free; the heavy ones only need their
backend at **runtime** (instantiation/inference). Split accordingly:

| Chunker | Where it runs | Backend |
|---|---|---|
| `SemanticChunker` (model2vec), `RecursiveChunker`, `SentenceChunker`, `TokenChunker`, `FastChunker`, `CodeChunker` (tree-sitter), `TableChunker` | **LOCAL, in-process** | torch-free |
| `NeuralChunker` (BERT) | **REMOTE MCP** (Colab now; scale-to-zero GPU rental e.g. RunPod as durable) | torch/transformers |
| `LateChunker` | **REMOTE MCP** | long-context embedder |
| `SlumberChunker` (LLM/agentic) | **REMOTE MCP** or skip for bulk | LLM (cost/non-deterministic — §2/§6: out for bulk ingest) |
| `TeraflopAIChunker` | external TeraflopAI API | not ours; skip unless needed |

**Rationale:** CPU-only box (hardware constraint) — never install torch locally just to have it
importable. The heavy inference power (Neural/Late + other future ML) is rented on demand and
driven over MCP, scale-to-zero so it costs nothing idle.

### 8.3 Build plan

1. **Local wrappers** — `server/analysis/chonkie_chunkers.py`: each CPU-friendly Chonkie chunker
   wrapped as a custom Agno `ChunkingStrategy` (subclass, implement `chunk()`), following the §3
   pattern. Re-verify the Agno base-class signature against the LIVE version (platform is agno
   **2.8.x**; this report's §1 was verified on 2.6.13 — classes still present, confirm ctor args).
2. **`chonkie[api]` as an MCP tool** — stand up Chonkie's REST API, wrap as an MCP server (use the
   `mcp-server-dev:build-mcp-server` skill) so chunking is callable CLI→MCP→agents (platform
   contract). This is also the seam a future custom GUI would call.
3. **Remote heavy executor** — a Colab notebook (driven via MCP) for Neural/Late now; design a
   scale-to-zero GPU rental (RunPod or similar) as the durable path, shared with other inference
   needs. The local wrappers for heavy chunkers become thin MCP clients to this executor.
4. **requirements.txt** — add `chonkie[semantic,code,table]` to the PROD lockfile (torch-free);
   heavy chunkers are NOT added to the prod image (they live remote).
5. **Preview** — chunk previews surface in the SBV GUI (ADR-0049 parse+preview), or a custom GUI
   on the Chonkie REST API.

### 8.4 Related follow-up

**Docling** (owner flagged "probably need docling"): a separate library (document → markdown:
PDF/DOCX/PPTX/XLSX). Not Chonkie. It has its own heavier deps and overlaps the doc-processing
mega-plugin target. Track as its own decision; do NOT fold into the Chonkie install.

### 8.5 Where chunking sits in the pipeline (ties to ADR-0051)

Chunking is the **head of Stage 2 (extraction)**, after SBV parse+preview → PG, triggered by PG
change-detection: `segment (turn-aware) → CHUNK (Chonkie semantic+fixed) → multipass classify →
lane → Semantica extract → Graphiti timeline → 6 lanes`. The chunk is the unit the **multipass
classifier routes to lanes** AND the unit stored/retrieved — so chunk quality directly sets
lane-routing quality (the segment→lane step the current stopgap lacks, per D-045).
