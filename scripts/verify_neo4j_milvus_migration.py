"""Post-migration verification for the ovh-data -> ovh-files cold copy of
Neo4j (data-neo4j) and Milvus (data-vector). Compares source vs target node
counts / collection row counts — the counts that actually prove the volume
copy carried real data, not just that a container started.

Byline: Claude Code · Sonnet (agent) · 2026-08-01

Run via (ephemeral deps — does NOT touch pyproject.toml/uv.lock):
    uv run --with pymilvus --with neo4j python scripts/verify_neo4j_milvus_migration.py

Credentials come from environment variables so nothing is printed or
hardcoded:
    NEO4J_PASSWORD          (same value on both boxes if the volume copy is
                             real — auth lives on disk, not in the env)
    MEMSEARCH_MILVUS_TOKEN  (parsed by the caller from ~/.secrets/memsearch.env,
                             same tolerant regex used elsewhere in this repo —
                             never `source` a secrets file)
"""

from __future__ import annotations

import os
import sys


def check_neo4j() -> bool:
    from neo4j import GraphDatabase

    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print("NEO4J_PASSWORD not set - skipping neo4j check", file=sys.stderr)
        return False

    for label, uri in [
        ("source (ovh-data)", "bolt://100.119.96.29:7687"),
        ("target (ovh-files)", "bolt://100.91.190.107:7687"),
    ]:
        print(f"== neo4j {label}: {uri} ==")
        driver = GraphDatabase.driver(uri, auth=("neo4j", password))
        try:
            with driver.session(database="system") as sess:
                dbs = [r["name"] for r in sess.run("SHOW DATABASES YIELD name")]
            print(f"  databases: {sorted(dbs)}")
            for db in ("neo4j", "memory"):
                if db not in dbs:
                    print(f"  {db}: NOT PRESENT")
                    continue
                with driver.session(database=db) as sess:
                    n = sess.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                print(f"  {db}: {n} nodes")
        finally:
            driver.close()
    return True


def check_milvus() -> bool:
    from pymilvus import MilvusClient

    token = os.environ.get("MEMSEARCH_MILVUS_TOKEN")
    if not token:
        print("MEMSEARCH_MILVUS_TOKEN not set - skipping milvus check", file=sys.stderr)
        return False

    for label, uri in [
        ("source (ovh-data)", "http://100.119.96.29:19530"),
        ("target (ovh-files)", "http://100.91.190.107:19530"),
    ]:
        print(f"== milvus {label}: {uri} ==")
        client = MilvusClient(uri=uri, token=token)
        cols = client.list_collections()
        print(f"  collections: {cols}")
        if "platform_knowledge" in cols:
            # Exact live count - NOT get_collection_stats()['row_count'],
            # which includes soft-deleted rows (lied 2x, verified live
            # 2026-08-01 per the migrate_milvus_to_weaviate.py precedent).
            res = client.query(
                collection_name="platform_knowledge", filter="", output_fields=["count(*)"]
            )
            count = int(str(res[0]["count(*)"]))
            print(f"  platform_knowledge live row count: {count}")
            rows = client.query(
                collection_name="platform_knowledge",
                filter="",
                limit=1,
                output_fields=["id", "dense_vector"],
            )
            if rows:
                vec = rows[0].get("dense_vector")
                dim = len(vec) if vec else 0
                print(f"  spot-check row id={rows[0].get('id')} vector_dim={dim}")
    return True


if __name__ == "__main__":
    ok_neo4j = check_neo4j()
    print()
    ok_milvus = check_milvus()
    sys.exit(0 if (ok_neo4j or ok_milvus) else 1)
