# .duckdb/ — local derived databases + the npm-catalog rescan rule

> _Byline: Claude Code · Fable 5 · 2026-08-24 (owner-ordered rule)_

This folder holds LOCAL, gitignored DuckDB databases (derived, always rebuildable). The two
rule files (AGENTS.md, CLAUDE.md) are the only tracked content.

## npm-community-nodes.duckdb — the n8n community-node catalog

- **Source of truth:** `docs/research/integration-audit-2026-08-24/npm-community-node-catalog.jsonl`
  (committed). The DB is derived; rebuild any time:
  `duckdb .duckdb/npm-community-nodes.duckdb -c "CREATE OR REPLACE TABLE packages AS SELECT * FROM read_ndjson('docs/research/integration-audit-2026-08-24/npm-community-node-catalog.jsonl', auto_detect=true); CREATE TABLE IF NOT EXISTS scans(scanned_at TIMESTAMP, package_count INT, new_since_prev INT);"`
- **Schema:** `packages` (one row per npm package: name, description, version, last publish,
  downloads, keywords, relevance tags, owner_flagged) + `scans` (scan history ledger).

## THE RESCAN RULE (owner, 2026-08-24)

**Check this catalog's freshness whenever you touch n8n build/integration work, and rescan
when it is stale (> 30 days) or when hunting for a capability you can't find in it.**

1. Freshness check: `duckdb .duckdb/npm-community-nodes.duckdb -c "SELECT max(scanned_at), count(*) FROM scans"` — if > 30 days old (or table missing), rescan.
2. Rescan = re-enumerate the registry (paginate `https://registry.npmjs.org/-/v1/search?text=keywords:n8n-community-node-package&size=250&from=N`, plus a `n8n-nodes-` text net, dedupe), regenerate the JSONL, reload `packages`, and append a `scans` row with the new-package count.
3. **Diff and surface:** report NEW packages and version bumps since the previous scan,
   filtered to the platform's relevance groups (LLM routing, parsers/OCR, RAG/rerankers,
   memory stores, geo, messaging/transcripts, legal/forensic, workflow plumbing) — per the
   community-check mandate, new arrivals may beat current picks.
4. Commit the refreshed JSONL + catalog markdown; the .duckdb file itself stays local.

Query it before searching npm — `SELECT name, description FROM packages WHERE description ILIKE '%rerank%'` beats a web search.

## TOOLS (use these — don't hand-write queries)

| Command | Does |
|---|---|
| `scripts/npm-catalog search <term>` | Find nodes by name/description/keyword (newest first) |
| `scripts/npm-catalog stats` | Totals + freshness + scan history |
| `scripts/npm-catalog fresh` | Staleness verdict for the 30-day rescan rule |
| `scripts/npm-catalog rescan` | Full registry re-enumeration → JSONL + DB reload + NEW-package diff (`scripts/npm_catalog_rescan.py`) |

Fuzzy/semantic hunting: the catalog markdown + JSONL live in the ccc-indexed tree — use
`ccc grep`/semantic search over `docs/research/integration-audit-2026-08-24/` for concept-level
questions ("something that dedupes files"), and `scripts/npm-catalog search` for keyword hits.
After a rescan, refresh the index (`ccc index`) so ccc sees the new catalog.
