"""parsers — atomic parser tools, grouped by capability (ADR-0035).

Sub-packages (``messaging``, ``ai_chat``, ``generic``) each hold parser modules
that self-register on import via ``@register``. ``reference.load_builtin_tools()``
walks this tree recursively; leaf modules whose name starts with ``_`` are
skipped as shared helpers.
"""
