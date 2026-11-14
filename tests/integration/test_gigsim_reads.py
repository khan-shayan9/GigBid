"""GigSim slice 1: loader, clock, auth, rate limit, seeded faults and read endpoints."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gigsim.app import create_app
from gigsim.clock import SimClock
from gigsim.db import StateDB
from gigsim.settings import (
    DEFAULT_CONFIG_PATH,
    RateLimit,
    Settings,
    SimConfig,
    load_settings,
    parse_tokens,
)
from gigsim.store import SeedError, load_seed

SEED_DIR = Path("data/gigsim_seed")
TOKEN, OTHER_TOKEN, ADMIN_TOKEN = "test-user-token", "test-other-token", "test-admin-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ADMIN = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
ALL_RELEASED_MIN = 60 * 24 * 30
HIDDEN_KEYS = {
    "source", "derived_from", "history_source", "behaviour", "must_have_skills",
    "budget_ceiling", "dislikes_generic_opening", "reply_propensity",
}


def make_settings(tmp_path: Path, faults: bool = False, **config_update: Any) -> Settings:
    config = SimConfig.model_validate(json.loads(Path(DEFAULT_CONFIG_PATH).read_text(encoding="utf-8")))
    update = {"time_scale": 0, "rate_limit": RateLimit(capacity=10_000, refill_per_second=100)}
    return Settings(
        config=config.model_copy(update={**update, **config_update}),
        seed_dirs=[SEED_DIR],
        db_path=tmp_path / "gigsim.sqlite",
        tokens={TOKEN: "ai_ml_engineer", OTHER_TOKEN: "data_analyst"},
        admin_token=ADMIN_TOKEN,
        faults_enabled=faults,
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    with TestClient(create_app(make_settings(tmp_path))) as test_client:
        yield test_client


def advance(client: TestClient, minutes: float) -> None:
    assert client.post("/admin/clock/advance", json={"minutes": minutes}, headers=ADMIN).status_code == 200


def all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in all_keys(item)}
    return set()


def test_health_needs_no_auth(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "service": "gigsim"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}])
def test_rejects_missing_or_bad_token(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/jobs", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthenticated"


def test_admin_endpoint_needs_admin_token(client: TestClient) -> None:
    response = client.post("/admin/clock/advance", json={"minutes": 5}, headers=AUTH)
    assert response.status_code == 403


def test_only_released_jobs_are_served(client: TestClient) -> None:
    stream = [json.loads(line) for line in (SEED_DIR / "stream.jsonl").read_text(encoding="utf-8").splitlines()]
    live_at_start = {row["job_id"] for row in stream if row["release_after_min"] == 0}
    hidden_job = next(row["job_id"] for row in stream if row["release_after_min"] > 0)

    assert client.get("/jobs?limit=1", headers=AUTH).json()["total"] == len(live_at_start)
    assert client.get(f"/jobs/{hidden_job}", headers=AUTH).status_code == 404

    advance(client, ALL_RELEASED_MIN)
    assert client.get("/jobs?limit=1", headers=AUTH).json()["total"] == len(stream)
    assert client.get(f"/jobs/{hidden_job}", headers=AUTH).status_code == 200


def test_no_provenance_or_hidden_preferences_are_served(client: TestClient) -> None:
    advance(client, ALL_RELEASED_MIN)
    responses, client_ids, offset = [], set(), 0
    while page := client.get(f"/jobs?limit=100&offset={offset}", headers=AUTH).json()["jobs"]:
        responses.append(page)
        client_ids |= {job["client_id"] for job in page}
        offset += 100
    responses += [client.get(f"/clients/{cid}", headers=AUTH).json() for cid in client_ids]
    responses.append(client.get("/market/rates", headers=AUTH).json())
    responses.append(client.get("/market/historical?limit=100", headers=AUTH).json())
    assert not all_keys(responses) & HIDDEN_KEYS


def test_search_filters(client: TestClient) -> None:
    advance(client, ALL_RELEASED_MIN)
    hourly = client.get("/jobs?payment_type=hourly&limit=100", headers=AUTH).json()["jobs"]
    assert hourly and all(job["payment_type"] == "hourly" for job in hourly)

    job = hourly[0]
    by_skill = client.get("/jobs", params={"skills": job["skills"][0], "limit": 100}, headers=AUTH)
    assert all(job["skills"][0] in found["skills"] for found in by_skill.json()["jobs"])

    word = job["title"].split()[0]
    by_text = client.get("/jobs", params={"q": word, "limit": 100}, headers=AUTH).json()["jobs"]
    assert job["job_id"] in {found["job_id"] for found in by_text}

    newest = client.get("/jobs?limit=1", headers=AUTH).json()["jobs"][0]
    after = client.get("/jobs", params={"since": newest["posted_at"]}, headers=AUTH).json()
    assert after["total"] == 0


def test_connects_balance_and_market_data(client: TestClient) -> None:
    assert client.get("/connects", headers=AUTH).json() == {
        "user_id": "ai_ml_engineer", "balance": 120,
    }
    assert "ai_ml" in client.get("/market/rates", headers=AUTH).json()["domains"]
    web = client.get("/market/historical?category=web", headers=AUTH).json()
    assert web["total"] > 0 and all(job["category"] == "web" for job in web["jobs"])


def test_rate_limit_returns_429_with_retry_after(tmp_path: Path) -> None:
    limit = RateLimit(capacity=3, refill_per_second=0.01)
    with TestClient(create_app(make_settings(tmp_path, rate_limit=limit))) as client:
        statuses = [client.get("/connects", headers=AUTH).status_code for _ in range(4)]
        response = client.get("/connects", headers=AUTH)
        other_user = client.get("/connects", headers={"Authorization": f"Bearer {OTHER_TOKEN}"})
    assert statuses == [200, 200, 200, 429]
    assert response.json()["detail"]["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) >= 1
    assert other_user.status_code == 200  # limits are per user


def test_faults_are_seeded_and_retries_converge(tmp_path: Path) -> None:
    def statuses(db_dir: Path) -> list[int]:
        db_dir.mkdir()
        settings = make_settings(db_dir, faults=True, fault_rate=0.5)
        with TestClient(create_app(settings)) as client:
            return [client.get("/connects", headers=AUTH).status_code for _ in range(30)]

    first, second = statuses(tmp_path / "a"), statuses(tmp_path / "b")
    assert first == second
    assert {200, 503} <= set(first)
    assert max(_failure_streaks(first)) < 10


def _failure_streaks(statuses: list[int]) -> list[int]:
    streaks, current = [0], 0
    for status in statuses:
        current = current + 1 if status == 503 else 0
        streaks.append(current)
    return streaks


def test_clock_persists_across_restart(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path))) as client:
        advance(client, 500)
        epoch = client.app.state.sim.clock.epoch
    with TestClient(create_app(make_settings(tmp_path))) as client:
        clock = client.app.state.sim.clock
        assert clock.epoch == epoch
        assert clock.minutes() == pytest.approx(500)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


GRADER_CLIENT = {
    "client_id": "grader-client-1", "country": "Pakistan", "payment_verified": True,
    "enterprise": False, "total_spent_usd": 1200.0, "rating": 4.8, "feedback_count": 3,
    "history": [], "source": "grader",
}
GRADER_JOB = {
    "job_id": "grader-job-1", "title": "Build a RAG chatbot", "description": "Docs Q&A bot.",
    "skills": ["Python", "LangChain"], "experience_level": "intermediate",
    "payment_type": "fixed", "budget_usd": 800.0, "hourly_usd": None, "duration": None,
    "applicants": "5 to 10", "connects_cost": 4, "client_id": "grader-client-1",
}


def test_loader_accepts_grader_folder_with_defaults(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "clients.jsonl", [GRADER_CLIENT])
    write_jsonl(tmp_path / "jobs.jsonl", [GRADER_JOB])
    defaults = {"behaviour": "genuine", "reply_propensity": 0.5}
    seed = load_seed([tmp_path], defaults)
    assert seed.release_min == {"grader-job-1": 0.0}
    assert seed.client_prefs["grader-client-1"].items() >= defaults.items()


@pytest.mark.parametrize(
    "jobs",
    [[{**GRADER_JOB, "client_id": "missing-client"}], [GRADER_JOB, GRADER_JOB]],
    ids=["dangling-client", "duplicate-job"],
)
def test_loader_rejects_inconsistent_data(tmp_path: Path, jobs: list[dict[str, Any]]) -> None:
    write_jsonl(tmp_path / "clients.jsonl", [GRADER_CLIENT])
    write_jsonl(tmp_path / "jobs.jsonl", jobs)
    with pytest.raises(SeedError):
        load_seed([tmp_path], {})


def test_grader_folder_is_served_without_provenance(tmp_path: Path) -> None:
    grader_dir = tmp_path / "grader"
    grader_dir.mkdir()
    write_jsonl(grader_dir / "clients.jsonl", [GRADER_CLIENT])
    write_jsonl(grader_dir / "jobs.jsonl", [{**GRADER_JOB, "source": "grader"}])
    settings = make_settings(tmp_path).model_copy(update={"seed_dirs": [SEED_DIR, grader_dir]})
    with TestClient(create_app(settings)) as client:
        job = client.get("/jobs/grader-job-1", headers=AUTH).json()
        grader_client = client.get("/clients/grader-client-1", headers=AUTH).json()
    assert job["title"] == GRADER_JOB["title"]
    assert not all_keys([job, grader_client]) & HIDDEN_KEYS


def test_minimal_grader_job_loads_with_defaults(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "clients.jsonl", [{"client_id": "c1"}])
    minimal = {"job_id": "j1", "title": "T", "description": "D", "payment_type": "fixed",
               "client_id": "c1"}
    write_jsonl(tmp_path / "jobs.jsonl", [minimal])
    seed = load_seed([tmp_path], {})
    assert seed.jobs["j1"].connects_cost is None and seed.jobs["j1"].skills == []
    assert seed.clients["c1"].payment_verified is False


def test_parse_tokens_rejects_bad_entries() -> None:
    assert parse_tokens("a=x, b=y", {"a", "b"}) == {"x": "a", "y": "b"}
    for raw in ["ghost=x", "a=", "a=x,b=x"]:
        with pytest.raises(ValueError):
            parse_tokens(raw, {"a", "b"})


def test_load_settings_reads_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIGSIM_TOKENS", "ai_ml_engineer=t1")
    monkeypatch.setenv("GIGSIM_SEED_DIRS", f"{SEED_DIR}, {tmp_path}")
    monkeypatch.setenv("GIGSIM_FAULTS", "off")
    monkeypatch.setenv("GIGSIM_EPOCH", "2026-11-02T00:00:00Z")
    settings = load_settings()
    assert settings.tokens == {"t1": "ai_ml_engineer"}
    assert settings.seed_dirs == [SEED_DIR, tmp_path]
    assert settings.faults_enabled is False and settings.epoch == "2026-11-02T00:00:00Z"


def test_clock_runs_scaled_from_a_utc_epoch(tmp_path: Path) -> None:
    epoch = datetime.now(UTC) - timedelta(minutes=10)
    clock = SimClock(StateDB(tmp_path / "c.sqlite"), 60, epoch.isoformat().replace("+00:00", "Z"))
    assert clock.epoch == epoch
    assert clock.minutes() == pytest.approx(600, abs=1)
    clock.advance(30)
    assert clock.minutes() == pytest.approx(630, abs=1)


def test_users_can_read_sim_time(client: TestClient) -> None:
    advance(client, 90)
    assert client.get("/time", headers=AUTH).json()["sim_minutes"] == pytest.approx(90)


def test_reset_returns_to_minute_zero_with_a_fixed_epoch(tmp_path: Path) -> None:
    epoch = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    clock = SimClock(StateDB(tmp_path / "c.sqlite"), 60, epoch)
    clock.advance(500)
    clock.reset()
    assert clock.minutes() == pytest.approx(0, abs=1)
    assert clock.epoch == datetime.fromisoformat(epoch)
