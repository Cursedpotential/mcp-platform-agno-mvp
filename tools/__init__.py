"""Top-level cross-domain PLATFORM tools (NOT domain-specific).

General utilities callable by ANY domain or surface — via the mesh registry + the
tools-facade -> ContextForge MCP (ADR-0023). e.g. extract.text (OCR / text
extraction). Discovered by evidence.registry.load_builtin_tools() alongside
evidence/tools/, so homing a tool here (vs under evidence/) is the only difference.
Byline: Claude Code / Opus 4.8 / 2026-06-25
"""
