"""Pricing Strategist: propose a bid from the post's own budget or rate range.

shortcut: the fixed budget, or the top of the posted hourly range; market stats
(get_market_rates), client spend and the user's floor join this when the token budget allows.
"""

from agent.handoffs import JobSpec, PriceQuote
from agent.state import GigBidState

FALLBACK_HOURLY_USD = 40.0  # used only when a post states no budget at all


def quote(job: dict, spec: JobSpec) -> PriceQuote:
    if job.get("payment_type") == "fixed" and spec.budget_max:
        return PriceQuote(bid_type="fixed", amount_usd=spec.budget_max,
                          rationale="the client's posted fixed budget")
    rate = spec.budget_max or spec.budget_min or FALLBACK_HOURLY_USD
    return PriceQuote(bid_type="hourly", amount_usd=rate,
                      rationale="the top of the client's posted hourly range")


async def pricing(state: GigBidState) -> GigBidState:
    return {"price_quote": quote(state["job"], JobSpec(**state["job_spec"])).model_dump()}
