"""Write endpoints (proposal drafts, submit, messages) and the proposal and message reads.

Every write takes an Idempotency-Key header and a dry_run flag. The same key with the same body
replays the stored response; the same key with a different body is a 409.
"""

import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query

from gigsim.client_sim import decide_outcome, schedule
from gigsim.guard import api_error
from gigsim.models import (
    Bid,
    EventList,
    Job,
    Message,
    MessageIn,
    MessageList,
    ProposalEvent,
    ProposalIn,
    ProposalList,
    ProposalOut,
    SubmitResult,
)
from gigsim.policy import Kind
from gigsim.sim import Sim, SimDep, UserDep

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
MAX_MESSAGES = 500
MINUTES_PER_DAY = 24 * 60

router = APIRouter()


@router.post("/proposals", response_model=ProposalOut)
def create_proposal_draft(
    body: ProposalIn, user_id: UserDep, sim: SimDep, key: IdempotencyKey, dry_run: bool = False
) -> Any:
    now = sim.clock.minutes()
    job = _released_job(sim, body.job_id, now)
    _check_policy(sim, "\n".join([body.cover_letter, *body.screening_answers]), "proposal")
    draft = ProposalOut(
        proposal_id=_make_id("prop", user_id, key), job_id=job.job_id, status="drafted",
        cover_letter=body.cover_letter, bid=body.bid, screening_answers=body.screening_answers,
        connects_cost=sim.policy.connects_cost(job), created_at=sim.clock.at(now),
    )
    if dry_run:
        return draft.model_copy(update={"dry_run": True})

    def insert(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            "INSERT INTO proposals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (draft.proposal_id, user_id, job.job_id, job.client_id, body.cover_letter,
             body.bid.type, body.bid.amount_usd, json.dumps(body.screening_answers), now),
        )
        _add_event(conn, draft.proposal_id, user_id, "drafted", now)
        return draft.model_dump(mode="json")

    return _idempotent(sim, user_id, key, {"route": "draft", **body.model_dump()}, insert)


@router.post("/proposals/{proposal_id}/submit", response_model=SubmitResult)
def submit_proposal(
    proposal_id: str, user_id: UserDep, sim: SimDep, key: IdempotencyKey, dry_run: bool = False
) -> Any:
    now = sim.clock.minutes()
    row = _own_proposal(sim, proposal_id, user_id)
    job = sim.seed.jobs[row["job_id"]]
    cost = sim.policy.connects_cost(job)
    if dry_run:
        with sim.db.tx() as conn:  # read-only: the same checks as a real submit, nothing written
            balance = _submit_checks(sim, conn, user_id, proposal_id, job, cost, now)
        return SubmitResult(proposal=_proposal_out(sim, row, now), connects_cost=cost,
                            balance_after=balance - cost, dry_run=True)
    # Decided before the transaction so an LLM call never holds the database lock.
    outcome = decide_outcome(sim.settings, sim.seed.client_prefs[job.client_id], job, dict(row))

    def submit(conn: sqlite3.Connection) -> dict[str, Any]:
        balance = _submit_checks(sim, conn, user_id, proposal_id, job, cost, now)
        conn.execute(
            "INSERT INTO connects_ledger (user_id, delta, reason, at_min) VALUES (?, ?, ?, ?)",
            (user_id, -cost, f"submit {proposal_id}", now),
        )
        _add_event(conn, proposal_id, user_id, "submitted", now)
        for number, (event, at_min, text) in enumerate(schedule(sim.settings, outcome, now)):
            _add_event(conn, proposal_id, user_id, event, at_min)
            if text:
                conn.execute(
                    "INSERT INTO messages VALUES (?, ?, ?, ?, ?, 'client', ?, ?)",
                    (f"{proposal_id}-c{number}", user_id, proposal_id, job.job_id,
                     job.client_id, text, at_min),
                )
        return SubmitResult(proposal=_proposal_out(sim, row, now), connects_cost=cost,
                            balance_after=balance - cost).model_dump(mode="json")

    return _idempotent(sim, user_id, key, {"route": "submit", "proposal_id": proposal_id}, submit)


@router.get("/proposals", response_model=ProposalList)
def list_proposals(user_id: UserDep, sim: SimDep) -> ProposalList:
    now = sim.clock.minutes()
    found = sim.db.rows(
        "SELECT * FROM proposals WHERE user_id = ? ORDER BY created_min DESC", (user_id,)
    )
    return ProposalList(proposals=[_proposal_out(sim, row, now) for row in found])


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: str, user_id: UserDep, sim: SimDep) -> ProposalOut:
    return _proposal_out(sim, _own_proposal(sim, proposal_id, user_id), sim.clock.minutes())


