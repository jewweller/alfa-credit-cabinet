"""JSON-compatible ranking stubs. Preserve the backend's candidate order."""


def _response(ids: list[str], id_field: str, version: str) -> dict:
    if len(ids) != len(set(ids)):
        raise ValueError("Candidate IDs must be unique")

    count = len(ids)
    return {
        "model_version": version,
        "ranking": [
            {
                id_field: candidate_id,
                # Positional placeholder, not a model probability.
                "score": (count - position) / count,
                "reasons": [],
            }
            for position, candidate_id in enumerate(ids)
        ],
    }


def rank_feed(payload: dict) -> dict:
    """Preserve news order. Filtering remains the backend's responsibility."""
    ids = [candidate["id"] for candidate in payload["candidates"]]
    return _response(ids, "id", "feed-stub-0.1.0")


def rank_products(payload: dict) -> dict:
    """Preserve product order. Credit decisions remain rule-based."""
    ids = [
        candidate["product"]["id"]
        for candidate in payload["candidates"]
    ]
    return _response(ids, "product_id", "product-stub-0.1.0")
