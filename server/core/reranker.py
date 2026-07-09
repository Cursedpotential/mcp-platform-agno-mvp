"""
NVIDIA NIM reranker — native ranking API client
===============================================

Agno 2.6.9 ships no NvidiaReranker, and its CohereReranker ignores base_url
(verified: requests leak to api.cohere.com). This subclass calls NVIDIA's
native retrieval/ranking endpoint directly:

    POST {NVIDIA_RERANK_URL}
    {"model": ..., "query": {"text": ...}, "passages": [{"text": ...}, ...]}
    -> {"rankings": [{"index": int, "logit": float}, ...]}  (sorted, best first)

Model: nvidia/rerank-qa-mistral-4b — the ranking function this account has
access to (probed 2026-06-10; nv-rerankqa-mistral-4b-v3 returned 404
"Not found for account"). Auth: NVIDIA_API_KEY.
On any failure we return the documents unranked — reranking is an enhancement,
never a point of failure for retrieval.
"""

from __future__ import annotations

from typing import List, Optional

import httpx

from agno.knowledge.document import Document
from agno.knowledge.reranker.base import Reranker
from agno.utils.log import logger

# NIM's ranking endpoint lives on ai.api.nvidia.com (NOT the OpenAI-compatible
# integrate.api.nvidia.com used for chat/embeddings). Shared endpoint; the
# model is selected in the request body.
DEFAULT_RERANK_URL = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"


class NvidiaReranker(Reranker):
    model: str = "nvidia/rerank-qa-mistral-4b"
    api_key: Optional[str] = None
    url: str = DEFAULT_RERANK_URL
    top_n: Optional[int] = None
    timeout: float = 30.0

    def _rerank(self, query: str, documents: List[Document]) -> List[Document]:
        if not documents:
            return []

        url = self.url
        payload = {
            "model": self.model,
            "query": {"text": query},
            "passages": [{"text": d.content} for d in documents],
        }
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        rankings = response.json().get("rankings", [])

        ranked: List[Document] = []
        for r in rankings:
            doc = documents[r["index"]]
            doc.reranking_score = r.get("logit")
            ranked.append(doc)

        if self.top_n and self.top_n > 0:
            ranked = ranked[: self.top_n]
        return ranked

    def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        try:
            return self._rerank(query=query, documents=documents)
        except Exception:
            logger.exception("NVIDIA rerank failed. Returning original documents")
            return documents
