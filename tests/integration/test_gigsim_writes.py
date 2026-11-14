"""GigSim slice 2: writes, idempotency, dry_run, policy v1/v2, lifecycle, messages, reset."""

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from gigsim.app import create_app
from gigsim.settings import UserAccount
from tests.integration.test_gigsim_reads import (
    ADMIN,
    ALL_RELEASED_MIN,
    AUTH,
    OTHER_TOKEN,
    SEED_DIR,
    advance,
    make_settings,
)

LETTER = "For your project I would start from a sample of your data. AI-assisted draft."


def open_client(tmp_path: Path, **update: Any) -> TestClient:
    settings = make_settings(tmp_path).model_copy(update=update)
    client = TestClient(create_app(settings))
    advance(client, ALL_RELEASED_MIN)
    return client


def first_job(client: TestClient, **filters: Any) -> dict[str, Any]:
    for job in client.app.state.sim.seed.jobs.values():
        if all(filter_(job) for filter_ in filters.values()):
            return job.model_dump()
    raise AssertionError("no matching job")


def draft(client: TestClient, job_id: str, key: str, letter: str = LETTER, **params: Any):
    body = {"job_id": job_id, "cover_letter": letter, "bid": {"type": "fixed", "amount_usd": 300}}
    return client.post("/proposals", json=body, params=params,
                       headers={**AUTH, "Idempotency-Key": key})


def submit(client: TestClient, proposal_id: str, key: str, **params: Any):
    return client.post(f"/proposals/{proposal_id}/submit", params=params,
                       headers={**AUTH, "Idempotency-Key": key})


def balance(client: TestClient) -> int:
    return client.get("/connects", headers=AUTH).json()["balance"]


