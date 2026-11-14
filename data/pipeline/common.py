"""Shared paths, constants and deterministic file helpers for the data pipeline."""

import csv
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

SEED = 4016

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / "kaggle"
SEED_DIR = REPO_ROOT / "data" / "gigsim_seed"
PERSONA_DIR = REPO_ROOT / "data" / "personas"
EVAL_DIR = REPO_ROOT / "evals" / "datasets"

SOURCE_JOBS_50K = "kaggle:asaniczka/upwork-job-postings-dataset-2024-50k-records"
SOURCE_JOBS_60K = "kaggle:ahmedmyalo/upwork-freelance-jobs-60k"
SOURCE_CONTRACTS = "kaggle:asaniczka/freelance-contracts-dataset-1-3-million-entries"
SOURCE_FREELANCERS = "kaggle:sarveshchhetri/freelancer-success-earnings-and-churn-prediction"
SOURCE_SYNTHETIC = "synthetic"

csv.field_size_limit(10**9)


def read_csv(path: Path) -> Iterator[dict[str, str]]:
    """Yield rows in file order; utf-8-sig strips the BOM some Kaggle exports carry."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    """Write one JSON object per line with LF endings so rebuilds are byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def parse_money(text: str) -> float | None:
    """'$2,500 ' -> 2500.0; empty or zero -> None."""
    cleaned = text.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None
