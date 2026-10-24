"""Модель ленты (ml/): логистическая регрессия, причины, контракт, без тяжёлых зависимостей."""

import ast
import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from ml import rank_feed, rank_products  # noqa: E402
from ml.synth import logreg, ranking  # noqa: E402
from ml.synth.features import FEATURES, features  # noqa: E402

from app.schemas.ml import FeedRankRequest, FeedRankResponse, is_permutation  # noqa: E402

EXAMPLE = json.loads((REPO / "docs/ml/feed-rank.request.json").read_text(encoding="utf-8"))
MODEL = json.loads(ranking.MODEL_PATH.read_text(encoding="utf-8"))
STDLIB = set(sys.stdlib_module_names)


def _payload() -> dict:
    return FeedRankRequest.model_validate(EXAMPLE).model_dump(mode="json")


def _z(payload: dict, candidate: dict) -> float:
    x = features(payload["profile"], candidate, payload["now"])
    return MODEL["intercept"] + sum(w * v for w, v in zip(MODEL["coef"], x, strict=True))


# ── Модель и её параметры ───────────────────────────────────────────────────


def test_model_file_matches_features() -> None:
    assert MODEL["model_version"] == "feed-logreg-1.0.0"
    assert MODEL["features"] == FEATURES and len(MODEL["coef"]) == 20
    assert all(math.isfinite(c) for c in [*MODEL["coef"], MODEL["intercept"]])


def test_published_weights_are_reproduced_by_training(tmp_path: Path) -> None:
    """Переобучение на тех же синтетических данных (seed 42) даёт те же коэффициенты."""
    trained = logreg.train(tmp_path / "seed-42")

    assert trained["training"]["data_sha256"] == MODEL["training"]["data_sha256"]
    assert trained["C"] == MODEL["C"]
    assert trained["intercept"] == pytest.approx(MODEL["intercept"], abs=1e-9)
    assert trained["coef"] == pytest.approx(MODEL["coef"], abs=1e-9)


def test_score_is_logistic_regression_of_features() -> None:
    payload = _payload()

    result = rank_feed(payload)

    by_id = {c["id"]: c for c in payload["candidates"]}
    for item in result["ranking"]:
        expected = 1 / (1 + math.exp(-_z(payload, by_id[item["id"]])))
        assert item["score"] == pytest.approx(expected, rel=1e-12)
    zs = [_z(payload, by_id[item["id"]]) for item in result["ranking"]]
    assert zs == sorted(zs, reverse=True)


# ── Контракт ответа ─────────────────────────────────────────────────────────


def test_answer_passes_backend_schema_and_keeps_candidates() -> None:
    payload = _payload()

    result = rank_feed(payload)

    response = FeedRankResponse.model_validate(result)
    assert response.model_version == "feed-logreg-1.0.0"
    candidates = [c["id"] for c in payload["candidates"]]
    assert is_permutation([str(i.id) for i in response.ranking], candidates)
    assert all(0 < i.score < 1 for i in response.ranking)


def test_model_changes_order_and_is_deterministic() -> None:
    payload = _payload()
    rules = sorted(payload["candidates"], key=lambda c: -c["rule_score"])

    first, second = rank_feed(payload), rank_feed(_payload())

    assert first == second
    assert [i["id"] for i in first["ranking"]] != [c["id"] for c in rules]


def test_empty_candidates_give_empty_ranking() -> None:
    payload = {**_payload(), "candidates": []}

    assert rank_feed(payload) == {"model_version": "feed-logreg-1.0.0", "ranking": []}


@pytest.mark.parametrize(
    "broken",
    [
        lambda p: {k: v for k, v in p.items() if k != "profile"},
        lambda p: {**p, "candidates": [p["candidates"][0], p["candidates"][0]]},
        lambda p: {**p, "candidates": [{**p["candidates"][0], "published_at": "вчера"}]},
        lambda p: {
            **p,
            "candidates": [{k: v for k, v in p["candidates"][0].items() if k != "matched"}],
        },
        lambda p: {**p, "profile": {**p["profile"], "registered_at": None}},
    ],
    ids=["no-profile", "duplicate", "bad-date", "no-matched", "no-registration"],
)
def test_invalid_input_raises_value_error(broken) -> None:  # noqa: ANN001
    with pytest.raises(ValueError):
        rank_feed(broken(_payload()))


def test_extreme_scores_stay_finite() -> None:
    assert ranking._sigmoid(1000) == 1.0 and ranking._sigmoid(-1000) == 0.0


def test_broken_model_file_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = tmp_path / "model.json"
    bad.write_text(json.dumps({**MODEL, "features": FEATURES[:-1]}))
    monkeypatch.setattr(ranking, "MODEL_PATH", bad)
    ranking._model.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            rank_feed(_payload())
    finally:
        ranking._model.cache_clear()


# ── Причины показа ──────────────────────────────────────────────────────────


def test_reasons_are_matched_tags_with_positive_contribution() -> None:
    payload = _payload()
    by_id = {c["id"]: c for c in payload["candidates"]}

    result = rank_feed(payload)

    assert any(item["reasons"] for item in result["ranking"])
    for item in result["ranking"]:
        candidate = by_id[item["id"]]
        x = features(payload["profile"], candidate, payload["now"])
        assert len(item["reasons"]) <= 2
        for reason in item["reasons"]:
            assert reason["code"] in candidate["matched"]
            assert reason["code"] in {"okved", "status", "product", "segment"}
            feature = next(f for f, c in ranking.REASON_FEATURES.items() if c == reason["code"])
            assert MODEL["coef"][FEATURES.index(feature)] * x[FEATURES.index(feature)] > 0
            assert 0 < len(reason["text"]) <= 120


def test_reasons_do_not_leak_personal_data() -> None:
    payload = _payload()
    payload["profile"]["revenue"] = {"2024": 123456789, "2025": 987654321}

    text = json.dumps(rank_feed(payload), ensure_ascii=False)

    for secret in ("123456789", "987654321", "ИНН", payload["profile"]["region"]):
        assert secret not in text


def test_reason_texts_fit_every_profile() -> None:
    for segment in ("micro", "small"):
        for code in ("okved", "status", "product", "segment"):
            text = ranking._reason_text(code, {"okved_main": "10.71", "segment": segment})
            assert 0 < len(text) <= 120


# ── Без тяжёлых зависимостей ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "module", ["ml/__init__.py", "ml/synth/ranking.py", "ml/synth/features.py"]
)
def test_inference_uses_only_standard_library(module: str) -> None:
    tree = ast.parse((REPO / module).read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
    }
    assert imported <= STDLIB, imported - STDLIB


def test_inference_does_not_load_heavy_libraries() -> None:
    rank_feed(_payload())

    assert not {"numpy", "xgboost", "sklearn"} & set(sys.modules)


def test_products_are_not_reordered() -> None:
    ids = ["7f1c2b0a-0000-4000-8000-000000000001", "7f1c2b0a-0000-4000-8000-000000000003"]
    payload = {"candidates": [{"product": {"id": i}} for i in ids]}

    assert [r["product_id"] for r in rank_products(payload)["ranking"]] == ids
