"""Measure fresh-process startup and warm 15-candidate latency, without a service."""

import copy
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from uuid import UUID

import numpy as np

from ml import rank_feed, warmup

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    example = ROOT.parent / "docs/ml/feed-rank.request.json"
    payload = json.loads(example.read_text())
    payload["candidates"] = [
        {
            **copy.deepcopy(payload["candidates"][i % len(payload["candidates"])]),
            "id": str(UUID(int=i + 1)),
        }
        for i in range(15)
    ]
    code = """
import json, sys, time
payload = json.load(sys.stdin)
start = time.perf_counter()
from ml import rank_feed
rank_feed(payload)
print(time.perf_counter() - start)
"""
    cold = [
        float(
            subprocess.run(
                [sys.executable, "-c", code],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=True,
            ).stdout
        )
        for _ in range(3)
    ]
    model_version = warmup()
    durations = []
    for _ in range(1000):
        start = time.perf_counter()
        rank_feed(payload)
        durations.append(time.perf_counter() - start)
    result = {
        "model_version": model_version,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "candidates": 15,
        "warm_calls": len(durations),
        "fresh_process_import_and_first_call_ms": [1000 * t for t in cold],
        "warm_p50_ms": float(np.quantile(durations, 0.5) * 1000),
        "warm_p95_ms": float(np.quantile(durations, 0.95) * 1000),
        "warm_max_ms": max(durations) * 1000,
    }
    (ROOT / "reports/latency.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
