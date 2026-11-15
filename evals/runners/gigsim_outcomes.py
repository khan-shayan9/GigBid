"""B4 outcomes: submit proposals to a fresh in-process GigSim and read the simulated outcome.

Each call starts its own GigSim (temporary database, faults off, rule-based client simulation,
seed 4016), so variants are compared on the same jobs and the same client noise: a proposal's
noise draw depends only on its user and idempotency key, which stay the same across variants.
Nothing here touches a real marketplace.
"""

import json
import tempfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from gigsim.app import create_app
from gigsim.settings import DEFAULT_CONFIG_PATH, RateLimit, Settings, SimConfig
from mcp_servers.common import REPO_ROOT

SEED_DIR = REPO_ROOT / "data" / "gigsim_seed"
ADMIN = "eval-admin-token"
ALL_RELEASED_MIN = 60 * 24 * 30  # past the last stream release
DECIDED_MIN = 60 * 24 * 3  # past the longest outcome delay (two days)
REPLIED = {"replied", "interview", "hired"}
FINAL = ("hired", "interview", "replied")
EVAL_CONNECTS = 10_000  # each fresh sim is for evaluation only; the budget is not under test


def outcomes(proposals: list[dict[str, Any]]) -> list[str]:
    """One outcome per proposal: hired, interview, replied, ignored, or rejected (policy block).

    Each proposal: {"persona", "key", "job_id", "cover_letter", "bid": {"type", "amount_usd"}}.
    """
    with tempfile.TemporaryDirectory() as folder:
        client, tokens = _open(Path(folder), {proposal["persona"] for proposal in proposals})
        with client:
            results = [_submit(client, tokens[proposal["persona"]], proposal)
                       for proposal in proposals]
            client.post("/admin/clock/advance", json={"minutes": DECIDED_MIN},
                        headers={"Authorization": f"Bearer {ADMIN}"})
            return [_final(client, tokens[proposal["persona"]], proposal_id)
                    if proposal_id else "rejected"
                    for proposal, proposal_id in zip(proposals, results, strict=True)]


def rates(results: list[str]) -> dict[str, Any]:
    submitted = [result for result in results if result != "rejected"]
    return {"submitted": len(submitted), "rejected": len(results) - len(submitted),
            "reply_rate": round(sum(r in REPLIED for r in submitted) / len(submitted), 4)
            if submitted else None,
            "hire_rate": round(sum(r == "hired" for r in submitted) / len(submitted), 4)
            if submitted else None}


def _open(folder: Path, personas: set[str]) -> tuple[TestClient, dict[str, str]]:
    config = SimConfig.model_validate(json.loads(Path(DEFAULT_CONFIG_PATH).read_text("utf-8")))
    users = {name: account.model_copy(update={"starting_connects": EVAL_CONNECTS})
             for name, account in config.users.items()}
    config = config.model_copy(update={
        "time_scale": 0, "users": users,
        "rate_limit": RateLimit(capacity=10_000, refill_per_second=100)})
    tokens = {persona: f"eval-token-{persona}" for persona in personas}
    settings = Settings(config=config, seed_dirs=[SEED_DIR], db_path=folder / "gigsim.sqlite",
                        tokens={token: persona for persona, token in tokens.items()},
                        admin_token=ADMIN, faults_enabled=False)
    client = TestClient(create_app(settings))
    client.post("/admin/clock/advance", json={"minutes": ALL_RELEASED_MIN},
                headers={"Authorization": f"Bearer {ADMIN}"})
    return client, tokens


def _submit(client: TestClient, token: str, proposal: dict[str, Any]) -> str | None:
    auth = {"Authorization": f"Bearer {token}"}
    body = {key: proposal[key] for key in ("job_id", "cover_letter", "bid")}
    drafted = client.post("/proposals", json=body,
                          headers=auth | {"Idempotency-Key": f"draft-{proposal['key']}"})
    if drafted.status_code != 200:  # the policy pack blocked the letter
        return None
    proposal_id = drafted.json()["proposal_id"]
    submitted = client.post(f"/proposals/{proposal_id}/submit",
                            headers=auth | {"Idempotency-Key": f"submit-{proposal['key']}"})
    submitted.raise_for_status()
    return proposal_id


def _final(client: TestClient, token: str, proposal_id: str) -> str:
    events = client.get(f"/proposals/{proposal_id}/events",
                        headers={"Authorization": f"Bearer {token}"}).json()["events"]
    seen = {event["type"] for event in events}
    return next((outcome for outcome in FINAL if outcome in seen), "ignored")
