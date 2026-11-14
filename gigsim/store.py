"""Seed loader. Reads one or more seed folders in the format documented in docs/DATA_CARD.md §8.

New grader jobs and clients are a new folder in GIGSIM_SEED_DIRS, never a code change.
Every file is optional per folder; cross-references are checked after all folders load.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from gigsim.models import Client, ClientPrefs, Conversation, HistoricalJob, Job

ModelT = TypeVar("ModelT", bound=BaseModel)


class SeedError(ValueError):
    """Seed data is malformed or inconsistent; GigSim refuses to start on it."""


@dataclass
class Seed:
    jobs: dict[str, Job] = field(default_factory=dict)
    clients: dict[str, Client] = field(default_factory=dict)
    client_prefs: dict[str, dict[str, Any]] = field(default_factory=dict)
    release_min: dict[str, float] = field(default_factory=dict)
    client_first_release: dict[str, float] = field(default_factory=dict)
    conversations: dict[str, Conversation] = field(default_factory=dict)
    historical_jobs: dict[str, HistoricalJob] = field(default_factory=dict)
    market_domains: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_seed(seed_dirs: list[Path], default_client_prefs: dict[str, Any]) -> Seed:
    seed = Seed()
    for seed_dir in seed_dirs:
        if not seed_dir.is_dir():
            raise SeedError(f"seed folder not found: {seed_dir}")
        _load_folder(seed, seed_dir)
    _check_references(seed)
    for job_id in seed.jobs:
        seed.release_min.setdefault(job_id, 0.0)  # a job without a stream entry is live at start
    for client_id in seed.clients:
        merged = {**default_client_prefs, **seed.client_prefs.get(client_id, {})}
        try:
            seed.client_prefs[client_id] = ClientPrefs.model_validate(merged).model_dump()
        except ValidationError as error:
            raise SeedError(f"client_prefs for {client_id}: {error}") from error
    for job in seed.jobs.values():
        release = seed.release_min[job.job_id]
        first = seed.client_first_release.get(job.client_id, release)
        seed.client_first_release[job.client_id] = min(first, release)
    return seed


def _load_folder(seed: Seed, seed_dir: Path) -> None:
    _add_models(seed.jobs, seed_dir / "jobs.jsonl", Job, "job_id")
    _add_models(seed.clients, seed_dir / "clients.jsonl", Client, "client_id")
    _add_models(seed.historical_jobs, seed_dir / "historical_jobs.jsonl", HistoricalJob, "job_id")
    for where, row in _read_jsonl(seed_dir / "client_prefs.jsonl"):
        _put(seed.client_prefs, row.get("client_id"), row, where)
    _add_models(seed.conversations, seed_dir / "conversations.jsonl", Conversation,
                "conversation_id")
    for where, row in _read_jsonl(seed_dir / "stream.jsonl"):
        release = row.get("release_after_min")
        if not isinstance(release, int | float) or release < 0:
            raise SeedError(f"{where}: release_after_min must be a number >= 0")
        _put(seed.release_min, row.get("job_id"), float(release), where)
    rates_path = seed_dir / "market_rates.json"
    if rates_path.exists():
        seed.market_domains.update(json.loads(rates_path.read_text(encoding="utf-8"))["domains"])


def _check_references(seed: Seed) -> None:
    for job in seed.jobs.values():
        if job.client_id not in seed.clients:
            raise SeedError(f"job {job.job_id} names unknown client {job.client_id}")
    for job_id in seed.release_min:
        if job_id not in seed.jobs:
            raise SeedError(f"stream entry for unknown job {job_id}")
    for client_id in seed.client_prefs:
        if client_id not in seed.clients:
            raise SeedError(f"client_prefs entry for unknown client {client_id}")
    for conversation_id, conversation in seed.conversations.items():
        if conversation.job_id not in seed.jobs:
            raise SeedError(f"conversation {conversation_id} names an unknown job")
        if conversation.client_id not in seed.clients:
            raise SeedError(f"conversation {conversation_id} names an unknown client")


def _add_models(into: dict[str, ModelT], path: Path, model: type[ModelT], key: str) -> None:
    for where, row in _read_jsonl(path):
        try:
            record = model.model_validate(row)
        except ValidationError as error:
            raise SeedError(f"{where}: {error}") from error
        _put(into, getattr(record, key), record, where)


def _put(into: dict[str, Any], record_id: Any, value: Any, where: str) -> None:
    if not isinstance(record_id, str) or not record_id:
        raise SeedError(f"{where}: missing id")
    if record_id in into:
        raise SeedError(f"{where}: duplicate id {record_id}")
    into[record_id] = value


def _read_jsonl(path: Path) -> list[tuple[str, dict[str, Any]]]:
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append((f"{path}:{number}", json.loads(line)))
        except json.JSONDecodeError as error:
            raise SeedError(f"{path}:{number}: invalid JSON") from error
    return rows
