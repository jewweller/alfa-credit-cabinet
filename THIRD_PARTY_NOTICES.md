# Third-party notices — offline synthetic ranking module

The generator does not use real customer datasets, paid APIs, SDV, or closed models.
All distribution parameters are synthetic assumptions documented in `ml/DATA_CARD.md`.
The XGBoost model is trained on these synthetic records only.

Direct dependencies are pinned in `ml/pyproject.toml`; direct and transitive
versions and package hashes are recorded in `ml/uv.lock`. Packages retain their
copyright and license notices in the installed distributions.

| Component | Version | License | Purpose |
|---|---|---|---|
| NumPy | 2.2.6 | BSD-3-Clause | Seeded random generation and numerical arrays |
| SciPy | 1.15.3 | BSD-3-Clause | Normal CDF/copula and logistic probabilities |
| pandas | 2.2.3 | BSD-3-Clause | Categoricals, model matrices, evaluation |
| Apache Arrow / PyArrow | 19.0.1 | Apache-2.0 | Deterministic Parquet journals |
| Faker | 37.3.0 | MIT | Synthetic Russian names, addresses, valid INNs |
| PyYAML | 6.0.2 | MIT | Safe configuration loading |
| scikit-learn | 1.6.1 | BSD-3-Clause | Company-group split and estimator interface |
| XGBoost | 3.0.2 | Apache-2.0 | Learning to rank, JSON model artifact |
| pytest | 8.3.5 | MIT | Tests |
| Ruff | 0.11.13 | MIT | Lint and formatting |

Transitive Python components: cloudpickle (BSD-3-Clause), colorama (BSD-3-Clause),
iniconfig (MIT), joblib
(BSD-3-Clause), packaging (Apache-2.0 OR BSD-2-Clause), pluggy (MIT), python-dateutil
(Apache-2.0 OR BSD-3-Clause), pytz (MIT), six (MIT), threadpoolctl (BSD-3-Clause),
tzdata (Apache-2.0 with public-domain IANA data). Linux XGBoost wheels may include
the separately licensed `nvidia-nccl-cu12` runtime (BSD-3-Clause); GPU execution
is not used. Binary scientific wheels contain additional bundled notices for
their numerical libraries; preserve those notices when redistributing wheels.

Simulated integrations: EGRUL/EGRIP company registration data, FNS financial data,
BKI credit reports, manual underwriting, customer consent, acceptance and issuance.
No requests are sent to these services, no credit is issued, and no external
person is contacted by this module.

The TypeScript reference in `ml/synth/reference/loanMath.ts` is copied from this
same repository at the commit recorded in `ml/DATA_CARD.md`, solely for parity tests.
