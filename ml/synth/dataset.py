"""Validated training table; IDs, labels and oracle probabilities never enter X."""

import csv
import json
from pathlib import Path

import numpy as np
from app.schemas.ml import FeedRankRequest

from .features import FEATURES, features


def load_dataset(data: Path) -> dict:
    labels = {}
    with (data / "clicks.csv").open() as source:
        for row in csv.DictReader(source):
            key = (int(row["request_id"]), row["candidate_id"])
            if key in labels:
                raise ValueError(f"Duplicate label: {key}")
            click, interest = int(row["click"]), float(row["p_interest"])
            if click not in (0, 1) or not 0 <= interest <= 1:
                raise ValueError("Invalid label or oracle probability")
            labels[key] = (click, interest)
    parts = {
        s: {"X": [], "y": [], "qid": [], "rules": [], "groups": []}
        for s in ("train", "validation", "test")
    }
    clients, seen = {}, set()
    with (data / "requests.jsonl").open() as requests, (data / "metadata.jsonl").open() as metadata:
        for line, meta_line in zip(requests, metadata, strict=True):
            payload = FeedRankRequest.model_validate_json(line).model_dump(mode="json")
            meta = json.loads(meta_line)
            rid, cid, split = meta["request_id"], meta["client_id"], meta["split"]
            if rid in seen:
                raise ValueError("Duplicate request ID")
            seen.add(rid)
            if split not in parts:
                raise ValueError("Unknown split")
            if cid in clients and clients[cid] != split:
                raise ValueError("Client leakage across splits")
            clients[cid] = split
            part = parts[split]
            start = len(part["X"])
            ids = [c["id"] for c in payload["candidates"]]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate candidate ID")
            clicks, interest = [], []
            for candidate in payload["candidates"]:
                key = (rid, candidate["id"])
                if key not in labels:
                    raise ValueError(f"Missing label: {key}")
                click, probability = labels.pop(key)
                part["X"].append(features(payload["profile"], candidate, payload["now"]))
                part["y"].append(click)
                part["qid"].append(len(part["groups"]))
                part["rules"].append(candidate["rule_score"])
                clicks.append(click)
                interest.append(probability)
            part["groups"].append(
                {
                    "start": start,
                    "end": len(part["X"]),
                    "ids": ids,
                    "clicks": clicks,
                    "interest": interest,
                    "client_id": cid,
                    "request_id": rid,
                    "published": [c["published_at"] for c in payload["candidates"]],
                }
            )
    if labels:
        raise ValueError("Labels contain unknown candidates or requests")
    for part in parts.values():
        if not part["groups"]:
            raise ValueError("Each split must contain requests")
        part["X"] = np.asarray(part["X"], dtype=np.float32)
        part["y"] = np.asarray(part["y"], dtype=np.int32)
        part["qid"] = np.asarray(part["qid"], dtype=np.int32)
        part["rules"] = np.asarray(part["rules"], dtype=np.float64)
        if part["X"].shape[1] != len(FEATURES) or not np.isfinite(part["X"]).all():
            raise ValueError("Invalid feature matrix")
    if len(np.unique(parts["train"]["y"])) != 2:
        raise ValueError("Training needs both click classes")
    return parts
