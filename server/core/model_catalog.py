"""server/core/model_catalog.py — live-enumerated model catalog for the
DIRECT provider chain (Ollama Cloud, NVIDIA NIM).

Captured 2026-08-01 via ``scripts/verify_direct_providers.py`` (real
``GET /api/tags`` / ``GET /v1/models`` calls, not a guess). This is a
SNAPSHOT, not derived at import time — resolving a model list on every agent
boot would add a network dependency (and a new failure mode) to process
startup. Re-run the verify script and paste the fresh lists in here when the
account's catalog changes; nothing else in this module needs to change.

This is pure DATA plus small classification helpers. ``server/core/settings.py``
owns model SELECTION (ADR-0008's priority-chain/override resolution) and is
NOT restructured by this module — ``available_models()`` here is an additive
lookup a caller (e.g. a future UI model picker, or a validation check before
setting ``<PROVIDER>_MODEL_ID``) can use; it does not change which model
``build_model()`` picks by default.

Byline: Claude Code · Sonnet (agent) · 2026-08-01
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Ollama Cloud — GET https://ollama.com/api/tags, Bearer OLLAMA_API_KEY.
# 18 models, key verified live (chat probe against glm-5.1: HTTP 200, "OK").
# ---------------------------------------------------------------------------

OLLAMA_CLOUD_MODELS: list[str] = [
    "deepseek-v4-flash",
    "deepseek-v4-flash:0731",
    "deepseek-v4-pro",
    "gemma4:31b",
    "glm-5.1",
    "glm-5.2",
    "gpt-oss:120b",
    "gpt-oss:20b",
    "kimi-k2.6",
    "kimi-k2.7-code",
    "kimi-k3",
    "minimax-m2.7",
    "minimax-m3",
    "mistral-large-3:675b",
    "nemotron-3-nano:30b",
    "nemotron-3-super",
    "nemotron-3-ultra",
    "qwen3.5:397b",
]

# Platform rule (verified empirically 2026-07-04, CLAUDE.md): glm-5.1 cannot
# emit JSON-schema-conformant structured output (markdown fences / wrong
# keys, fails retries). NEVER route schema-constrained workloads (entity
# extraction, structured tool args) to any model in this set.
#
# glm-5.2 is glm-5.1's same-family successor and has NOT itself been
# empirically verified as of this catalog snapshot — included here on family
# resemblance as a caution flag, not a confirmed failure. Verify before
# trusting it with structured output; do not silently assume it's fixed.
OLLAMA_NON_STRUCTURED_OUTPUT_MODELS: frozenset[str] = frozenset({"glm-5.1", "glm-5.2"})


# ---------------------------------------------------------------------------
# NVIDIA NIM — GET https://integrate.api.nvidia.com/v1/models, Bearer
# NVIDIA_API_KEY. 102 models total, key verified live (chat probe against
# nvidia/nemotron-3-super-120b-a12b: HTTP 200, real completion text).
#
# Chat/embed split is a heuristic substring match on the id ("embed" in id)
# — NIM's /v1/models response doesn't self-describe model type. See the
# correction sets below for ids that slip through the heuristic.
# ---------------------------------------------------------------------------

NVIDIA_NIM_CHAT_MODELS: list[str] = [
    "01-ai/yi-large",
    "adept/fuyu-8b",
    "ai21labs/jamba-1.5-large-instruct",
    "aisingapore/sea-lion-7b-instruct",
    "baai/bge-m3",
    "bigcode/starcoder2-15b",
    "databricks/dbrx-instruct",
    "deepseek-ai/deepseek-coder-6.7b-instruct",
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-pro",
    "google/codegemma-1.1-7b",
    "google/codegemma-7b",
    "google/deplot",
    "google/diffusiongemma-26b-a4b-it",
    "google/gemma-2b",
    "google/gemma-3-12b-it",
    "google/gemma-3-4b-it",
    "google/gemma-4-31b-it",
    "google/recurrentgemma-2b",
    "ibm/granite-3.0-3b-a800m-instruct",
    "ibm/granite-3.0-8b-instruct",
    "ibm/granite-34b-code-instruct",
    "ibm/granite-8b-code-instruct",
    "meta/codellama-70b",
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-1b-instruct",
    "meta/llama-3.2-3b-instruct",
    "meta/llama-3.2-90b-vision-instruct",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-guard-4-12b",
    "meta/llama2-70b",
    "microsoft/kosmos-2",
    "microsoft/phi-3-vision-128k-instruct",
    "microsoft/phi-3.5-moe-instruct",
    "minimaxai/minimax-m3",
    "mistralai/codestral-22b-instruct-v0.1",
    "mistralai/mistral-7b-instruct-v0.3",
    "mistralai/mistral-large",
    "mistralai/mistral-large-2-instruct",
    "mistralai/mistral-medium-3.5-128b",
    "mistralai/mistral-nemotron",
    "mistralai/mixtral-8x22b-v0.1",
    "moonshotai/kimi-k2.6",
    "nv-mistralai/mistral-nemo-12b-instruct",
    "nvidia/ai-synthetic-video-detector",
    "nvidia/cosmos-reason2-8b",
    "nvidia/ising-calibration-1.5-31b",
    "nvidia/llama-3.1-nemoguard-8b-content-safety",
    "nvidia/llama-3.1-nemoguard-8b-topic-control",
    "nvidia/llama-3.1-nemotron-51b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/llama-3.1-nemotron-nano-8b-v1",
    "nvidia/llama-3.1-nemotron-nano-vl-8b-v1",
    "nvidia/llama-3.1-nemotron-safety-guard-8b-v3",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "nvidia/llama3-chatqa-1.5-70b",
    "nvidia/mistral-nemo-minitron-8b-8k-instruct",
    "nvidia/nemoretriever-parse",
    "nvidia/nemotron-3-nano-30b-a3b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3.5-content-safety",
    "nvidia/nemotron-4-340b-instruct",
    "nvidia/nemotron-4-340b-reward",
    "nvidia/nemotron-mini-4b-instruct",
    "nvidia/nemotron-nano-12b-v2-vl",
    "nvidia/nemotron-nano-3-30b-a3b",
    "nvidia/nemotron-parse",
    "nvidia/neva-22b",
    "nvidia/nvclip",
    "nvidia/nvidia-nemotron-nano-9b-v2",
    "nvidia/riva-translate-4b-instruct",
    "nvidia/riva-translate-4b-instruct-v1.1",
    "nvidia/riva-translate-4b-instruct-v2",
    "nvidia/vila",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "poolside/laguna-xs-2.1",
    "stepfun-ai/step-3.7-flash",
    "thinkingmachines/inkling",
    "writer/palmyra-creative-122b",
    "writer/palmyra-fin-70b-32k",
    "writer/palmyra-med-70b",
    "writer/palmyra-med-70b-32k",
    "z-ai/glm-5.2",
    "zyphra/zamba2-7b-instruct",
]

NVIDIA_NIM_EMBED_MODELS: list[str] = [
    "nvidia/embed-qa-4",
    "nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1",
    "nvidia/llama-3.2-nv-embedqa-1b-v1",
    "nvidia/llama-nemotron-embed-1b-v2",
    "nvidia/llama-nemotron-embed-vl-1b-v2",
    "nvidia/nemotron-3-embed-1b",
    "nvidia/nv-embed-v1",
    "nvidia/nv-embedcode-7b-v1",
    "nvidia/nv-embedqa-e5-v5",
    "nvidia/nv-embedqa-mistral-7b-v2",
    "snowflake/arctic-embed-l",
]

# NIM's rerank models (NVIDIA_RERANK_ID / NVIDIA_RERANK_URL in settings.py's
# docstring) don't show up in this /v1/models listing at all — reranking is
# served from a distinct NIM endpoint, not the OpenAI-compatible
# chat/embeddings base_url. 0 matches here is expected, not a bug.
NVIDIA_NIM_RERANK_MODELS: list[str] = []

# ids in NVIDIA_NIM_CHAT_MODELS that the "embed" substring heuristic missed —
# these are embedders/encoders, not general chat models, despite landing in
# the chat bucket above.
NVIDIA_CHAT_BUCKET_MISCLASSIFIED_AS_CHAT: frozenset[str] = frozenset(
    {
        "baai/bge-m3",  # text embedder (former platform default before nv-embed-v1)
        "nvidia/nvclip",  # CLIP-style image+text embedder
    }
)

# ids in NVIDIA_NIM_CHAT_MODELS that ARE chat-completions-callable but are
# special-purpose (moderation/guard/reward/parse/translate), not
# general-purpose chat/instruct models — surfaced separately so a model
# picker doesn't offer them as generic chat options.
NVIDIA_CHAT_BUCKET_SPECIAL_PURPOSE: frozenset[str] = frozenset(
    {
        "meta/llama-guard-4-12b",
        "nvidia/llama-3.1-nemoguard-8b-content-safety",
        "nvidia/llama-3.1-nemoguard-8b-topic-control",
        "nvidia/llama-3.1-nemotron-safety-guard-8b-v3",
        "nvidia/nemotron-3.5-content-safety",
        "nvidia/nemotron-4-340b-reward",
        "nvidia/nemoretriever-parse",
        "nvidia/nemotron-parse",
        "nvidia/riva-translate-4b-instruct",
        "nvidia/riva-translate-4b-instruct-v1.1",
        "nvidia/riva-translate-4b-instruct-v2",
        "google/deplot",
    }
)

# Embedder symmetry — owner rule (CLAUDE.md, verified 2026-07-04): asymmetric
# NIM embedqa models silently collapse retrieval margin (~3.5x, measured
# 0.33->0.09) for clients that can't send `input_type` per call. NEVER pick
# one of these for a symmetric-embedding use case without also sending
# `input_type` on every call.
#
# `nvidia/llama-nemotron-embed-vl-1b-v2` is explicitly called out as
# asymmetric in server/core/settings.py's own module docstring (the legacy
# NIM-fallback text embedder) — carried forward here rather than re-derived.
NVIDIA_ASYMMETRIC_EMBED_MODELS: frozenset[str] = frozenset(
    {
        "nvidia/embed-qa-4",
        "nvidia/llama-3.2-nv-embedqa-1b-v1",
        "nvidia/nv-embedqa-e5-v5",
        "nvidia/nv-embedqa-mistral-7b-v2",
        "nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1",
        "nvidia/llama-nemotron-embed-vl-1b-v2",
    }
)

# Symmetric (safe default, no per-call input_type requirement). Current LIVE
# contract per ADR-0040 / server/core/session.py: nvidia/nv-embed-v1 (4096-d).
NVIDIA_SYMMETRIC_EMBED_MODELS: frozenset[str] = frozenset(NVIDIA_NIM_EMBED_MODELS) - NVIDIA_ASYMMETRIC_EMBED_MODELS


# ---------------------------------------------------------------------------
# Lookup helpers — additive only. Does not change build_model()'s selection
# behavior in settings.py.
# ---------------------------------------------------------------------------


def available_models(provider: str) -> list[str]:
    """Return the known model ids for *provider* from this catalog snapshot.

    Parameters
    ----------
    provider:
        ``"ollama"`` or ``"nvidia"`` (chat models only for nvidia — see
        ``available_embed_models`` for the embedding-model list).

    Returns
    -------
    list[str]
        Model ids, or an empty list for an unrecognized/unenumerated
        provider (e.g. providers without a stable public listing endpoint).
    """
    if provider == "ollama":
        return list(OLLAMA_CLOUD_MODELS)
    if provider == "nvidia":
        return list(NVIDIA_NIM_CHAT_MODELS)
    return []


def available_embed_models(provider: str) -> list[str]:
    """Return known embedding-model ids for *provider* from this snapshot."""
    if provider == "nvidia":
        return list(NVIDIA_NIM_EMBED_MODELS)
    return []


def structured_output_capable(provider: str, model_id: str) -> bool:
    """Whether *model_id* is known-safe for schema-constrained workloads
    (entity extraction, structured tool args).

    Only encodes a NEGATIVE list (known-bad models) — returns True for
    anything not explicitly flagged, since most models are fine and this
    catalog can't exhaustively verify every id. Check
    ``OLLAMA_NON_STRUCTURED_OUTPUT_MODELS`` directly if you need the
    reverse (only known-good).
    """
    if provider == "ollama" and model_id in OLLAMA_NON_STRUCTURED_OUTPUT_MODELS:
        return False
    return True


def is_symmetric_embedder(model_id: str) -> bool:
    """Whether *model_id* is safe to use WITHOUT sending `input_type` on
    every call. False for known-asymmetric NIM embedqa-family models."""
    return model_id not in NVIDIA_ASYMMETRIC_EMBED_MODELS
