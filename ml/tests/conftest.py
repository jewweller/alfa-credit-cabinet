import json
from pathlib import Path

import pytest
from ml.synth.make_requests import generate
from ml.synth.simulate import simulate

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def payload():
    return json.loads((REPO / "docs/ml/feed-rank.request.json").read_text())


@pytest.fixture(scope="session")
def generated(tmp_path_factory):
    path = tmp_path_factory.mktemp("dataset")
    generate(path, clients=40, visits=3, seed=11)
    simulate(path, seed=12)
    return path
