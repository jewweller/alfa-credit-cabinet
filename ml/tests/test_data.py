import csv
import json
import shutil

import numpy as np
import pytest
from app.domain.feed_ranking import FeedProfile, eligible_news
from app.schemas.feed import NewsItem
from app.schemas.ml import FeedRankRequest
from ml.synth.dataset import load_dataset
from ml.synth.make_requests import REPO, generate
from ml.synth.simulate import simulate


def test_generated_requests_match_backend_schema_and_selection(generated):
    news = [NewsItem.model_validate(n) for n in json.loads((REPO / "seed/news.json").read_text())]
    products = {p["code"]: p["name"] for p in json.loads((REPO / "seed/products.json").read_text())}
    for line in (generated / "requests.jsonl").read_text().splitlines():
        raw = json.loads(line)
        assert set(raw) == {"now", "profile", "candidates"}
        request = FeedRankRequest.model_validate(raw)
        profile = request.profile
        eligible = eligible_news(
            news,
            FeedProfile(
                okved_main=profile.okved_main,
                segment=profile.segment,
                products={
                    a.product_code: products[a.product_code]
                    for a in profile.applications
                    if a.product_code in products
                },
                statuses=frozenset(a.status for a in profile.applications),
            ),
            request.now,
        )
        assert {c.id for c in request.candidates} == {r.news.id for r in eligible}
        expected = {r.news.id: r for r in eligible}
        for candidate in request.candidates:
            assert candidate.rule_score == expected[candidate.id].score
            assert candidate.matched == [r.code for r in expected[candidate.id].reasons]
            assert candidate.published_at <= request.now


def test_generation_and_clicks_are_reproducible(generated, tmp_path):
    generate(tmp_path, clients=40, visits=3, seed=11)
    simulate(tmp_path, seed=12)
    for name in ("requests.jsonl", "metadata.jsonl", "clicks.csv"):
        assert (generated / name).read_bytes() == (tmp_path / name).read_bytes()


def test_clients_do_not_cross_splits_and_qid_is_grouped(generated):
    parts = load_dataset(generated)
    seen = set()
    for part in parts.values():
        clients = {g["client_id"] for g in part["groups"]}
        assert not clients & seen
        seen |= clients
        assert np.all(np.diff(part["qid"]) >= 0)
        assert part["X"].shape[1] == 20
        for qid, group in enumerate(part["groups"]):
            assert np.all(part["qid"][group["start"] : group["end"]] == qid)


def test_loader_rejects_client_leakage(generated, tmp_path):
    shutil.copytree(generated, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "metadata.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]["split"] = "test" if rows[0]["split"] != "test" else "train"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="Client leakage"):
        load_dataset(tmp_path)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "extra"])
def test_loader_rejects_bad_label_join(generated, tmp_path, kind):
    shutil.copytree(generated, tmp_path, dirs_exist_ok=True)
    path = tmp_path / "clicks.csv"
    lines = path.read_text().splitlines()
    if kind == "missing":
        lines.pop()
    elif kind == "duplicate":
        lines.append(lines[1])
    else:
        lines.append("999999,unknown,0,0.5")
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="label|Labels"):
        load_dataset(tmp_path)


def test_oracle_probabilities_do_not_affect_training_matrix(generated, tmp_path):
    shutil.copytree(generated, tmp_path, dirs_exist_ok=True)
    before = load_dataset(generated)
    path = tmp_path / "clicks.csv"
    with path.open() as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        rows = list(reader)
    with path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            row["p_interest"] = "0.12345"
            writer.writerow(row)
    after = load_dataset(tmp_path)
    for split in before:
        np.testing.assert_array_equal(before[split]["X"], after[split]["X"])
        np.testing.assert_array_equal(before[split]["y"], after[split]["y"])
