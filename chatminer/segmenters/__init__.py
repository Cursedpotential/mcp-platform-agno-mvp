"""
ChatMiner Topic Segmenters — split conversations into semantically
coherent chunks for topic-routed processing.

Three variants:
    - segmenter_local.py: Sentence-transformers on 2GB GPU (your machine)
    - segmenter_colab.py: Google Colab T4 GPU (free, faster)
    - segmenter_configurable.py: Swappable embedding provider

Usage:
    from chatminer.segmenters import get_segmenter
    
    segmenter = get_segmenter("local")  # or "colab", "configurable"
    segments = segmenter.segment(messages)
    
    for seg in segments:
        print(f"{seg.topic_tag.value}: {seg.message_count} messages")
"""

from chatminer.segmenters.segmenter_local import LocalSegmenter
from chatminer.segmenters.segmenter_configurable import ConfigurableSegmenter

__all__ = ["LocalSegmenter", "ConfigurableSegmenter", "get_segmenter"]


def get_segmenter(method: str = "local", **kwargs):
    """
    Factory: get the right segmenter by name.
    
    Args:
        method: "local" | "colab" | "configurable"
        **kwargs: Passed to segmenter constructor
    
    Returns:
        Segmenter instance
    """
    if method == "local":
        return LocalSegmenter(**kwargs)
    elif method == "configurable":
        return ConfigurableSegmenter(**kwargs)
    elif method == "colab":
        # Colab segmenter is the configurable one with Colab defaults
        return ConfigurableSegmenter(
            provider="local",  # On Colab, "local" means the T4 GPU
            model_name="all-MiniLM-L6-v2",
            **kwargs,
        )
    else:
        raise ValueError(f"Unknown segmenter method: {method}. Use: local, colab, configurable")
