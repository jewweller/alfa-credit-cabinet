import sys
import types

import ml.synth.rules as rules
import pyarrow.parquet as pq
import pytest
from ml.synth.generate import generate


def test_completely_filtered_run_still_has_typed_tables(config, tmp_path):
    config["company"]["statuses"]["weights"] = [0, 0, 1]
    directory = generate(config, 17, tmp_path, companies=10)
    for name in ("train", "validation", "test", "candidates", "evaluation", "outcomes"):
        table = pq.read_table(directory / f"{name}.parquet")
        assert table.num_rows == 0 and len(table.schema) > 0
    assert pq.read_table(directory / "requests.parquet").num_rows > 0
    assert pq.read_table(directory / "latent_truth.parquet").num_rows > 0


def test_reference_adapter_refuses_silent_backend_duplication(config, tmp_path, monkeypatch):
    fake_file = tmp_path / "ml/synth/rules.py"
    monkeypatch.setattr(rules, "__file__", str(fake_file))
    backend = tmp_path / "backend/app/scoring"
    backend.mkdir(parents=True)
    (backend / "engine.py").write_text("# existing backend engine\n")
    with pytest.raises(ValueError, match="backend engines exist"):
        rules.load_engine(config)


def test_explicit_backend_adapter_is_used(config, monkeypatch):
    module = types.ModuleType("test_synth_backend_adapter")
    module.Engine = rules.PlanRules
    monkeypatch.setitem(sys.modules, module.__name__, module)
    config["rules"]["adapter"] = f"{module.__name__}:Engine"
    assert isinstance(rules.load_engine(config), rules.PlanRules)
