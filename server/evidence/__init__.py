"""
evidence — the completed Part-1 spine (plans/logical-herding-forest.md P2).

custody  : the single entry gate (hash -> evidence row -> write-once blob)
registry : atomic-tool registry (capability-based resolution + substitution)
normalize: canonical record schema (bitemporal: valid/knowledge time + tier)
store    : normalized records -> analysis schema (+ knowledge engine ingest)
workflows: named workflows on native agno.workflow (custody-gated verticals)
tools    : atomic parser modules — ONE PER FORMAT, swappable units
cli      : `python -m evidence ...`

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
    "ToolRegistry": ("server.evidence.registry", "ToolRegistry"),
    "registry": ("server.evidence.registry", "registry"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module, attr = _LAZY[name]
        return getattr(importlib.import_module(module), attr)
    raise AttributeError(f"module 'evidence' has no attribute {name!r}")
