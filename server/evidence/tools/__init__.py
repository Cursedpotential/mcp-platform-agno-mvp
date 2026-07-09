"""evidence.tools — atomic tool modules, ONE PER PARSER/FORMAT (owner intent:
each parser is a separate swappable unit — another module, nothing more).

Auto-discovery: every .py module in this package is imported by
registry.load_builtin_tools(); importing self-registers the module's tools.
Adding a format = dropping in one new module. Removing/replacing a format =
deleting/replacing one module. No central list to edit.

Shared helpers (timestamps, output shaping) live in evidence.tools._common.
"""
