"""Disjoint companies plus a forward test window; incompatible rows remain logged."""

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


def company_splits(company_ids: list[str], config: dict, seed: int) -> dict[str, str]:
    train_fraction, validation_fraction, test_fraction = config["split"]["company_fractions"]
    groups = np.asarray(company_ids)
    split = GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=seed % (2**32))
    remaining, test = next(split.split(groups, groups=groups))
    split = GroupShuffleSplit(
        n_splits=1,
        test_size=validation_fraction / (train_fraction + validation_fraction),
        random_state=(seed + 1) % (2**32),
    )
    train, validation = next(split.split(groups[remaining], groups=groups[remaining]))
    return {
        **dict.fromkeys(groups[remaining[train]], "train"),
        **dict.fromkeys(groups[remaining[validation]], "validation"),
        **dict.fromkeys(groups[test], "test"),
    }


def cutoff_date(config: dict) -> str:
    return (
        (
            pd.Timestamp(config["simulation"]["end_date"])
            - pd.DateOffset(months=config["split"]["test_months"])
        )
        .date()
        .isoformat()
    )


def temporal_split(company_split: str, created_at: str, config: dict) -> tuple[str, str | None]:
    recent = created_at[:10] >= cutoff_date(config)
    if company_split == "test" and not recent:
        return "excluded", "test_company_before_cutoff"
    if company_split != "test" and recent:
        return "excluded", "development_company_after_cutoff"
    return company_split, None
