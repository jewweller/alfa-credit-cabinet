"""Public JSON-to-JSON ranking interface."""

from .synth.ranking import rank_feed, rank_products

__all__ = ["rank_feed", "rank_products"]