@router.get("/proposals/{proposal_id}/events", response_model=EventList)
def list_proposal_events(proposal_id: str, user_id: UserDep, sim: SimDep) -> EventList:
    _own_proposal(sim, proposal_id, user_id)
    found = sim.db.rows(
        "SELECT type, at_min FROM events WHERE proposal_id = ? AND at_min <= ? ORDER BY id",
        (proposal_id, sim.clock.minutes()),
    )
    return EventList(events=[ProposalEvent(type=e["type"], at=sim.clock.at(e["at_min"]))
                             for e in found])


@router.post("/messages", response_model=Message)
def send_message(
    body: MessageIn, user_id: UserDep, sim: SimDep, key: IdempotencyKey, dry_run: bool = False
) -> Any:
    now = sim.clock.minutes()
    job_id, client_id = _thread(sim, user_id, body.thread_id)
    _check_policy(sim, body.text, "message")
    message = Message(
        message_id=_make_id("msg", user_id, key), thread_id=body.thread_id, job_id=job_id,
        client_id=client_id, sender="freelancer", text=body.text, sent_at=sim.clock.at(now),
    )
    if dry_run:
        return message.model_copy(update={"dry_run": True})

    def insert(conn: sqlite3.Connection) -> dict[str, Any]:
        conn.execute(
            "INSERT INTO messages VALUES (?, ?, ?, ?, ?, 'freelancer', ?, ?)",
            (message.message_id, user_id, body.thread_id, job_id, client_id, body.text, now),
        )
        return message.model_dump(mode="json")

    return _idempotent(sim, user_id, key, {"route": "message", **body.model_dump()}, insert)


@router.get("/messages", response_model=MessageList)
def list_messages(
    user_id: UserDep,
    sim: SimDep,
    thread_id: Annotated[str | None, Query(max_length=100)] = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_MESSAGES)] = 100,
) -> MessageList:
    now = sim.clock.minutes()
    messages = []
    for conv in sim.seed.conversations.values():
        if conv.persona_id != user_id:
            continue
        release = sim.seed.release_min[conv.job_id]
        for seeded in conv.messages:
            # A client cannot write about a job before it is posted.
            at_min = max(seeded.sent_after_min, release)
            if at_min <= now:
                messages.append(Message(
                    message_id=seeded.message_id, thread_id=conv.conversation_id,
                    job_id=conv.job_id, client_id=conv.client_id, sender="client",
                    text=seeded.text, sent_at=sim.clock.at(at_min),
                ))
    stored = sim.db.rows("SELECT * FROM messages WHERE user_id = ? AND at_min <= ?", (user_id, now))
    messages += [
        Message(message_id=m["message_id"], thread_id=m["thread_id"], job_id=m["job_id"],
                client_id=m["client_id"], sender=m["sender"], text=m["text"],
                sent_at=sim.clock.at(m["at_min"]))
        for m in stored
    ]
    since_utc = since if since is None or since.tzinfo else since.replace(tzinfo=UTC)
    messages = [
        m for m in messages
        if (thread_id is None or m.thread_id == thread_id) and (not since_utc or m.sent_at > since_utc)
    ]
    messages.sort(key=lambda m: (m.sent_at, m.message_id))
    return MessageList(messages=messages[:limit])


def _idempotent(
    sim: Sim, user_id: str, key: str, body: dict[str, Any],
    action: Callable[[sqlite3.Connection], dict[str, Any]],
) -> dict[str, Any]:
    body_hash = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    with sim.db.tx() as conn:
        stored = conn.execute(
            "SELECT body_hash, response FROM idempotency WHERE user_id = ? AND key = ?",
            (user_id, key),
        ).fetchone()
        if stored and stored["body_hash"] != body_hash:
            raise api_error(409, "idempotency_conflict", "Key reused with a different request.")
        if stored:
            response = json.loads(stored["response"])
        else:
            response = action(conn)
            conn.execute("INSERT INTO idempotency VALUES (?, ?, ?, ?)",
                         (user_id, key, body_hash, json.dumps(response)))
    sim.guard.after_commit(user_id, key)
    return response


