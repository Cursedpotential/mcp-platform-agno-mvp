"""
Configurable Topic Segmenter — swappable embedding provider
============================================================

Uses the same segmentation logic as LocalSegmenter but allows
configuring the embedding provider via settings:

    - "local"  → sentence-transformers (your 2GB GPU)
    - "ollama" → Ollama API (local or remote)
    - "openai" → text-embedding-3-small API
    - "gemini" → Gemini embedding API
    - "nvidia" → NVIDIA NIM API

Configuration (config/settings.py or .env):
    SEGMENTER_PROVIDER=local
    SEGMENTER_MODEL=all-MiniLM-L6-v2
    SEGMENTER_SIMILARITY_THRESHOLD=0.65

Usage:
    from chatminer.segmenters import ConfigurableSegmenter
    
    segmenter = ConfigurableSegmenter(
        provider="openai",  # or "local", "ollama", "gemini", "nvidia"
        model_name="text-embedding-3-small",
    )
    segments = segmenter.segment(messages)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np

from chatminer.segmenters.segmenter_local import LocalSegmenter, SegmenterConfig
from chatminer.core.types import ParsedMessage, TopicSegment

logger = logging.getLogger(__name__)


class ConfigurableSegmenter(LocalSegmenter):
    """
    Topic segmenter with swappable embedding provider.

    Inherits all segmentation logic from LocalSegmenter.
    Only overrides the embedding creation to support multiple providers.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Optional[SegmenterConfig] = None,
    ):
        # Initialize base with config
        super().__init__(config)

        # Provider selection
        self.provider = (provider or os.getenv("SEGMENTER_PROVIDER", "local")).lower()
        self.model_name = model_name or os.getenv("SEGMENTER_MODEL", self.config.model_name)
        self.api_key = api_key
        self.base_url = base_url

        logger.info(f"ConfigurableSegmenter: provider={self.provider}, model={self.model_name}")

    def _embed_messages(self, messages: list[ParsedMessage]) -> np.ndarray:
        """Create embeddings using the configured provider."""
        texts = [m.content[:512] for m in messages]

        if self.provider == "local":
            return self._embed_local(texts)
        elif self.provider == "ollama":
            return self._embed_ollama(texts)
        elif self.provider == "openai":
            return self._embed_openai(texts)
        elif self.provider == "gemini":
            return self._embed_gemini(texts)
        elif self.provider == "nvidia":
            return self._embed_nvidia(texts)
        else:
            logger.warning(f"Unknown provider '{self.provider}', falling back to local")
            return self._embed_local(texts)

    def _embed_local(self, texts: list[str]) -> np.ndarray:
        """Use sentence-transformers locally."""
        model = self._load_model()
        return model.encode(
            texts,
            batch_size=self.config.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

    def _embed_ollama(self, texts: list[str]) -> np.ndarray:
        """Use Ollama embedding API."""
        import requests

        base = self.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model = self.model_name
        key = self.api_key or os.getenv("OLLAMA_API_KEY", "")

        embeddings = []
        for text in texts:
            resp = requests.post(
                f"{base}/api/embeddings",
                json={"model": model, "prompt": text},
                headers={"Authorization": f"Bearer {key}"} if key else {},
                timeout=60,
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"])

        return np.array(embeddings, dtype=np.float32)

    def _embed_openai(self, texts: list[str]) -> np.ndarray:
        """Use OpenAI embedding API."""
        import openai

        client = openai.OpenAI(
            api_key=self.api_key or os.getenv("OPENAI_API_KEY"),
            base_url=self.base_url,
        )

        all_embeddings = []
        batch_size = 100  # OpenAI limit
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = client.embeddings.create(model=self.model_name, input=batch)
            all_embeddings.extend([d.embedding for d in resp.data])

        return np.array(all_embeddings, dtype=np.float32)

    def _embed_gemini(self, texts: list[str]) -> np.ndarray:
        """Use Gemini embedding API."""
        import google.generativeai as genai

        genai.configure(api_key=self.api_key or os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel(self.model_name)

        embeddings = []
        for text in texts:
            result = genai.embed_content(model=self.model_name, content=text)
            embeddings.append(result["embedding"])

        return np.array(embeddings, dtype=np.float32)

    def _embed_nvidia(self, texts: list[str]) -> np.ndarray:
        """Use NVIDIA NIM embedding API."""
        import requests

        base = self.base_url or os.getenv("NVIDIA_NIM_URL", "")
        key = self.api_key or os.getenv("NVIDIA_API_KEY", "")

        embeddings = []
        for text in texts:
            resp = requests.post(
                f"{base}/v1/embeddings",
                json={"input": text, "model": self.model_name},
                headers={"Authorization": f"Bearer {key}"},
                timeout=60,
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["data"][0]["embedding"])

        return np.array(embeddings, dtype=np.float32)
