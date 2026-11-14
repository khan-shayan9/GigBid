"""Aggregate statistics from the contracts and freelancer datasets."""

from statistics import median, quantiles
from typing import Any

from data.pipeline.common import RAW_DIR, SOURCE_CONTRACTS, SOURCE_FREELANCERS, read_csv
from data.pipeline.domains import classify_domain
from data.pipeline.pii import mask_pii

CONTRACT_POOL_CAP = 5000  # per domain, first rows in file order; enough variety for histories


def _quartiles(values: list[float]) -> dict[str, float]:
    p25, p50, p75 = quantiles(values, n=4)
    return {"p25": round(p25, 2), "p50": round(p50, 2), "p75": round(p75, 2)}


def build_market_rates() -> tuple[dict[str, Any], dict[str, list[tuple[str, float]]]]:
    """Return per-domain rate bands and a capped pool of (title, total_paid) for histories.

    Contract and freelancer ids are never read into the output.
    """
    hourly: dict[str, list[float]] = {}
    paid: dict[str, list[float]] = {}
    pools: dict[str, list[tuple[str, float]]] = {}
    for row in read_csv(RAW_DIR / "contracts.csv"):
        title = row["job_title"].strip()
        try:
            total_paid = float(row["total_paid"] or 0)
            rate = float(row["hourly_rate"] or 0)
        except ValueError:
            continue
        if not title or total_paid <= 0:
            continue
        domain = classify_domain(title)
        paid.setdefault(domain, []).append(total_paid)
        if rate > 0:
            hourly.setdefault(domain, []).append(rate)
        pool = pools.setdefault(domain, [])
        if len(pool) < CONTRACT_POOL_CAP:
            pool.append((mask_pii(title), round(total_paid, 2)))

    rates = {
        "source": SOURCE_CONTRACTS,
        "domains": {
            domain: {
                "contracts": len(paid[domain]),
                "hourly_usd": _quartiles(hourly[domain]),
                "total_paid_usd": _quartiles(paid[domain]),
            }
            for domain in sorted(paid)
        },
    }
    return rates, pools


def build_persona_priors() -> dict[str, Any]:
    """Median success rate and response time per primary skill.

    hourly_rate_usd is skipped: 63% of its values sit at exactly 280, a clipping artefact,
    so persona rates come from the contracts-based market_rates.json instead.
    """
    groups: dict[str, dict[str, list[float]]] = {}
    fields = ["job_success_rate", "avg_response_time_hrs"]
    for row in read_csv(RAW_DIR / "freelancer_gig_success_dataset.csv"):
        skill = row["primary_skill"].strip()
        if not skill:
            continue
        group = groups.setdefault(skill, {field: [] for field in fields})
        for field in fields:
            if row[field]:
                group[field].append(float(row[field]))
    return {
        "source": SOURCE_FREELANCERS,
        "primary_skills": {
            skill: {"freelancers": len(group["job_success_rate"])}
            | {f"median_{field}": round(median(group[field]), 2) for field in fields}
            for skill, group in sorted(groups.items())
        },
    }
