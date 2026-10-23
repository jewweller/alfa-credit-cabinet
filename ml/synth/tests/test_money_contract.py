import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from ml.synth.money import money, monthly_payment

REFERENCE = Path(__file__).parents[1] / "reference"


def test_payment_matches_actual_typescript_on_random_and_boundary_cases():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node >= 22 required for cross-language parity (installed in CI)")
    source = REFERENCE / "loanMath.ts"
    rng = np.random.default_rng(42)
    cases = [["3000000.00", "18.00", 12], ["0.01", "0.00", 2], ["0.05", "0.00", 2]]
    cases += [
        [
            money(float(rng.uniform(0.01, 30000000))),
            money(float(rng.uniform(0, 40))),
            int(rng.integers(1, 61)),
        ]
        for _ in range(200)
    ]
    script = (
        f"import {{ monthlyPayment }} from {json.dumps(source.as_uri())};\n"
        "import { readFileSync } from 'node:fs';\n"
        "const cases = JSON.parse(readFileSync(0, 'utf8'));\n"
        "console.log(JSON.stringify(cases.map(([a,r,n]) => monthlyPayment(a,r,n))));"
    )
    result = subprocess.run(
        [node, "--experimental-strip-types", "--input-type=module", "-e", script],
        input=json.dumps(cases),
        text=True,
        capture_output=True,
        check=True,
    )
    assert [monthly_payment(*case) for case in cases] == json.loads(result.stdout)


def test_catalog_and_enums_match_inspected_api(config):
    contract = json.loads((REFERENCE / "contract.json").read_text())["schemas"]
    required = set(contract["Product"]["required"])
    for product in config["products"]:
        assert set(product) == required
        assert set(product["purpose_tags"]) <= set(contract["LoanPurpose"]["enum"])
    assert set(config["company"]["kinds"]["values"]) == set(contract["CompanyKind"]["enum"])
    assert set(config["company"]["statuses"]["values"]) == set(
        contract["CompanyRegistryStatus"]["enum"]
    )


def test_live_loan_math_has_not_drifted_if_merged():
    live = Path(__file__).parents[3] / "frontend/src/mocks/loanMath.ts"
    if live.exists():
        assert live.read_bytes() == (REFERENCE / "loanMath.ts").read_bytes(), (
            "loanMath.ts changed: re-review and update the reference/parity test"
        )


@pytest.mark.parametrize(
    ("amount", "rate", "months"),
    [("-1.00", "18.00", 12), ("1.00", "-1.00", 12), ("1.00", "0.00", 0)],
)
def test_invalid_money_inputs_fail(amount, rate, months):
    with pytest.raises(ValueError):
        monthly_payment(amount, rate, months)
