"""One-off Milvus -> Weaviate migration (HANDOFF Phase-1 task 3, ADR-0040).

Byline: Claude Code · Fable 5 · 2026-07-29

Copies the `platform_knowledge` collection (nv-embed-v1 4096-d dense vectors +
agno knowledge fields) from the sidelined Milvus into the platform Weaviate,
creating the collection through agno's own Weaviate class so the schema is
byte-identical to what the knowledge stage will write. Sparse/BM25 vectors are
NOT copied — Weaviate computes BM25 natively from the `content` property.

Run from the repo venv on the tailnet (reads MEMSEARCH_MILVUS_TOKEN from
~/.secrets/memsearch.env, never printing it):

    .venv/Scripts/python.exe scripts/migrate_milvus_to_weaviate.py

Idempotent: objects are inserted with deterministic UUIDs derived from the
Milvus primary key, so re-runs overwrite rather than duplicate.
"""

from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

COLLECTION = "platform_knowledge"
MILVUS_URI = "http://100.119.96.29:19530"


def _milvus_token() -> str:
    secret_path = Path.home() / ".secrets" / "memsearch.env"
    for line in secret_path.read_text().splitlines():
        m = re.match(r"^\s*MEMSEARCH_MILVUS_TOKEN\s*=\s*(.+?)\s*$", line)
        if m:
            return m.group(1)
    raise SystemExit("MEMSEARCH_MILVUS_TOKEN not found in ~/.secrets/memsearch.env")


def main() -> int:
    from pymilvus import MilvusClient

    from server.core.session import _embedder, EMBED_TEXT_DIM, EMBED_TEXT_ID, get_weaviate_client
    from agno.vectordb.search import SearchType
    from agno.vectordb.weaviate import Weaviate

    milvus = MilvusClient(uri=MILVUS_URI, token=_milvus_token())
    # exact count — get_collection_stats' row_count includes soft-deleted
    # entities (it read 14 against 7 live rows on the real store).
    src_count = int(str(milvus.query(collection_name=COLLECTION, filter="", output_fields=["count(*)"])[0]["count(*)"]))
    print(f"source rows (live): {src_count}")

    # Create the destination collection via agno's own class (schema parity
    # with what create_knowledge() will use at runtime).
    vector_db = Weaviate(
        client=get_weaviate_client(),
        collection=COLLECTION,
        search_type=SearchType.hybrid,
        embedder=_embedder(EMBED_TEXT_ID, EMBED_TEXT_DIM),
    )
    vector_db.create()
    client = vector_db.get_client()
    dest = client.collections.get(COLLECTION)

    rows = milvus.query(
        collection_name=COLLECTION,
        filter="",
        limit=16384,
        output_fields=["id", "name", "content", "content_id", "content_hash", "meta_data", "dense_vector"],
    )
    print(f"fetched {len(rows)} rows from Milvus")

    inserted = 0
    vectors = {r["id"]: r["dense_vector"] for r in rows}  # keep for parity check (pop mutates r)
    with dest.batch.dynamic() as batch:
        for r in rows:
            vec = r.pop("dense_vector")
            assert len(vec) == EMBED_TEXT_DIM, f"dim mismatch: {len(vec)}"
            meta = r.get("meta_data")
            if isinstance(meta, (dict, list)):
                meta = json.dumps(meta)
            batch.add_object(
                properties={
                    "name": r.get("name"),
                    "content": r.get("content"),
                    "meta_data": meta,
                    "content_id": r.get("content_id"),
                    "content_hash": r.get("content_hash"),
                },
                vector=vec,
                uuid=uuid.uuid5(uuid.NAMESPACE_OID, f"milvus:{COLLECTION}:{r['id']}"),
            )
            inserted += 1
    if dest.batch.failed_objects:
        print(f"FAILED objects: {len(dest.batch.failed_objects)}")
        for f in dest.batch.failed_objects[:5]:
            print("  ", f.message)
        return 1

    dst_count = dest.aggregate.over_all(total_count=True).total_count
    print(f"inserted {inserted}; weaviate count: {dst_count}")
    if dst_count != src_count:
        print("COUNT MISMATCH")
        return 1

    # Parity spot-check: nearest neighbor of each of 3 source vectors should be
    # the object migrated from that very row (cosine, distance ~0 to itself).
    ok = 0
    for r in rows[:3]:
        near = dest.query.near_vector(near_vector=vectors[r["id"]], limit=1, return_properties=["content_hash"])
        if near.objects and near.objects[0].properties.get("content_hash") == r.get("content_hash"):
            ok += 1
    print(f"parity spot-check: {ok}/3 self-neighbor hits")
    client.close()
    return 0 if ok == 3 else 1


if __name__ == "__main__":
    sys.exit(main())
