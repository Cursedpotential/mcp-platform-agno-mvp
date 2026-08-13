#!/usr/bin/env python3
"""scripts/search_weaviate.py — Direct semantic search against Weaviate.

Bypasses PG entirely. Connects straight to Weaviate for vector search.

Usage:
    python scripts/search_weaviate.py "what happened with the custody"
    python scripts/search_weaviate.py "financial abuse patterns" --collection Legal_knowledge
    python scripts/search_weaviate.py "timeline of events" --limit 10
    python scripts/search_weaviate.py --list-collections
    python scripts/search_weaviate.py "keyword search" --keyword
    python scripts/search_weaviate.py --collection Platform_knowledge --near-text "agent architecture"

Examples:
    # Semantic search across all collections
    python scripts/search_weaviate.py "gaslighting incidents"

    # Search only legal knowledge
    python scripts/search_weaviate.py "custody evaluation" --collection Legal_knowledge

    # Keyword (BM25) search instead of vector
    python scripts/search_weaviate.py "incident report" --keyword

    # Show what's in each collection
    python scripts/search_weaviate.py --list-collections

    # Search with filters
    python scripts/search_weaviate.py "abuse" --collection Evidence_knowledge --limit 20
"""
# Byline: Claude Code · opencode/mimo-v2.5-free · 2026-08-12

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))


def _get_client():
    """Connect to Weaviate directly."""
    from server.core.session import get_weaviate_client

    return get_weaviate_client()


def _list_collections(client):
    """Show all Weaviate collections with counts."""
    print(f"\n{'Collection':<35} {'Objects':>10}  {'Properties'}")
    print("-" * 80)
    for name, cfg in client.collections.list_all().items():
        props = [p.name for p in (cfg.properties or [])]
        try:
            agg = client.collections.get(name).aggregate.over_all(total_count=True)
            count = agg.total_count
        except Exception:
            count = "?"
        print(f"  {name:<33} {count:>10}  {', '.join(props[:6])}")
    print()


def _near_text_search(client, query: str, collection: str | None, limit: int, alpha: float):
    """Semantic (nearText) search across collections."""
    collections = _resolve_collections(client, collection)
    all_results = []

    for col_name in collections:
        col = client.collections.get(col_name)
        try:
            results = col.query.near_text(
                query=query,
                limit=limit,
                return_metadata=["distance", "certainty"],
                return_properties=[
                    "name",
                    "content",
                    "meta_data",
                    "content_id",
                    "content_hash",
                ],
            )
            for obj in results.objects:
                meta = obj.metadata
                props = obj.properties or {}
                md = props.get("meta_data") or {}
                all_results.append(
                    {
                        "collection": col_name,
                        "id": str(obj.uuid),
                        "distance": meta.distance if meta else None,
                        "certainty": meta.certainty if meta else None,
                        "content": (props.get("content", "") or "")[:300],
                        "name": props.get("name"),
                        "content_id": props.get("content_id"),
                        "source": md.get("source"),
                        "conversation_title": md.get("conversation_title"),
                        "role": md.get("role"),
                        "occurred_at": md.get("occurred_at"),
                        "lane": md.get("lane"),
                        "disclosure_tier": md.get("disclosure_tier"),
                    }
                )
        except Exception as e:
            print(f"  [WARN] {col_name}: {e}", file=sys.stderr)

    all_results.sort(key=lambda x: x["distance"] or 999)
    return all_results


def _keyword_search(client, query: str, collection: str | None, limit: int):
    """BM25 keyword search."""
    collections = _resolve_collections(client, collection)
    all_results = []

    for col_name in collections:
        col = client.collections.get(col_name)
        try:
            results = col.query.bm25(
                query=query,
                limit=limit,
                return_metadata=["score"],
                return_properties=[
                    "content",
                    "source",
                    "conversation_id",
                    "conversation_title",
                    "role",
                    "occurred_at",
                    "lane",
                    "disclosure_tier",
                ],
            )
            for obj in results.objects:
                meta = obj.metadata
                props = obj.properties or {}
                all_results.append(
                    {
                        "collection": col_name,
                        "id": str(obj.uuid),
                        "score": meta.score if meta else None,
                        "content": (props.get("content", "") or "")[:300],
                        "source": props.get("source"),
                        "conversation_title": props.get("conversation_title"),
                        "role": props.get("role"),
                        "occurred_at": props.get("occurred_at"),
                        "lane": props.get("lane"),
                        "disclosure_tier": props.get("disclosure_tier"),
                    }
                )
        except Exception as e:
            print(f"  [WARN] {col_name}: {e}", file=sys.stderr)

    all_results.sort(key=lambda x: x["score"] or 0, reverse=True)
    return all_results


def _resolve_collections(client, collection: str | None) -> list[str]:
    """Resolve collection name(s) to search."""
    if collection:
        return [collection]
    all_names = list(client.collections.list_all().keys())
    if not all_names:
        print("No collections found in Weaviate.", file=sys.stderr)
        sys.exit(1)
    return all_names


def _print_results(results: list[dict], query: str, mode: str):
    """Pretty-print search results."""
    if not results:
        print(f"\nNo results for '{query}' ({mode} search).")
        return

    print(f"\n{'=' * 80}")
    print(f"  {len(results)} results for '{query}' ({mode} search)")
    print(f"{'=' * 80}")

    for i, r in enumerate(results, 1):
        score_label = f"dist={r['distance']:.4f}" if r.get("distance") is not None else f"score={r.get('score', '?')}"
        title = r.get("conversation_title") or "(no title)"
        source = r.get("source") or "?"
        role = r.get("role") or "?"
        tier = r.get("disclosure_tier") or "?"
        ts = r.get("occurred_at") or "?"
        lane = r.get("lane") or "?"

        print(f"\n  [{i}] {r['collection']}  |  {score_label}")
        print(f"      {title}  |  {source}  |  {lane}  |  {tier}")
        print(f"      {role} @ {ts}")
        print(f"      {r['content'][:250].replace(chr(10), ' ')}")

    print(f"\n{'=' * 80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Direct semantic search against Weaviate (bypasses PG)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", nargs="?", help="Search query (text or keywords)")
    parser.add_argument("--list-collections", "-l", action="store_true", help="List all collections with object counts")
    parser.add_argument("--collection", "-c", help="Search specific collection (default: all)")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Max results per collection (default: 5)")
    parser.add_argument("--keyword", "-k", action="store_true", help="Use BM25 keyword search instead of semantic")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--alpha", type=float, default=0.75, help="Hybrid alpha (0=keyword, 1=semantic, default: 0.75)")

    args = parser.parse_args()

    if not args.query and not args.list_collections:
        parser.print_help()
        sys.exit(1)

    print("Connecting to Weaviate...")
    client = _get_client()
    print(f"  Connected: {client.is_ready()}")

    if args.list_collections:
        _list_collections(client)
        client.close()
        return

    t0 = time.time()
    if args.keyword:
        results = _keyword_search(client, args.query, args.collection, args.limit)
        mode = "BM25"
    else:
        results = _near_text_search(client, args.query, args.collection, args.limit, args.alpha)
        mode = "semantic"
    elapsed = time.time() - t0

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        _print_results(results, args.query, mode)
        print(f"  Search completed in {elapsed:.2f}s")

    client.close()


if __name__ == "__main__":
    main()