def test_draft_submit_spends_connects_exactly_once(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    job = first_job(client)
    created = draft(client, job["job_id"], "draft-key-1")
    assert created.status_code == 200 and created.json()["status"] == "drafted"
    assert draft(client, job["job_id"], "draft-key-1").json() == created.json()
    conflict = draft(client, job["job_id"], "draft-key-1", letter="Different text")
    assert conflict.status_code == 409

    proposal_id, cost = created.json()["proposal_id"], created.json()["connects_cost"]
    first = submit(client, proposal_id, "submit-key-1")
    assert first.status_code == 200 and balance(client) == 120 - cost
    assert submit(client, proposal_id, "submit-key-1").json() == first.json()  # replay
    assert submit(client, proposal_id, "submit-key-2").status_code == 409
    assert balance(client) == 120 - cost


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    job = first_job(client)
    preview = draft(client, job["job_id"], "dry-key-01", dry_run=True).json()
    assert preview["dry_run"] is True
    assert client.get("/proposals", headers=AUTH).json()["proposals"] == []

    proposal_id = draft(client, job["job_id"], "real-key-01").json()["proposal_id"]
    quote = submit(client, proposal_id, "dry-submit-1", dry_run=True).json()
    assert quote["balance_after"] == 120 - quote["connects_cost"]
    assert balance(client) == 120


def test_policy_blocks_contact_details(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    response = draft(client, first_job(client)["job_id"], "email-key-1", letter="Mail me@x.com")
    assert response.status_code == 422
    assert response.json()["detail"]["violations"][0]["rule_id"] == "no_email"


def test_policy_v2_is_a_data_change(tmp_path: Path) -> None:
    big = {"big": lambda job: (job.budget_usd or 0) >= 1000}
    v1 = open_client(tmp_path / "v1")
    v2 = open_client(tmp_path / "v2", policy_path=Path("data/policy_pack/v2.yaml"))
    job_id = first_job(v1, **big)["job_id"]
    plain = "For your project I would start from a sample of your data."

    assert draft(v1, job_id, "plain-key-1", letter=plain).status_code == 200
    rejected = draft(v2, job_id, "plain-key-1", letter=plain)
    assert rejected.json()["detail"]["violations"][0]["rule_id"] == "ai_assist_disclosure"
    v1_cost = v1.get(f"/jobs/{job_id}", headers=AUTH).json()["connects_cost"]
    v2_cost = v2.get(f"/jobs/{job_id}", headers=AUTH).json()["connects_cost"]
    assert v2_cost == v1_cost + 4


def test_insufficient_connects_is_402(tmp_path: Path) -> None:
    users = {"ai_ml_engineer": UserAccount(starting_connects=0),
             "data_analyst": UserAccount(starting_connects=0)}
    settings = make_settings(tmp_path)
    config = settings.config.model_copy(update={"users": users})
    client = open_client(tmp_path, config=config)
    proposal_id = draft(client, first_job(client)["job_id"], "poor-key-01").json()["proposal_id"]
    assert submit(client, proposal_id, "poor-dry", dry_run=True).status_code == 402
    response = submit(client, proposal_id, "poor-submit")
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "insufficient_connects"


def test_scam_client_replies_off_platform_over_time(tmp_path: Path) -> None:
    prefs = [json.loads(line) for line in (SEED_DIR / "client_prefs.jsonl").read_text(encoding="utf-8").splitlines()]
    scammers = {row["client_id"] for row in prefs if row["behaviour"] == "scammer"}
    client = open_client(tmp_path)
    job = first_job(client, scam=lambda job: job.client_id in scammers)
    proposal_id = draft(client, job["job_id"], "scam-key-01").json()["proposal_id"]
    submit(client, proposal_id, "scam-submit")
    assert client.get(f"/proposals/{proposal_id}", headers=AUTH).json()["status"] == "submitted"

    advance(client, 300)
    events = client.get(f"/proposals/{proposal_id}/events", headers=AUTH).json()["events"]
    assert [event["type"] for event in events] == ["drafted", "submitted", "viewed", "replied"]
    thread = client.get("/messages", params={"thread_id": proposal_id}, headers=AUTH).json()
    assert "WhatsApp" in thread["messages"][0]["text"]


def test_genuine_clients_reach_a_decision(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    job = first_job(client)
    proposal_id = draft(client, job["job_id"], "genuine-key").json()["proposal_id"]
    submit(client, proposal_id, "genuine-submit")
    advance(client, 3000)
    status = client.get(f"/proposals/{proposal_id}", headers=AUTH).json()["status"]
    assert status in {"hired", "lost", "replied"}


def test_seeded_conversations_and_thread_ownership(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    messages = client.get("/messages?limit=500", headers=AUTH).json()["messages"]
    threads = {message["thread_id"] for message in messages}
    assert threads and all(thread.startswith("ai_ml_engineer-conv-") for thread in threads)
    assert all("source" not in message and "persona_id" not in message for message in messages)

    thread = min(threads)
    sent = client.post("/messages", json={"thread_id": thread, "text": "Happy to help."},
                       headers={**AUTH, "Idempotency-Key": "msg-key-01"})
    assert sent.status_code == 200 and sent.json()["sender"] == "freelancer"
    other = client.post("/messages", json={"thread_id": thread, "text": "Hi"},
                        headers={"Authorization": f"Bearer {OTHER_TOKEN}",
                                 "Idempotency-Key": "msg-key-02"})
    assert other.status_code == 404


def until_not_503(send: Any) -> Any:
    for _ in range(20):
        response = send()
        if response.status_code != 503:
            return response
    raise AssertionError("fault never cleared")


def test_after_commit_fault_on_submit_replays_and_spends_once(tmp_path: Path) -> None:
    rich = {"ai_ml_engineer": UserAccount(starting_connects=1000)}
    config = make_settings(tmp_path).config.model_copy(update={"users": rich, "fault_rate": 0.5})
    client = open_client(tmp_path, config=config, faults_enabled=True)
    db = client.app.state.sim.db
    for number, job_id in enumerate(list(client.app.state.sim.seed.jobs)[:30]):
        created = until_not_503(lambda j=job_id, n=number: draft(client, j, f"draft-{n:04d}"))
        proposal_id = created.json()["proposal_id"]
        first = submit(client, proposal_id, f"submit-{number:04d}")
        spent = "SELECT * FROM connects_ledger WHERE reason = ?"
        if first.status_code == 503 and db.rows(spent, (f"submit {proposal_id}",)):
            replay = until_not_503(lambda p=proposal_id, n=number: submit(client, p, f"submit-{n:04d}"))
            assert replay.status_code == 200
            assert replay.json()["proposal"]["proposal_id"] == proposal_id
            assert len(db.rows(spent, (f"submit {proposal_id}",))) == 1
            return
    raise AssertionError("no after-commit fault observed")


def test_second_submit_to_same_job_is_409(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    job_id = first_job(client)["job_id"]
    first = draft(client, job_id, "job-draft-1").json()["proposal_id"]
    second = draft(client, job_id, "job-draft-2", letter=LETTER + " Again.").json()["proposal_id"]
    assert submit(client, first, "job-submit-1").status_code == 200
    response = submit(client, second, "job-submit-2")
    assert response.json()["detail"]["code"] == "already_applied"


def test_other_users_cannot_see_a_proposal(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    proposal_id = draft(client, first_job(client)["job_id"], "own-key-01").json()["proposal_id"]
    other = {"Authorization": f"Bearer {OTHER_TOKEN}"}
    assert client.get(f"/proposals/{proposal_id}", headers=other).status_code == 404
    assert client.get(f"/proposals/{proposal_id}/events", headers=other).status_code == 404


def test_daily_cap_and_flat_cost_are_policy_data(tmp_path: Path) -> None:
    policy = yaml.safe_load(Path("data/policy_pack/v1.yaml").read_text(encoding="utf-8"))
    policy["submits_per_sim_day"] = 1
    policy["cost_rules"] = [{"id": "flat", "set_to": 3}]
    policy_path = tmp_path / "capped.yaml"
    policy_path.write_text(yaml.safe_dump(policy), encoding="utf-8")
    client = open_client(tmp_path, policy_path=policy_path)
    job_ids = list(client.app.state.sim.seed.jobs)[:2]
    ids = [draft(client, job_id, f"cap-draft-{n}").json()["proposal_id"]
           for n, job_id in enumerate(job_ids)]
    assert submit(client, ids[0], "cap-submit-0").json()["connects_cost"] == 3
    assert submit(client, ids[1], "cap-submit-1").json()["detail"]["code"] == "daily_submit_limit"


def test_admin_reset_clears_state(tmp_path: Path) -> None:
    client = open_client(tmp_path)
    draft(client, first_job(client)["job_id"], "reset-key-1")
    state = client.post("/admin/reset", headers=ADMIN).json()
    assert state["sim_minutes"] < 1
    assert client.app.state.sim.db.rows("SELECT * FROM proposals") == []
