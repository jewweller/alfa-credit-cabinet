"""Public JSON-to-JSON ranking interface and explicit startup warmup."""

from .synth.ranking import rank_feed, rank_products, warmup

__all__ = ["rank_feed", "rank_products", "warmup"]
