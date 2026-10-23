# Reproducible 1% example

The adjacent `synth-v0.1.0-seed42-54374ff37dfc/` is a complete synthetic example:
200 companies, 596 requests and 9,421 candidates, generated with the default
configuration and `--debug`. It includes empty/zero-positive requests, all
journals, the three flat splits, a data card and checksums.

From the repository root:

```sh
uv sync --project ml --frozen
uv run --project ml python -m ml.synth --seed 42 --debug --out /tmp/alfa-replay
```

Compare the output with `manifest.json`. Byte-level reproduction requires the
same runtime recorded there (Python 3.12.4 and the locked package versions).
Run-specific source digests make changes to the generator explicit.

This is a small inspection fixture, not a representative benchmark. The checked
experiment reports use the full 20,000-company configuration. Complete datasets
are generated locally and excluded from Git; no real customer data is present.
