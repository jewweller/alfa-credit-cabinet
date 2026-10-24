"""Generate exact backend payloads plus a separate training metadata file."""

import argparse
import copy
import json
import random
from datetime import timedelta
from pathlib import Path

# Run with PYTHONPATH=..:../backend from ml/. These imports are read-only reuse.
from app.domain.feed_ranking import OKVED_NAMES, FeedProfile, eligible_news
from app.domain.state_machine import ApplicationStatus
from app.schemas.companies import CompanyKind, CompanySegment
from app.schemas.feed import NewsItem
from app.schemas.ml import FeedRankCandidate, FeedRankRequest, RankerProfile
from app.schemas.products import LoanPurpose

REPO = Path(__file__).resolve().parents[2]
PURPOSES = {
    "EXPRESS_WC": LoanPurpose.WORKING_CAPITAL,
    "EQUIPMENT": LoanPurpose.EQUIPMENT,
    "OVERDRAFT": LoanPurpose.CASH_GAP,
}
REGIONS = ["Москва", "Московская область", "Санкт-Петербург", "Казань", "Екатеринбург"]
STATUSES = [s for s in ApplicationStatus if s != ApplicationStatus.CANCELLED]


def random_applications(rng: random.Random, products: dict) -> list[dict]:
    apps = []
    for _ in range(rng.choice([0, 0, 1, 1, 1, 2])):
        code = rng.choice(list(products))
        apps.append(
            {
                "status": rng.choice(STATUSES),
                "product_code": code,
                "purpose": PURPOSES[code],
            }
        )
    # Null product/purpose are legitimate in the backend contract (unfinished draft).
    for app in apps:
        if app["status"] == ApplicationStatus.DRAFT and rng.random() < 0.25:
            app.update(product_code=None, purpose=None)
    return apps


def generate(out: Path, clients: int = 4000, visits: int = 3, seed: int = 42) -> dict:
    if clients < 10 or visits < 1:
        raise ValueError("Need at least 10 clients and one visit")
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    news = [
        NewsItem.model_validate(n)
        for n in json.loads((REPO / "seed/news.json").read_text(encoding="utf-8"))
    ]
    products = {
        p["code"]: p["name"]
        for p in json.loads((REPO / "seed/products.json").read_text(encoding="utf-8"))
    }
    # No future news; keep the original catalogue and its timestamps unchanged.
    start = max(n.published_at for n in news) + timedelta(hours=2)
    ids = list(range(clients))
    random.Random(seed + 1000).shuffle(ids)
    train_end, valid_end = int(clients * 0.7), int(clients * 0.85)
    splits = {
        cid: "train" if i < train_end else "validation" if i < valid_end else "test"
        for i, cid in enumerate(ids)
    }
    count, rows = 0, 0
    with (
        (out / "requests.jsonl").open("w", encoding="utf-8") as requests,
        (out / "metadata.jsonl").open("w", encoding="utf-8") as metadata,
    ):
        for cid in range(clients):
            segment = rng.choice(list(CompanySegment))
            revenue = {}
            if rng.random() < 0.85:
                base = int(rng.lognormvariate(16 if segment == "micro" else 18, 0.6))
                revenue = {"2024": base, "2025": int(base * rng.uniform(0.4, 2.0))}
            profile = {
                "kind": rng.choice(list(CompanyKind)),
                "okved_main": rng.choice(list(OKVED_NAMES)),
                "region": rng.choice(REGIONS),
                "segment": segment,
                "registered_at": (start.date() - timedelta(days=rng.randint(30, 16 * 365))),
                "revenue": revenue,
                "applications": [],
            }
            for visit in range(visits):
                now = start + timedelta(days=visit * 10, hours=rng.randint(0, 9 * 24))
                current = copy.deepcopy(profile)
                current["applications"] = random_applications(rng, products)
                parsed = RankerProfile.model_validate(current)
                filtered = eligible_news(
                    news,
                    FeedProfile(
                        okved_main=parsed.okved_main,
                        segment=parsed.segment,
                        products={
                            a.product_code: products[a.product_code]
                            for a in parsed.applications
                            if a.product_code in products
                        },
                        statuses=frozenset(a.status for a in parsed.applications),
                    ),
                    now,
                )
                if len(filtered) < 2:
                    raise ValueError("Catalogue must supply at least two candidates per request")
                candidates = [
                    FeedRankCandidate(
                        **r.news.model_dump(),
                        rule_score=r.score,
                        matched=[x.code for x in r.reasons],
                    )
                    for r in filtered
                ]
                # Input position must not be a proxy for relevance.
                rng.shuffle(candidates)
                payload = FeedRankRequest(now=now, profile=parsed, candidates=candidates)
                requests.write(payload.model_dump_json() + "\n")
                metadata.write(
                    json.dumps(
                        {
                            "request_id": count,
                            "client_id": cid,
                            "split": splits[cid],
                        }
                    )
                    + "\n"
                )
                count += 1
                rows += len(candidates)
    result = {
        "seed": seed,
        "clients": clients,
        "visits": visits,
        "requests": count,
        "candidate_rows": rows,
        "catalogue_news": len(news),
    }
    (out / "generation.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data/seed-42"))
    parser.add_argument("--clients", type=int, default=4000)
    parser.add_argument("--visits", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(generate(args.out, args.clients, args.visits, args.seed)))


if __name__ == "__main__":
    main()
