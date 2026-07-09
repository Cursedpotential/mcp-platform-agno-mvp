"""SHA-256 content-addressed result store with paged retrieval.

Port of the pre-Agno content-store.ts: dedup by content hash, 2-char sharded
directories, byte-range paging (4 KB default) so large tool outputs are
retrieved incrementally instead of landing in an agent's context whole.

Layout under the store root:
    objects/<sha[:2]>/<sha>          payload bytes
    objects/<sha[:2]>/<sha>.meta     {"size": ..., "mime": ..., "created": ...}
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PAGE_SIZE = 4096
PREVIEW_CHARS = 280


class ContentStore:
    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            root = os.getenv("GATEWAY_STORE_DIR", "data/content_store")
        self.root = Path(root)
        (self.root / "objects").mkdir(parents=True, exist_ok=True)

    def _paths(self, sha: str) -> tuple[Path, Path]:
        shard = self.root / "objects" / sha[:2]
        return shard / sha, shard / f"{sha}.meta"

    def put(self, content: str | bytes, mime: str = "application/json") -> dict[str, Any]:
        """Store content; return its ref envelope. Identical content dedupes."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        sha = hashlib.sha256(data).hexdigest()
        obj, meta = self._paths(sha)
        if not obj.exists():
            obj.parent.mkdir(parents=True, exist_ok=True)
            obj.write_bytes(data)
            meta.write_text(
                json.dumps(
                    {
                        "size": len(data),
                        "mime": mime,
                        "created": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                encoding="utf-8",
            )
        return self.ref(sha)

    def exists(self, sha: str) -> bool:
        return self._paths(sha)[0].exists()

    def ref(self, sha: str) -> dict[str, Any]:
        """The compact envelope handed to consumers instead of the payload."""
        obj, meta_path = self._paths(sha)
        if not obj.exists():
            raise KeyError(f"content store: unknown ref {sha!r}")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        size = meta.get("size", obj.stat().st_size)
        preview = obj.read_bytes()[:PREVIEW_CHARS].decode("utf-8", errors="replace")
        return {
            "ref": f"sha256:{sha}",
            "size": size,
            "mime": meta.get("mime", "application/octet-stream"),
            "preview": preview,
            "total_pages": max(1, -(-size // DEFAULT_PAGE_SIZE)),
        }

    def get(self, sha: str) -> bytes:
        obj, _ = self._paths(sha)
        if not obj.exists():
            raise KeyError(f"content store: unknown ref {sha!r}")
        return obj.read_bytes()

    def get_page(self, sha: str, page: int = 0, page_size: int = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
        """Byte-range page of a stored object (the token-efficiency mechanism)."""
        if page < 0 or page_size < 1:
            raise ValueError("page must be >= 0 and page_size >= 1")
        data = self.get(sha)
        total_pages = max(1, -(-len(data) // page_size))
        if page >= total_pages:
            raise IndexError(f"page {page} out of range (total_pages={total_pages})")
        chunk = data[page * page_size : (page + 1) * page_size]
        return {
            "ref": f"sha256:{sha}",
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "has_more": page + 1 < total_pages,
            "size": len(data),
            "content": chunk.decode("utf-8", errors="replace"),
        }


def parse_ref(ref: str) -> str:
    """Accept 'sha256:<hex>' or bare hex; return the hex digest."""
    sha = ref.split(":", 1)[1] if ref.startswith("sha256:") else ref
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha.lower()):
        raise ValueError(f"not a sha256 ref: {ref!r}")
    return sha.lower()
