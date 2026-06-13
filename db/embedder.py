"""
NimEmbedder — asymmetric NVIDIA NIM embedder with correct query/passage modes
=============================================================================

NIM embedqa models are ASYMMETRIC: documents must be embedded with
`input_type="passage"` and search queries with `input_type="query"`. Embedding
a query in passage space (the previous behavior) silently degraded retrieval.

Agno's PgVector uses two distinct embedder methods (verified against agno 2.6.9):
  - documents → Document.async_embed → `async_get_embedding_and_usage`  (PASSAGE)
  - queries   → PgVector.vector_search → `get_embedding`                 (QUERY)

So the fix is surgical: the base `request_params` carries the PASSAGE input_type
(covers every document path, incl. the sync + batch variants), and we override
ONLY the two query-path methods to use the QUERY input_type.
"""

from __future__ import annotations

from typing import Any, Dict, List

from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.utils.log import log_warning


class NimEmbedder(OpenAIEmbedder):
    # Document/index path default (inherited methods read this via response()/req).
    # Set at construction in db/session.py to {"extra_body": {"input_type": "passage", ...}}.
    query_input_type: str = "query"
    truncate: str = "NONE"

    def _query_req(self, text: str) -> Dict[str, Any]:
        req: Dict[str, Any] = {
            "input": text,
            "model": self.id,
            "encoding_format": self.encoding_format,
            "extra_body": {"input_type": self.query_input_type, "truncate": self.truncate},
        }
        if self.id.startswith("text-embedding-3") or self.base_url is not None:
            req["dimensions"] = self.dimensions
        if self.user is not None:
            req["user"] = self.user
        return req

    # --- QUERY path (PgVector search) — override to query mode ----------------
    def get_embedding(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings.create(**self._query_req(text))
            return response.data[0].embedding
        except Exception as e:
            log_warning(f"NimEmbedder query embedding failed: {e}")
            return []

    async def async_get_embedding(self, text: str) -> List[float]:
        try:
            response = await self.aclient.embeddings.create(**self._query_req(text))
            return response.data[0].embedding
        except Exception as e:
            log_warning(f"NimEmbedder async query embedding failed: {e}")
            return []

    # Document path (get_embedding_and_usage / async_get_embedding_and_usage /
    # batch) is inherited unchanged — it uses request_params (PASSAGE).