def _submit_checks(
    sim: Sim, conn: sqlite3.Connection, user_id: str, proposal_id: str, job: Job, cost: int,
    now: float,
) -> int:
    """Raise if this submit is not allowed; return the balance before spending."""
    already = "SELECT 1 FROM events WHERE proposal_id = ? AND type = 'submitted'"
    if conn.execute(already, (proposal_id,)).fetchone():
        raise api_error(409, "already_submitted", "This proposal was already submitted.")
    same_job = (
        "SELECT 1 FROM events e JOIN proposals p ON p.proposal_id = e.proposal_id "
        "WHERE p.user_id = ? AND p.job_id = ? AND e.type = 'submitted'"
    )
    if conn.execute(same_job, (user_id, job.job_id)).fetchone():
        raise api_error(409, "already_applied", "You already submitted to this job.")
    _check_daily_cap(sim, conn, user_id, now)
    balance = _balance(sim, user_id, conn)
    if balance < cost:
        raise api_error(402, "insufficient_connects", f"Needs {cost} Connects, have {balance}.")
    return balance


def _check_daily_cap(sim: Sim, conn: sqlite3.Connection, user_id: str, now: float) -> None:
    cap = sim.policy.submits_per_sim_day
    if cap is None:
        return
    recent = conn.execute(
        "SELECT COUNT(*) AS n FROM events WHERE user_id = ? AND type = 'submitted' AND at_min > ?",
        (user_id, now - MINUTES_PER_DAY),
    ).fetchone()["n"]
    if recent >= cap:
        raise api_error(409, "daily_submit_limit", f"Policy allows {cap} submissions per day.")


def _check_policy(sim: Sim, text: str, kind: Kind) -> None:
    violations = sim.policy.violations(text, kind)
    if violations:
        raise HTTPException(422, detail={
            "code": "policy_violation",
            "message": f"Blocked by platform policy {sim.policy.version}.",
            "violations": [violation.model_dump() for violation in violations],
        })


def _released_job(sim: Sim, job_id: str, now: float) -> Job:
    job = sim.seed.jobs.get(job_id)
    if job is None or not sim.job_released(job_id, now):
        raise api_error(404, "job_not_found", f"No job {job_id}.")
    return job


def _own_proposal(sim: Sim, proposal_id: str, user_id: str) -> sqlite3.Row:
    found = sim.db.rows(
        "SELECT * FROM proposals WHERE proposal_id = ? AND user_id = ?", (proposal_id, user_id)
    )
    if not found:
        raise api_error(404, "proposal_not_found", f"No proposal {proposal_id}.")
    return found[0]


def _thread(sim: Sim, user_id: str, thread_id: str) -> tuple[str, str]:
    conversation = sim.seed.conversations.get(thread_id)
    if conversation and conversation.persona_id == user_id:
        if not sim.job_released(conversation.job_id, sim.clock.minutes()):
            raise api_error(404, "thread_not_found", f"No thread {thread_id}.")
        return conversation.job_id, conversation.client_id
    found = sim.db.rows(
        "SELECT job_id, client_id FROM proposals WHERE proposal_id = ? AND user_id = ?",
        (thread_id, user_id),
    )
    if not found:
        raise api_error(404, "thread_not_found", f"No thread {thread_id}.")
    return found[0]["job_id"], found[0]["client_id"]


def _proposal_out(sim: Sim, row: sqlite3.Row, now: float) -> ProposalOut:
    latest = sim.db.rows(
        "SELECT type FROM events WHERE proposal_id = ? AND at_min <= ? ORDER BY at_min DESC, id DESC "
        "LIMIT 1",
        (row["proposal_id"], now),
    )
    return ProposalOut(
        proposal_id=row["proposal_id"], job_id=row["job_id"],
        status=latest[0]["type"] if latest else "drafted", cover_letter=row["cover_letter"],
        bid=Bid(type=row["bid_type"], amount_usd=row["bid_amount_usd"]),
        screening_answers=json.loads(row["screening_json"]),
        connects_cost=sim.policy.connects_cost(sim.seed.jobs[row["job_id"]]),
        created_at=sim.clock.at(row["created_min"]),
    )


def _balance(sim: Sim, user_id: str, conn: sqlite3.Connection | None = None) -> int:
    starting = sim.settings.config.users[user_id].starting_connects
    return starting + sim.db.connects_delta(user_id, conn)


def _add_event(
    conn: sqlite3.Connection, proposal_id: str, user_id: str, event: str, at_min: float
) -> None:
    conn.execute("INSERT INTO events (proposal_id, user_id, type, at_min) VALUES (?, ?, ?, ?)",
                 (proposal_id, user_id, event, at_min))


def _make_id(prefix: str, user_id: str, key: str) -> str:
    # Derived from the idempotency key so reruns of an eval produce the same ids.
    return f"{prefix}-{hashlib.sha256(f'{user_id}|{key}'.encode()).hexdigest()[:12]}"
