"""
evidence — the completed Part-1 spine (plans/logical-herding-forest.md P2).

custody  : the single entry gate (hash -> evidence row -> write-once blob)
normalize: canonical record schema (bitemporal: valid/knowledge time + tier)
store    : normalized records -> analysis schema (+ knowledge engine ingest)
workflows: named workflows on native agno.workflow (custody-gated verticals)
cli      : `python -m evidence ...`

registry + atomic parser tools live in server/tools/ (D-026) — a cross-domain
capability layer, not owned by the evidence spine (evidence/analysis/agents/
workflows/CLI all consume it). `registry` and `ToolRegistry` remain re-exported
here (lazily) for backward compatibility.

Evidence is immutable: ONLY custody.py writes the `evidence` schema, append-only.
Everything derived lands in `analysis` or the knowledge engine.

Imports are LAZY (PEP 562) so light consumers (the tools-facade container)
can use registry+parsers without dragging sqlalchemy/agno into their runtime.
"""

from typing import Any

__all__ = [
    "ArtifactRef",
    "DisclosureTier",
    "NormalizedRecord",
    "ToolRegistry",
    "ingest_artifact",
    "registry",
]

_LAZY = {
    "ArtifactRef": ("server.evidence.custody", "ArtifactRef"),
    "ingest_artifact": ("server.evidence.custody", "ingest_artifact"),
    "DisclosureTier": ("server.evidence.normalize", "DisclosureTier"),
    "NormalizedRecord": ("server.evidence.normalize", "NormalizedRecord"),
    "ToolRegistry": ("server.tools.registry", "ToolRegistry"),
    "registry": ("server.tools.registry", "registry"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module, attr = _LAZY[name]
        return getattr(importlib.import_module(module), attr)
    raise AttributeError(f"module 'evidence' has no attribute {name!r}")
