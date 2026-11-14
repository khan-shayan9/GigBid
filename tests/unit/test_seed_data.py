"""Invariants of the committed seed and eval data (rebuilt by `make seed`)."""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "gigsim_seed"
EVALS = ROOT / "evals" / "datasets"
LABEL_KEYS = {"kind", "family", "is_scam", "decision", "injection_family", "duplicate_of"}


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _annotations() -> dict[str, dict]:
    return {note["job_id"]: note for note in _rows(EVALS / "job_annotations.jsonl")}


def test_every_record_is_tagged_with_its_source() -> None:
    files = [*SEED.glob("*.jsonl"), *EVALS.glob("*.jsonl"), *ROOT.glob("data/personas/*/*.jsonl")]
    assert len(files) >= 14
    for path in files:
        for row in _rows(path):
            assert row["source"] == "synthetic" or row["source"].startswith("kaggle:"), path


def test_served_jobs_carry_no_labels() -> None:
    for row in _rows(SEED / "jobs.jsonl"):
        assert not LABEL_KEYS & row.keys()


def test_job_kind_is_not_readable_from_id_order() -> None:
    notes = _annotations()
    numbers = {kind: [int(job_id[-5:]) for job_id, note in notes.items() if note["kind"] == kind]
               for kind in ["real", "scam", "duplicate"]}
    for kind in ["scam", "duplicate"]:
        assert min(numbers[kind]) < max(numbers["real"])
        assert max(numbers[kind]) > min(numbers["real"])


def test_splits_keep_groups_together() -> None:
    labels = _rows(EVALS / "dev.jsonl") + _rows(EVALS / "heldout.jsonl")
    split_of = {label["job_id"]: label["split"] for label in labels}
    sides_by_group: dict[str, set[str]] = defaultdict(set)
    for job_id, note in _annotations().items():
        if job_id in split_of:
            sides_by_group[note["group_id"]].add(split_of[job_id])
    assert all(len(sides) == 1 for sides in sides_by_group.values())
    assert {"dev", "heldout"} == set(split_of.values())


def test_heldout_injection_families_never_appear_in_dev() -> None:
    labels = _rows(EVALS / "dev.jsonl") + _rows(EVALS / "heldout.jsonl")
    heldout = {label["injection_family"] for label in labels
               if label["split"] == "heldout" and label["injection_family"]}
    dev_jobs = {label["injection_family"] for label in labels if label["split"] == "dev"}
    dev_messages = {message["injection_family"] for message in
                    _rows(EVALS / "message_annotations.jsonl") if message["split"] == "dev"}
    assert heldout and not heldout & (dev_jobs | dev_messages)
