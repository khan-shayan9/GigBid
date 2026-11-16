"""The web API end to end with a fake marketplace and scripted models (Part D backend)."""

import secrets
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agent.config import load_config
from agent.mcp_client import ToolUnavailable
from apps.api.auth.users import hash_password
from apps.api.main import create_app
from apps.api.services import insights, jobs
from tests.e2e.fake_backend import (
    CLIENT_MESSAGE,
    PARAGRAPH,
    REPLY,
    FakeMarket,
    fake_overrides,
)

PASSWORD = secrets.token_hex(8)
CLINIC_THREAD = "reviewer:bid:job-clinic"


@pytest.fixture
def market() -> FakeMarket:
    return FakeMarket()


@pytest.fixture
def client(market: FakeMarket, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_SECRET_KEY", secrets.token_hex(16))
    monkeypatch.setenv("APP_USERS", f"reviewer={hash_password(PASSWORD)},"
                                    f"other={hash_password(PASSWORD)}")
    monkeypatch.setenv("API_PERSISTENCE", "memory")
    with TestClient(create_app(**fake_overrides(market))) as test_client:
        yield test_client


def sign_in(client: TestClient, name: str = "reviewer") -> None:
    assert client.post("/auth/login", json={"username": name, "password": PASSWORD}).is_success
    assert client.put("/profile", json={"persona": "ai_ml_engineer"}).is_success


def wait_idle(client: TestClient, thread_id: str) -> dict[str, Any]:
    for _ in range(100):
        run = client.get(f"/runs/{thread_id}").json()
        if not run["running"]:
            return run
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_sign_in_is_required_and_bad_passwords_are_refused(client: TestClient) -> None:
    assert client.get("/jobs").json()["detail"]["code"] == "unauthenticated"
    wrong = client.post("/auth/login", json={"username": "reviewer", "password": "nope"})
    assert wrong.status_code == 401 and wrong.json()["detail"]["code"] == "bad_credentials"
    assert client.post("/auth/login", json={"username": "reviewer", "password": PASSWORD}).is_success
    assert client.get("/jobs").json()["detail"]["code"] == "onboarding_required"


def test_a_job_runs_to_approval_and_submits_once(client: TestClient, market: FakeMarket) -> None:
    sign_in(client)
    assert [item["job"]["job_id"] for item in client.get("/jobs").json()["items"]] == [
        "job-clinic", "job-scam", "job-dash"]
    thread = client.post("/jobs/job-clinic/analyse").json()["thread_id"]
    assert thread == CLINIC_THREAD
    run = wait_idle(client, thread)
    assert run["pending_approval"] and run["draft"]["evidence_ids"] == ["ai-cs-01"]
    assert run["preview"]["proposal"]["connects_cost"] == 4 and run["preview"]["proposal"]["dry_run"]
    assert run["fit_report"]["matrix"][0]["covered"] and run["timeline"]
    assert not market.tools("submit_proposal")
    # A refresh reads the same pending approval back from the checkpoint.
    assert client.get("/runs?kind=bid").json()["runs"][0]["pending_approval"]
    # Timed up to the approval pause, not through the human wait.
    assert client.get("/analytics").json()["cost_and_latency"]["jobs_timed"] == 1
    assert client.post(f"/runs/{thread}/resume", json={"action": "approve"}).status_code == 202
    done = wait_idle(client, thread)
    assert done["approval_status"] == "approved" and done["submission"]["proposal"]["status"]
    again = client.post(f"/runs/{thread}/resume", json={"action": "approve"})
    assert again.status_code == 409 and len(market.tools("submit_proposal")) == 1
    board = client.get("/pipeline").json()["cards"]
    assert [(card["stage"], card["thread_id"]) for card in board] == [("submitted", thread)]
    stats = client.get("/analytics").json()
    assert stats["connects_spent"] == 4 and stats["approvals"] == {"approved": 1}
    cost = stats["cost_and_latency"]
    assert cost["jobs_timed"] == cost["proposals_timed"] == 1 and cost["p95_seconds_per_job"] >= 0


def test_a_scam_is_skipped_and_ranked_below(client: TestClient) -> None:
    sign_in(client)
    for job in ("job-scam", "job-clinic"):
        wait_idle(client, client.post(f"/jobs/{job}/analyse").json()["thread_id"])
    items = client.get("/jobs").json()["items"]
    assert [item["job"]["job_id"] for item in items][:2] == ["job-clinic", "job-scam"]
    scam = items[1]["run"]
    assert scam["decision"] == "skip" and "injected_instructions" in scam["risk_flags"]


def test_reject_with_reason_and_edit_validation(client: TestClient, market: FakeMarket) -> None:
    sign_in(client)
    thread = client.post("/jobs/job-clinic/analyse").json()["thread_id"]
    wait_idle(client, thread)
    bad_edit = client.post(f"/runs/{thread}/resume", json={"action": "edit"})
    assert bad_edit.status_code == 422
    regenerated = client.post(f"/runs/{thread}/regenerate", json={"paragraph": "Hello."})
    assert regenerated.json()["paragraph"] == PARAGRAPH
    client.post(f"/runs/{thread}/resume", json={"action": "reject", "reason": "rate too low"})
    assert wait_idle(client, thread)["approval_status"] == "rejected: rate too low"
    assert not market.tools("submit_proposal")
    reasons = client.get("/analytics").json()["top_rejection_reasons"]
    assert reasons == [{"reason": "rate too low", "count": 1}]


def test_another_account_cannot_read_or_resume_a_run(client: TestClient) -> None:
    sign_in(client)
    wait_idle(client, client.post("/jobs/job-clinic/analyse").json()["thread_id"])
    sign_in(client, "other")
    assert client.get(f"/runs/{CLINIC_THREAD}").status_code == 403
    assert client.post(f"/runs/{CLINIC_THREAD}/resume",
                       json={"action": "approve"}).status_code == 403
    assert client.get("/runs?kind=bid").json()["runs"] == []


def test_a_client_reply_is_drafted_with_slots_and_sent_after_approval(
        client: TestClient, market: FakeMarket) -> None:
    sign_in(client)
    thread = client.post("/messages/ai_ml_engineer-conv-01-m1/reply").json()["thread_id"]
    run = wait_idle(client, thread)
    assert run["pending_approval"] and run["reply"] == REPLY and run["slots"]
    client.post(f"/runs/{thread}/resume", json={"action": "approve"})
    assert wait_idle(client, thread)["approval_status"] == "approved"
    texts = [m["text"] for m in client.get("/messages").json()["threads"][0]["messages"]]
    assert texts[-1] == REPLY and len(market.tools("send_message")) == 1


def test_marketplace_down_is_a_503_with_a_stable_code(client: TestClient,
                                                      market: FakeMarket) -> None:
    sign_in(client)
    market.down = True
    response = client.get("/jobs")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "marketplace_unavailable"
    assert client.get("/profile/connections").json()["marketplace"] is False


def test_the_stream_starts_with_a_snapshot_and_ends(client: TestClient) -> None:
    sign_in(client)
    thread = client.post("/jobs/job-clinic/analyse").json()["thread_id"]
    with client.stream("GET", f"/runs/{thread}/stream") as stream:
        body = "".join(stream.iter_text())
    assert body.startswith("event: snapshot") and "event: end" in body


def test_uploads_are_checked_before_saving(client: TestClient, tmp_path: Any,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    from rag.ingest import uploads
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path)
    sign_in(client)
    fake_pdf = client.post("/profile/portfolio", files={"file": ("cv.pdf", b"not a pdf")})
    assert fake_pdf.json()["detail"]["code"] == "unsupported_type"
    saved = client.post("/profile/portfolio",
                        files={"file": ("../../evil name.md", b"# Case study\nA bot.")})
    assert saved.status_code == 201 and saved.json()["saved_as"] == "repos/evil_name.md"
    assert (tmp_path / "reviewer" / "repos" / "evil_name.md").exists()  # the account's folder


def test_the_committed_openapi_schema_matches_the_api() -> None:
    from apps.api.export_openapi import SCHEMA_PATH, schema_text
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_text(), "run make api-client"


def test_a_run_that_fails_before_its_first_checkpoint_says_so(
        client: TestClient, market: FakeMarket) -> None:
    sign_in(client)
    client.app.state.runtime.model_for = lambda kind: (_ for _ in ()).throw(KeyError("GROQ"))
    thread = client.post("/jobs/job-clinic/analyse").json()["thread_id"]
    for _ in range(100):
        response = client.get(f"/runs/{thread}")
        if response.status_code != 200:
            break
        time.sleep(0.05)
    assert response.status_code == 502 and response.json()["detail"]["code"] == "run_failed"


def test_scheduled_scouting_starts_runs_only_for_new_jobs(client: TestClient) -> None:
    sign_in(client)
    rt = client.app.state.runtime
    client.post("/jobs/job-dash/skip")
    assert client.portal.call(jobs.accounts, rt) == ["reviewer"]
    assert client.portal.call(jobs.queue_new_jobs, rt, "reviewer", 1) == 1
    wait_idle(client, CLINIC_THREAD)  # newest unseen job first; the skipped job never runs
    assert client.portal.call(jobs.queue_new_jobs, rt, "reviewer", 5) == 1  # job-scam only
    wait_idle(client, "reviewer:bid:job-scam")
    assert client.portal.call(jobs.queue_new_jobs, rt, "reviewer", 5) == 0


def test_outcomes_reach_memory_once_and_only_for_the_sender(client: TestClient,
                                                           market: FakeMarket) -> None:
    sign_in(client, "other")  # same persona, so it sees the same marketplace proposals
    client.post("/auth/logout")
    sign_in(client)
    client.post("/jobs/job-clinic/analyse")
    wait_idle(client, CLINIC_THREAD)
    client.post(f"/runs/{CLINIC_THREAD}/resume", json={"action": "approve"})
    wait_idle(client, CLINIC_THREAD)
    rt = client.app.state.runtime
    assert client.portal.call(insights.sync_outcomes, rt, "reviewer") == 0  # "submitted"
    next(iter(market.proposals.values()))["status"] = "replied"
    assert client.portal.call(insights.sync_outcomes, rt, "reviewer") == 1
    assert client.portal.call(insights.sync_outcomes, rt, "reviewer") == 0
    assert client.portal.call(insights.sync_outcomes, rt, "other") == 0
    outcome = client.get("/memory").json()["items"]
    assert [(item["kind"], "replied" in item["summary"]) for item in outcome] == [
        ("outcome", True)]


def test_a_preloaded_reviewer_skips_onboarding(market: FakeMarket,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECRET_KEY", secrets.token_hex(16))
    monkeypatch.setenv("APP_USERS", f"reviewer={hash_password(PASSWORD)}")
    monkeypatch.setenv("API_PERSISTENCE", "memory")
    monkeypatch.setenv("PRELOAD_PERSONAS", "reviewer=ai_ml_engineer")
    with TestClient(create_app(**fake_overrides(market))) as client:
        client.post("/auth/login", json={"username": "reviewer", "password": PASSWORD})
        assert client.get("/auth/session").json()["profile"]["persona"] == "ai_ml_engineer"
        assert client.get("/jobs").is_success


def test_a_dead_lettered_run_replays_from_before_its_failure(
        client: TestClient, market: FakeMarket, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(load_config()["budgets"], "node_backoff_s", 0)
    sign_in(client)
    market.slow = 0.3  # the writer's evidence search: time to take the marketplace down
    client.post("/jobs/job-clinic/analyse")
    market.down = True
    failed = wait_idle(client, CLINIC_THREAD)
    assert failed["status"] == "dead_letter" and not failed["pending_approval"]
    market.down, market.slow = False, 0.0
    assert client.post(f"/runs/{CLINIC_THREAD}/retry").status_code == 202
    done = wait_idle(client, CLINIC_THREAD)
    assert done["pending_approval"] and not done["status"] and not done["errors"]
    assert client.post(f"/runs/{CLINIC_THREAD}/retry").status_code == 409


def test_agency_mode_routes_a_job_and_submits_as_that_member(client: TestClient,
                                                             market: FakeMarket) -> None:
    sign_in(client)
    assert client.put("/profile", json={"persona": "ai_ml_engineer", "agency": True}).is_success
    market.scores["fullstack_dev"] = 0.95  # every member covers the job; this one most strongly
    thread = client.post("/jobs/job-clinic/analyse").json()["thread_id"]
    assert thread == CLINIC_THREAD  # one thread per job, whichever member bids
    run = wait_idle(client, thread)
    assert run["member"] == "fullstack_dev" and run["pending_approval"]
    assert set(run["route"]["fit_scores"]) == set(load_config()["api"]["personas"])
    assert "tied with" in run["route"]["reason"]
    assert client.get("/runs?kind=bid").json()["runs"][0]["member"] == "fullstack_dev"
    # resume hands run_segment the account persona; the checkpoint's member must win
    client.post(f"/runs/{thread}/resume", json={"action": "approve"})
    assert wait_idle(client, thread)["approval_status"] == "approved"
    assert [persona for persona, tool in market.by_persona if tool == "submit_proposal"] == [
        "fullstack_dev"]
    rt = client.app.state.runtime
    board = client.get("/pipeline").json()["cards"]
    assert [(card["stage"], card["thread_id"]) for card in board] == [("submitted", thread)]
    # Turned off, the routed member's proposal and its outcome still belong to this account.
    assert client.put("/profile", json={"persona": "ai_ml_engineer"}).is_success
    assert len(client.get("/pipeline").json()["cards"]) == 1
    next(iter(market.proposals.values()))["status"] = "replied"
    assert client.portal.call(insights.sync_outcomes, rt, "reviewer") == 1


def test_agency_mode_replies_as_the_member_who_holds_the_thread(client: TestClient,
                                                                market: FakeMarket) -> None:
    sign_in(client)
    assert client.put("/profile", json={"persona": "ai_ml_engineer", "agency": True}).is_success
    message = CLIENT_MESSAGE | {"message_id": "fullstack_dev-conv-01-m1",
                                "thread_id": "fullstack_dev-conv-01"}
    market.messages.append(message)
    market.owner[message["message_id"]] = "fullstack_dev"
    assert len(client.get("/messages").json()["threads"]) == 2
    thread = client.post(f"/messages/{message['message_id']}/reply").json()["thread_id"]
    assert wait_idle(client, thread)["member"] == "fullstack_dev"
    client.post(f"/runs/{thread}/resume", json={"action": "approve"})
    wait_idle(client, thread)
    assert [persona for persona, tool in market.by_persona if tool == "send_message"][-1] ==         "fullstack_dev"


def test_agency_mode_is_off_by_default(client: TestClient, market: FakeMarket) -> None:
    sign_in(client)
    market.scores["fullstack_dev"] = 0.95
    run = wait_idle(client, client.post("/jobs/job-clinic/analyse").json()["thread_id"])
    assert run["member"] is None and run["route"] is None
    assert {persona for persona, _ in market.by_persona} == {"ai_ml_engineer"}


def test_agency_routing_skips_a_member_whose_portfolio_is_down(client: TestClient,
                                                               market: FakeMarket) -> None:
    sign_in(client)
    assert client.put("/profile", json={"persona": "ai_ml_engineer", "agency": True}).is_success
    market.scores["fullstack_dev"] = 0.95
    rt = client.app.state.runtime
    healthy = rt.open_mcp

    def flaky(persona: str, servers: list[str]) -> Any:
        if persona == "fullstack_dev" and servers == ["portfolio"]:
            raise ToolUnavailable("portfolio down")
        return healthy(persona, servers)

    rt.open_mcp = flaky
    run = wait_idle(client, client.post("/jobs/job-clinic/analyse").json()["thread_id"])
    assert run["member"] == "ai_ml_engineer" and "fullstack_dev" not in run["route"]["fit_scores"]
