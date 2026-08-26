# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""server.timeline — the ADR-0060 canonical timeline + Timesketch-projection package.

WP-D01/D02/E02 only: builds immutable PostgreSQL projection generations from the
`timeline.event_candidate` / `timeline.timeline_member` tables (sql/0035_timeline_projection.sql)
and exposes the read/receipt surface the Timesketch-fork importer (under
`timesketch-fork/personal_case_authority/`) and R09 reconciliation consume.

Does NOT own curation/amendment commands (WP-F01/F02) or the Timesketch UI (WP-F03) — see
`AGENTS.md` in this directory for the exact boundary.
"""

from __future__ import annotations
