"""Temporary ranking stub. Preserves input order and does not load an ML model."""


def rank_candidates(
    request,
    candidates,
    *,
    company,
    fns,
    bki,
    config,
    engine,
    enabled=False,
    model_directory=None,
):
    """Return eligible candidates in their original order.

    Scoring and credit decisions remain the backend's responsibility.
    """
    return list(candidates)
