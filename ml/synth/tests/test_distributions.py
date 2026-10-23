from collections import Counter
from datetime import date

import numpy as np
import pytest
from ml.synth.population import Population


@pytest.mark.distribution
def test_configured_population_distributions_and_correlations(config):
    """Large independent-company sample, not a flaky check on the 1% demo."""
    population = Population(config, np.random.default_rng(2026))
    kinds, statuses, regions, industries = Counter(), Counter(), Counter(), Counter()
    revenues = {"micro": [], "small": []}
    ages, overdue, debts, flags, unavailable = [], [], [], [], []
    count = 10000
    for _ in range(count):
        company, latent = population.company(population.new_id())
        kinds[company["kind"]] += 1
        statuses[company["status"]] += 1
        regions[company["region"]] += 1
        industries[company["okved_main"]] += 1
        revenues[company["segment"]].append(latent["annual_revenue"])
        ages.append((population.end - date.fromisoformat(company["registered_at"])).days / 365.25)
        fns, bki, _ = population.profiles(
            company, latent, population.new_id(), "2026-10-22T12:00:00+00:00"
        )
        overdue.append(int(bki["max_overdue_days_24m"] > 0))
        debts.append(
            0
            if float(fns["tax_debt_rub"]) == 0
            else 1
            if float(fns["tax_debt_rub"]) <= 100000
            else 2
        )
        flags.append(list(fns["flags"].values()))
        unavailable.append(not fns["available"])
    tolerance = config["quality"]["category_tolerance"]
    for name, observed in (("kinds", kinds), ("statuses", statuses)):
        spec = config["company"][name]
        for category, expected in zip(spec["values"], spec["weights"], strict=True):
            assert abs(observed[category] / count - expected) <= tolerance
    for name, observed in (("regions", regions), ("industries", industries)):
        for item in config["company"][name]:
            assert abs(observed[item["code"]] / count - item["weight"]) <= tolerance
    median_tolerance = config["quality"]["median_relative_tolerance"]
    assert abs(np.median(ages) / config["company"]["age_median_years"] - 1) <= median_tolerance
    for segment, values in revenues.items():
        assert (
            abs(np.median(values) / config["company"][f"{segment}_revenue_median"] - 1)
            <= median_tolerance
        )
    for bucket, expected in enumerate(config["fns"]["debt_weights"]):
        assert abs(np.mean(np.array(debts) == bucket) - expected) <= tolerance
    np.testing.assert_allclose(
        np.mean(flags, axis=0), config["fns"]["flag_probability"], atol=tolerance
    )
    assert abs(np.mean(unavailable) - config["fns"]["unavailable_probability"]) < tolerance
    assert np.corrcoef(ages, overdue)[0, 1] < -0.02
