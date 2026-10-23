"""python -m ml.synth --config ml/synth/config.yaml --seed 42 --out data/"""

import argparse
import sys

from .config import DEFAULT_CONFIG, load_config
from .generate import generate


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate reproducible synthetic credit-ranking journals"
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--debug", action="store_true", help="1%% company population")
    parser.add_argument("--companies", type=int, help="explicit population override (at least 10)")
    args = parser.parse_args(argv)
    try:
        path = generate(
            load_config(args.config),
            args.seed,
            args.out,
            debug=args.debug,
            companies=args.companies,
            progress=lambda done, total: print(f"Companies: {done}/{total}", file=sys.stderr),
        )
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(path)


if __name__ == "__main__":
    main()
