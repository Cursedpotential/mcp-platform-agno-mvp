"""llm_probe/probes.py — the actual model-calling logic: one low-level
`call_model` that exposes every knob (max_tokens, temperature,
reasoning_effort, tools) plus a handful of named, scored probes built on top
of it (liveness / tool_use / summarization / instruction_following) that
mirror the harness this service replaces.

`reasoning_effort` is the fix for the "some models return nothing / get
truncated" class of bug found while probing Google's reasoning-enabled
Gemini models by hand: several providers (Google, and reasoning-tuned models
on NIM/Ollama Cloud/OpenRouter) spend part of `max_tokens` on a hidden
"thinking" pass before the visible answer. Passing `reasoning_effort="none"`
(supported by Google's OpenAI-compat layer; harmlessly ignored by providers
that don't have the concept) eliminates that overhead outright instead of
just padding the token budget and hoping.

Byline: Claude Code · Sonnet 5 · 2026-08-27
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

import httpx

from .providers import get_provider


async def call_model(
    provider: str,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int = 500,
    temperature: float = 0,
    reasoning_effort: Optional[str] = None,
    top_p: Optional[float] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[str] = None,
    timeout: float = 60,
) -> dict[str, Any]:
    p = get_provider(provider)
    if not p.api_key:
        return {"http_ok": False, "status": None, "latency_s": 0.0, "error": f"no API key configured for {provider}",
                "content": None, "tool_calls": None, "usage": None, "raw": None}

    url = f"{p.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {p.api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort
    if top_p is not None:
        body["top_p"] = top_p
    if presence_penalty is not None:
        body["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        body["frequency_penalty"] = frequency_penalty
    if tools is not None:
        body["tools"] = tools
        body["tool_choice"] = tool_choice or "auto"

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=body, timeout=timeout)
        latency = round(time.monotonic() - t0, 2)
        if r.status_code != 200:
            return {"http_ok": False, "status": r.status_code, "latency_s": latency, "error": r.text[:1000],
                    "content": None, "tool_calls": None, "usage": None, "raw": None}
        data = r.json()
        msg = data.get("choices", [{}])[0].get("message", {})
        return {
            "http_ok": True, "status": 200, "latency_s": latency, "error": None,
            "content": msg.get("content"),
            "tool_calls": msg.get("tool_calls"),
            "usage": data.get("usage"),
            "raw": data,
        }
    except Exception as e:
        return {"http_ok": False, "status": None, "latency_s": round(time.monotonic() - t0, 2), "error": repr(e),
                "content": None, "tool_calls": None, "usage": None, "raw": None}


def reasoning_overhead_tokens(usage: Optional[dict]) -> Optional[int]:
    """completion+prompt should equal total; anything extra is hidden reasoning.
    Returns None if usage wasn't returned at all."""
    if not usage:
        return None
    total = usage.get("total_tokens")
    completion = usage.get("completion_tokens")
    prompt = usage.get("prompt_tokens")
    if total is None or completion is None or prompt is None:
        return None
    return max(0, total - completion - prompt)


# ---------------------------------------------------------------------------
# Named, scored probes — same prompts/scoring as the original harness.
# ---------------------------------------------------------------------------

LIVENESS_PROMPT = "Are you operational? Reply with only the single word YES or NO. No punctuation, no explanation."

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_case_status",
        "description": "Look up the current status of a legal case by its docket number.",
        "parameters": {
            "type": "object",
            "properties": {
                "docket_number": {"type": "string", "description": "The docket number, e.g. 24-CV-1187"},
                "include_history": {"type": "boolean", "description": "Whether to include full status history"},
            },
            "required": ["docket_number"],
        },
    },
}
TOOL_PROMPT = "What is the current status of case 24-CV-1187? Use the get_case_status tool to find out."

SUMMARY_SOURCE = (
    "The Riverton County Family Court issued a temporary custody order on March 14, 2026, "
    "granting the petitioner, Maria Alvarez, primary physical custody of the two minor children "
    "pending a full evidentiary hearing scheduled for June 2, 2026. The order requires the "
    "respondent, David Alvarez, to complete a court-mandated parenting class within 60 days and "
    "restricts overnight visitation until a supervised-visitation report is filed by the "
    "court-appointed guardian ad litem, Sandra Kwan. Both parties are barred from discussing the "
    "litigation with the children and must attend mediation on April 20, 2026, before the next "
    "hearing. Violation of any provision may result in a finding of contempt."
)
SUMMARY_PROMPT = f"Summarize the following in exactly one sentence:\n\n{SUMMARY_SOURCE}"
SUMMARY_KEY_FACTS = ["march 14", "alvarez", "custody", "june 2", "parenting class", "mediation", "april 20", "guardian ad litem"]

