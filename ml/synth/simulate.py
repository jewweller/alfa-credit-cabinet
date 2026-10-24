"""Behavioral hypotheses on raw payloads; the trainer sees sampled clicks only."""

import argparse
import csv
import json
import math
import random
from datetime import date, datetime
from pathlib import Path

SIMULATOR_VERSION = "feed-behavior-1"


def interest(profile: dict, candidate: dict, now: str, scenario: str = "mixed") -> float:
    """Latent logit, never a training feature. Hypotheses are documented in DATA_CARD.md."""
    days = max(
        0,
        (
            datetime.fromisoformat(now) - datetime.fromisoformat(candidate["published_at"])
        ).total_seconds()
        / 86400,
    )
    age = (
        datetime.fromisoformat(now).date() - date.fromisoformat(profile["registered_at"])
    ).days / 365
    apps, topic, matched = profile["applications"], candidate["topic"], set(candidate["matched"])
    action = any(
        a["status"] in {"INFO_REQUESTED", "APPROVED", "COUNTER_OFFER", "SIGNING"} for a in apps
    )
    small_or_young = profile["segment"] == "micro" or age < 2
    revenue = profile["revenue"]
    years = sorted(revenue, key=int)
    growth = 0.0
    if len(years) >= 2 and revenue[years[-2]] > 0:
        growth = max(-1, min(1, revenue[years[-1]] / revenue[years[-2]] - 1))
    equipment = "EQUIPMENT" in candidate["tags"]["product"]
    known = bool(set(candidate["tags"]["product"]) & {a["product_code"] for a in apps})
    z = -2.4 + 0.9 * ("okved" in matched) + 0.4 * ("product" in matched)
    z += 0.3 * ("segment" in matched) + 0.5 * ("status" in matched)
    z += 1.1 * (topic == "step" and action)
    z += 0.8 * (topic == "support" and small_or_young)
    z += 0.7 * (topic == "product" and not apps)
    z += 1.2 * math.exp(-days / 7)
    z += 0.8 * equipment * max(0, growth)
    if scenario == "mixed":
        # A pending action gives practical instructions priority over product discovery.
        z += 1.0 * (topic == "step" and action and days < 21)
        z -= 0.8 * (topic == "product" and action)
        # Support matters more when a small/young company is losing revenue.
        z += 1.1 * (topic == "support" and small_or_young and growth < -0.1)
        # Expansion has a threshold and diminishing returns, not unlimited linear benefit.
        if equipment:
            z += 1.3 * (growth > 0.2) - 0.8 * (growth < -0.1)
            z += 0.4 * min(max(growth - 0.2, 0), 0.3) / 0.3
        # Sector news expires faster; advice linked to an application remains useful longer.
        z -= 0.9 * (topic == "industry" and days > 14)
        z -= 0.5 * (topic == "product" and known and days > 21)
    elif scenario != "additive":
        raise ValueError(f"Unknown scenario: {scenario}")
    return z


def simulate(data: Path, seed: int = 7, scenario: str = "mixed") -> dict:
    rng = random.Random(seed)
    clients = {}
    rows, clicks = 0, 0
    with (
        (data / "requests.jsonl").open() as requests,
        (data / "metadata.jsonl").open() as metadata,
        (data / "clicks.csv").open("w", newline="") as output,
    ):
        writer = csv.writer(output)
        writer.writerow(["request_id", "candidate_id", "click", "p_interest"])
        for line, meta_line in zip(requests, metadata, strict=True):
            request, meta = json.loads(line), json.loads(meta_line)
            cid = meta["client_id"]
            if cid not in clients:
                clients[cid] = rng.gauss(0, 0.35)
            request_bias = clients[cid] + rng.gauss(0, 0.2)
            for candidate in request["candidates"]:
                z = interest(request["profile"], candidate, request["now"], scenario)
                # All candidates are exposed; no artificial position bias is introduced.
                p = 1 / (1 + math.exp(-(z + request_bias)))
                click = int(rng.random() < p)
                writer.writerow([meta["request_id"], candidate["id"], click, round(p, 8)])
                clicks += click
                rows += 1
    result = {
        "simulator_version": SIMULATOR_VERSION,
        "seed": seed,
        "scenario": scenario,
        "rows": rows,
        "click_rate": clicks / rows if rows else 0,
    }
    (data / "simulation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/seed-42"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--scenario", choices=["mixed", "additive"], default="mixed")
    args = parser.parse_args()
    print(json.dumps(simulate(args.data, args.seed, args.scenario)))


if __name__ == "__main__":
    main()
