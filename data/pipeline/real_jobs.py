"""Build job and client records from the Kaggle job datasets.

Every record comes from exactly one source dataset (no stitching). URLs and Upwork ids are
dropped, and free text is PII-masked.
"""

import random
import re
from datetime import datetime
from typing import Any

from data.pipeline.common import (
    RAW_DIR,
    SOURCE_CONTRACTS,
    SOURCE_JOBS_50K,
    SOURCE_JOBS_60K,
    SOURCE_SYNTHETIC,
    parse_money,
    read_csv,
)
from data.pipeline.domains import DOMAINS, classify_domain
from data.pipeline.pii import mask_pii

HISTORICAL_PER_DOMAIN = 500
STREAM_PER_DOMAIN = 200
STREAM_OTHER = 100
MIN_DESCRIPTION_CHARS = 150
MAX_CLIENT_HISTORY = 6
REPLACEMENT_CHAR = "�"  # present in the source file; such rows are skipped, not repaired
HISTORY_SOURCE = f"{SOURCE_SYNTHETIC} (titles and amounts from {SOURCE_CONTRACTS})"
EXPERIENCE_LEVELS = {"Entry level": "entry", "Intermediate": "intermediate", "Expert": "expert"}


def _dedupe_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()[:200]


def _usable(title: str, description: str) -> bool:
    return (
        bool(title.strip())
        and len(description) >= MIN_DESCRIPTION_CHARS
        and REPLACEMENT_CHAR not in title + description
    )


def _sample_by_domain(
    rng: random.Random, pools: dict[str, list[Any]], quotas: dict[str, int]
) -> list[Any]:
    """Seeded sample per domain, returned in source-file order for stable output."""
    chosen = []
    for domain, quota in quotas.items():
        pool = pools.get(domain, [])
        chosen.extend(rng.sample(pool, min(quota, len(pool))))
    return sorted(chosen, key=lambda item: item[0])


def build_historical_jobs(rng: random.Random) -> list[dict[str, Any]]:
    pools: dict[str, list[tuple[int, str, dict[str, str]]]] = {}
    seen: set[str] = set()
    for index, row in enumerate(read_csv(RAW_DIR / "upwork-jobs.csv")):
        title, description = row["title"], row["description"]
        if not _usable(title, description) or _dedupe_key(description) in seen:
            continue
        if parse_money(row["budget"]) is None and parse_money(row["hourly_low"]) is None:
            continue
        seen.add(_dedupe_key(description))
        domain = classify_domain(f"{title} {description[:300]}")
        pools.setdefault(domain, []).append((index, domain, row))

    quotas = {domain: HISTORICAL_PER_DOMAIN for domain in DOMAINS}
    jobs = []
    for number, (_, domain, row) in enumerate(_sample_by_domain(rng, pools, quotas), start=1):
        is_hourly = row["is_hourly"] == "True"
        low, high = parse_money(row["hourly_low"]), parse_money(row["hourly_high"])
        posted = datetime.fromisoformat(row["published_date"])
        jobs.append({
            "job_id": f"hist-{number:05d}",
            "source": SOURCE_JOBS_50K,
            "category": domain,
            "title": mask_pii(row["title"].strip()),
            "description": mask_pii(row["description"].strip()),
            "payment_type": "hourly" if is_hourly else "fixed",
            "budget_usd": None if is_hourly else parse_money(row["budget"]),
            "hourly_usd": {"min": low, "max": high} if is_hourly and low else None,
            "country": row["country"] or None,
            "posted_at": posted.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return jobs


def _skills(row: dict[str, str]) -> list[str]:
    return [row[f"Category_{n}"].strip() for n in range(1, 10) if row[f"Category_{n}"].strip()]


def client_history(
    rng: random.Random, feedback_count: int, rating: float | None, pool: list[tuple[str, float]]
) -> list[dict[str, Any]]:
    """Synthetic past contracts drawn from real contract titles and amounts in the same domain."""
    history = []
    for title, paid in rng.sample(pool, min(feedback_count, MAX_CLIENT_HISTORY, len(pool))):
        given = None if rating is None else round(min(5.0, max(1.0, rng.gauss(rating, 0.3))), 1)
        history.append({"title": title, "paid_usd": paid, "rating": given})
    return history


def build_stream_jobs_and_clients(
    rng: random.Random, contract_pools: dict[str, list[tuple[str, float]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pools: dict[str, list[tuple[int, str, dict[str, str]]]] = {}
    seen: set[str] = set()
    for index, row in enumerate(read_csv(RAW_DIR / "Final_Upwork_Dataset.csv")):
        title, description = row["Job Title"], row["Description"]
        if not _usable(title, description) or _dedupe_key(description) in seen:
            continue
        seen.add(_dedupe_key(description))
        domain = classify_domain(f"{title} {' '.join(_skills(row))}")
        pools.setdefault(domain, []).append((index, domain, row))

    quotas = {domain: STREAM_PER_DOMAIN for domain in DOMAINS} | {"other": STREAM_OTHER}
    jobs, clients = [], []
    for number, (_, domain, row) in enumerate(_sample_by_domain(rng, pools, quotas), start=1):
        job_id, client_id = f"job-{number:05d}", f"client-{number:05d}"
        is_hourly = row["Payment_type"] == "Hourly"
        low, high = parse_money(row["Start_rate"]), parse_money(row["End_rate"])
        jobs.append({
            "job_id": job_id,
            "source": SOURCE_JOBS_60K,
            "title": mask_pii(row["Job Title"].strip()),
            "description": mask_pii(row["Description"].strip()),
            "skills": _skills(row),
            "experience_level": EXPERIENCE_LEVELS.get(row["EX_level_demand"]),
            "payment_type": "hourly" if is_hourly else "fixed",
            "budget_usd": None if is_hourly else parse_money(row["Job_Cost"]),
            "hourly_usd": {"min": low, "max": high} if is_hourly and low else None,
            "duration": row["Time_Limitation"] or None,
            "applicants": row["Applicants_Num"] or None,
            "connects_cost": int(row["Connects_Num"]),
            "client_id": client_id,
        })
        rating = float(row["Rating"]) if row["Rating"] else None
        feedback_count = int(row["Feedback_Num"] or 0)
        clients.append({
            "client_id": client_id,
            "source": SOURCE_JOBS_60K,
            "history_source": HISTORY_SOURCE,
            "country": row["Client_Country"] or None,
            "payment_verified": row["Payment_Situation"] == "Payment verified",
            "enterprise": row["Enterprise_Client"] == "Enterprise",
            "total_spent_usd": parse_money(row["Spent($)"]) or 0.0,
            "rating": rating,
            "feedback_count": feedback_count,
            "history": client_history(rng, feedback_count, rating, contract_pools[domain]),
        })
    return jobs, clients
