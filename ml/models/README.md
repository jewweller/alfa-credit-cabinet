# Offline synthetic ranker artifact

`ranker-0.1.0.json` is an XGBoost 3.0.2 model trained on the default 20,000-company
configuration with seed 42. This seed was selected by convention before comparing
seeds, not by the highest test score. `features.json` contains the exact feature
order and categorical vocabulary; `provenance.json` records source, data and
artifact hashes. `training-report.json` includes validation-selected iteration,
test results, ablations, regional/segment diagnostics and feature importance.

Load through `XGBRanker.load_model` and `ml.synth.features.model_frame`, or use
`ml.synth.ranking.rank_candidates`. This preserves categories and the saved
early-stopping iteration. Do not pass IDs, shown positions or outcome fields.

The artifact is for offline reproduction. `RANKER_ENABLED` remains false in the
integration design; no backend route or production configuration is changed by
this module. Deployment criteria and the remaining rule ambiguities in
`ml/DATA_CARD.md` must be resolved before product integration.

Reproduce from the repository root:

```sh
uv run --project ml python -m ml.synth --seed 42 --out data/reproduce
uv run --project ml python -m ml.synth.train \
  --data data/reproduce/synth-v0.1.0-seed42-e5d55793d403 \
  --out ml/runs/reproduced-model
```
