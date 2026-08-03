"""server/core/model_registry.py — turn the verified model catalog into live
agno ``Model`` instances for the AgentOS **Registry**.

WHY THIS EXISTS
---------------
The os.agno.com Studio model picker offered exactly one model. Two different
agno surfaces were being confused:

* ``GET /models`` (``agno/os/router.py::get_models``, identical in 2.8.0 and
  2.8.6) reports the DISTINCT models already attached to registered agents and
  teams. It is a *usage report*, not a catalog — every one of our 6 agents and
  3 teams shares the single object returned by ``build_model()``, so the set
  collapses to one entry. There is no config-driven path into it, and growing
  it would mean attaching junk agents to the roster the user sees.
* ``GET /registry?resource_type=model`` (``agno/os/routers/registry/``) serves
  ``Registry.models``. Per the docs, Studio's agent builder shows "Model:
  select from registered models" (docs.agno.com /agent-os/studio/agents) and
  the Registry is documented as the home for "model provider instances" that
  "Studio depends on" (/agent-os/studio/registry). THAT is the supported,
  documented picker source, and it is what this module feeds.

``AgentOSConfig.available_models`` (``server/api/config.yaml``, rendered by
``/config``) stays the single source of truth for WHICH models are offered —
it is the list ``scripts/update_available_models.py`` writes after probing
each candidate with a real 1-token completion. This module reads that same
list and instantiates it, so the two surfaces can never drift apart.

Nothing here changes model SELECTION: ``build_model()`` still resolves the
default per ADR-0008's provider chain. This is purely additive catalog
plumbing.

Byline: Claude Code · Fable 5 · 2026-08-02
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from agno.utils.log import log_info, log_warning

from server.core.settings import build_model

# Providers this platform can construct from a catalog string. Everything the
# ``build_model()`` chain knows about — an entry naming anything else is
# skipped with a warning rather than crashing the boot path.
KNOWN_PROVIDERS: frozenset[str] = frozenset(
    {"ollama", "nvidia", "kimi", "openrouter", "anthropic", "openai", "google", "groq"}
)


def parse_model_string(entry: str) -> Optional[tuple[str, str]]:
    """Split a ``"<provider>:<model-id>"`` catalog entry.

    Splits on the FIRST colon only: Ollama tags legitimately contain colons
    (``ollama:deepseek-v4-flash:0731`` -> ``("ollama", "deepseek-v4-flash:0731")``)
    and NVIDIA ids use slashes (``nvidia:meta/llama-3.3-70b-instruct``).

    Parameters
    ----------
    entry:
        A catalog string from ``AgentOSConfig.available_models``.

    Returns
    -------
    tuple[str, str] | None
        ``(provider, model_id)``, or ``None`` when the entry is malformed or
        names a provider this platform cannot construct.
    """
    if not entry or ":" not in entry:
        return None
    provider, _, model_id = entry.partition(":")
    provider = provider.strip().lower()
    model_id = model_id.strip()
    if not model_id or provider not in KNOWN_PROVIDERS:
        return None
    return provider, model_id


def load_available_models(config_path: Path) -> list[str]:
    """Read ``available_models`` out of the AgentOS config YAML.

    Returns an empty list — never raises — if the file is missing,
    unparseable, or has no ``available_models`` key. The registry is a
    convenience surface and must not be able to crash-loop the boot path.
    """
    try:
        import yaml

        with open(config_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:  # pragma: no cover - defensive boot guard
        log_warning(f"model_registry: could not read {config_path}: {exc}")
        return []
    entries = data.get("available_models") or []
    return [e for e in entries if isinstance(e, str)]


def build_catalog_models(entries: Iterable[str]) -> list[Any]:
    """Instantiate one agno model object per catalog entry.

    Entries whose provider has no credentials in this environment (or which
    are malformed) are skipped — the Studio picker should only offer models
    this deployment can actually call.

    Parameters
    ----------
    entries:
        ``"<provider>:<model-id>"`` strings, e.g. from
        ``AgentOSConfig.available_models``.

    Returns
    -------
    list[Any]
        Configured agno model instances, de-duplicated on
        ``(provider, model_id)``, in catalog order.
    """
    models: list[Any] = []
    seen: set[tuple[str, str]] = set()
    skipped: list[str] = []

    for entry in entries:
        parsed = parse_model_string(entry)
        if parsed is None:
            skipped.append(entry)
            continue
        if parsed in seen:
            continue
        provider, model_id = parsed
        try:
            model = build_model(provider=provider, model_id=model_id)
        except Exception as exc:
            # Missing credentials raise ValueError out of build_model(); any
            # other construction failure is equally non-fatal here.
            skipped.append(f"{entry} ({type(exc).__name__})")
            continue
        seen.add(parsed)
        models.append(model)

    if skipped:
        log_warning(f"model_registry: skipped {len(skipped)} catalog entries: {', '.join(skipped[:10])}")
    log_info(f"model_registry: registered {len(models)} models for the Studio picker")
    return models
