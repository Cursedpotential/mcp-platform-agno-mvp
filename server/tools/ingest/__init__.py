"""server/tools/ingest — registered ingest/projection tools.

Capability sub-package (ADR-0035): the modules here self-register on import via
`load_builtin_tools()`. This `__init__` registers nothing itself.
"""