INSTRUCTION_PROMPT = (
    "Output exactly five words describing a courtroom, separated by single spaces, "
    "all lowercase, no punctuation, nothing else before or after."
)

PROBE_CATALOG = {
    "liveness": {"prompt": LIVENESS_PROMPT, "description": "Does the model respond at all, in the requested yes/no format?"},
    "tool_use": {"prompt": TOOL_PROMPT, "description": "Given one function schema, does it emit a correctly shaped tool call?"},
    "summarization": {"prompt": SUMMARY_PROMPT, "description": "Compress a dense paragraph into one factual sentence."},
    "instruction_following": {"prompt": INSTRUCTION_PROMPT, "description": "Exact word count / casing / punctuation constraint."},
}

# Retry-time prompt variants. Rewording only — the underlying rubric each
# probe is scored against (SUMMARY_KEY_FACTS, the tool schema, the 5-word
# format check) stays fixed, so a variant is still a fair like-for-like
# retry, just phrased differently in case the original wording is what a
# particular model is tripping on (verbose preamble, ignoring "exactly",
# reasoning models over-explaining, etc).
PROMPT_VARIANTS: dict[str, list[dict[str, str]]] = {
    "liveness": [
        {"key": "default", "label": "Default", "prompt": LIVENESS_PROMPT},
        {"key": "terse", "label": "Terser", "prompt": "Respond with exactly one word: YES."},
        {"key": "direct", "label": "Direct question", "prompt": "Can you process this message? Answer YES or NO only."},
    ],
    "tool_use": [
        {"key": "default", "label": "Default", "prompt": TOOL_PROMPT},
        {"key": "imperative", "label": "Imperative", "prompt": "Call the get_case_status tool for docket 24-CV-1187 now."},
        {"key": "no_hint", "label": "No tool hint", "prompt": "What is the current status of case 24-CV-1187?"},
    ],
    "summarization": [
        {"key": "default", "label": "Default", "prompt": SUMMARY_PROMPT},
        {"key": "no_preamble", "label": "No preamble", "prompt": f"Respond with ONLY one sentence summarizing this, nothing else before or after:\n\n{SUMMARY_SOURCE}"},
        {"key": "compress", "label": "Compress hard", "prompt": f"In as few words as possible (one sentence, under 40 words), capture every key fact of:\n\n{SUMMARY_SOURCE}"},
    ],
    "instruction_following": [
        {"key": "default", "label": "Default", "prompt": INSTRUCTION_PROMPT},
        {"key": "numbered", "label": "Numbered reminder", "prompt": "Output exactly 5 words (count them) describing a courtroom. Lowercase, space-separated, no punctuation, no other text."},
    ],
}

RETRY_PRESETS = [
    {"key": "same", "label": "Same as before"},
    {"key": "no_reasoning", "label": "reasoning_effort=none"},
    {"key": "bigger_budget", "label": "3x max_tokens"},
    {"key": "no_reasoning_bigger_budget", "label": "reasoning_effort=none + 3x budget"},
]


def score_liveness(content: Optional[str]) -> tuple[bool, dict]:
    ok = bool(content and content.strip())
    followed = (content or "").strip().upper() in ("YES", "NO", "YES.", "NO.")
    return ok, {"content": content, "followed_format": followed}


def score_tool_use(tool_calls: Optional[list], content: Optional[str]) -> tuple[bool, dict]:
    if not tool_calls:
        return False, {"reason": "no tool_calls emitted", "content": content}
    call = tool_calls[0]
    fn = call.get("function", {})
    if fn.get("name") != "get_case_status":
        return False, {"reason": f"wrong function name: {fn.get('name')}"}
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except json.JSONDecodeError:
        return False, {"reason": "arguments not valid JSON", "raw": fn.get("arguments")}
    if "docket_number" not in args:
        return False, {"reason": "missing required arg docket_number", "args": args}
    return True, {"args": args}


def score_summary(content: Optional[str]) -> tuple[bool, dict]:
    if not content or not content.strip():
        return False, {"reason": "empty response"}
    c = content.strip()
    words = len(c.split())
    hits = [f for f in SUMMARY_KEY_FACTS if f in c.lower()]
    missed = [f for f in SUMMARY_KEY_FACTS if f not in c.lower()]
    sentence_like = c.count(".") <= 2
    ok = words < 130 and len(hits) >= 3 and sentence_like
    return ok, {"word_count": words, "key_facts_hit": len(hits), "hits": hits, "missed": missed,
                "sentence_like": sentence_like, "content": c}


