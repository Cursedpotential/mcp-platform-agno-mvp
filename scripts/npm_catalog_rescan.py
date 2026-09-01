"""Rescan the npm registry for n8n community nodes -> refresh JSONL + DuckDB catalog.

Byline: Claude Code · Fable 5 · 2026-08-24  (owner rescan rule: .duckdb/AGENTS.md)

Usage:  uv run --no-sync python scripts/npm_catalog_rescan.py
Writes: docs/research/integration-audit-2026-08-24/npm-community-node-catalog.jsonl (truth, committed)
        .duckdb/npm-community-nodes.duckdb (derived, gitignored)
Prints: totals + NEW packages since the previous scan (the community-check diff).
"""
from __future__ import annotations
import json, time, urllib.request, urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JSONL = REPO / "docs/research/integration-audit-2026-08-24/npm-community-node-catalog.jsonl"
DB = REPO / ".duckdb/npm-community-nodes.duckdb"

def fetch_all() -> dict[str, dict]:
    pkgs: dict[str, dict] = {}
    for query in ("keywords:n8n-community-node-package", "n8n-nodes-"):
        offset = 0
        while True:
            url = ("https://reference.npmjs.org/-/v1/search?text="
                   + urllib.parse.quote(query) + f"&size=250&from={offset}")
            with urllib.request.urlopen(url, timeout=60) as r:
                data = json.load(r)
            objs = data.get("objects", [])
            if not objs:
                break
            for o in objs:
                p = o.get("package", {})
                name = p.get("name")
                if not name:
                    continue
                # second net: only keep n8n-ish names/keywords to avoid noise
                kw = [k.lower() for k in (p.get("keywords") or [])]
                if query.startswith("n8n-nodes-") and "n8n" not in name and \
                   not any("n8n" in k for k in kw):
                    continue
                pkgs[name] = {
                    "name": name,
                    "description": p.get("description") or "",
                    "version": p.get("version") or "",
                    "last_publish": (p.get("date") or "")[:10],
                    "keywords": kw,
                    "downloads_weekly": (o.get("downloads") or {}).get("weekly"),
                    "score_quality": (o.get("score", {}).get("detail", {}) or {}).get("quality"),
                }
            offset += len(objs)
            if offset >= data.get("total", 0):
                break
            time.sleep(0.4)  # be polite
    return pkgs

def main() -> None:
    prev = set()
    if JSONL.exists():
        for line in JSONL.read_text(encoding="utf-8").splitlines():
            try:
                prev.add(json.loads(line)["name"])
            except Exception:
                pass
    pkgs = fetch_all()
    new = sorted(set(pkgs) - prev)
    JSONL.parent.mkdir(parents=True, exist_ok=True)
    with JSONL.open("w", encoding="utf-8") as f:
        for name in sorted(pkgs):
            f.write(json.dumps(pkgs[name], ensure_ascii=False) + "\n")
    import duckdb
    DB.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("CREATE OR REPLACE TABLE packages AS SELECT * FROM read_ndjson(?, auto_detect=true)", [str(JSONL)])
    con.execute("CREATE TABLE IF NOT EXISTS scans(scanned_at TIMESTAMP, package_count INT, new_since_prev INT)")
    con.execute("INSERT INTO scans VALUES (now(), ?, ?)", [len(pkgs), len(new)])
    con.close()
    print(f"catalog: {len(pkgs)} packages ({len(new)} new since previous scan)")
    for n in new[:40]:
        print(f"  NEW {n}: {pkgs[n]['description'][:80]}")
    if len(new) > 40:
        print(f"  ... and {len(new)-40} more new")
if __name__ == "__main__":
    main()