def score_instruction(content: Optional[str]) -> tuple[bool, dict]:
    if not content:
        return False, {"reason": "empty response"}
    c = content.strip()
    words = c.split(" ")
    ok = len(words) == 5 and c == c.lower() and not re.search(r'[.,!?;:"]', c) and "\n" not in c
    return ok, {"content": c, "word_count": len(words)}


async def run_named_probe(
    provider: str, model: str, probe: str, *,
    max_tokens: int = 500, temperature: float = 0, reasoning_effort: Optional[str] = None,
    top_p: Optional[float] = None, presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None, prompt_override: Optional[str] = None,
) -> dict[str, Any]:
    if probe not in PROBE_CATALOG:
        raise ValueError(f"unknown probe {probe!r}; known: {list(PROBE_CATALOG)}")

    prompt = prompt_override or PROBE_CATALOG[probe]["prompt"]
    extra = {}
    if probe == "tool_use":
        extra = {"tools": [TOOL_SCHEMA], "tool_choice": "auto"}

    result = await call_model(
        provider, model, [{"role": "user", "content": prompt}],
        max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort,
        top_p=top_p, presence_penalty=presence_penalty, frequency_penalty=frequency_penalty, **extra,
    )
    if not result["http_ok"]:
        return {"probe": probe, "ok": False, "latency_s": result["latency_s"], "reason": "http_error",
                "error": result["error"], "usage": result["usage"], "reasoning_overhead_tokens": None}

    if probe == "liveness":
        ok, detail = score_liveness(result["content"])
    elif probe == "tool_use":
        ok, detail = score_tool_use(result["tool_calls"], result["content"])
    elif probe == "summarization":
        ok, detail = score_summary(result["content"])
    else:
        ok, detail = score_instruction(result["content"])

    return {
        "probe": probe, "ok": ok, "latency_s": result["latency_s"], "usage": result["usage"],
        "reasoning_overhead_tokens": reasoning_overhead_tokens(result["usage"]),
        "prompt_used": prompt, "max_tokens_used": max_tokens, "reasoning_effort_used": reasoning_effort,
        **detail,
    }


async def run_custom_prompt(
    provider: str, model: str, prompt: str, *,
    max_tokens: int = 500, temperature: float = 0, reasoning_effort: Optional[str] = None,
    top_p: Optional[float] = None, presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
) -> dict[str, Any]:
    """Playground mode: no scoring, just the raw call plus reasoning-overhead
    visibility so a user can see what a param change actually did."""
    result = await call_model(
        provider, model, [{"role": "user", "content": prompt}],
        max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort,
        top_p=top_p, presence_penalty=presence_penalty, frequency_penalty=frequency_penalty,
    )
    result["reasoning_overhead_tokens"] = reasoning_overhead_tokens(result.get("usage"))
    return result


async def stream_custom_prompt(
    provider: str, model: str, prompt: str, *,
    max_tokens: int = 500, temperature: float = 0, reasoning_effort: Optional[str] = None,
    top_p: Optional[float] = None, presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
):
    """Playground streaming mode — yields plain text deltas as they arrive
    from the provider's own SSE stream, for the frontend's Vercel AI SDK
    `useCompletion({streamProtocol: 'text'})` consumer. All providers here
    speak OpenAI-compatible SSE: `data: {...}\\n\\n` chunks with
    `choices[0].delta.content`, terminated by `data: [DONE]`.

    Yields the FIRST chunk's usage-derived reasoning-overhead marker as a
    special `\\x00REASONING:<n>\\x00` sentinel is deliberately NOT done here —
    streaming responses don't reliably include usage until the final chunk
    (and several providers omit it in streaming mode entirely), so overhead
    visibility stays a non-streaming (`run_custom_prompt`) feature.
    """
    p = get_provider(provider)
    if not p.api_key:
        yield f"[no API key configured for {provider}]"
        return

    url = f"{p.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {p.api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": temperature, "stream": True,
    }
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort
    if top_p is not None:
        body["top_p"] = top_p
    if presence_penalty is not None:
        body["presence_penalty"] = presence_penalty
    if frequency_penalty is not None:
        body["frequency_penalty"] = frequency_penalty

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=body, timeout=120) as r:
                if r.status_code != 200:
                    err = await r.aread()
                    yield f"[http {r.status_code}: {err.decode(errors='replace')[:500]}]"
                    return
                async for line in r.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        yield text
    except Exception as e:
        yield f"[stream error: {e!r}]"
